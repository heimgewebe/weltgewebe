from __future__ import annotations

import importlib.util
import json
import subprocess
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

    def test_seed_is_private_repository_owned_and_digest_only(self) -> None:
        result = self.publisher.validate()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["owner"], "heimgewebe/weltgewebe")
        self.assertEqual(
            result["target_repository"],
            "ghcr.io/heimgewebe/weltgewebe-proof-oci",
        )
        self.assertEqual(result["visibility"], "private")
        self.assertEqual(result["image_count"], 25)
        self.assertEqual(len(result["seed_sha256"]), 64)

    def test_manifest_digest_mismatch_fails_without_retry(self) -> None:
        canonical = "registry.invalid/image:v1@sha256:" + "a" * 64
        with mock.patch.object(
            self.publisher,
            "_manifest_digest",
            side_effect=["sha256:" + "a" * 64, "sha256:" + "b" * 64],
        ), mock.patch.object(self.publisher, "_run") as run, mock.patch.object(
            self.publisher.time, "sleep"
        ) as sleep:
            with self.assertRaises(self.publisher.PublisherError):
                self.publisher._publish_one(
                    "ghcr.io/heimgewebe/weltgewebe-proof-oci",
                    "test",
                    canonical,
                    3,
                )
        run.assert_called_once()
        sleep.assert_not_called()

    def test_transient_publication_failure_is_bounded(self) -> None:
        canonical = "registry.invalid/image:v1@sha256:" + "a" * 64
        error = subprocess.CalledProcessError(1, ["docker", "buildx"])
        with mock.patch.object(
            self.publisher,
            "_manifest_digest",
            return_value="sha256:" + "a" * 64,
        ), mock.patch.object(
            self.publisher, "_run", side_effect=error
        ) as run, mock.patch.object(self.publisher.time, "sleep") as sleep:
            with self.assertRaises(self.publisher.PublisherError):
                self.publisher._publish_one(
                    "ghcr.io/heimgewebe/weltgewebe-proof-oci",
                    "test",
                    canonical,
                    3,
                )
        self.assertEqual(run.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [1.0, 2.0])

    def test_publish_requires_exact_head_and_seed_before_any_registry_write(self) -> None:
        with mock.patch.object(self.publisher, "_git_head", return_value="a" * 40), mock.patch.object(
            self.publisher, "_sha256", return_value="b" * 64
        ), mock.patch.object(self.publisher, "_publish_one") as publish_one:
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(self.publisher.PublisherError):
                    self.publisher.publish(
                        "c" * 40,
                        "b" * 64,
                        Path(tmp) / "provenance.json",
                    )
        publish_one.assert_not_called()

    def test_successful_publication_writes_head_and_seed_bound_provenance(self) -> None:
        seed = {
            "schema_version": 1,
            "owner": "heimgewebe/weltgewebe",
            "target": {
                "repository": "ghcr.io/heimgewebe/weltgewebe-proof-oci",
                "visibility": "private",
            },
            "publisher": {"canonical_attempts": 3},
            "images": {
                "test": {
                    "canonical": "registry.invalid/image:v1@sha256:" + "a" * 64,
                    "suites": ["kind-gitops"],
                }
            },
        }
        published = {
            "canonical": seed["images"]["test"]["canonical"],
            "canonical_digest": "sha256:" + "a" * 64,
            "mirror_tag": "ghcr.io/heimgewebe/weltgewebe-proof-oci:test-aaaaaaaaaaaaaaaa",
            "mirror": "ghcr.io/heimgewebe/weltgewebe-proof-oci@sha256:" + "a" * 64,
            "mirror_digest": "sha256:" + "a" * 64,
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            self.publisher, "_git_head", return_value="c" * 40
        ), mock.patch.object(
            self.publisher, "_sha256", return_value="d" * 64
        ), mock.patch.object(
            self.publisher, "_load_seed", return_value=seed
        ), mock.patch.object(
            self.publisher, "_publish_one", return_value=published
        ):
            output = Path(tmp) / "provenance.json"
            result = self.publisher.publish("c" * 40, "d" * 64, output)
            observed = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result, observed)
        self.assertEqual(observed["source_head"], "c" * 40)
        self.assertEqual(observed["seed_sha256"], "d" * 64)
        self.assertEqual(observed["images"]["test"]["mirror_digest"], "sha256:" + "a" * 64)

    def test_workflow_separates_pr_contract_from_manual_package_write(self) -> None:
        path = ROOT / ".github/workflows/kubernetes-proof-oci-mirror.yml"
        source = path.read_text(encoding="utf-8")
        workflow = yaml.safe_load(source)
        jobs = workflow["jobs"]
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(jobs["publish"]["permissions"], {"contents": "read", "packages": "write"})
        self.assertEqual(jobs["publish"]["if"], "github.event_name == 'workflow_dispatch'")
        steps = {
            step["name"]: step
            for step in jobs["publish"]["steps"]
            if "name" in step
        }
        verify = steps["Verify immutable publisher inputs"]["run"]
        self.assertIn("git rev-parse HEAD", verify)
        self.assertIn("sha256sum platform/oci-proof-mirror.seed.json", verify)
        publish = steps["Publish exact digest-preserving OCI mirror"]["run"]
        self.assertIn('--expected-head "$EXPECTED_HEAD"', publish)
        self.assertIn('--expected-seed-sha256 "$EXPECTED_SEED_SHA256"', publish)
        bind = steps["Bind private package access to this repository"]["run"]
        self.assertIn("visibility", bind)
        self.assertIn("heimgewebe/weltgewebe", bind)
        self.assertNotIn("weltgewebe-api", source)
        self.assertNotIn("weltgewebe-web", source)


if __name__ == "__main__":
    unittest.main()
