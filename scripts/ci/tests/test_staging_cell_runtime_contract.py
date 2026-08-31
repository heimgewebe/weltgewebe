from __future__ import annotations

import argparse
import io
import json
import subprocess
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

    def _tool_receipt(self) -> dict:
        return {
            "tools": {
                "kind": "kind",
                "kubectl": "kubectl",
                "flux": "flux",
                "helm": "helm",
            },
            "kubernetes": {"kind_node_image": "kind-node-image"},
            "artifacts": {},
            "lock_sha256": "f" * 64,
        }

    def _write_bound_receipt(self, root: Path, *, owner: str, commit: str) -> str:
        (root / "data/postgres").mkdir(parents=True, exist_ok=True)
        _, source_sha = staging.load_or_create_secret_material(root)
        staging.write_cell_receipt(
            root,
            {
                "schema_version": 1,
                "status": "infrastructure-ready-image-promotion-blocked",
                "cluster": staging.DEFAULT_CLUSTER,
                "owner_id": owner,
                "bootstrap_commit": commit,
                "external_secret": {
                    "source_sha256": source_sha,
                    "required_keys": ["database-url"],
                },
            },
        )
        return source_sha

    def test_persistent_volumes_are_static_prebound_and_fenced_to_data_worker(self) -> None:
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
            terms = pv["spec"]["nodeAffinity"]["required"]["nodeSelectorTerms"]
            self.assertEqual(
                terms,
                [
                    {
                        "matchExpressions": [
                            {
                                "key": "kubernetes.io/hostname",
                                "operator": "In",
                                "values": [staging.data_node_name(staging.DEFAULT_CLUSTER)],
                            }
                        ]
                    }
                ],
            )
            self.assertEqual(pvc["spec"].get("storageClassName"), "")
            self.assertEqual(pvc["spec"].get("volumeName"), volume)

    def test_network_policies_allow_only_staging_api_pods(self) -> None:
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
            peer = ingress[0]["from"][0]
            self.assertEqual(
                peer["namespaceSelector"]["matchLabels"],
                {"kubernetes.io/metadata.name": staging.APP_NAMESPACE},
            )
            self.assertEqual(
                peer["podSelector"]["matchLabels"],
                {"app.kubernetes.io/name": "weltgewebe-api"},
            )
            self.assertEqual(ingress[0]["ports"], [{"port": port, "protocol": "TCP"}])
        self.assertNotIn("allow-app-data-access", policies)

    def test_data_workloads_are_pinned_and_avoid_recursive_fs_group_churn(self) -> None:
        for relative in (
            "platform/clusters/staging/data/postgres.yaml",
            "platform/clusters/staging/data/nats.yaml",
        ):
            documents = self._documents(relative)
            deployment = next(
                document for document in documents if document.get("kind") == "Deployment"
            )
            pod_spec = deployment["spec"]["template"]["spec"]
            self.assertEqual(
                pod_spec["nodeSelector"],
                {"kubernetes.io/hostname": staging.data_node_name(staging.DEFAULT_CLUSTER)},
            )
            self.assertEqual(
                pod_spec["securityContext"]["fsGroupChangePolicy"], "OnRootMismatch"
            )
            self.assertEqual(deployment["spec"]["strategy"], {"type": "Recreate"})

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

    def test_kind_template_mounts_retained_data_on_exactly_one_worker(self) -> None:
        config = yaml.safe_load(
            (ROOT / "platform/clusters/staging/kind.yaml").read_text(encoding="utf-8")
        )
        nodes = config["nodes"]
        self.assertEqual([node["role"] for node in nodes], ["control-plane", "worker", "worker"])
        mounted = [
            (index, node, node.get("extraMounts", []))
            for index, node in enumerate(nodes)
            if node.get("extraMounts")
        ]
        self.assertEqual(len(mounted), 1)
        index, node, mounts = mounted[0]
        self.assertEqual(index, 1)
        self.assertEqual(node["role"], "worker")
        self.assertEqual(len(mounts), 1)
        self.assertEqual(mounts[0]["hostPath"], "__COMMONTHING_STAGING_DATA_ROOT__")
        self.assertEqual(mounts[0]["containerPath"], "/var/local/weltgewebe-staging")
        self.assertFalse(mounts[0]["readOnly"])

    def test_apply_yaml_emits_native_multi_document_stream(self) -> None:
        documents = [
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "one"}},
            {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "two"}},
        ]
        with mock.patch.object(staging, "run") as run_mock:
            staging.apply_yaml("kubectl", documents)
        body = run_mock.call_args.kwargs["input_text"]
        self.assertTrue(body.startswith("---\n"))
        self.assertEqual(list(yaml.safe_load_all(body)), documents)

    def test_public_parser_does_not_offer_state_root_override(self) -> None:
        parser = staging.parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["status", "--state-root", "/tmp/other"])

    def test_public_parser_does_not_offer_cluster_override(self) -> None:
        parser = staging.parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["status", "--cluster", "other"])
        parsed = parser.parse_args(["status"])
        self.assertEqual(parsed.cluster, staging.DEFAULT_CLUSTER)

    def test_public_status_keeps_diagnostics_without_secret_material(self) -> None:
        result = {
            "status": "degraded",
            "cluster": staging.DEFAULT_CLUSTER,
            "bootstrap_commit": "a" * 40,
            "source_revision": "main@sha1:" + "b" * 40,
            "source_matches_commit": False,
            "data_ready": "False",
            "data_revision": "main@sha1:" + "d" * 40,
            "data_matches_commit": False,
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
        self.assertFalse(public["data_matches_commit"])
        self.assertEqual(public["data_revision"], "main@sha1:" + "d" * 40)
        self.assertEqual(public["pvcs"]["nats-data"], "Pending")
        self.assertFalse(public["external_secret"]["runtime"])
        rendered = stdout.getvalue()
        self.assertNotIn("must-not-escape", rendered)
        self.assertNotIn("c" * 64, rendered)

    def test_public_down_output_preserves_actual_status(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            staging.emit_public_success(
                "down",
                {
                    "status": "cluster-absent-state-preserved",
                    "cluster": staging.DEFAULT_CLUSTER,
                },
            )
        public = json.loads(stdout.getvalue())
        self.assertEqual(public["status"], "cluster-absent-state-preserved")
        self.assertEqual(public["cluster"], staging.DEFAULT_CLUSTER)

    def test_retained_secret_preflight_blocks_cluster_mutation(self) -> None:
        args = argparse.Namespace(
            cluster=staging.DEFAULT_CLUSTER,
            owner_id="owner",
            source_commit=None,
        )
        receipt = self._tool_receipt()
        with tempfile.TemporaryDirectory(prefix="staging-cell-preflight-") as tmp_name:
            root = Path(tmp_name)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=receipt),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(staging, "retained_staging_data_exists", return_value=True),
                mock.patch.object(staging, "require_clean_commit") as commit_mock,
                mock.patch.object(staging.reference, "create_kind_cluster") as create_mock,
            ):
                with self.assertRaisesRegex(staging.StagingCellError, "without a bootstrap receipt"):
                    staging.command_up(args)
        commit_mock.assert_not_called()
        create_mock.assert_not_called()

    def test_invalid_owner_ids_fail_before_any_staging_write(self) -> None:
        for owner_id in ("team ops", "x" * 129):
            with self.subTest(owner_id=owner_id):
                args = argparse.Namespace(
                    cluster=staging.DEFAULT_CLUSTER,
                    owner_id=owner_id,
                    source_commit=None,
                )
                with (
                    mock.patch.object(staging, "state_root") as state_root_mock,
                    mock.patch.object(staging, "load_or_create_secret_material") as secret_mock,
                    mock.patch.object(staging, "write_cell_receipt") as receipt_mock,
                ):
                    with self.assertRaisesRegex(
                        staging.reference.ProofError, "stable owner id"
                    ):
                        staging.command_up(args)
                state_root_mock.assert_not_called()
                secret_mock.assert_not_called()
                receipt_mock.assert_not_called()

    def test_bootstrap_receipt_is_persisted_before_cluster_creation(self) -> None:
        args = argparse.Namespace(
            cluster=staging.DEFAULT_CLUSTER,
            owner_id="owner-a",
            source_commit=None,
        )
        commit = "a" * 40
        receipt = self._tool_receipt()
        with tempfile.TemporaryDirectory(prefix="staging-cell-bootstrap-receipt-") as tmp_name:
            root = Path(tmp_name)

            def fail_after_receipt(*call_args, **call_kwargs):
                del call_kwargs
                bound = staging.load_cell_receipt(root)
                self.assertEqual(bound["status"], "bootstrap-in-progress")
                self.assertEqual(bound["owner_id"], "owner-a")
                self.assertEqual(bound["bootstrap_commit"], commit)
                self.assertEqual(call_args[4], commit)
                self.assertEqual(call_args[5], "owner-a")
                raise RuntimeError("stop after ownership receipt proof")

            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=receipt),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(staging, "require_clean_commit", return_value=commit),
                mock.patch.object(
                    staging.reference,
                    "create_kind_cluster",
                    side_effect=fail_after_receipt,
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "ownership receipt proof"):
                    staging.command_up(args)

            self.assertTrue((root / "receipts/cell-bootstrap.json").is_file())
            self.assertTrue((root / "secrets/staging-runtime.json").is_file())

    def test_recreate_after_down_preserves_receipt_owner_and_commit_pin(self) -> None:
        owner = "owner-a"
        persisted_commit = "b" * 40
        args = argparse.Namespace(
            cluster=staging.DEFAULT_CLUSTER,
            owner_id=owner,
            source_commit=None,
        )
        receipt = self._tool_receipt()
        with tempfile.TemporaryDirectory(prefix="staging-cell-recreate-") as tmp_name:
            root = Path(tmp_name)
            source_sha = self._write_bound_receipt(
                root, owner=owner, commit=persisted_commit
            )
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=receipt),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(
                    staging,
                    "require_clean_commit",
                    return_value=persisted_commit,
                ) as commit_mock,
                mock.patch.object(staging.reference, "create_kind_cluster") as create_mock,
                mock.patch.object(staging, "prepare_volume_permissions"),
                mock.patch.object(staging.reference, "control_plane_address", return_value="127.0.0.1"),
                mock.patch.object(staging.reference, "install_platform_components"),
                mock.patch.object(staging, "run"),
                mock.patch.object(
                    staging,
                    "inject_external_secrets",
                    return_value={"source_sha256": source_sha, "required_keys": ["database-url"]},
                ),
                mock.patch.object(staging, "apply_yaml"),
                mock.patch.object(staging, "wait_data"),
                mock.patch.object(
                    staging,
                    "output",
                    return_value="node-a\nnode-b\nnode-c",
                ),
                mock.patch.object(
                    staging,
                    "image_promotion_state",
                    return_value={"status": "blocked"},
                ),
            ):
                result = staging.command_up(args)

            commit_mock.assert_called_once_with(
                None,
                expected_commit=persisted_commit,
                require_public_main=False,
            )
            create_args = create_mock.call_args.args
            self.assertEqual(create_args[4], persisted_commit)
            self.assertEqual(create_args[5], owner)
            self.assertEqual(result["bootstrap_commit"], persisted_commit)

    def test_recreate_after_down_rejects_different_owner_before_mutation(self) -> None:
        persisted_commit = "c" * 40
        args = argparse.Namespace(
            cluster=staging.DEFAULT_CLUSTER,
            owner_id="owner-b",
            source_commit=None,
        )
        with tempfile.TemporaryDirectory(prefix="staging-cell-owner-pin-") as tmp_name:
            root = Path(tmp_name)
            self._write_bound_receipt(root, owner="owner-a", commit=persisted_commit)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(staging, "require_clean_commit") as commit_mock,
                mock.patch.object(staging.reference, "create_kind_cluster") as create_mock,
            ):
                with self.assertRaisesRegex(staging.StagingCellError, "persisted cluster owner"):
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

    def test_status_degrades_when_external_secret_binding_is_invalid(self) -> None:
        owner = "owner-a"
        commit = "d" * 40
        args = argparse.Namespace(cluster=staging.DEFAULT_CLUSTER)
        with tempfile.TemporaryDirectory(prefix="staging-cell-status-secret-") as tmp_name:
            root = Path(tmp_name)
            self._write_bound_receipt(root, owner=owner, commit=commit)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(
                    staging.reference,
                    "clusters",
                    return_value=[staging.DEFAULT_CLUSTER],
                ),
                mock.patch.object(staging.reference, "require_owned_cluster"),
                mock.patch.object(
                    staging,
                    "output",
                    side_effect=[
                        f"main@sha1:{commit}",
                        "1|1|True",
                        f"1|1|True|main@sha1:{commit}",
                        "Bound",
                        "Bound",
                    ],
                ),
                mock.patch.object(
                    staging,
                    "verify_external_secret_binding",
                    side_effect=staging.StagingCellError("secret source missing"),
                ),
                mock.patch.object(
                    staging,
                    "image_promotion_state",
                    return_value={"status": "blocked"},
                ),
            ):
                result = staging.command_status(args)

        self.assertEqual(result["status"], "degraded")
        self.assertEqual(
            result["external_secret"],
            {"database": False, "runtime": False, "ready": False},
        )

    def test_status_degrades_when_injected_secret_is_missing(self) -> None:
        owner = "owner-a"
        commit = "d" * 40
        args = argparse.Namespace(cluster=staging.DEFAULT_CLUSTER)
        with tempfile.TemporaryDirectory(prefix="staging-cell-status-missing-secret-") as tmp_name:
            root = Path(tmp_name)
            self._write_bound_receipt(root, owner=owner, commit=commit)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(staging.reference, "clusters", return_value=[staging.DEFAULT_CLUSTER]),
                mock.patch.object(staging.reference, "require_owned_cluster"),
                mock.patch.object(
                    staging,
                    "output",
                    side_effect=[
                        f"main@sha1:{commit}",
                        "1|1|True",
                        f"1|1|True|main@sha1:{commit}",
                        "Bound",
                        "Bound",
                    ],
                ),
                mock.patch.object(
                    staging,
                    "verify_external_secret_binding",
                    side_effect=subprocess.CalledProcessError(
                        1, ["kubectl", "get", "secret"]
                    ),
                ),
                mock.patch.object(
                    staging, "image_promotion_state", return_value={"status": "blocked"}
                ),
            ):
                result = staging.command_status(args)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(
            result["external_secret"],
            {"database": False, "runtime": False, "ready": False},
        )

    def test_down_cleans_exactly_bound_marker_when_cluster_is_absent(self) -> None:
        owner = "owner-a"
        commit = "e" * 40
        args = argparse.Namespace(cluster=staging.DEFAULT_CLUSTER, owner_id=owner)
        with tempfile.TemporaryDirectory(prefix="staging-cell-down-absent-") as tmp_name:
            root = Path(tmp_name)
            self._write_bound_receipt(root, owner=owner, commit=commit)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(
                    staging.reference,
                    "delete_owned_cluster_if_present",
                    return_value=True,
                ) as delete_mock,
            ):
                result = staging.command_down(args)
        delete_mock.assert_called_once_with(
            "kind",
            staging.DEFAULT_CLUSTER,
            expected_commit=commit,
            expected_owner_id=owner,
        )
        self.assertEqual(result["status"], "cluster-absent-state-preserved")

    def test_down_fails_closed_for_wrong_owner_or_marker_binding(self) -> None:
        owner = "owner-a"
        commit = "e" * 40
        with tempfile.TemporaryDirectory(prefix="staging-cell-down-binding-") as tmp_name:
            root = Path(tmp_name)
            self._write_bound_receipt(root, owner=owner, commit=commit)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(
                    staging.reference, "delete_owned_cluster_if_present"
                ) as delete_mock,
            ):
                with self.assertRaisesRegex(
                    staging.StagingCellError, "persisted cluster owner"
                ):
                    staging.command_down(
                        argparse.Namespace(
                            cluster=staging.DEFAULT_CLUSTER, owner_id="owner-b"
                        )
                    )
            delete_mock.assert_not_called()

            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(
                    staging.reference,
                    "delete_owned_cluster_if_present",
                    side_effect=staging.reference.ProofError("marker binding mismatch"),
                ),
            ):
                with self.assertRaisesRegex(
                    staging.reference.ProofError, "marker binding mismatch"
                ):
                    staging.command_down(
                        argparse.Namespace(
                            cluster=staging.DEFAULT_CLUSTER, owner_id=owner
                        )
                    )
        self.assertFalse((root / "receipts/cell-down.json").exists())

    def test_lifecycle_lock_rejects_parallel_mutations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="staging-cell-lifecycle-lock-") as tmp_name:
            root = Path(tmp_name)
            with staging.lifecycle_lock(root):
                with self.assertRaisesRegex(
                    staging.StagingCellError, "lifecycle mutation is already in progress"
                ):
                    with staging.lifecycle_lock(root):
                        self.fail("parallel lifecycle lock unexpectedly acquired")
            with staging.lifecycle_lock(root):
                pass

    def test_status_degrades_when_flux_or_pvc_resources_are_missing(self) -> None:
        owner = "owner-a"
        commit = "f" * 40
        args = argparse.Namespace(cluster=staging.DEFAULT_CLUSTER)
        with tempfile.TemporaryDirectory(prefix="staging-cell-status-missing-resources-") as tmp_name:
            root = Path(tmp_name)
            self._write_bound_receipt(root, owner=owner, commit=commit)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(staging.reference, "clusters", return_value=[staging.DEFAULT_CLUSTER]),
                mock.patch.object(staging.reference, "require_owned_cluster"),
                mock.patch.object(staging, "output", side_effect=["", "", "", "", ""]) as output_mock,
                mock.patch.object(
                    staging,
                    "verify_external_secret_binding",
                    return_value={"database": True, "runtime": True, "ready": True},
                ),
                mock.patch.object(
                    staging, "image_promotion_state", return_value={"status": "blocked"}
                ),
            ):
                result = staging.command_status(args)
        self.assertEqual(result["status"], "degraded")
        self.assertEqual(result["source_revision"], "missing")
        self.assertEqual(result["data_ready"], "missing")
        self.assertEqual(
            result["pvcs"],
            {"postgres-data": "missing", "nats-data": "missing"},
        )
        for call in output_mock.call_args_list:
            self.assertIn("--ignore-not-found", call.args[0])

    def test_atomic_writes_fsync_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory(prefix="staging-cell-fsync-parent-") as tmp_name:
            root = Path(tmp_name)
            json_path = root / "receipt.json"
            text_path = root / "receipt.txt"
            with mock.patch.object(staging, "fsync_directory") as fsync_mock:
                staging.atomic_json(json_path, {"schema_version": 1})
                fsync_mock.assert_called_once_with(root)
            with mock.patch.object(staging, "fsync_directory") as fsync_mock:
                staging.atomic_text(text_path, "ok\n")
                fsync_mock.assert_called_once_with(root)

    def test_status_reports_not_bootstrapped_without_toolchain(self) -> None:
        args = argparse.Namespace(cluster=staging.DEFAULT_CLUSTER)
        with tempfile.TemporaryDirectory(prefix="staging-cell-not-bootstrapped-") as tmp_name:
            root = Path(tmp_name)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt") as tool_receipt_mock,
            ):
                result = staging.command_status(args)
        self.assertEqual(result["status"], "not-bootstrapped")
        tool_receipt_mock.assert_not_called()

    def test_status_requires_current_gitrepository_ready_condition(self) -> None:
        owner = "owner-a"
        commit = "7" * 40
        args = argparse.Namespace(cluster=staging.DEFAULT_CLUSTER)
        with tempfile.TemporaryDirectory(prefix="staging-cell-source-ready-") as tmp_name:
            root = Path(tmp_name)
            self._write_bound_receipt(root, owner=owner, commit=commit)
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(staging, "load_tool_receipt", return_value=self._tool_receipt()),
                mock.patch.object(staging.reference, "clusters", return_value=[staging.DEFAULT_CLUSTER]),
                mock.patch.object(staging.reference, "require_owned_cluster"),
                mock.patch.object(
                    staging,
                    "output",
                    side_effect=[
                        f"main@sha1:{commit}",
                        "3|3|False",
                        f"1|1|True|main@sha1:{commit}",
                        "Bound",
                        "Bound",
                    ],
                ),
                mock.patch.object(
                    staging,
                    "verify_external_secret_binding",
                    return_value={"database": True, "runtime": True, "ready": True},
                ),
                mock.patch.object(
                    staging, "image_promotion_state", return_value={"status": "blocked"}
                ),
            ):
                result = staging.command_status(args)
        self.assertEqual(result["status"], "degraded")
        self.assertTrue(result["source_matches_commit"])
        self.assertEqual(result["source_ready"], "False")

    def test_status_binds_data_kustomization_to_current_revision(self) -> None:
        owner = "owner-a"
        commit = "6" * 40
        other_commit = "8" * 40
        args = argparse.Namespace(cluster=staging.DEFAULT_CLUSTER)
        cases = (
            (
                "stale-generation",
                f"4|3|True|main@sha1:{commit}",
                "degraded",
                "stale",
                True,
            ),
            (
                "wrong-revision",
                f"4|4|True|main@sha1:{other_commit}",
                "degraded",
                "True",
                False,
            ),
            (
                "current-revision",
                f"4|4|True|main@sha1:{commit}",
                "ready",
                "True",
                True,
            ),
        )
        for name, data_health, expected_status, expected_ready, expected_match in cases:
            with self.subTest(name=name):
                with tempfile.TemporaryDirectory(
                    prefix=f"staging-cell-data-status-{name}-"
                ) as tmp_name:
                    root = Path(tmp_name)
                    self._write_bound_receipt(root, owner=owner, commit=commit)
                    with (
                        mock.patch.object(staging, "state_root", return_value=root),
                        mock.patch.object(staging, "configure_reference_paths"),
                        mock.patch.object(
                            staging,
                            "load_tool_receipt",
                            return_value=self._tool_receipt(),
                        ),
                        mock.patch.object(
                            staging.reference,
                            "clusters",
                            return_value=[staging.DEFAULT_CLUSTER],
                        ),
                        mock.patch.object(staging.reference, "require_owned_cluster"),
                        mock.patch.object(
                            staging,
                            "output",
                            side_effect=[
                                f"main@sha1:{commit}",
                                "1|1|True",
                                data_health,
                                "Bound",
                                "Bound",
                            ],
                        ),
                        mock.patch.object(
                            staging,
                            "verify_external_secret_binding",
                            return_value={
                                "database": True,
                                "runtime": True,
                                "ready": True,
                            },
                        ),
                        mock.patch.object(
                            staging,
                            "image_promotion_state",
                            return_value={"status": "blocked"},
                        ),
                    ):
                        result = staging.command_status(args)
                self.assertEqual(result["status"], expected_status)
                self.assertEqual(result["data_ready"], expected_ready)
                self.assertEqual(result["data_matches_commit"], expected_match)
                self.assertEqual(
                    result["data_revision"], data_health.rsplit("|", 1)[-1]
                )

    def test_wait_data_checks_pvcs_before_flux_health_without_rollout_duplication(self) -> None:
        events: list[str] = []

        def wait_condition(_kubectl: str, _namespace: str, resource: str, _condition: str) -> None:
            events.append(resource)

        with (
            mock.patch.object(staging.reference, "wait_condition", side_effect=wait_condition),
            mock.patch.object(
                staging,
                "wait_pvcs_bound",
                side_effect=lambda _kubectl: events.append("pvcs-bound"),
            ),
            mock.patch.object(
                staging.reference,
                "wait_rollout",
                side_effect=AssertionError("redundant rollout wait must not run"),
            ),
        ):
            staging.wait_data("kubectl")
        self.assertEqual(
            events,
            [
                f"gitrepository/{staging.SOURCE_NAME}",
                "pvcs-bound",
                f"kustomization/{staging.DATA_KUSTOMIZATION}",
            ],
        )

    def test_volume_permissions_verify_single_mount_and_do_not_touch_healthy_data(self) -> None:
        nodes = [
            f"{staging.DEFAULT_CLUSTER}-control-plane",
            staging.data_node_name(staging.DEFAULT_CLUSTER),
            f"{staging.DEFAULT_CLUSTER}-worker2",
        ]
        with tempfile.TemporaryDirectory(prefix="staging-cell-volume-proof-") as tmp_name:
            root = Path(tmp_name)
            (root / "data").mkdir()
            expected_source = str((root / "data").resolve())

            def fake_output(argv: list[str], *, timeout: int | None = None) -> str:
                del timeout
                if argv[:2] == ["docker", "inspect"]:
                    node = argv[-1]
                    mounts = (
                        [
                            {
                                "Destination": "/var/local/weltgewebe-staging",
                                "Source": expected_source,
                                "RW": True,
                            }
                        ]
                        if node == staging.data_node_name(staging.DEFAULT_CLUSTER)
                        else []
                    )
                    return json.dumps(mounts)
                if "stat" in argv:
                    volume_path = argv[-1]
                    if volume_path.endswith("/postgres"):
                        return "999:999:770"
                    if volume_path.endswith("/nats"):
                        return "1000:1000:2770"
                self.fail(f"unexpected command: {argv}")

            with (
                mock.patch.object(staging.reference, "kind_nodes", return_value=nodes),
                mock.patch.object(staging, "run") as run_mock,
                mock.patch.object(staging, "output", side_effect=fake_output) as output_mock,
            ):
                staging.prepare_volume_permissions("kind", staging.DEFAULT_CLUSTER, root)

        self.assertEqual(run_mock.call_count, 2)
        self.assertEqual(output_mock.call_count, 5)
        flattened = [str(item) for call in run_mock.call_args_list for item in call.args[0]]
        self.assertNotIn("chown", flattened)
        self.assertNotIn("chmod", flattened)

    def test_volume_permission_initialization_never_uses_recursive_chown(self) -> None:
        nodes = [
            f"{staging.DEFAULT_CLUSTER}-control-plane",
            staging.data_node_name(staging.DEFAULT_CLUSTER),
            f"{staging.DEFAULT_CLUSTER}-worker2",
        ]
        with tempfile.TemporaryDirectory(prefix="staging-cell-volume-init-") as tmp_name:
            root = Path(tmp_name)
            (root / "data").mkdir()
            expected_source = str((root / "data").resolve())
            stat_calls = {"postgres": 0, "nats": 0}

            def fake_output(argv: list[str], *, timeout: int | None = None) -> str:
                del timeout
                if argv[:2] == ["docker", "inspect"]:
                    node = argv[-1]
                    mounts = (
                        [
                            {
                                "Destination": "/var/local/weltgewebe-staging",
                                "Source": expected_source,
                                "RW": True,
                            }
                        ]
                        if node == staging.data_node_name(staging.DEFAULT_CLUSTER)
                        else []
                    )
                    return json.dumps(mounts)
                if "find" in argv:
                    return ""
                if "stat" in argv:
                    volume = "postgres" if argv[-1].endswith("/postgres") else "nats"
                    stat_calls[volume] += 1
                    if stat_calls[volume] == 1:
                        return "0:0:755"
                    return "999:999:700" if volume == "postgres" else "1000:1000:700"
                self.fail(f"unexpected command: {argv}")

            with (
                mock.patch.object(staging.reference, "kind_nodes", return_value=nodes),
                mock.patch.object(staging, "run") as run_mock,
                mock.patch.object(staging, "output", side_effect=fake_output),
            ):
                staging.prepare_volume_permissions("kind", staging.DEFAULT_CLUSTER, root)

        commands = [call.args[0] for call in run_mock.call_args_list]
        chowns = [argv for argv in commands if "chown" in argv]
        self.assertEqual(len(chowns), 2)
        self.assertTrue(all("-R" not in argv for argv in chowns))
        self.assertEqual(len([argv for argv in commands if "chmod" in argv]), 2)

    def test_nats_only_retained_state_blocks_unbound_recreation(self) -> None:
        args = argparse.Namespace(
            cluster=staging.DEFAULT_CLUSTER,
            owner_id="owner",
            source_commit=None,
        )
        with tempfile.TemporaryDirectory(prefix="staging-cell-nats-retained-") as tmp_name:
            root = Path(tmp_name)
            nats = root / "data/nats"
            nats.mkdir(parents=True)
            (nats / "jetstream.marker").write_text("retained", encoding="utf-8")
            with (
                mock.patch.object(staging, "state_root", return_value=root),
                mock.patch.object(staging, "configure_reference_paths"),
                mock.patch.object(
                    staging, "load_tool_receipt", return_value=self._tool_receipt()
                ),
                mock.patch.object(staging.reference, "clusters", return_value=[]),
                mock.patch.object(staging, "require_clean_commit") as commit_mock,
                mock.patch.object(
                    staging.reference, "create_kind_cluster"
                ) as create_mock,
            ):
                with self.assertRaisesRegex(
                    staging.StagingCellError, "without a bootstrap receipt"
                ):
                    staging.command_up(args)
        commit_mock.assert_not_called()
        create_mock.assert_not_called()

    def test_retained_postgres_permission_error_is_preservation_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="staging-cell-retained-permission-") as tmp_name:
            root = Path(tmp_name)
            pgdata = root / "data/postgres"
            pgdata.mkdir(parents=True)
            with mock.patch.object(staging.os, "scandir", side_effect=PermissionError):
                self.assertTrue(staging.retained_postgres_state_exists(root))


if __name__ == "__main__":
    unittest.main()
