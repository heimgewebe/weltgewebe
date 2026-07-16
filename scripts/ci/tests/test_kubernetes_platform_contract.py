from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_static_platform_contract_passes(self) -> None:
        result = self.validator.validate(render=False)
        self.assertEqual(result["status"], "pass")

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
                with self.assertRaisesRegex(self.reference.ProofError, "marker missing"):
                    self.reference.delete_owned_cluster("kind", "foreign")
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

    def test_web_container_replaces_caddy_binary_before_nonroot_user(self) -> None:
        dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
        final_stage = dockerfile.index(
            "FROM caddy:2.7@sha256:"
            "236c6a30ccb84fa412a5360ca8b586d804faba0621ea182fb45902608cd8a563"
        )
        copy_uncapped = dockerfile.index("RUN cp /usr/bin/caddy /usr/bin/caddy.uncapped")
        move_uncapped = dockerfile.index("&& mv /usr/bin/caddy.uncapped /usr/bin/caddy")
        chmod_uncapped = dockerfile.index("&& chmod 0755 /usr/bin/caddy")
        chmod_config = dockerfile.index("&& chmod 0444 /etc/caddy/Caddyfile")
        user = dockerfile.index("USER 10001:10001")
        self.assertLess(final_stage, copy_uncapped)
        self.assertLess(copy_uncapped, move_uncapped)
        self.assertLess(move_uncapped, chmod_uncapped)
        self.assertLess(chmod_uncapped, chmod_config)
        self.assertLess(chmod_config, user)

    def test_api_container_scripts_are_world_readable_and_executable(self) -> None:
        dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
        self.assertIn(
            "RUN chmod 0755 /usr/local/bin/generate-demo-data "
            "/usr/local/bin/bootstrap-first-account /usr/local/bin/entrypoint.sh",
            dockerfile,
        )
        self.assertNotIn("RUN chmod +x /usr/local/bin/generate-demo-data", dockerfile)

    def test_api_version_retries_service_propagation(self) -> None:
        temporary_failure = subprocess.CalledProcessError(4, ["wget"])
        response = '{"git_commit":"0123456789abcdef0123456789abcdef01234567"}'
        with mock.patch.object(
            self.reference,
            "output",
            side_effect=["api-pod", temporary_failure, response],
        ), mock.patch.object(self.reference.time, "sleep") as sleep:
            observed = self.reference.api_version("kubectl", "weltgewebe")
        self.assertEqual(observed, response)
        sleep.assert_called_once_with(1)

    def test_reference_binds_cluster_access_after_cni_bootstrap(self) -> None:
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertNotIn('"--wait",\n                "180s"', source)
        self.assertIn("configure_cluster_access(kind, args.cluster)", source)
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
