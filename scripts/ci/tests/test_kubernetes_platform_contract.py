from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[3]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KubernetesPlatformContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.validator = load_module(
            "weltgewebe_platform_validator",
            ROOT / "scripts/platform/validate_platform.py",
        )
        cls.reference = load_module(
            "weltgewebe_kind_reference",
            ROOT / "scripts/platform/kind_reference.py",
        )
        cls.bootstrap = load_module(
            "weltgewebe_platform_bootstrap",
            ROOT / "scripts/platform/bootstrap_tools.py",
        )
        cls.proof_identity = load_module(
            "weltgewebe_proof_identity",
            ROOT / "scripts/platform/proof_identity.py",
        )
        cls.oci_mirror = load_module(
            "weltgewebe_oci_proof_mirror",
            ROOT / "scripts/platform/oci_proof_mirror.py",
        )

    def test_tool_bootstrap_selection_is_exact_and_deduplicated(self) -> None:
        lock = {"tools": {"kustomize": {"version": "x"}, "trivy": {"version": "y"}}}
        selected = self.bootstrap._selected_tool_specs(lock, ["trivy", "trivy"])
        self.assertEqual(selected, {"trivy": {"version": "y"}})
        with self.assertRaisesRegex(RuntimeError, "unknown tool selection"):
            self.bootstrap._selected_tool_specs(lock, ["missing"])

    def test_tool_download_retries_transient_gateway_failure_and_cleans_temps(self) -> None:
        payload = b"kind-binary"
        expected = hashlib.sha256(payload).hexdigest()
        transient = urllib.error.HTTPError(
            "https://downloads.example/kind", 504, "gateway timeout", {}, None
        )

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "downloads" / "kind"
            with mock.patch.object(
                self.bootstrap.urllib.request,
                "urlopen",
                side_effect=[transient, Response(payload)],
            ) as urlopen, mock.patch.object(self.bootstrap.time, "sleep") as sleep:
                self.bootstrap._download(
                    "https://downloads.example/kind", expected, destination
                )
            self.assertEqual(destination.read_bytes(), payload)
            self.assertEqual(urlopen.call_count, 2)
            sleep.assert_called_once_with(1.0)
            self.assertEqual(list(destination.parent.glob("*.download.tmp")), [])

    def test_tool_download_hash_mismatch_is_integrity_failure_without_retry(self) -> None:
        payload = b"tampered"

        class Response(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "downloads" / "kind"
            with mock.patch.object(
                self.bootstrap.urllib.request, "urlopen", return_value=Response(payload)
            ) as urlopen, mock.patch.object(self.bootstrap.time, "sleep") as sleep:
                with self.assertRaises(self.bootstrap.DownloadIntegrityError):
                    self.bootstrap._download(
                        "https://downloads.example/kind", "0" * 64, destination
                    )
            urlopen.assert_called_once()
            sleep.assert_not_called()
            self.assertFalse(destination.exists())
            self.assertEqual(list(destination.parent.glob("*.download.tmp")), [])

    def test_tool_download_mirror_is_controlled_and_falls_back_to_canonical(self) -> None:
        canonical = "https://github.com/org/repo/releases/download/v1/tool"
        mirror = self.bootstrap._mirror_url(
            canonical, "https://mirror.example/platform-cache"
        )
        self.assertEqual(
            mirror,
            "https://mirror.example/platform-cache/github.com/org/repo/releases/download/v1/tool",
        )
        with self.assertRaises(self.bootstrap.DownloadError):
            self.bootstrap._mirror_url(canonical, "http://mirror.example/cache")

    def test_tool_download_rechecks_symlink_after_lock_acquisition(self) -> None:
        payload = b"cached"
        expected = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "downloads" / "kind"
            destination.parent.mkdir(parents=True)
            target = root / "target"
            target.write_bytes(payload)

            @contextmanager
            def replace_with_symlink(_destination):
                destination.symlink_to(target)
                yield

            with mock.patch.object(
                self.bootstrap, "_download_lock", side_effect=replace_with_symlink
            ), mock.patch.object(self.bootstrap.urllib.request, "urlopen") as urlopen:
                with self.assertRaises(self.bootstrap.DownloadIntegrityError):
                    self.bootstrap._download(
                        "https://downloads.example/kind", expected, destination
                    )
            urlopen.assert_not_called()

    def test_tool_download_uses_valid_cached_digest_without_network(self) -> None:
        payload = b"cached"
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "downloads" / "kind"
            destination.parent.mkdir(parents=True)
            destination.write_bytes(payload)
            with mock.patch.object(self.bootstrap.urllib.request, "urlopen") as urlopen:
                self.bootstrap._download(
                    "https://downloads.example/kind",
                    hashlib.sha256(payload).hexdigest(),
                    destination,
                )
            urlopen.assert_not_called()

    def test_kind_reference_requests_ha_required_kubectl_cnpg_tool(self) -> None:
        source = (ROOT / "scripts/platform/kind_reference.py").read_text(encoding="utf-8")
        self.assertIn('"kubectl_cnpg"', source)

    def test_static_platform_contract_passes(self) -> None:
        result = self.validator.validate(render=False)
        self.assertEqual(result["status"], "pass")

    def test_oci_proof_mirror_contract_is_private_digest_bound_and_budgeted(self) -> None:
        result = self.oci_mirror.validate_contract()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["owner"], "heimgewebe/weltgewebe")
        self.assertEqual(result["source_kind"], "private-ghcr-digest-mirror")
        self.assertEqual(
            result["mirror_repository"],
            "ghcr.io/heimgewebe/weltgewebe-proof-oci",
        )
        self.assertEqual(result["visibility"], "private")
        self.assertEqual(result["repository_binding"], "heimgewebe/weltgewebe")
        self.assertEqual(result["image_count"], 25)
        self.assertTrue(result["retention"]["unbounded_growth_prevented"])
        self.assertEqual(result["retention"]["observed_package_versions"], 193)
        self.assertEqual(result["retention"]["package_version_hard_limit"], 512)
        self.assertEqual(result["retention"]["orphan_grace_days"], 14)

    def test_oci_mirror_suite_selection_is_exact(self) -> None:
        lock = self.oci_mirror._load_lock()
        kind = self.oci_mirror._selected_images(
            lock, ["kind-gitops", "app-build"]
        )
        ha = self.oci_mirror._selected_images(
            lock, ["ha-recovery", "app-build"]
        )
        self.assertEqual(len(kind), 15)
        self.assertEqual(len(ha), 23)
        self.assertEqual(len({name for name, _spec in kind}), 15)
        self.assertEqual(len({name for name, _spec in ha}), 23)

    def test_oci_mirror_wrong_digest_fails_without_retry(self) -> None:
        digest = "sha256:" + "a" * 64
        spec = {
            "mirror": "ghcr.io/heimgewebe/weltgewebe-proof-oci@" + digest,
            "local_ref": "example.invalid/image:test",
        }
        budgets = {"pull_attempts": 3, "retry_backoff_seconds": [5, 10]}
        with mock.patch.object(
            self.oci_mirror, "_local_image", return_value=None
        ), mock.patch.object(self.oci_mirror, "_run") as run, mock.patch.object(
            self.oci_mirror,
            "_repo_digests",
            return_value=["ghcr.io/heimgewebe/weltgewebe-proof-oci@sha256:" + "b" * 64],
        ), mock.patch.object(self.oci_mirror.time, "sleep") as sleep:
            with self.assertRaises(self.oci_mirror.IntegrityError):
                self.oci_mirror._pull_one("test", spec, budgets)
        run.assert_called_once_with(["docker", "pull", spec["mirror"]], timeout=900)
        sleep.assert_not_called()

    def test_oci_mirror_unavailable_uses_bounded_retries(self) -> None:
        digest = "sha256:" + "a" * 64
        spec = {
            "mirror": "ghcr.io/heimgewebe/weltgewebe-proof-oci@" + digest,
            "local_ref": "example.invalid/image:test",
        }
        budgets = {"pull_attempts": 3, "retry_backoff_seconds": [5, 10]}
        error = subprocess.CalledProcessError(1, ["docker", "pull"])
        with mock.patch.object(
            self.oci_mirror, "_local_image", return_value=None
        ), mock.patch.object(
            self.oci_mirror, "_run", side_effect=error
        ) as run, mock.patch.object(self.oci_mirror.time, "sleep") as sleep:
            with self.assertRaises(
                self.oci_mirror.ControlledMirrorUnavailableError
            ):
                self.oci_mirror._pull_one("test", spec, budgets)
        self.assertEqual(run.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in sleep.call_args_list],
            [5.0, 10.0],
        )

    def test_oci_mirror_pull_tags_only_after_exact_digest_verification(self) -> None:
        digest = "sha256:" + "a" * 64
        spec = {
            "mirror": "ghcr.io/heimgewebe/weltgewebe-proof-oci@" + digest,
            "local_ref": "example.invalid/image:test",
        }
        budgets = {"pull_attempts": 3, "retry_backoff_seconds": [5, 10]}
        verified = {"image_id": "sha256:" + "c" * 64, "source": "local-verified"}
        with mock.patch.object(
            self.oci_mirror, "_local_image", side_effect=[None, verified]
        ), mock.patch.object(self.oci_mirror, "_run") as run, mock.patch.object(
            self.oci_mirror, "_repo_digests", return_value=[spec["mirror"]]
        ):
            result = self.oci_mirror._pull_one("test", spec, budgets)
        self.assertEqual(result["action"], "pulled")
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["docker", "pull", spec["mirror"]],
                ["docker", "tag", spec["mirror"], spec["local_ref"]],
            ],
        )

    def test_oci_mirror_registers_and_verifies_kind_digest_alias(self) -> None:
        digest = "sha256:" + "a" * 64
        local_ref = "docker.io/library/test:v1"
        digest_ref = f"{local_ref}@{digest}"
        payload = f"REF TYPE DIGEST SIZE PLATFORMS LABELS\n{digest_ref} type {digest} 1B linux/amd64 -"
        with mock.patch.object(self.oci_mirror, "_run") as run, mock.patch.object(
            self.oci_mirror, "_output", return_value=payload
        ) as output:
            result = self.oci_mirror._register_kind_digest_alias(
                "proof-control-plane", local_ref, digest_ref, digest
            )
        run.assert_called_once_with(
            [
                "docker",
                "exec",
                "proof-control-plane",
                "ctr",
                "--namespace",
                "k8s.io",
                "images",
                "tag",
                "--force",
                local_ref,
                digest_ref,
            ],
            timeout=60,
        )
        output.assert_called_once_with(
            [
                "docker",
                "exec",
                "proof-control-plane",
                "ctr",
                "--namespace",
                "k8s.io",
                "images",
                "list",
                f"name=={digest_ref}",
            ],
            timeout=60,
        )
        self.assertEqual(result["target_digest"], digest)

    def test_oci_mirror_kind_digest_alias_mismatch_fails_closed(self) -> None:
        digest = "sha256:" + "a" * 64
        local_ref = "docker.io/library/test:v1"
        digest_ref = f"{local_ref}@{digest}"
        payload = f"REF TYPE DIGEST SIZE PLATFORMS LABELS\n{digest_ref} type sha256:{'b' * 64} 1B linux/amd64 -"
        with mock.patch.object(self.oci_mirror, "_run"), mock.patch.object(
            self.oci_mirror, "_output", return_value=payload
        ):
            with self.assertRaisesRegex(
                self.oci_mirror.IntegrityError, "digest alias target mismatch"
            ):
                self.oci_mirror._register_kind_digest_alias(
                    "proof-control-plane", local_ref, digest_ref, digest
                )

    def test_oci_mirror_live_package_budget_is_fail_closed(self) -> None:
        lock = self.oci_mirror._load_lock()
        package = {
            "id": lock["mirror"]["package_id"],
            "name": "weltgewebe-proof-oci",
            "package_type": "container",
            "visibility": "private",
            "repository": {"full_name": "heimgewebe/weltgewebe"},
            "version_count": lock["budgets"]["package_version_hard_limit"] + 1,
        }
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
            self.oci_mirror, "_output", return_value=json.dumps(package)
        ):
            state = Path(tmp)
            with self.assertRaises(self.oci_mirror.BudgetError):
                self.oci_mirror.verify_live_package(state)
            receipt = json.loads((state / "live-package-receipt.json").read_text())
        self.assertEqual(receipt["status"], "fail")
        self.assertEqual(
            receipt["failure_class"], "integrity_or_budget_mismatch"
        )

    def test_oci_mirror_lock_rejects_target_digest_injection(self) -> None:
        lock = json.loads(
            (ROOT / "platform/oci-proof-mirror.lock.json").read_text()
        )
        lock["images"]["kind_node"]["mirror"] = (
            "ghcr.io/heimgewebe/weltgewebe-proof-oci@sha256:" + "0" * 64
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lock.json"
            path.write_text(json.dumps(lock))
            with mock.patch.object(self.oci_mirror, "LOCK_PATH", path):
                with self.assertRaises(self.oci_mirror.IntegrityError):
                    self.oci_mirror._load_lock()

    def test_oci_mirror_lock_rejects_seed_binding_drift(self) -> None:
        lock = json.loads(
            (ROOT / "platform/oci-proof-mirror.lock.json").read_text()
        )
        lock["images"]["kind_node"]["canonical"] = (
            "docker.io/kindest/node@sha256:" + "0" * 64
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lock.json"
            path.write_text(json.dumps(lock))
            with mock.patch.object(self.oci_mirror, "LOCK_PATH", path):
                with self.assertRaises(self.oci_mirror.IntegrityError):
                    self.oci_mirror._load_lock()

    def test_strict_oci_dockerfiles_use_verified_local_base_tags(self) -> None:
        with mock.patch.dict(
            os.environ,
            {self.reference.OCI_STRICT_ENV: "1"},
            clear=False,
        ):
            api = self.reference.controlled_oci_dockerfile(
                ROOT / "apps/api/Dockerfile"
            )
            web = self.reference.controlled_oci_dockerfile(
                ROOT / "apps/web/Dockerfile"
            )
        api_from = [line for line in api.splitlines() if line.startswith("FROM ")]
        web_from = [line for line in web.splitlines() if line.startswith("FROM ")]
        self.assertTrue(api_from)
        self.assertTrue(web_from)
        self.assertFalse(any("@sha256:" in line for line in api_from + web_from))
        self.assertIn("FROM rust:1.89.0-bookworm AS builder", api_from)
        self.assertIn("FROM debian:bookworm-slim", api_from)
        self.assertIn("FROM node:20.19.0-alpine AS builder", web_from)
        self.assertIn("FROM caddy:2.7", web_from)

    def test_strict_image_builds_consume_dockerfiles_from_stdin(self) -> None:
        with mock.patch.object(
            self.reference,
            "_build_dockerfile",
            side_effect=[
                (["--file", "-"], "FROM rust:local AS builder\n"),
                (["--file", "-"], "FROM node:local AS builder\n"),
            ],
        ), mock.patch.object(self.reference, "run") as run, mock.patch.object(
            self.reference,
            "output",
            return_value="sha256:" + "a" * 64,
        ):
            self.reference.build_images("kind", "proof", "b" * 40, "timestamp")
        api_build = run.call_args_list[0]
        web_build = run.call_args_list[1]
        self.assertEqual(api_build.args[0][:5], ["docker", "build", "--pull=false", "--file", "-"])
        self.assertEqual(web_build.args[0][:5], ["docker", "build", "--pull=false", "--file", "-"])
        self.assertEqual(api_build.kwargs["input_text"], "FROM rust:local AS builder\n")
        self.assertEqual(web_build.kwargs["input_text"], "FROM node:local AS builder\n")

    def test_strict_oci_policy_sets_cnpg_cluster_pull_policy(self) -> None:
        cluster = {
            "apiVersion": "postgresql.cnpg.io/v1",
            "kind": "Cluster",
            "spec": {"instances": 3},
        }
        with mock.patch.dict(os.environ, {self.reference.OCI_STRICT_ENV: "1"}):
            result = self.reference.enforce_controlled_oci_pull_policy([cluster])
        self.assertEqual(result[0]["spec"]["imagePullPolicy"], "Never")

    def test_strict_oci_policy_forces_never_for_every_pod_container(self) -> None:
        documents = [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "spec": {
                    "template": {
                        "spec": {
                            "initContainers": [{"name": "init", "image": "init:v1"}],
                            "containers": [{"name": "app", "image": "app:v1"}],
                        }
                    }
                },
            }
        ]
        with mock.patch.dict(os.environ, {self.reference.OCI_STRICT_ENV: "1"}):
            result = self.reference.enforce_controlled_oci_pull_policy(documents)
        pod = result[0]["spec"]["template"]["spec"]
        self.assertEqual(pod["initContainers"][0]["imagePullPolicy"], "Never")
        self.assertEqual(pod["containers"][0]["imagePullPolicy"], "Never")

    def test_kubernetes_proof_workflow_is_reusable_and_auditable(self) -> None:
        workflow_path = ROOT / ".github/workflows/kubernetes-platform.yml"
        workflow_text = workflow_path.read_text()
        workflow = yaml.safe_load(workflow_text)
        self.assertFalse(workflow["concurrency"]["cancel-in-progress"])
        self.assertIn("github.event.pull_request.head.sha || github.sha", workflow["concurrency"]["group"])
        self.assertNotIn("oci-proof-cache", workflow_text)
        for job_name in (
            "contract",
            "trivy-rendered-security",
            "kind-gitops-proof",
            "kind-ha-recovery-proof",
        ):
            checkout = workflow["jobs"][job_name]["steps"][0]
            self.assertTrue(str(checkout["uses"]).startswith("actions/checkout@"))
            self.assertEqual(checkout["with"]["fetch-depth"], 0)
            self.assertIs(checkout["with"]["persist-credentials"], False)

        def named_steps(job_name: str) -> dict[str, dict]:
            return {
                step["name"]: step
                for step in workflow["jobs"][job_name]["steps"]
                if "name" in step
            }

        for job_name, suite, cleanup_name in (
            ("kind-gitops-proof", "kind-gitops", "Reconcile owned kind proof resources"),
            ("kind-ha-recovery-proof", "ha-recovery", "Reconcile owned HA proof resources"),
        ):
            steps = named_steps(job_name)
            self.assertEqual(workflow["jobs"][job_name]["needs"], "contract")
            self.assertEqual(
                workflow["jobs"][job_name]["env"]["WELTGEWEBE_PROOF_OCI_STRICT"],
                "1",
            )
            self.assertEqual(
                workflow["jobs"][job_name]["permissions"],
                {"contents": "read", "packages": "read"},
            )
            init_step = steps["Initialize isolated OCI mirror credentials"]
            self.assertIn("$RUNNER_TEMP", init_step["run"])
            self.assertIn("$GITHUB_ENV", init_step["run"])
            live_step = steps["Verify live OCI mirror package budget"]
            self.assertEqual(live_step["env"], {"GH_TOKEN": "${{ github.token }}"})
            self.assertIn("oci_proof_mirror.py", live_step["run"])
            self.assertIn("verify-live", live_step["run"])
            auth_step = steps["Authenticate controlled OCI mirror"]
            self.assertEqual(auth_step["env"], {"GH_TOKEN": "${{ github.token }}"})
            self.assertIn("docker login ghcr.io", auth_step["run"])
            load_step = next(
                step for name, step in steps.items() if name.startswith("Load controlled")
            )
            self.assertIn("oci_proof_mirror.py", load_step["run"])
            self.assertIn("load-host", load_step["run"])
            self.assertIn(f"--suite {suite}", load_step["run"])
            self.assertIn("--suite app-build", load_step["run"])
            logout_step = steps["Remove OCI mirror credentials"]
            self.assertEqual(
                logout_step["if"],
                "always() && steps.proof-cache.outputs.cache-hit != 'true'",
            )
            self.assertIn("docker logout ghcr.io", logout_step["run"])
            block_step = steps["Block all OCI registries after mirror load"]
            for registry in ("registry-1.docker.io", "quay.io", "ghcr.io"):
                self.assertIn(registry, block_step["run"])
            self.assertIn('echo "::1 $host"', block_step["run"])
            self.assertIn("getent ahostsv4", block_step["run"])
            self.assertIn("getent ahostsv6", block_step["run"])
            offline_step = steps["Verify loaded OCI inputs offline"]
            self.assertIn("verify-host", offline_step["run"])
            self.assertIn(f"--suite {suite}", offline_step["run"])
            self.assertIn("--suite app-build", offline_step["run"])
            compute = next(step for name, step in steps.items() if name.startswith("Compute immutable"))
            restore = next(step for name, step in steps.items() if name.startswith("Restore immutable"))
            validate = next(step for name, step in steps.items() if name.startswith("Validate restored"))
            cleanup = steps[cleanup_name]
            self.assertIn(f"--suite {suite}", compute["run"])
            self.assertIn('--source-commit "$PROOF_SOURCE_COMMIT"', compute["run"])
            self.assertTrue(str(restore["uses"]).startswith("actions/cache@"))
            self.assertIn("steps.proof-identity.outputs.identity", restore["with"]["key"] )
            self.assertEqual(validate["if"], "steps.proof-cache.outputs.cache-hit == 'true'")
            self.assertIn("proof_identity.py validate", validate["run"])
            self.assertEqual(
                cleanup["if"],
                "always() && steps.proof-cache.outputs.cache-hit != 'true'",
            )
            self.assertIn("--receipt build/kubernetes-platform/", cleanup["run"])

        gitops = named_steps("kind-gitops-proof")
        self.assertEqual(
            gitops["Stage failure diagnostics"]["if"],
            "failure() && steps.proof-cache.outputs.cache-hit != 'true'",
        )
        self.assertEqual(
            gitops["Collect failure diagnostics"]["with"]["path"],
            "build/kubernetes-platform/failures/",
        )

        ha = named_steps("kind-ha-recovery-proof")
        stage_receipt = ha["Stage HA recovery receipt"]
        self.assertEqual(stage_receipt["if"], "success()")
        self.assertIn(
            "build/kubernetes-platform/reuse/ha-recovery/proof.json",
            stage_receipt["run"],
        )
        self.assertNotIn("ha-recovery-oci-mirror", stage_receipt["run"])
        upload_receipt = ha["Upload HA recovery receipt"]
        self.assertEqual(upload_receipt["if"], "success()")
        self.assertIn("ha-recovery-identity.json", upload_receipt["with"]["path"])
        self.assertIn(
            "build/kubernetes-platform/ha-recovery-oci-mirror/*.json",
            upload_receipt["with"]["path"],
        )

        for job_name in ("kind-gitops-proof", "kind-ha-recovery-proof"):
            for step in workflow["jobs"][job_name]["steps"]:
                if str(step.get("uses", "")).startswith("actions/upload-artifact@"):
                    self.assertNotIn(".cache/", str((step.get("with") or {}).get("path", "")))

    def test_ci_proof_binds_pull_requests_to_checked_out_merge_state(self) -> None:
        workflow_path = ROOT / ".github/workflows/kubernetes-platform.yml"
        workflow_text = workflow_path.read_text()
        workflow = yaml.safe_load(workflow_text)
        steps = workflow["jobs"]["kind-gitops-proof"]["steps"]
        named_steps = {step["name"]: step for step in steps if "name" in step}

        direct = named_steps["Run pull-request direct reference proof"]
        gitops = named_steps["Run commit-bound GitOps reference proof"]

        self.assertEqual(
            direct["if"],
            "steps.proof-cache.outputs.cache-hit != 'true' && github.event_name == 'pull_request'",
        )
        self.assertEqual(
            gitops["if"],
            "steps.proof-cache.outputs.cache-hit != 'true' && github.event_name != 'pull_request'",
        )
        self.assertEqual(
            shlex.split(direct["run"]),
            [
                "python",
                "scripts/platform/kind_reference.py",
                "proof",
                "--cluster",
                "$CLUSTER_NAME",
                "--mode",
                "direct",
                "--owner-id",
                "$PROOF_OWNER_ID",
            ],
        )
        self.assertEqual(
            shlex.split(gitops["run"]),
            [
                "python",
                "scripts/platform/kind_reference.py",
                "proof",
                "--cluster",
                "$CLUSTER_NAME",
                "--mode",
                "gitops",
                "--source-commit",
                "$GITHUB_SHA",
                "--owner-id",
                "$PROOF_OWNER_ID",
            ],
        )
        self.assertIn("PROOF_SOURCE_COMMIT: ${{ github.event.pull_request.head.sha || github.sha }}", workflow_text)
        self.assertNotIn("SOURCE_REF:", workflow_text)
        self.assertNotIn("github.head_ref || github.ref_name", workflow_text)

    def test_proof_identity_ignores_unrelated_inputs_and_rejects_tampering(self) -> None:
        commit = "0123456789abcdef0123456789abcdef01234567"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "platform").mkdir()
            (root / "scripts/platform").mkdir(parents=True)
            (root / "docs").mkdir()
            (root / "platform/toolchain.lock.json").write_text("{}\n")
            (root / "platform/oci-proof-mirror.lock.json").write_text("{}\n")
            (root / "scripts/platform/proof_identity.py").write_text("helper-v1\n")
            (root / "docs/unrelated.md").write_text("one\n")
            tracked = (
                "platform/toolchain.lock.json",
                "platform/oci-proof-mirror.lock.json",
                "scripts/platform/proof_identity.py",
                "docs/unrelated.md",
            )
            with mock.patch.object(self.proof_identity, "ROOT", root), mock.patch.object(
                self.proof_identity, "_tracked_files", return_value=tracked
            ), mock.patch.dict(
                self.proof_identity.SUITE_INPUTS,
                {"kind-gitops": ("platform/", "scripts/platform/")},
                clear=True,
            ):
                first = self.proof_identity.compute_identity("kind-gitops", commit)
                (root / "docs/unrelated.md").write_text("two\n")
                second = self.proof_identity.compute_identity("kind-gitops", commit)
                self.assertEqual(first["identity_sha256"], second["identity_sha256"])
                (root / "scripts/platform/proof_identity.py").write_text("helper-v2\n")
                third = self.proof_identity.compute_identity("kind-gitops", commit)
                self.assertNotEqual(first["identity_sha256"], third["identity_sha256"])

                identity_path = root / "identity.json"
                identity_path.write_bytes(self.proof_identity._canonical_json(third))
                proof_path = root / "source-proof.json"
                proof_path.write_text(json.dumps({
                    "status": "pass",
                    "tool_lock_sha256": third["tool_lock_sha256"],
                    "commit": commit,
                    "source_commit": commit,
                    "production_changed": False,
                }))
                reuse = root / "reuse"
                with mock.patch.object(
                    self.proof_identity, "_checkout_commit", return_value=commit
                ):
                    self.proof_identity.record(identity_path, proof_path, reuse)
                self.proof_identity.validate(
                    identity_path, reuse / "record.json", reuse / "proof.json"
                )
                with (reuse / "proof.json").open("a") as handle:
                    handle.write(" ")
                with self.assertRaises(self.proof_identity.IdentityError):
                    self.proof_identity.validate(
                        identity_path, reuse / "record.json", reuse / "proof.json"
                    )

    def test_proof_validate_rejects_crafted_policy_and_record_fields(self) -> None:
        identity = {
            "schema_version": 1,
            "suite": "kind-gitops",
            "source_commit": "1" * 40,
            "input_manifest_sha256": "2" * 64,
            "tool_lock_sha256": "3" * 64,
            "invalidation_contract": [],
            "identity_sha256": "4" * 64,
        }
        proof = {
            "status": "pass",
            "tool_lock_sha256": "3" * 64,
            "commit": "5" * 40,
            "source_commit": "1" * 40,
            "production_changed": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity_path = root / "identity.json"
            source_proof_path = root / "source-proof.json"
            reuse = root / "reuse"
            identity_path.write_text(json.dumps(identity))
            source_proof_path.write_text(json.dumps(proof))
            with mock.patch.object(
                self.proof_identity, "compute_identity", return_value=identity
            ), mock.patch.object(
                self.proof_identity, "_checkout_commit", return_value="5" * 40
            ):
                self.proof_identity.record(identity_path, source_proof_path, reuse)

                proof_path = reuse / "proof.json"
                record_path = reuse / "record.json"
                crafted_proof = json.loads(proof_path.read_text())
                crafted_proof["production_changed"] = None
                proof_bytes = self.proof_identity._canonical_json(crafted_proof)
                proof_path.write_bytes(proof_bytes)
                crafted_record = json.loads(record_path.read_text())
                crafted_record["proof_receipt_sha256"] = hashlib.sha256(proof_bytes).hexdigest()
                crafted_record["production_changed"] = None
                record_path.write_bytes(self.proof_identity._canonical_json(crafted_record))
                with self.assertRaisesRegex(
                    self.proof_identity.IdentityError, "production_changed=false"
                ):
                    self.proof_identity.validate(identity_path, record_path, proof_path)

                self.proof_identity.record(identity_path, source_proof_path, reuse)
                drifted_record = json.loads(record_path.read_text())
                drifted_record["proof_commit"] = "6" * 40
                record_path.write_bytes(self.proof_identity._canonical_json(drifted_record))
                with self.assertRaisesRegex(
                    self.proof_identity.IdentityError, "record commit"
                ):
                    self.proof_identity.validate(identity_path, record_path, proof_path)

    def test_proof_record_rejects_receipt_from_different_checkout(self) -> None:
        identity = {
            "schema_version": 1,
            "suite": "kind-gitops",
            "source_commit": "1" * 40,
            "input_manifest_sha256": "2" * 64,
            "tool_lock_sha256": "3" * 64,
            "invalidation_contract": [],
            "identity_sha256": "4" * 64,
        }
        proof = {
            "status": "pass",
            "tool_lock_sha256": "3" * 64,
            "commit": "5" * 40,
            "production_changed": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity_path = root / "identity.json"
            proof_path = root / "proof.json"
            identity_path.write_text(json.dumps(identity))
            proof_path.write_text(json.dumps(proof))
            with mock.patch.object(
                self.proof_identity, "compute_identity", return_value=identity
            ), mock.patch.object(
                self.proof_identity, "_checkout_commit", return_value="6" * 40
            ):
                with self.assertRaisesRegex(
                    self.proof_identity.IdentityError, "current checkout commit"
                ):
                    self.proof_identity.record(identity_path, proof_path, root / "reuse")

    def test_proof_record_requires_explicit_no_production_change(self) -> None:
        identity = {
            "schema_version": 1,
            "suite": "ha-recovery",
            "source_commit": "1" * 40,
            "input_manifest_sha256": "2" * 64,
            "tool_lock_sha256": "3" * 64,
            "invalidation_contract": [],
            "identity_sha256": "4" * 64,
        }
        proof = {
            "status": "pass",
            "tool_lock_sha256": "3" * 64,
            "commit": "5" * 40,
            "production_changed": None,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity_path = root / "identity.json"
            proof_path = root / "proof.json"
            identity_path.write_text(json.dumps(identity))
            proof_path.write_text(json.dumps(proof))
            with mock.patch.object(
                self.proof_identity, "compute_identity", return_value=identity
            ), mock.patch.object(
                self.proof_identity, "_checkout_commit", return_value="5" * 40
            ):
                with self.assertRaisesRegex(
                    self.proof_identity.IdentityError, "production_changed=false"
                ):
                    self.proof_identity.record(identity_path, proof_path, root / "reuse")

    def test_cli_parser_accepts_exact_source_commit(self) -> None:
        commit = "0123456789abcdef0123456789abcdef01234567"
        args = self.reference.argument_parser().parse_args(
            [
                "proof",
                "--cluster",
                "reference",
                "--mode",
                "gitops",
                "--source-commit",
                commit,
            ]
        )
        self.assertEqual(args.command, "proof")
        self.assertEqual(args.source_commit, commit)
        self.assertIsNone(args.source_ref)
        with self.assertRaises(SystemExit):
            self.reference.argument_parser().parse_args(
                [
                    "proof",
                    "--mode",
                    "gitops",
                    "--source-ref",
                    "main",
                    "--source-commit",
                    commit,
                ]
            )

    def test_source_binding_fails_before_cluster_work_for_invalid_modes(self) -> None:
        commit = "0123456789abcdef0123456789abcdef01234567"
        self.reference.validate_source_binding(
            "direct", source_ref=None, source_commit=None
        )
        self.reference.validate_source_binding(
            "gitops", source_ref=None, source_commit=commit
        )
        self.reference.validate_source_binding(
            "gitops", source_ref="main", source_commit=None
        )
        invalid = (
            ("unsupported", None, commit, "unsupported proof mode"),
            ("direct", "main", None, "invalid for direct"),
            ("direct", None, commit, "invalid for direct"),
            ("gitops", None, None, "exactly one"),
            ("gitops", "main", commit, "exactly one"),
            ("gitops", None, "abc", "full lowercase"),
            ("gitops", None, "A" * 40, "full lowercase"),
        )
        for mode, source_ref, source_commit, message in invalid:
            with self.subTest(mode=mode, source_ref=source_ref), self.assertRaisesRegex(
                self.reference.ProofError, message
            ):
                self.reference.validate_source_binding(
                    mode, source_ref=source_ref, source_commit=source_commit
                )

    def test_commit_source_must_match_local_workspace_head(self) -> None:
        commit = "0123456789abcdef0123456789abcdef01234567"
        self.reference.validate_workspace_binding(
            source_commit=None, workspace_commit=commit
        )
        self.reference.validate_workspace_binding(
            source_commit=commit, workspace_commit=commit
        )
        with self.assertRaisesRegex(
            self.reference.ProofError, "exact local workspace HEAD"
        ):
            self.reference.validate_workspace_binding(
                source_commit="fedcba9876543210fedcba9876543210fedcba98",
                workspace_commit=commit,
            )

    def test_flux_source_can_bind_exact_commit_or_explicit_branch(self) -> None:
        commit = "0123456789abcdef0123456789abcdef01234567"
        by_commit = self.reference.flux_source_document(commit=commit)
        by_branch = self.reference.flux_source_document(branch="main")
        self.assertEqual(by_commit["spec"]["ref"], {"commit": commit})
        self.assertEqual(by_branch["spec"]["ref"], {"branch": "main"})
        with self.assertRaisesRegex(self.reference.ProofError, "exactly one"):
            self.reference.flux_source_document()
        with self.assertRaisesRegex(self.reference.ProofError, "exactly one"):
            self.reference.flux_source_document(branch="main", commit=commit)

    def test_nonlocal_overlays_reject_local_fixture_markers(self) -> None:
        production = "platform/apps/weltgewebe/overlays/production"
        for marker in self.validator.LOCAL_FIXTURE_SENTINELS:
            with self.subTest(marker=marker), self.assertRaisesRegex(
                self.validator.ContractError, "local-only fixture"
            ):
                self.validator._assert_nonlocal_overlay_fixture_boundary(
                    production, marker
                )
        self.validator._assert_nonlocal_overlay_fixture_boundary(
            "platform/apps/weltgewebe/overlays/local",
            "\n".join(self.validator.LOCAL_FIXTURE_SENTINELS),
        )
        self.validator._assert_nonlocal_overlay_fixture_boundary(
            production, "WELTGEWEBE_API_MIGRATION_ONLY"
        )

    def test_toolchain_is_hash_bound(self) -> None:
        lock = json.loads((ROOT / "platform/toolchain.lock.json").read_text())
        self.assertEqual(lock["schema_version"], 1)
        for section in (lock["tools"], lock["artifacts"]):
            for name, entry in section.items():
                self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$", name)
        self.assertIn("@sha256:", lock["kubernetes"]["kind_node_image"])

    def test_gateway_api_pin_matches_cilium_required_crds(self) -> None:
        lock = json.loads((ROOT / "platform/toolchain.lock.json").read_text())
        expected = {
            "gateway_api_gatewayclasses": ("GatewayClass", "7d958ad3965ea4a4996616846d9ecaf1fededbf9351b9752b8b85973936ae8c8"),
            "gateway_api_gateways": ("Gateway", "a02ea425fc901f197b668c9ddd56375e1f6896994914c6e6b9b4fdb85cf3ba6e"),
            "gateway_api_httproutes": ("HTTPRoute", "98c6777c22309d319292e9c288ee632006c9ffdd4272383d6f9dffa3fbccaf14"),
            "gateway_api_referencegrants": ("ReferenceGrant", "d74fc2f8e90094f4c4d6dc13a2d720011a40e30e5640b3e2a2051fac820f6584"),
            "gateway_api_grpcroutes": ("GRPCRoute", "b72068b42cb32051ca609e5a8dfefb16904d164abe2e71d9f3c776fae41c4dab"),
        }
        gateway_entries = {
            name: entry
            for name, entry in lock["artifacts"].items()
            if name.startswith("gateway_api_")
        }
        self.assertEqual(set(gateway_entries), set(expected))
        for name, (kind, sha256) in expected.items():
            entry = gateway_entries[name]
            self.assertEqual(entry["version"], "1.4.1")
            self.assertEqual(entry["required_crd_kind"], kind)
            self.assertEqual(entry["sha256"], sha256)
        self.assertNotIn("TLSRoute", json.dumps(gateway_entries))
        self.assertEqual(
            self.reference.GATEWAY_API_ARTIFACTS, tuple(expected)
        )

    def test_tool_install_is_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded-kind"
            destination = root / "bin" / "kind"
            source.write_bytes(b"new-kind-binary")
            destination.parent.mkdir()
            destination.write_bytes(b"old-kind-binary")
            real_copy2 = self.bootstrap.shutil.copy2
            real_replace = os.replace
            copy_targets: list[Path] = []

            def guarded_copy(source_path, destination_path):
                target = Path(destination_path)
                self.assertNotEqual(target, destination)
                copy_targets.append(target)
                return real_copy2(source_path, destination_path)

            with mock.patch.object(
                self.bootstrap.shutil, "copy2", side_effect=guarded_copy
            ), mock.patch.object(
                self.bootstrap.os, "replace", wraps=real_replace
            ) as replace:
                self.bootstrap._install_executable(source, destination)

            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertTrue(destination.stat().st_mode & 0o110)
            self.assertEqual(len(copy_targets), 1)
            replace.assert_called_once_with(copy_targets[0], destination)

            with mock.patch.object(self.bootstrap.shutil, "copy2") as copy:
                self.bootstrap._install_executable(source, destination)
            copy.assert_not_called()

    def test_gateway_artifact_contract_rejects_extra_or_wrong_crds(self) -> None:
        spec = {"required_crd_kind": "HTTPRoute"}
        compatible = """apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
spec:
  names:
    kind: HTTPRoute
"""
        wrong = compatible.replace("HTTPRoute", "TLSRoute")
        extra = compatible + "---\n" + wrong
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "gateway.yaml"
            artifact.write_text(compatible)
            self.bootstrap._assert_artifact_contract("http", artifact, spec)
            artifact.write_text(wrong)
            with self.assertRaisesRegex(RuntimeError, "HTTPRoute"):
                self.bootstrap._assert_artifact_contract("http", artifact, spec)
            artifact.write_text(extra)
            with self.assertRaisesRegex(RuntimeError, "HTTPRoute"):
                self.bootstrap._assert_artifact_contract("http", artifact, spec)

    def test_reference_never_adopts_existing_cluster(self) -> None:
        with mock.patch.object(self.reference, "clusters", return_value={"occupied"}):
            with self.assertRaisesRegex(self.reference.ProofError, "never adopted"):
                self.reference.assert_available_cluster_name("kind", "occupied")

    def test_reference_refuses_unmarked_cluster_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                with self.assertRaisesRegex(self.reference.ProofError, "regular ownership marker"):
                    self.reference.delete_owned_cluster(
                        "kind",
                        "foreign",
                        expected_commit="a" * 40,
                        expected_owner_id="owner-proof",
                    )
            finally:
                self.reference.MARKERS = original

    def test_reference_never_silently_removes_stale_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                marker = self.reference.marker_path("stale")
                marker.write_text("{}\n", encoding="utf-8")
                with mock.patch.object(self.reference, "clusters", return_value=set()):
                    with self.assertRaisesRegex(self.reference.ProofError, "stale ownership marker"):
                        self.reference.assert_available_cluster_name("kind", "stale")
                self.assertTrue(marker.is_file())
            finally:
                self.reference.MARKERS = original

    def test_reference_refuses_cleanup_for_wrong_commit_or_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                self.reference.write_marker("proof", "a" * 40, "owner-a")
                with mock.patch.object(self.reference, "clusters", return_value=set()):
                    with self.assertRaisesRegex(self.reference.ProofError, "exact owner binding"):
                        self.reference.delete_owned_cluster(
                            "kind",
                            "proof",
                            expected_commit="b" * 40,
                            expected_owner_id="owner-a",
                        )
                    with self.assertRaisesRegex(self.reference.ProofError, "exact owner binding"):
                        self.reference.delete_owned_cluster(
                            "kind",
                            "proof",
                            expected_commit="a" * 40,
                            expected_owner_id="owner-b",
                        )
                self.assertTrue(self.reference.marker_path("proof").is_file())
            finally:
                self.reference.MARKERS = original

    def test_reference_reservation_records_exact_owner_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                with mock.patch.object(self.reference, "clusters", return_value=set()):
                    self.reference.reserve_cluster_name(
                        "kind", "proof", "a" * 40, "owner-proof"
                    )
                marker = json.loads(
                    self.reference.marker_path("proof").read_text(encoding="utf-8")
                )
                self.assertEqual(marker["schema_version"], 2)
                self.assertEqual(marker["commit"], "a" * 40)
                self.assertEqual(marker["owner_id"], "owner-proof")
            finally:
                self.reference.MARKERS = original

    def test_reference_refuses_symlink_ownership_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                target = Path(tmp) / "target.json"
                target.write_text("{}\n", encoding="utf-8")
                self.reference.marker_path("proof").symlink_to(target)
                with self.assertRaisesRegex(
                    self.reference.ProofError, "regular ownership marker"
                ):
                    self.reference.delete_owned_cluster(
                        "kind",
                        "proof",
                        expected_commit="a" * 40,
                        expected_owner_id="owner-proof",
                    )
            finally:
                self.reference.MARKERS = original

    def test_reference_refuses_cluster_without_marker_in_if_present_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                with mock.patch.object(
                    self.reference, "clusters", return_value={"proof"}
                ):
                    with self.assertRaisesRegex(
                        self.reference.ProofError, "exists without ownership marker"
                    ):
                        self.reference.delete_owned_cluster_if_present(
                            "kind",
                            "proof",
                            expected_commit="a" * 40,
                            expected_owner_id="owner-proof",
                        )
            finally:
                self.reference.MARKERS = original

    def test_kind_cluster_creation_retries_only_transient_registry_failure(self) -> None:
        transient = subprocess.CalledProcessError(
            1,
            ["kind", "create", "cluster"],
            output="",
            stderr="429 Too Many Requests from registry-1.docker.io",
        )
        success = subprocess.CompletedProcess(
            ["kind", "create", "cluster"], 0, stdout="created\n", stderr=""
        )
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                reservation = mock.MagicMock()
                with mock.patch.object(
                    self.reference,
                    "cluster_creation_reservation",
                    return_value=reservation,
                ) as reserve, mock.patch.object(
                    self.reference, "run", side_effect=[transient, success]
                ) as run, mock.patch.object(
                    self.reference, "configure_cluster_access"
                ) as configure, mock.patch.object(
                    self.reference.time, "sleep"
                ) as sleep:
                    self.reference.create_kind_cluster(
                        "kind",
                        "proof",
                        "kindest/node@sha256:" + "a" * 64,
                        "kind.yaml",
                        "a" * 40,
                        "owner-proof",
                        timeout=600,
                    )
                self.assertEqual(run.call_count, 2)
                self.assertEqual(reserve.call_count, 2)
                configure.assert_called_once_with("kind", "proof")
                sleep.assert_called_once_with(5.0)
            finally:
                self.reference.MARKERS = original

    def test_kind_cluster_creation_does_not_retry_contract_failure(self) -> None:
        permanent = subprocess.CalledProcessError(
            1,
            ["kind", "create", "cluster"],
            output="",
            stderr="invalid kind configuration",
        )
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                with mock.patch.object(
                    self.reference,
                    "cluster_creation_reservation",
                    return_value=mock.MagicMock(),
                ), mock.patch.object(
                    self.reference, "run", side_effect=permanent
                ) as run, mock.patch.object(
                    self.reference.time, "sleep"
                ) as sleep:
                    with self.assertRaises(subprocess.CalledProcessError):
                        self.reference.create_kind_cluster(
                            "kind",
                            "proof",
                            "kindest/node@sha256:" + "a" * 64,
                            "kind.yaml",
                            "a" * 40,
                            "owner-proof",
                            timeout=600,
                        )
                run.assert_called_once()
                sleep.assert_not_called()
            finally:
                self.reference.MARKERS = original

    def test_exact_owner_cleanup_reconciles_marker_after_sigkill(self) -> None:
        commit = "a" * 40
        owner = "owner-sigkill"
        cluster = "proof-sigkill"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            markers = root / "clusters"
            kubeconfigs = root / "kubeconfigs"
            child = f"""
import importlib.util
import time
from pathlib import Path
spec = importlib.util.spec_from_file_location(
    'sigkill_kind_reference',
    {str(ROOT / 'scripts/platform/kind_reference.py')!r},
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.MARKERS = Path({str(markers)!r})
module.KUBECONFIGS = Path({str(kubeconfigs)!r})
module.write_marker({cluster!r}, {commit!r}, {owner!r})
print('marker-published', flush=True)
time.sleep(60)
"""
            process = subprocess.Popen(
                [sys.executable, "-c", child],
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(process.stdout.readline().strip(), "marker-published")
                process.kill()
                process.communicate(timeout=5)
                self.assertLess(process.returncode, 0)
                self.assertTrue((markers / f"{cluster}.json").is_file())

                original_markers = self.reference.MARKERS
                original_kubeconfigs = self.reference.KUBECONFIGS
                self.reference.MARKERS = markers
                self.reference.KUBECONFIGS = kubeconfigs
                try:
                    with mock.patch.object(
                        self.reference, "clusters", return_value=set()
                    ):
                        deleted = self.reference.delete_owned_cluster_if_present(
                            "kind",
                            cluster,
                            expected_commit=commit,
                            expected_owner_id=owner,
                        )
                    self.assertTrue(deleted)
                    self.assertFalse((markers / f"{cluster}.json").exists())
                finally:
                    self.reference.MARKERS = original_markers
                    self.reference.KUBECONFIGS = original_kubeconfigs
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)

    def test_reference_marker_publication_is_no_clobber_and_crash_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                with mock.patch.object(
                    self.reference.os, "link", side_effect=OSError("link failed")
                ):
                    with self.assertRaisesRegex(OSError, "link failed"):
                        self.reference.write_marker(
                            "proof", "a" * 40, "owner-proof"
                        )
                self.assertFalse(
                    self.reference.marker_path("proof").exists()
                )
                self.assertEqual(
                    list(Path(tmp).glob(".proof.*.marker.tmp")), []
                )
            finally:
                self.reference.MARKERS = original

    def test_reference_serializes_competing_reservations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            outcomes: list[str] = []
            start = threading.Barrier(2)

            def reserve() -> None:
                start.wait(timeout=1)
                try:
                    self.reference.reserve_cluster_name(
                        "kind", "proof", "a" * 40, "owner-proof"
                    )
                    outcomes.append("reserved")
                except self.reference.ProofError:
                    outcomes.append("rejected")

            try:
                with mock.patch.object(
                    self.reference, "clusters", return_value=set()
                ):
                    threads = [threading.Thread(target=reserve) for _ in range(2)]
                    for thread in threads:
                        thread.start()
                    for thread in threads:
                        thread.join(timeout=2)
                self.assertCountEqual(outcomes, ["reserved", "rejected"])
            finally:
                self.reference.MARKERS = original

    def test_creation_reservation_blocks_exact_owner_cleanup_until_create_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            created: set[str] = set()
            entered = threading.Event()
            release = threading.Event()
            cleanup_started = threading.Event()
            cleanup_finished = threading.Event()
            cleanup_result: list[bool] = []

            def observed_clusters(_kind: str) -> set[str]:
                return set(created)

            def creator() -> None:
                with self.reference.cluster_creation_reservation(
                    "kind", "proof", "a" * 40, "owner-proof"
                ):
                    entered.set()
                    release.wait(timeout=2)
                    created.add("proof")

            def cleanup() -> None:
                cleanup_started.set()
                cleanup_result.append(
                    self.reference.delete_owned_cluster_if_present(
                        "kind",
                        "proof",
                        expected_commit="a" * 40,
                        expected_owner_id="owner-proof",
                    )
                )
                cleanup_finished.set()

            try:
                with mock.patch.object(
                    self.reference, "clusters", side_effect=observed_clusters
                ), mock.patch.object(self.reference, "run"):
                    creator_thread = threading.Thread(target=creator)
                    cleanup_thread = threading.Thread(target=cleanup)
                    creator_thread.start()
                    self.assertTrue(entered.wait(timeout=1))
                    cleanup_thread.start()
                    self.assertTrue(cleanup_started.wait(timeout=1))
                    time.sleep(0.05)
                    self.assertFalse(cleanup_finished.is_set())
                    release.set()
                    creator_thread.join(timeout=2)
                    cleanup_thread.join(timeout=2)
                self.assertEqual(cleanup_result, [True])
                self.assertFalse(self.reference.marker_path("proof").exists())
            finally:
                release.set()
                self.reference.MARKERS = original

    def test_creation_reservation_preserves_original_error_when_rollback_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original = self.reference.MARKERS
            self.reference.MARKERS = Path(tmp)
            try:
                with mock.patch.object(
                    self.reference,
                    "clusters",
                    side_effect=[set(), {"proof"}],
                ), mock.patch.object(
                    self.reference,
                    "run",
                    side_effect=self.reference.ProofError("rollback failed"),
                ):
                    with self.assertRaisesRegex(
                        self.reference.ProofError, "create failed"
                    ):
                        with self.reference.cluster_creation_reservation(
                            "kind", "proof", "a" * 40, "owner-proof"
                        ):
                            raise self.reference.ProofError("create failed")
                self.assertTrue(self.reference.marker_path("proof").is_file())
            finally:
                self.reference.MARKERS = original

    def test_web_container_copies_postinstall_script_before_install(self) -> None:
        dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
        script_copy = dockerfile.index(
            "COPY apps/web/scripts/verify-cookie-version.js ./scripts/verify-cookie-version.js"
        )
        install = dockerfile.index("RUN pnpm install --frozen-lockfile")
        self.assertLess(script_copy, install)
        self.assertIn(
            "COPY --from=builder /workspace/build /srv/weltgewebe",
            dockerfile,
        )

    def test_web_container_removes_caddy_capability_before_nonroot_user(self) -> None:
        dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
        final_stage = dockerfile.index(
            "FROM caddy:2.7@sha256:"
            "236c6a30ccb84fa412a5360ca8b586d804faba0621ea182fb45902608cd8a563"
        )
        remove_capability = dockerfile.index("RUN setcap -r /usr/bin/caddy")
        chmod_config = dockerfile.index("&& chmod 0444 /etc/caddy/Caddyfile")
        user = dockerfile.index("USER 10001:10001")
        self.assertLess(final_stage, remove_capability)
        self.assertLess(remove_capability, chmod_config)
        self.assertLess(chmod_config, user)
        self.assertNotIn("caddy.uncapped", dockerfile)

    def test_api_container_scripts_are_world_readable_and_executable(self) -> None:
        dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
        self.assertIn(
            "RUN chmod 0755 /usr/local/bin/generate-demo-data "
            "/usr/local/bin/bootstrap-first-account /usr/local/bin/entrypoint.sh",
            dockerfile,
        )
        self.assertNotIn("RUN chmod +x /usr/local/bin/generate-demo-data", dockerfile)

    def test_ready_api_pods_exclude_terminating_and_unready_pods(self) -> None:
        document = {
            "items": [
                {
                    "metadata": {"name": "terminating", "uid": "uid-old", "deletionTimestamp": "now"},
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "containerStatuses": [{"ready": True}],
                    },
                },
                {
                    "metadata": {"name": "unready", "uid": "uid-unready"},
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "False"}],
                        "containerStatuses": [{"ready": False}],
                    },
                },
                {
                    "metadata": {"name": "current", "uid": "uid-current"},
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "containerStatuses": [{"ready": True}],
                    },
                },
            ]
        }
        with mock.patch.object(
            self.reference, "output", return_value=json.dumps(document)
        ):
            self.assertEqual(
                self.reference.ready_api_pods("kubectl", "weltgewebe"),
                [("current", "uid-current")],
            )

    def test_api_version_reselects_current_ready_pod_after_failure(self) -> None:
        temporary_failure = subprocess.CalledProcessError(4, ["wget"])
        response = '{"git_commit":"0123456789abcdef0123456789abcdef01234567"}'
        first = {
            "items": [{
                "metadata": {"name": "api-old", "uid": "uid-old"},
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerStatuses": [{"ready": True}],
                },
            }]
        }
        second = {
            "items": [
                {
                    "metadata": {"name": "api-old", "uid": "uid-old", "deletionTimestamp": "now"},
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "containerStatuses": [{"ready": True}],
                    },
                },
                {
                    "metadata": {"name": "api-new", "uid": "uid-new"},
                    "status": {
                        "phase": "Running",
                        "conditions": [{"type": "Ready", "status": "True"}],
                        "containerStatuses": [{"ready": True}],
                    },
                },
            ]
        }
        with mock.patch.object(
            self.reference,
            "output",
            side_effect=[
                json.dumps(first),
                temporary_failure,
                json.dumps(second),
                response,
            ],
        ) as output_mock, mock.patch.object(
            self.reference.time, "sleep"
        ) as sleep:
            observed = self.reference.api_version("kubectl", "weltgewebe")
        self.assertEqual(observed, response)
        self.assertEqual(output_mock.call_args_list[1].args[0][4], "api-old")
        self.assertEqual(output_mock.call_args_list[3].args[0][4], "api-new")
        sleep.assert_called_once_with(1)

    def test_restart_proof_requires_complete_pod_replacement(self) -> None:
        response = '{"git_commit":"0123456789abcdef0123456789abcdef01234567"}'
        with (
            mock.patch.object(
                self.reference,
                "ready_api_pod_uids",
                side_effect=[{"old-a", "old-b"}, {"new-a", "new-b"}],
            ),
            mock.patch.object(
                self.reference, "api_version", side_effect=[response, response]
            ),
            mock.patch.object(self.reference, "run"),
            mock.patch.object(self.reference, "wait_rollout"),
        ):
            result = self.reference.prove_restart("kubectl", "weltgewebe")
        self.assertEqual(result["before"], result["after"])
        self.assertEqual(result["replaced_replicas"], "2")
        self.assertNotEqual(
            result["before_pods_sha256"], result["after_pods_sha256"]
        )

    def test_restart_proof_rejects_surviving_ready_pod(self) -> None:
        response = '{"git_commit":"0123456789abcdef0123456789abcdef01234567"}'
        with (
            mock.patch.object(
                self.reference,
                "ready_api_pod_uids",
                side_effect=[{"old-a", "old-b"}, {"old-a", "new-b"}],
            ),
            mock.patch.object(self.reference, "api_version", return_value=response),
            mock.patch.object(self.reference, "run"),
            mock.patch.object(self.reference, "wait_rollout"),
        ):
            with self.assertRaisesRegex(
                self.reference.ProofError, "did not replace every ready pod"
            ):
                self.reference.prove_restart("kubectl", "weltgewebe")

    def test_reference_binds_cluster_access_after_cluster_creation(self) -> None:
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertNotIn('"--wait",\n                "180s"', source)
        self.assertIn("def create_kind_cluster(", source)
        self.assertIn("configure_cluster_access(kind, name)", source)
        self.assertIn("create_kind_cluster(\n            kind,\n            args.cluster,", source)
        self.assertIn('"--for=condition=Ready", "nodes"', source)

    def test_control_plane_address_uses_kind_network(self) -> None:
        payload = [
            {
                "NetworkSettings": {
                    "Networks": {
                        "other": {"IPAddress": "172.19.0.9"},
                        "kind": {"IPAddress": "172.18.0.2"},
                    }
                }
            }
        ]
        with mock.patch.object(
            self.reference, "output", return_value=json.dumps(payload)
        ):
            self.assertEqual(
                self.reference.control_plane_address("reference"), "172.18.0.2"
            )

    def test_http_route_wait_reads_parent_scoped_conditions(self) -> None:
        route = {
            "metadata": {"generation": 3},
            "status": {
                "parents": [
                    {
                        "parentRef": {
                            "name": "weltgewebe",
                            "namespace": "weltgewebe-gateway",
                        },
                        "conditions": [
                            {
                                "type": "Accepted",
                                "status": "True",
                                "observedGeneration": 3,
                            },
                            {
                                "type": "ResolvedRefs",
                                "status": "True",
                                "observedGeneration": 3,
                            },
                        ],
                    }
                ]
            }
        }
        with mock.patch.object(
            self.reference, "output", return_value=json.dumps(route)
        ) as output:
            self.reference.wait_http_route_parent_condition(
                "kubectl",
                "weltgewebe",
                "weltgewebe",
                "Accepted",
                parent_name="weltgewebe",
                parent_namespace="weltgewebe-gateway",
                timeout_seconds=1,
            )
        output.assert_called_once_with(
            [
                "kubectl",
                "-n",
                "weltgewebe",
                "get",
                "httproute/weltgewebe",
                "-o",
                "json",
            ]
        )

    def test_http_route_wait_rejects_stale_generation(self) -> None:
        stale = {
            "metadata": {"generation": 2},
            "status": {
                "parents": [
                    {
                        "parentRef": {
                            "name": "weltgewebe",
                            "namespace": "weltgewebe-gateway",
                        },
                        "conditions": [
                            {
                                "type": "Accepted",
                                "status": "True",
                                "observedGeneration": 1,
                            }
                        ],
                    }
                ]
            },
        }
        current = json.loads(json.dumps(stale))
        current["status"]["parents"][0]["conditions"][0][
            "observedGeneration"
        ] = 2
        with mock.patch.object(
            self.reference,
            "output",
            side_effect=[json.dumps(stale), json.dumps(current)],
        ), mock.patch.object(self.reference.time, "sleep") as sleep:
            self.reference.wait_http_route_parent_condition(
                "kubectl",
                "weltgewebe",
                "weltgewebe",
                "Accepted",
                parent_name="weltgewebe",
                parent_namespace="weltgewebe-gateway",
                timeout_seconds=10,
            )
        sleep.assert_called_once_with(2)

    def test_gateway_contract_uses_cilium_kube_proxy_replacement(self) -> None:
        kind_config = (ROOT / "platform/clusters/local/kind.yaml").read_text()
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertIn("disableDefaultCNI: true", kind_config)
        self.assertIn("kubeProxyMode: none", kind_config)
        self.assertIn('"gatewayAPI.enabled=true"', source)
        self.assertNotIn('"gatewayAPI.hostNetwork.enabled=true"', source)
        self.assertIn('"nodeIPAM.enabled=true"', source)
        self.assertIn('"defaultLBServiceIPAM=nodeipam"', source)
        self.assertIn('"kubeProxyReplacement=true"', source)
        self.assertIn('f"k8sServiceHost={api_server_host}"', source)
        self.assertIn('"k8sServicePort=6443"', source)

    def test_gateway_addresses_use_status_ipv4_values(self) -> None:
        document = {"status": {"addresses": [
            {"type": "Hostname", "value": "ignored.example"},
            {"type": "IPAddress", "value": "172.22.0.3"},
            {"type": "IPAddress", "value": "172.22.0.4"},
            {"type": "IPAddress", "value": "172.22.0.3"},
        ]}}
        with mock.patch.object(self.reference, "output", return_value=json.dumps(document)):
            self.assertEqual(self.reference.gateway_addresses("kubectl"), ["172.22.0.3", "172.22.0.4"])

    def test_gateway_listener_port_requires_one_http_listener(self) -> None:
        document = {
            "spec": {"listeners": [{"protocol": "HTTP", "port": 80}]}
        }
        with mock.patch.object(
            self.reference, "output", return_value=json.dumps(document)
        ):
            self.assertEqual(self.reference.gateway_listener_port("kubectl"), 80)
        document["spec"]["listeners"].append({"protocol": "HTTP", "port": 8080})
        with mock.patch.object(
            self.reference, "output", return_value=json.dumps(document)
        ):
            with self.assertRaisesRegex(
                self.reference.ProofError, "exactly one HTTP listener"
            ):
                self.reference.gateway_listener_port("kubectl")

    def test_gateway_service_binds_load_balancer_listener_port(self) -> None:
        document = {
            "spec": {
                "type": "LoadBalancer",
                "ports": [{"protocol": "TCP", "port": 80, "nodePort": 31293}],
            }
        }
        with mock.patch.object(
            self.reference, "output", return_value=json.dumps(document)
        ):
            self.assertEqual(
                self.reference.gateway_service_listener_port(
                    "kubectl", "gateway-service", 80
                ),
                80,
            )
        document["spec"]["type"] = "NodePort"
        with mock.patch.object(
            self.reference, "output", return_value=json.dumps(document)
        ):
            with self.assertRaisesRegex(self.reference.ProofError, "not a LoadBalancer"):
                self.reference.gateway_service_listener_port(
                    "kubectl", "gateway-service", 80
                )

    def test_kind_nodes_require_nonempty_cluster(self) -> None:
        with mock.patch.object(
            self.reference,
            "output",
            return_value="control-plane\nworker\n",
        ):
            self.assertEqual(
                self.reference.kind_nodes("kind", "cluster"),
                ["control-plane", "worker"],
            )
        with mock.patch.object(self.reference, "output", return_value=""):
            with self.assertRaisesRegex(self.reference.ProofError, "no nodes"):
                self.reference.kind_nodes("kind", "cluster")

    def test_gateway_http_probe_uses_status_address_listener_port(self) -> None:
        health = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"healthy", stderr=b""
        )
        web = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"web", stderr=b""
        )
        api_nodes = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"[]", stderr=b""
        )
        with (
            mock.patch.object(
                self.reference,
                "kind_nodes",
                return_value=["cluster-worker"],
            ),
            mock.patch.object(
                self.reference.subprocess,
                "run",
                side_effect=[health, web, api_nodes],
            ) as run_mock,
        ):
            result = self.reference.probe_gateway_http(
                "kind",
                "cluster",
                ["172.22.0.3"],
                80,
                timeout_seconds=1,
            )
        self.assertEqual(
            result,
            ("cluster-worker", "172.22.0.3", b"healthy", b"web", b"[]"),
        )
        argv = run_mock.call_args_list[0].args[0]
        self.assertEqual(argv[:3], ["docker", "exec", "cluster-worker"])
        self.assertIn("curl", argv)
        self.assertIn("--fail", argv)
        self.assertIn("--max-time", argv)
        self.assertEqual(argv[-1], "http://172.22.0.3:80/health/live")
        self.assertEqual(
            run_mock.call_args_list[1].args[0][-1],
            "http://172.22.0.3:80/",
        )
        self.assertEqual(
            run_mock.call_args_list[2].args[0][-1],
            "http://172.22.0.3:80/api/nodes",
        )

    def test_gateway_http_probe_rejects_broken_api_rewrite(self) -> None:
        health = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"healthy", stderr=b""
        )
        web = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b"web", stderr=b""
        )
        broken_api = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=b'{"not":"a-list"}', stderr=b""
        )
        with (
            mock.patch.object(
                self.reference,
                "kind_nodes",
                return_value=["cluster-worker"],
            ),
            mock.patch.object(
                self.reference.subprocess,
                "run",
                side_effect=[health, web, broken_api],
            ),
            mock.patch.object(
                self.reference.time,
                "monotonic",
                side_effect=[0, 1],
            ),
        ):
            with self.assertRaisesRegex(
                self.reference.ProofError, "did not serve listener HTTP"
            ):
                self.reference.probe_gateway_http(
                    "kind",
                    "cluster",
                    ["172.22.0.3"],
                    80,
                    timeout_seconds=0,
                )

    def test_gateway_policy_allows_only_cilium_ingress_identity(self) -> None:
        source = (
            ROOT
            / "platform/apps/weltgewebe/base/network-policy-gateway-ingress.yaml"
        ).read_text()
        self.assertIn("apiVersion: cilium.io/v2", source)
        self.assertIn("kind: CiliumNetworkPolicy", source)
        self.assertIn("fromEntities:", source)
        self.assertIn("- ingress", source)
        self.assertIn('port: "8080"', source)
        self.assertNotIn("namespaceSelector:", source)

    def test_gateway_proof_does_not_port_forward_selectorless_service(self) -> None:
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertNotIn("def port_forward", source)
        self.assertNotIn('"port-forward"', source)
        self.assertNotIn("gateway_node_port", source)
        self.assertIn(
            "gateway_service_listener_port(kubectl, service, listener_port)", source
        )

    def test_full_proof_uses_canonical_builder_signature(self) -> None:
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertIn(
            "image_ids = build_images(kind, args.cluster, commit, timestamp)",
            source,
        )
        self.assertNotIn("commit_timestamp()", source)
        self.assertNotIn("load_images(tools", source)

    def test_local_fixture_is_public_config_map_only(self) -> None:
        data_fixture = (
            ROOT / "platform/infrastructure/local-data/fixture-config-map.yaml"
        ).read_text()
        app_fixture = (
            ROOT / "platform/apps/weltgewebe/migration/local/fixture-config-map.yaml"
        ).read_text()
        self.assertIn("kind: ConfigMap", data_fixture)
        self.assertIn("kind: ConfigMap", app_fixture)
        self.assertIn("local-test-only-weltgewebe", data_fixture)
        self.assertIn("local-test-only-weltgewebe", app_fixture)
        self.assertNotIn("kind: Secret", data_fixture + app_fixture)
        patch = (
            ROOT / "platform/apps/weltgewebe/overlays/local/database-url-patch.yaml"
        ).read_text()
        self.assertIn("configMapKeyRef:", patch)
        self.assertIn("name: weltgewebe-local-fixture", patch)

    def test_migration_is_a_declarative_completion_gated_job(self) -> None:
        job = self.reference.yaml.safe_load(
            (ROOT / "platform/apps/weltgewebe/migration/local/job.yaml").read_text()
        )
        self.assertEqual(job["apiVersion"], "batch/v1")
        self.assertEqual(job["kind"], "Job")
        self.assertEqual(job["spec"]["backoffLimit"], 0)
        pod = job["spec"]["template"]["spec"]
        self.assertEqual(pod["restartPolicy"], "Never")
        self.assertFalse(pod["automountServiceAccountToken"])
        container = pod["containers"][0]
        environment = {item["name"]: item for item in container["env"]}
        self.assertEqual(environment["WELTGEWEBE_API_MIGRATION_ONLY"]["value"], "1")
        self.assertEqual(environment["WELTGEWEBE_API_STARTUP_MIGRATIONS"]["value"], "run")
        self.assertEqual(
            environment["DATABASE_URL"]["valueFrom"]["configMapKeyRef"],
            {"name": "weltgewebe-local-fixture", "key": "database-url"},
        )
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertIn("migrate_direct(kubectl, kustomize)", source)
        self.assertIn('"job/weltgewebe-migration"', source)
        self.assertIn('"Complete"', source)
        self.assertNotIn("runtime_secret_document", source)
        self.assertNotIn("migration_pod", source)

    def test_flux_chain_gates_app_on_completed_migration(self) -> None:
        migration = self.reference.yaml.safe_load(
            (ROOT / "platform/clusters/local/migration.yaml").read_text()
        )
        app = self.reference.yaml.safe_load(
            (ROOT / "platform/clusters/local/app.yaml").read_text()
        )
        self.assertEqual(
            migration["spec"]["dependsOn"], [{"name": "weltgewebe-local-data"}]
        )
        self.assertTrue(migration["spec"]["force"])
        self.assertEqual(app["spec"]["dependsOn"], [{"name": "weltgewebe-migration"}])

    def test_reference_exposes_only_full_proof_and_owned_down(self) -> None:
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertIn('subparsers.add_parser("proof")', source)
        self.assertIn('subparsers.add_parser("down")', source)
        for command in ("phase-a", "phase-b", "phase-c", "phase-d"):
            self.assertNotIn(f'subparsers.add_parser("{command}")', source)
        for helper in ("data_up", "app_verify", "refresh_images", "local_data_up"):
            self.assertNotIn(f"def {helper}", source)

    def test_secret_contract_contains_no_values(self) -> None:
        contract = json.loads(
            (ROOT / "platform/apps/weltgewebe/secret-contract.json").read_text()
        )
        self.assertEqual(contract["required_keys"], ["database-url"])
        self.assertNotIn("stringData", contract)
        self.assertNotIn("data", contract)


if __name__ == "__main__":
    unittest.main()
