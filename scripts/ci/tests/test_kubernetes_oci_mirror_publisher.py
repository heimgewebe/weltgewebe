from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KubernetesOciMirrorPublisherContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.publisher = load_module(
            "weltgewebe_publish_oci_mirror",
            ROOT / "scripts/platform/publish_oci_mirror.py",
        )

    def policy(self) -> dict[str, object]:
        return dict(self.publisher.EXPECTED_PUBLISHER_POLICY)

    def test_seed_is_private_repository_owned_and_exactly_inventoried(self) -> None:
        result = self.publisher.validate()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["owner"], "heimgewebe/weltgewebe")
        self.assertEqual(
            result["target_repository"],
            "ghcr.io/heimgewebe/weltgewebe-proof-oci",
        )
        self.assertEqual(result["visibility"], "private")
        self.assertEqual(result["retention_state"], "bootstrap_pending_lock")
        self.assertEqual(set(result["inventory"]), set(self.publisher.EXPECTED_IMAGES))
        self.assertEqual(result["publisher_policy"]["max_parallelism"], 3)
        self.assertEqual(len(result["seed_sha256"]), 64)

    def test_inventory_replacement_is_rejected_even_when_count_is_unchanged(self) -> None:
        seed = json.loads(self.publisher.SEED_PATH.read_text(encoding="utf-8"))
        seed["images"]["replacement"] = seed["images"].pop("kind_node")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seed.json"
            path.write_text(json.dumps(seed), encoding="utf-8")
            with mock.patch.object(self.publisher, "SEED_PATH", path):
                with self.assertRaisesRegex(self.publisher.PublisherError, "inventory mismatch"):
                    self.publisher._load_seed()

    def test_invalid_suite_and_non_boolean_kind_binding_are_rejected(self) -> None:
        seed = json.loads(self.publisher.SEED_PATH.read_text(encoding="utf-8"))
        seed["images"]["kind_node"]["suites"] = ["wrong"]
        seed["images"]["kind_node"]["load_into_kind"] = "false"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "seed.json"
            path.write_text(json.dumps(seed), encoding="utf-8")
            with mock.patch.object(self.publisher, "SEED_PATH", path):
                with self.assertRaisesRegex(self.publisher.PublisherError, "suite binding"):
                    self.publisher._load_seed()

    def test_every_source_is_registry_qualified_and_target_is_not_a_source(self) -> None:
        seed = self.publisher._load_seed()
        target = seed["target"]["repository"]
        for spec in seed["images"].values():
            repository = self.publisher._reference_repository(spec["canonical"])
            self.assertIn(".", repository.split("/", 1)[0])
            self.assertNotEqual(repository, target)
            self.assertFalse(repository.startswith("ghcr.io/heimgewebe/"))

    def test_canonical_manifest_availability_is_retried_with_bounded_backoff(self) -> None:
        digest = "sha256:" + "a" * 64
        deadline = self.publisher.Deadline.after(60)
        with mock.patch.object(
            self.publisher,
            "_manifest_digest_once",
            side_effect=[self.publisher.AvailabilityError("429"), digest],
        ) as inspect, mock.patch.object(self.publisher, "_sleep_backoff") as backoff:
            observed = self.publisher._manifest_digest(
                "docker.io/library/test:v1@" + digest,
                attempts=3,
                backoff_seconds=[5, 10],
                operation_timeout=30,
                deadline=deadline,
            )
        self.assertEqual(observed, digest)
        self.assertEqual(inspect.call_count, 2)
        backoff.assert_called_once_with(5, deadline)

    def test_integrity_failure_is_not_retried(self) -> None:
        deadline = self.publisher.Deadline.after(60)
        with mock.patch.object(
            self.publisher,
            "_manifest_digest_once",
            side_effect=self.publisher.IntegrityError("wrong digest"),
        ) as inspect, mock.patch.object(self.publisher, "_sleep_backoff") as backoff:
            with self.assertRaises(self.publisher.IntegrityError):
                self.publisher._manifest_digest(
                    "docker.io/library/test:v1@sha256:" + "a" * 64,
                    attempts=3,
                    backoff_seconds=[5, 10],
                    operation_timeout=30,
                    deadline=deadline,
                )
        inspect.assert_called_once()
        backoff.assert_not_called()

    def test_existing_correct_mirror_tag_is_reused_without_mutation(self) -> None:
        digest = "sha256:" + "a" * 64
        canonical = "docker.io/library/test:v1@" + digest
        with mock.patch.object(
            self.publisher, "_manifest_digest", side_effect=[digest, digest]
        ), mock.patch.object(self.publisher, "_create_mirror") as create:
            result = self.publisher._publish_one(
                "ghcr.io/heimgewebe/weltgewebe-proof-oci",
                "test",
                canonical,
                self.policy(),
                self.publisher.Deadline.after(60),
            )
        self.assertEqual(result["action"], "reused")
        self.assertTrue(result["mirror_tag"].endswith("test-" + "a" * 64))
        create.assert_not_called()

    def test_copy_preserves_single_manifest_shape_and_uses_full_digest_tag(self) -> None:
        result = mock.Mock(returncode=0)
        with mock.patch.object(self.publisher.subprocess, "run", return_value=result) as run:
            self.publisher._create_mirror_once(
                "ghcr.io/heimgewebe/weltgewebe-proof-oci:test-" + "a" * 64,
                "docker.io/library/test:v1@sha256:" + "a" * 64,
                timeout=30,
            )
        argv = run.call_args.args[0]
        self.assertIn("--prefer-index=false", argv)
        self.assertTrue(any("test-" + "a" * 64 in item for item in argv))

    def test_publish_rejects_unreviewed_head_before_registry_work(self) -> None:
        with mock.patch.object(self.publisher, "_git_head", return_value="a" * 40), mock.patch.object(
            self.publisher, "_sha256", return_value="b" * 64
        ), mock.patch.object(self.publisher, "_load_seed") as load_seed:
            with self.assertRaisesRegex(self.publisher.PublisherError, "head mismatch"):
                self.publisher.publish(
                    "c" * 40,
                    "b" * 64,
                    ROOT / "build/kubernetes-platform/provenance.json",
                )
        load_seed.assert_not_called()

    def test_partial_batch_failure_is_written_to_durable_provenance(self) -> None:
        digest = "sha256:" + "a" * 64
        seed = {
            "owner": "heimgewebe/weltgewebe",
            "target": {
                "repository": "ghcr.io/heimgewebe/weltgewebe-proof-oci",
                "visibility": "private",
                "retention": {"state": "bootstrap_pending_lock"},
            },
            "publisher": {
                **self.policy(),
                "max_parallelism": 2,
            },
            "images": {
                "one": {
                    "canonical": "docker.io/library/one:v1@" + digest,
                    "suites": ["kind-gitops"],
                    "load_into_kind": True,
                },
                "two": {
                    "canonical": "docker.io/library/two:v1@" + digest,
                    "suites": ["kind-gitops"],
                    "load_into_kind": True,
                },
            },
        }

        def publish_one(_target, name, canonical, _policy, _deadline):
            if name == "two":
                raise self.publisher.AvailabilityError("offline")
            return {
                "action": "published",
                "canonical": canonical,
                "canonical_digest": digest,
                "mirror_tag": "mirror:one",
                "mirror": "mirror@" + digest,
                "mirror_digest": digest,
            }

        output_dir = ROOT / "build/kubernetes-platform"
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=output_dir) as tmp, mock.patch.object(
            self.publisher, "_git_head", return_value="c" * 40
        ), mock.patch.object(
            self.publisher, "_sha256", return_value="d" * 64
        ), mock.patch.object(
            self.publisher, "_load_seed", return_value=seed
        ), mock.patch.object(
            self.publisher, "_tool_versions", return_value={"docker": "x", "buildx": "y"}
        ), mock.patch.object(
            self.publisher, "_publish_one", side_effect=publish_one
        ):
            output = Path(tmp) / "provenance.json"
            with self.assertRaisesRegex(self.publisher.PublisherError, "failed batch"):
                self.publisher.publish("c" * 40, "d" * 64, output)
            observed = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(observed["status"], "partial")
        self.assertEqual(observed["completed_count"], 1)
        self.assertEqual(observed["failures"]["two"]["error_class"], "registry_unavailable")

    def test_provenance_output_cannot_escape_build_evidence_root(self) -> None:
        with self.assertRaisesRegex(self.publisher.PublisherError, "must remain below"):
            self.publisher._validated_output_path(Path("/tmp/provenance.json"))

    def test_workflow_executes_privileged_code_only_from_current_main(self) -> None:
        path = ROOT / ".github/workflows/kubernetes-proof-oci-mirror.yml"
        source = path.read_text(encoding="utf-8")
        workflow = yaml.safe_load(source)
        jobs = workflow["jobs"]
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(jobs["publish"]["permissions"], {"contents": "read", "packages": "write"})
        for job_name in ("contract", "publish", "verify-read-access"):
            checkout = next(
                step for step in jobs[job_name]["steps"]
                if str(step.get("uses", "")).startswith("actions/checkout@")
            )
            self.assertEqual(checkout["with"]["ref"], "${{ github.sha }}")
            self.assertFalse(checkout["with"]["persist-credentials"])
        contract_steps = {
            step["name"]: step for step in jobs["contract"]["steps"] if "name" in step
        }
        trusted = contract_steps["Verify trusted dispatch identity"]["run"]
        self.assertIn('test "$GITHUB_REF" = "refs/heads/main"', trusted)
        self.assertIn('test "$GITHUB_SHA" = "$EXPECTED_HEAD"', trusted)
        self.assertIn("git/ref/heads/main", trusted)
        self.assertIn("EXPECTED_SEED_SHA256", trusted)
        self.assertNotIn("GH_TOKEN", jobs["publish"]["env"])

    def test_workflow_preflights_metadata_and_always_uploads_partial_evidence(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/kubernetes-proof-oci-mirror.yml").read_text(encoding="utf-8")
        )
        steps = workflow["jobs"]["publish"]["steps"]
        named = {step["name"]: step for step in steps if "name" in step}
        order = [step.get("name") for step in steps]
        self.assertLess(
            order.index("Preflight existing package metadata"),
            order.index("Publish exact digest-preserving OCI mirror"),
        )
        preflight = named["Preflight existing package metadata"]["run"]
        self.assertIn(".owner.login", preflight)
        self.assertIn(".package_type", preflight)
        self.assertIn(".visibility", preflight)
        self.assertIn("not-visible-or-absent", preflight)
        self.assertNotIn("/repositories", preflight)
        self.assertNotIn("--method PATCH", preflight)
        postflight = named["Attest private package metadata"]["run"]
        self.assertIn(".version_count", postflight)
        self.assertNotIn("/repositories", postflight)
        self.assertNotIn("--method PATCH", postflight)
        publish = named["Publish exact digest-preserving OCI mirror"]["run"]
        self.assertIn('--expected-head "$EXPECTED_HEAD"', publish)
        self.assertIn('--expected-seed-sha256 "$EXPECTED_SEED_SHA256"', publish)
        self.assertEqual(named["Logout registry credentials"]["if"], "always()")
        self.assertEqual(named["Upload mirror provenance"]["if"], "always()")
        self.assertEqual(named["Upload mirror provenance"]["with"]["retention-days"], 14)
        self.assertIn("DOCKERHUB_TOKEN", named["Authenticate source and target registries"]["env"])

    def test_workflow_has_separate_repository_read_access_proof(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/kubernetes-proof-oci-mirror.yml").read_text(encoding="utf-8")
        )
        verify = workflow["jobs"]["verify-read-access"]
        self.assertEqual(verify["needs"], "publish")
        self.assertEqual(verify["permissions"], {"contents": "read", "packages": "read"})
        named = {step["name"]: step for step in verify["steps"] if "name" in step}
        download = named["Download publisher evidence"]
        self.assertTrue(str(download["uses"]).startswith("actions/download-artifact@"))
        check = named["Verify repository read access and every mirror digest"]["run"]
        self.assertIn(".images | to_entries[]", check)
        self.assertIn("docker buildx imagetools inspect", check)
        self.assertIn("checked_images", check)
        self.assertIn(".visibility", check)
        self.assertNotIn("/repositories", check)
        self.assertEqual(named["Logout registry credentials"]["if"], "always()")
        self.assertEqual(named["Upload read-access evidence"]["if"], "always()")

    def test_workflow_pins_runner_buildx_and_multiarch_inspection(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github/workflows/kubernetes-proof-oci-mirror.yml").read_text(encoding="utf-8")
        )
        for job_name in ("contract", "publish", "verify-read-access"):
            job = workflow["jobs"][job_name]
            self.assertEqual(job["runs-on"], "ubuntu-24.04")
            buildx = next(
                step for step in job["steps"]
                if str(step.get("uses", "")).startswith("docker/setup-buildx-action@")
            )
            self.assertEqual(buildx["with"]["version"], "v0.35.0")
        contract = {
            step["name"]: step
            for step in workflow["jobs"]["contract"]["steps"]
            if "name" in step
        }
        smoke = contract["Verify pinned Buildx multi-architecture digest inspection"]["run"]
        self.assertIn("kindest/node", smoke)
        self.assertIn(".Manifest.Digest", smoke)
        self.assertIn("--prefer-index", smoke)
        publish_verify = next(
            step for step in workflow["jobs"]["publish"]["steps"]
            if step.get("name") == "Verify immutable trusted-main publisher inputs"
        )
        self.assertIn("--prefer-index", publish_verify["run"])


if __name__ == "__main__":
    unittest.main()
