from __future__ import annotations

import importlib.util
import json
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

    def test_reference_binds_cluster_access_after_cni_bootstrap(self) -> None:
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertNotIn('"--wait",\n                "180s"', source)
        self.assertIn("configure_cluster_access(kind, args.cluster)", source)
        self.assertIn('"--for=condition=Ready", "nodes"', source)

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
            ROOT / "platform/apps/weltgewebe/overlays/local/fixture-config-map.yaml"
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

    def test_full_proof_wires_runtime_secret_to_public_fixture(self) -> None:
        app_fixture = (
            ROOT / "platform/apps/weltgewebe/overlays/local/fixture-config-map.yaml"
        )
        fixture_url = self.reference.local_fixture_database_url()
        self.assertEqual(
            fixture_url,
            self.reference.yaml.safe_load(app_fixture.read_text())["data"][
                "database-url"
            ],
        )
        secret = self.reference.runtime_secret_document("weltgewebe")
        self.assertEqual(secret["kind"], "Secret")
        self.assertEqual(secret["metadata"]["name"], "weltgewebe-runtime")
        self.assertEqual(secret["metadata"]["namespace"], "weltgewebe")
        self.assertEqual(secret["stringData"], {"database-url": fixture_url})
        self.assertNotIn("local-test-only-weltgewebe", json.dumps(secret["metadata"]))
        pod = self.reference.migration_pod("weltgewebe-api:local", "weltgewebe")
        database = next(
            item
            for item in pod["spec"]["containers"][0]["env"]
            if item["name"] == "DATABASE_URL"
        )
        self.assertEqual(
            database["valueFrom"]["secretKeyRef"],
            {"name": "weltgewebe-runtime", "key": "database-url"},
        )
        self.assertNotIn("configMapKeyRef", database["valueFrom"])
        source = (ROOT / "scripts/platform/kind_reference.py").read_text()
        self.assertIn("apply_runtime_secret(kubectl, app_namespace)", source)
        self.assertIn("migrate(kubectl, app_namespace)", source)
        self.assertNotIn("secrets.token_urlsafe", source)
        self.assertNotIn("secret_documents", source)

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
