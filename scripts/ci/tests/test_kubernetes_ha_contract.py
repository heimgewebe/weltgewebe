from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
PLATFORM_SCRIPTS = ROOT / "scripts/platform"
if str(PLATFORM_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PLATFORM_SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KubernetesHaContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ha = load_module(
            "weltgewebe_ha_reference",
            ROOT / "scripts/platform/ha_reference.py",
        )
        cls.validator = load_module(
            "weltgewebe_platform_validator_ha",
            ROOT / "scripts/platform/validate_platform.py",
        )

    def test_static_ha_contract_passes(self) -> None:
        self.validator._assert_ha_contract()

    def test_ha_migration_reads_database_url_from_secret(self) -> None:
        document = next(
            self.validator._documents(
                ROOT / "platform/apps/weltgewebe/migration/ha/job.yaml"
            )
        )
        environment = document["spec"]["template"]["spec"]["containers"][0]["env"]
        database_url = next(
            item for item in environment if item["name"] == "DATABASE_URL"
        )
        value_from = database_url["valueFrom"]
        self.assertEqual(
            value_from["secretKeyRef"],
            {"name": "weltgewebe-ha-runtime", "key": "database-url"},
        )
        self.assertNotIn("configMapKeyRef", value_from)

    def test_all_ha_images_are_digest_bound(self) -> None:
        lock = json.loads((ROOT / "platform/toolchain.lock.json").read_text())
        self.assertEqual(
            set(lock["images"]),
            {
                "cloudnative_pg_operator",
                "cloudnative_pg_postgresql",
                "nats",
                "nats_box",
                "seaweedfs",
            },
        )
        for name, image in lock["images"].items():
            self.assertRegex(image, r"@sha256:[0-9a-f]{64}$", name)

        self.assertEqual(
            {
                "cloudnative_pg_operator": self.ha.CNPG_OPERATOR_IMAGE,
                "cloudnative_pg_postgresql": self.ha.POSTGRES_IMAGE,
                "nats_box": self.ha.NATS_BOX_IMAGE,
                "seaweedfs": self.ha.SEAWEEDFS_IMAGE,
            },
            {
                name: lock["images"][name]
                for name in (
                    "cloudnative_pg_operator",
                    "cloudnative_pg_postgresql",
                    "nats_box",
                    "seaweedfs",
                )
            },
        )

    def test_failed_kind_creation_cleans_only_the_owned_cluster(self) -> None:
        with (
            mock.patch.object(self.ha.ref, "assert_available_cluster_name"),
            mock.patch.object(self.ha.ref, "write_marker") as marker,
            mock.patch.object(
                self.ha.ref, "run", side_effect=RuntimeError("create failed")
            ),
            mock.patch.object(self.ha.ref, "delete_owned_cluster") as cleanup,
        ):
            with self.assertRaisesRegex(RuntimeError, "create failed"):
                self.ha.create_kind_cluster(
                    "kind", "proof", "image", "config", "commit"
                )
        marker.assert_called_once_with("proof", "commit")
        cleanup.assert_called_once_with("kind", "proof")

    def test_failed_object_store_setup_cleans_only_owned_resources(self) -> None:
        absent = mock.Mock(returncode=1)
        with (
            mock.patch.object(self.ha.subprocess, "run", return_value=absent),
            mock.patch.object(self.ha.ref, "run"),
            mock.patch.object(
                self.ha,
                "run_with_environment",
                side_effect=RuntimeError("start failed"),
            ),
            mock.patch.object(self.ha, "delete_external_object_store") as cleanup,
        ):
            with self.assertRaisesRegex(RuntimeError, "start failed"):
                self.ha.start_external_object_store("proof", "commit", "secret")
        cleanup.assert_called_once_with("proof", "commit")

    def test_restore_document_uses_pitr_and_three_instances(self) -> None:
        target = "2026-07-17T15:00:00.000000Z"
        document = self.ha.restore_cluster_document(target)
        spec = document["spec"]
        self.assertEqual(document["metadata"]["name"], "postgres-restore")
        self.assertEqual(spec["instances"], 3)
        recovery = spec["bootstrap"]["recovery"]
        self.assertEqual(recovery["source"], "postgres-ha")
        self.assertEqual(recovery["recoveryTarget"]["targetTime"], target)
        self.assertTrue(recovery["recoveryTarget"]["exclusive"])
        self.assertEqual(
            spec["externalClusters"][0]["barmanObjectStore"]["serverName"],
            "postgres-ha",
        )

    def test_zone_contract_requires_three_distinct_zones(self) -> None:
        valid = {
            "a": {"node": "n1", "zone": "zone-a"},
            "b": {"node": "n2", "zone": "zone-b"},
            "c": {"node": "n3", "zone": "zone-c"},
        }
        self.ha.require_zones(valid, 3, "test")
        invalid = {**valid, "c": {"node": "n3", "zone": "zone-b"}}
        with self.assertRaisesRegex(self.ha.ref.ProofError, "not spread"):
            self.ha.require_zones(invalid, 3, "test")

    def test_external_object_store_cleanup_is_ownership_bound(self) -> None:
        inspect = mock.Mock(return_value=mock.Mock(returncode=0))
        with (
            mock.patch.object(self.ha.subprocess, "run", inspect),
            mock.patch.object(self.ha.ref, "output", return_value="foreign-commit"),
        ):
            with self.assertRaisesRegex(self.ha.ref.ProofError, "foreign"):
                self.ha.delete_external_object_store("proof", "expected-commit")

    def test_cnpg_release_uses_server_side_apply(self) -> None:
        artifact = ROOT / ".cache/test-cnpg-release.yaml"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        tagged = "ghcr.io/cloudnative-pg/cloudnative-pg:1.30.0"
        artifact.write_text(f"image: {tagged}\ndefault: {tagged}\n")
        try:
            with (
                mock.patch.object(self.ha.ref, "run") as run,
                mock.patch.object(self.ha.ref, "wait_rollout"),
                mock.patch.object(self.ha, "wait_until"),
                mock.patch.object(
                    self.ha.ref, "output", return_value=self.ha.CNPG_OPERATOR_IMAGE
                ),
            ):
                self.ha.install_cnpg("kubectl", str(artifact))
            apply_argv = run.call_args_list[0].args[0]
            self.assertIn("--server-side", apply_argv)
            self.assertIn("--force-conflicts", apply_argv)
            self.assertIn("--field-manager=weltgewebe-ha-proof", apply_argv)
            payload = run.call_args_list[0].kwargs["input_text"]
            self.assertNotIn(tagged, payload)
            self.assertEqual(payload.count(self.ha.CNPG_OPERATOR_IMAGE), 2)
        finally:
            artifact.unlink(missing_ok=True)

    def test_cnpg_webhook_probe_requires_endpoint_and_server_dry_run(self) -> None:
        endpoint = mock.Mock(returncode=0, stdout="10.0.0.12")
        dry_run = mock.Mock(
            returncode=0, stdout="cluster.postgresql.cnpg.io/probe serverside-applied"
        )
        with mock.patch.object(
            self.ha.subprocess, "run", side_effect=[endpoint, dry_run]
        ) as run:
            self.assertTrue(self.ha.cnpg_webhook_ready("kubectl"))
        endpoint_argv = run.call_args_list[0].args[0]
        dry_run_argv = run.call_args_list[1].args[0]
        self.assertIn("cnpg-webhook-service", endpoint_argv)
        self.assertIn("--dry-run=server", dry_run_argv)
        self.assertIn("--server-side", dry_run_argv)
        payload = json.loads(run.call_args_list[1].kwargs["input"])
        self.assertEqual(payload["kind"], "Cluster")
        self.assertEqual(payload["metadata"]["namespace"], "default")

    def test_cnpg_webhook_probe_rejects_missing_endpoint(self) -> None:
        endpoint = mock.Mock(returncode=0, stdout="")
        with mock.patch.object(self.ha.subprocess, "run", return_value=endpoint) as run:
            self.assertFalse(self.ha.cnpg_webhook_ready("kubectl"))
        self.assertEqual(run.call_count, 1)

    def test_sensitive_environment_values_never_enter_argv(self) -> None:
        completed = mock.Mock(returncode=0)
        with mock.patch.object(
            self.ha.subprocess, "run", return_value=completed
        ) as run:
            self.ha.run_with_environment(
                ["docker", "run", "--env", "PROOF_SECRET"],
                {"PROOF_SECRET": "ephemeral-sensitive-value"},
            )
        argv = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("ephemeral-sensitive-value", argv)
        self.assertEqual(environment["PROOF_SECRET"], "ephemeral-sensitive-value")
        self.assertNotIn(
            "AWS_SECRET_ACCESS_KEY=",
            (ROOT / "scripts/platform/ha_reference.py").read_text(),
        )

    def test_postgres_operand_keeps_version_and_digest(self) -> None:
        image = self.ha.POSTGRES_IMAGE
        self.assertIn(":16.14@sha256:", image)
        self.assertNotIn("postgresql@sha256:", image)
        catalog = next(
            self.validator._documents(
                ROOT / "platform/infrastructure/ha-data/postgres-image-catalog.yaml"
            )
        )
        self.assertEqual(catalog["spec"]["images"], [{"major": 16, "image": image}])
        manifest = (ROOT / "platform/infrastructure/ha-data/postgres.yaml").read_text()
        self.assertNotIn("imageName:", manifest)
        self.assertIn("name: weltgewebe-postgres", manifest)
        self.assertIn("major: 16", manifest)
        restored = self.ha.restore_cluster_document("2026-07-17T12:00:00Z")
        self.assertEqual(
            restored["spec"]["imageCatalogRef"],
            {
                "apiGroup": "postgresql.cnpg.io",
                "kind": "ImageCatalog",
                "name": "weltgewebe-postgres",
                "major": 16,
            },
        )
        lock = json.loads((ROOT / "platform/toolchain.lock.json").read_text())
        self.assertEqual(lock["images"]["cloudnative_pg_postgresql"], image)

    def test_committed_ha_yaml_contains_no_secret(self) -> None:
        roots = (
            ROOT / "platform/infrastructure/ha-data",
            ROOT / "platform/apps/weltgewebe/overlays/ha",
            ROOT / "platform/apps/weltgewebe/migration/ha",
        )
        for root in roots:
            for path in root.glob("*.yaml"):
                self.assertNotIn("kind: Secret", path.read_text(), path)

    def test_proof_is_bound_to_a_blank_restore_cluster(self) -> None:
        source = (ROOT / "scripts/platform/ha_reference.py").read_text()
        self.assertIn('restore_name = f"{args.cluster}-restore"', source)
        self.assertIn("platform/clusters/ha/restore-kind.yaml", source)
        self.assertIn('"blank_kind_cluster": True', source)
        self.assertIn('["docker", "stop"', source)
        self.assertIn('"production_changed": False', source)

    def test_cli_exposes_proof_and_ownership_bound_down(self) -> None:
        proof = self.ha.argument_parser().parse_args(
            ["proof", "--cluster", "weltgewebe-t004-test"]
        )
        self.assertEqual(proof.command, "proof")
        self.assertFalse(proof.keep)
        down = self.ha.argument_parser().parse_args(
            ["down", "--cluster", "weltgewebe-t004-test", "--commit", "a" * 40]
        )
        self.assertEqual(down.commit, "a" * 40)


if __name__ == "__main__":
    unittest.main()
