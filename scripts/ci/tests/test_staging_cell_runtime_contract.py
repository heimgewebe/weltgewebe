from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.platform import staging_cell as staging  # noqa: E402


class StagingCellRuntimeContractTests(unittest.TestCase):
    def _documents(self, relative: str) -> list[dict]:
        path = ROOT / relative
        return [
            document
            for document in yaml.safe_load_all(path.read_text(encoding="utf-8"))
            if isinstance(document, dict)
        ]

    def test_persistent_volumes_are_explicitly_static_and_prebound(self) -> None:
        documents = self._documents(
            "platform/clusters/staging/data/persistent-volumes.yaml"
        )
        by_kind_name = {
            (document.get("kind"), document.get("metadata", {}).get("name")): document
            for document in documents
        }
        for volume, claim in (
            ("weltgewebe-staging-postgres", "postgres-data"),
            ("weltgewebe-staging-nats", "nats-data"),
        ):
            pv = by_kind_name[("PersistentVolume", volume)]
            pvc = by_kind_name[("PersistentVolumeClaim", claim)]
            self.assertEqual(pv["spec"].get("storageClassName"), "")
            self.assertEqual(pv["spec"].get("persistentVolumeReclaimPolicy"), "Retain")
            self.assertEqual(pvc["spec"].get("storageClassName"), "")
            self.assertEqual(pvc["spec"].get("volumeName"), volume)

    def test_network_policies_follow_the_canonical_staging_compatibility_label(self) -> None:
        namespace = yaml.safe_load(
            (
                ROOT
                / "platform/apps/weltgewebe/overlays/staging/namespace.yaml"
            ).read_text(encoding="utf-8")
        )
        labels = namespace["metadata"]["labels"]
        data_client_labels = [
            key
            for key, value in labels.items()
            if key.endswith("/data-client") and str(value).lower() == "true"
        ]
        self.assertEqual(len(data_client_labels), 1)
        data_client_label = data_client_labels[0]

        documents = self._documents("platform/clusters/staging/data/network-policy.yaml")
        policies = {document["metadata"]["name"]: document for document in documents}
        expected = {
            "allow-app-postgres-access": ("postgres", 5432),
            "allow-app-nats-access": ("nats", 4222),
        }
        for name, (app_name, port) in expected.items():
            policy = policies[name]
            self.assertEqual(
                policy["spec"]["podSelector"]["matchLabels"],
                {"app.kubernetes.io/name": app_name},
            )
            ingress = policy["spec"]["ingress"]
            self.assertEqual(len(ingress), 1)
            selector = ingress[0]["from"][0]["namespaceSelector"]["matchLabels"]
            self.assertEqual(selector, {data_client_label: "true"})
            self.assertEqual(ingress[0]["ports"], [{"port": port, "protocol": "TCP"}])
        self.assertNotIn("allow-app-data-access", policies)

    def test_postgres_has_startup_budget_and_known_writable_mounts(self) -> None:
        documents = self._documents("platform/clusters/staging/data/postgres.yaml")
        deployment = next(
            document for document in documents if document.get("kind") == "Deployment"
        )
        container = deployment["spec"]["template"]["spec"]["containers"][0]
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        startup = container["startupProbe"]
        self.assertGreaterEqual(startup["failureThreshold"] * startup["periodSeconds"], 300)
        mounts = {entry["mountPath"] for entry in container["volumeMounts"]}
        self.assertTrue(
            {"/var/lib/postgresql/data", "/var/run/postgresql", "/tmp"}.issubset(mounts)
        )

    def test_kind_template_exposes_same_staging_mount_to_exactly_three_nodes(self) -> None:
        config = yaml.safe_load(
            (ROOT / "platform/clusters/staging/kind.yaml").read_text(encoding="utf-8")
        )
        nodes = config["nodes"]
        self.assertEqual(len(nodes), 3)
        mounts = [node["extraMounts"][0] for node in nodes]
        self.assertEqual(
            {mount["hostPath"] for mount in mounts},
            {"__COMMONTHING_STAGING_DATA_ROOT__"},
        )
        self.assertEqual(
            {mount["containerPath"] for mount in mounts},
            {"/var/local/weltgewebe-staging"},
        )

    def test_public_parser_does_not_offer_state_root_override(self) -> None:
        parser = staging.parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["status", "--state-root", "/tmp/other"])

    def test_public_status_keeps_diagnostics_without_secret_material(self) -> None:
        result = {
            "status": "degraded",
            "cluster": staging.DEFAULT_CLUSTER,
            "bootstrap_commit": "a" * 40,
            "source_revision": "main@sha1:" + "b" * 40,
            "source_matches_commit": False,
            "data_ready": "False",
            "pvcs": {"postgres-data": "Bound", "nats-data": "Pending"},
            "external_secret": {
                "database": True,
                "runtime": False,
                "ready": False,
                "source_sha256": "c" * 64,
                "password": "must-not-escape",
            },
        }
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            staging.emit_public_success("status", result)
        public = json.loads(stdout.getvalue())
        self.assertEqual(public["status"], "degraded")
        self.assertFalse(public["source_matches_commit"])
        self.assertEqual(public["pvcs"]["nats-data"], "Pending")
        self.assertFalse(public["external_secret"]["runtime"])
        rendered = stdout.getvalue()
        self.assertNotIn("must-not-escape", rendered)
        self.assertNotIn("c" * 64, rendered)

    def test_retained_secret_preflight_blocks_cluster_mutation(self) -> None:
        args = argparse.Namespace(
            cluster=staging.DEFAULT_CLUSTER,
            owner_id="owner",
            source_commit=None,
        )
        receipt = {
            "tools": {
                "kind": "kind",
                "kubectl": "kubectl",
                "flux": "flux",
                "helm": "helm",
            }
        }
        with tempfile.TemporaryDirectory(prefix="staging-cell-preflight-") as tmp_name:
            root = Path(tmp_name)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=receipt),
                mock.patch.object(staging, "retained_postgres_state_exists", return_value=True),
                mock.patch.object(
                    staging,
                    "load_or_create_secret_material",
                    side_effect=staging.StagingCellError("secret preflight failed"),
                ),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(staging, "require_clean_commit") as commit_mock,
                mock.patch.object(staging.reference, "create_kind_cluster") as create_mock,
            ):
                with self.assertRaisesRegex(staging.StagingCellError, "secret preflight failed"):
                    staging.command_up(args)
        commit_mock.assert_not_called()
        create_mock.assert_not_called()

    def test_existing_cluster_commit_check_is_receipt_bound_without_remote_lookup(self) -> None:
        head = "a" * 40

        def fake_output(argv: list[str], *, timeout: int | None = None) -> str:
            del timeout
            if argv[:3] == ["git", "status", "--porcelain"]:
                return ""
            if argv[:3] == ["git", "rev-parse", "HEAD"]:
                return head
            self.fail(f"unexpected command: {argv}")

        with mock.patch.object(staging, "output", side_effect=fake_output):
            observed = staging.require_clean_commit(
                None,
                expected_commit=head,
                require_public_main=False,
            )
        self.assertEqual(observed, head)

    def test_volume_visibility_is_verified_on_every_kind_node(self) -> None:
        nodes = ["node-a", "node-b", "node-c"]

        def fake_output(argv: list[str], *, timeout: int | None = None) -> str:
            del timeout
            path = argv[-1]
            if path.endswith("/postgres"):
                return "999:999:700"
            if path.endswith("/nats"):
                return "1000:1000:700"
            self.fail(f"unexpected command: {argv}")

        with (
            mock.patch.object(staging.reference, "kind_nodes", return_value=nodes),
            mock.patch.object(staging, "run") as run_mock,
            mock.patch.object(staging, "output", side_effect=fake_output) as output_mock,
        ):
            staging.prepare_volume_permissions("kind", staging.DEFAULT_CLUSTER)
        self.assertEqual(run_mock.call_count, 6)
        self.assertEqual(output_mock.call_count, 6)


if __name__ == "__main__":
    unittest.main()
