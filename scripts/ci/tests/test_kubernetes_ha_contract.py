from __future__ import annotations

import base64
import io
import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
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
                "barman_cloud_plugin",
                "barman_cloud_sidecar",
                "cert_manager_cainjector",
                "cert_manager_controller",
                "cert_manager_webhook",
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
                "barman_cloud_plugin": self.ha.BARMAN_PLUGIN_IMAGE,
                "barman_cloud_sidecar": self.ha.BARMAN_PLUGIN_SIDECAR_IMAGE,
                "cert_manager_cainjector": self.ha.CERT_MANAGER_IMAGES[
                    "quay.io/jetstack/cert-manager-cainjector:v1.21.0"
                ],
                "cert_manager_controller": self.ha.CERT_MANAGER_IMAGES[
                    "quay.io/jetstack/cert-manager-controller:v1.21.0"
                ],
                "cert_manager_webhook": self.ha.CERT_MANAGER_IMAGES[
                    "quay.io/jetstack/cert-manager-webhook:v1.21.0"
                ],
                "cloudnative_pg_operator": self.ha.CNPG_OPERATOR_IMAGE,
                "cloudnative_pg_postgresql": self.ha.POSTGRES_IMAGE,
                "nats_box": self.ha.NATS_BOX_IMAGE,
                "seaweedfs": self.ha.SEAWEEDFS_IMAGE,
            },
            {
                name: lock["images"][name]
                for name in (
                    "barman_cloud_plugin",
                    "barman_cloud_sidecar",
                    "cert_manager_cainjector",
                    "cert_manager_controller",
                    "cert_manager_webhook",
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
        plugin = spec["externalClusters"][0]["plugin"]
        self.assertEqual(plugin["name"], "barman-cloud.cloudnative-pg.io")
        self.assertEqual(
            plugin["parameters"],
            {"barmanObjectName": "postgres-ha", "serverName": "postgres-ha"},
        )
        self.assertNotIn("barmanObjectStore", spec["externalClusters"][0])

    def test_degraded_backup_targets_the_current_primary(self) -> None:
        document = self.ha.backup_document("proof-backup")
        self.assertEqual(document["metadata"]["name"], "proof-backup")
        self.assertEqual(document["spec"]["method"], "plugin")
        self.assertEqual(document["spec"]["target"], "primary")
        self.assertEqual(document["spec"]["cluster"], {"name": "postgres-ha"})
        self.assertEqual(
            document["spec"]["pluginConfiguration"],
            {"name": "barman-cloud.cloudnative-pg.io"},
        )
        self.assertNotIn("barmanObjectStore", json.dumps(document))

    def test_backup_wait_reports_terminal_status(self) -> None:
        failed = json.dumps(
            {
                "status": {
                    "phase": "failed",
                    "error": "object store unavailable",
                }
            }
        )
        with mock.patch.object(self.ha.ref, "output", return_value=failed):
            with self.assertRaisesRegex(
                self.ha.ref.ProofError, "object store unavailable"
            ):
                self.ha.wait_backup_complete("kubectl", "proof-backup")

    def test_ha_failure_snapshot_captures_backup_and_cnpg_logs(self) -> None:
        completed = mock.Mock(stdout="diagnostic", stderr="")
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with (
                mock.patch.object(self.ha, "CACHE", cache),
                mock.patch.object(self.ha.ref, "diagnostic_snapshot") as base_snapshot,
                mock.patch.object(
                    self.ha.subprocess, "run", return_value=completed
                ) as run,
            ):
                self.ha.ha_diagnostic_snapshot("kubectl", "proof-cluster")
            base_snapshot.assert_called_once_with("kubectl", "proof-cluster")
            target = cache / "failures" / "proof-cluster"
            self.assertEqual(
                {path.name for path in target.iterdir()},
                {
                    "postgres-backup-and-cluster.yaml",
                    "barman-object-store.yaml",
                    "barman-plugin.log",
                    "cnpg-operator.log",
                    "postgres-instances.log",
                },
            )
            argv = [call.args[0] for call in run.call_args_list]
            self.assertTrue(any("backups,clusters" in command for command in argv))
            self.assertTrue(
                any("objectstore/postgres-ha" in command for command in argv)
            )
            self.assertTrue(
                any("deployment/barman-cloud" in command for command in argv)
            )
            self.assertTrue(
                any("deployment/cnpg-controller-manager" in command for command in argv)
            )
            self.assertTrue(any("cnpg.io/cluster" in command for command in argv))

    def test_degraded_proof_requires_the_failed_zone_to_stay_down(self) -> None:
        with mock.patch.object(self.ha.ref, "output", return_value="false") as output:
            self.ha.require_container_stopped("worker-zone-b")
        output.assert_called_once_with(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Running}}",
                "worker-zone-b",
            ]
        )
        with mock.patch.object(self.ha.ref, "output", return_value="true"):
            with self.assertRaisesRegex(self.ha.ref.ProofError, "unexpectedly running"):
                self.ha.require_container_stopped("worker-zone-b")

    def test_backup_and_restore_run_before_failed_zone_cleanup(self) -> None:
        source = inspect.getsource(self.ha.prove)
        checks = [
            index
            for index in range(len(source))
            if source.startswith("require_container_stopped(stopped_node)", index)
        ]
        self.assertEqual(len(checks), 2)
        self.assertLess(checks[0], source.index('backup_name = f"t004-'))
        self.assertGreater(checks[1], source.index("PITR data comparison failed"))
        self.assertNotIn('ref.run(["docker", "start", stopped_node]', source)
        self.assertIn('"remained_unavailable_through_backup_and_restore": True', source)
        self.assertIn('"method": backup.get("spec", {}).get("method")', source)
        self.assertIn('"target": backup.get("spec", {}).get("target")', source)
        self.assertIn('"plugin": backup.get("spec", {})', source)
        self.assertIn('"automatic reintegration of the failed zone"', source)
        self.assertIn("postgres_archiver_state(kubectl)", source)
        self.assertNotIn("lastArchivedWAL", source)
        helper_source = inspect.getsource(self.ha.postgres_archiver_state)
        self.assertIn("pg_stat_archiver", helper_source)

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

    def test_barman_release_binds_controller_and_sidecar_images(self) -> None:
        artifact = ROOT / ".cache/test-barman-plugin-release.yaml"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        sidecar_tagged = "ghcr.io/cloudnative-pg/plugin-barman-cloud-sidecar:v0.13.0"
        encoded = base64.b64encode(sidecar_tagged.encode()).decode()
        artifact.write_text(
            "apiVersion: v1\ndata:\n  SIDECAR_IMAGE: |\n"
            f"    {encoded}\nkind: Secret\n---\n"
            "image: ghcr.io/cloudnative-pg/plugin-barman-cloud:v0.13.0\n"
        )
        try:
            payload = self.ha.barman_cloud_release_source(str(artifact))
            self.assertIn(self.ha.BARMAN_PLUGIN_IMAGE, payload)
            self.assertNotIn(sidecar_tagged, payload)
            lines = payload.splitlines()
            marker = lines.index("  SIDECAR_IMAGE: |")
            encoded_result = "".join(
                line.strip() for line in lines[marker + 1 :] if line.startswith("    ")
            )
            self.assertEqual(
                base64.b64decode(encoded_result).decode(),
                self.ha.BARMAN_PLUGIN_SIDECAR_IMAGE,
            )
        finally:
            artifact.unlink(missing_ok=True)

    def test_barman_release_rejects_sidecar_manifest_drift(self) -> None:
        artifact = ROOT / ".cache/test-barman-plugin-sidecar-drift.yaml"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        encoded = base64.b64encode(b"example.invalid/sidecar:v2").decode()
        artifact.write_text(
            "apiVersion: v1\ndata:\n  SIDECAR_IMAGE: |\n"
            f"    {encoded}\nkind: Secret\n---\n"
            "image: ghcr.io/cloudnative-pg/plugin-barman-cloud:v0.13.0\n"
        )
        try:
            with self.assertRaisesRegex(
                self.ha.ref.ProofError, "sidecar image reference changed"
            ):
                self.ha.barman_cloud_release_source(str(artifact))
        finally:
            artifact.unlink(missing_ok=True)

    def test_postgres_archiver_progress_is_plugin_neutral(self) -> None:
        before = {
            "archived_count": 4,
            "last_archived_wal": "000000010000000000000004",
            "failed_count": 0,
            "stats_reset": "2026-07-18T00:00:00.000000Z",
        }
        after = {
            **before,
            "archived_count": 5,
            "last_archived_wal": "000000010000000000000005",
        }
        with mock.patch.object(self.ha, "postgres_archiver_state", return_value=after):
            self.assertEqual(
                self.ha.wait_postgres_archive_progress(
                    "kubectl", before, timeout_seconds=1, interval=0
                ),
                after,
            )

    def test_postgres_archiver_progress_rejects_new_failures(self) -> None:
        before = {
            "archived_count": 4,
            "last_archived_wal": "000000010000000000000004",
            "failed_count": 0,
            "stats_reset": "2026-07-18T00:00:00.000000Z",
        }
        failed = {**before, "failed_count": 1, "last_failed_wal": "broken"}
        with mock.patch.object(self.ha, "postgres_archiver_state", return_value=failed):
            with self.assertRaisesRegex(self.ha.ref.ProofError, "new failure"):
                self.ha.wait_postgres_archive_progress(
                    "kubectl", before, timeout_seconds=1, interval=0
                )

    def test_postgres_archiver_progress_rejects_stats_reset(self) -> None:
        before = {
            "archived_count": 4,
            "last_archived_wal": "000000010000000000000004",
            "failed_count": 0,
            "stats_reset": "2026-07-18T00:00:00.000000Z",
        }
        reset = {**before, "stats_reset": "2026-07-18T00:01:00.000000Z"}
        with mock.patch.object(self.ha, "postgres_archiver_state", return_value=reset):
            with self.assertRaisesRegex(self.ha.ref.ProofError, "statistics reset"):
                self.ha.wait_postgres_archive_progress(
                    "kubectl", before, timeout_seconds=1, interval=0
                )

    def test_runtime_barman_sidecars_are_digest_bound(self) -> None:
        pods = {
            "items": [
                {
                    "metadata": {"name": f"postgres-ha-{index}"},
                    "spec": {
                        "initContainers": [
                            {
                                "name": "plugin-barman-cloud",
                                "image": self.ha.BARMAN_PLUGIN_SIDECAR_IMAGE,
                            }
                        ]
                    },
                    "status": {
                        "initContainerStatuses": [
                            {
                                "name": "plugin-barman-cloud",
                                "imageID": "ghcr.io/cloudnative-pg/plugin-barman-cloud-sidecar@sha256:"
                                + str(index) * 64,
                                "ready": True,
                                "state": {
                                    "running": {"startedAt": "2026-07-18T05:00:00Z"}
                                },
                            }
                        ]
                    },
                }
                for index in range(1, 4)
            ]
        }
        with mock.patch.object(self.ha.ref, "output", return_value=json.dumps(pods)):
            observed = self.ha.barman_sidecar_images("kubectl", "postgres-ha")
        self.assertEqual(len(observed), 3)
        self.assertTrue(
            all(
                item["declared_image"] == self.ha.BARMAN_PLUGIN_SIDECAR_IMAGE
                for item in observed.values()
            )
        )
        self.assertTrue(all(item["ready"] for item in observed.values()))
        self.assertTrue(all(item["running_started_at"] for item in observed.values()))

        not_running = json.loads(json.dumps(pods))
        status = not_running["items"][0]["status"]["initContainerStatuses"][0]
        status["ready"] = False
        status["state"] = {"waiting": {"reason": "CrashLoopBackOff"}}
        with mock.patch.object(
            self.ha.ref, "output", return_value=json.dumps(not_running)
        ):
            with self.assertRaisesRegex(
                self.ha.ref.ProofError, "not ready and running"
            ):
                self.ha.barman_sidecar_images("kubectl", "postgres-ha")

    def test_digest_bound_release_rewrites_exact_image_tags(self) -> None:
        artifact = ROOT / ".cache/test-digest-bound-release.yaml"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        tagged = "example.invalid/operator:v1"
        digest_bound = "example.invalid/operator@sha256:" + "a" * 64
        artifact.write_text(f"image: {tagged}\n")
        try:
            with mock.patch.object(self.ha.ref, "run") as run:
                self.ha.apply_digest_bound_release(
                    "kubectl",
                    str(artifact),
                    {tagged: digest_bound},
                    "test release",
                )
            argv = run.call_args.args[0]
            self.assertIn("--server-side", argv)
            self.assertIn("--force-conflicts", argv)
            payload = run.call_args.kwargs["input_text"]
            self.assertNotIn(tagged, payload)
            self.assertEqual(payload.count(digest_bound), 1)
        finally:
            artifact.unlink(missing_ok=True)

    def test_digest_bound_release_rejects_manifest_drift(self) -> None:
        artifact = ROOT / ".cache/test-digest-bound-release-drift.yaml"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text("image: example.invalid/operator:v2\n")
        try:
            with self.assertRaisesRegex(
                self.ha.ref.ProofError, "image reference changed unexpectedly"
            ):
                self.ha.apply_digest_bound_release(
                    "kubectl",
                    str(artifact),
                    {
                        "example.invalid/operator:v1": "example.invalid/operator@sha256:"
                        + "a" * 64
                    },
                    "test release",
                )
        finally:
            artifact.unlink(missing_ok=True)

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

    def test_main_logs_only_constant_success_summary(self) -> None:
        parser = mock.Mock()
        parser.parse_args.return_value = self.ha.argparse.Namespace(
            command="proof", cluster="proof", keep=False
        )
        with (
            mock.patch.object(self.ha, "argument_parser", return_value=parser),
            mock.patch.object(self.ha.ref, "tool_receipt", return_value={}),
            mock.patch.object(
                self.ha,
                "prove",
                return_value={"status": "pass", "secret": "must-not-leak"},
            ),
            mock.patch("builtins.print") as output,
        ):
            self.assertEqual(self.ha.main(), 0)
        output.assert_called_once_with('{"status": "pass"}')

    def test_main_does_not_log_subprocess_output(self) -> None:
        failure = subprocess.CalledProcessError(
            7,
            ["kubectl", "apply"],
            output="sensitive-stdout",
            stderr="sensitive-stderr",
        )
        parser = mock.Mock()
        parser.parse_args.return_value = self.ha.argparse.Namespace(
            command="proof", cluster="proof", keep=False
        )
        stream = io.StringIO()
        with (
            mock.patch.object(self.ha, "argument_parser", return_value=parser),
            mock.patch.object(self.ha.ref, "tool_receipt", return_value={}),
            mock.patch.object(self.ha, "prove", side_effect=failure),
            redirect_stderr(stream),
        ):
            self.assertEqual(self.ha.main(), 1)
        message = stream.getvalue()
        self.assertIn("subprocess exited with status 7", message)
        self.assertNotIn("sensitive-stdout", message)
        self.assertNotIn("sensitive-stderr", message)

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
