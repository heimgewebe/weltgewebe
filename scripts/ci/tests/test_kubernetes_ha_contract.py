from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
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

    def test_all_ha_images_are_digest_bound(self) -> None:
        lock = json.loads((ROOT / "platform/toolchain.lock.json").read_text())
        self.assertEqual(
            set(lock["images"]),
            {
                "cloudnative_pg_operator",
                "cloudnative_pg_postgresql",
                "cert_manager_controller",
                "cert_manager_cainjector",
                "cert_manager_webhook",
                "barman_cloud_plugin",
                "barman_cloud_sidecar",
                "nats",
                "nats_box",
                "seaweedfs",
            },
        )
        for name, image in lock["images"].items():
            self.assertRegex(image, r"@sha256:[0-9a-f]{64}$", name)

    def test_plugin_runtime_images_match_the_digest_lock(self) -> None:
        lock = json.loads((ROOT / "platform/toolchain.lock.json").read_text())
        expected = {
            "cert_manager_controller": self.ha.CERT_MANAGER_IMAGES[
                "quay.io/jetstack/cert-manager-controller:v1.21.0"
            ],
            "cert_manager_cainjector": self.ha.CERT_MANAGER_IMAGES[
                "quay.io/jetstack/cert-manager-cainjector:v1.21.0"
            ],
            "cert_manager_webhook": self.ha.CERT_MANAGER_IMAGES[
                "quay.io/jetstack/cert-manager-webhook:v1.21.0"
            ],
            "barman_cloud_plugin": self.ha.BARMAN_CLOUD_PLUGIN_IMAGE,
            "barman_cloud_sidecar": self.ha.BARMAN_CLOUD_SIDECAR_IMAGE,
        }
        for name, image in expected.items():
            self.assertEqual(lock["images"][name], image, name)
        self.assertEqual(lock["artifacts"]["cert_manager"]["version"], "1.21.0")
        self.assertEqual(lock["artifacts"]["barman_cloud_plugin"]["version"], "0.13.0")

    def test_cnpg_plugin_tool_matches_operator_version(self) -> None:
        lock = json.loads((ROOT / "platform/toolchain.lock.json").read_text())
        self.assertEqual(
            lock["tools"]["kubectl_cnpg"],
            {
                "version": "1.30.0",
                "url": "https://github.com/cloudnative-pg/cloudnative-pg/releases/download/v1.30.0/kubectl-cnpg_1.30.0_linux_x86_64.tar.gz",
                "sha256": "33784dc3b61edb0ddb1a68db6ef045bd32daace5db2ec1f0a02e0e8185eef7eb",
                "format": "tar.gz",
                "binary": "kubectl-cnpg",
            },
        )
        self.assertEqual(
            lock["tools"]["kubectl_cnpg"]["version"],
            lock["artifacts"]["cloudnative_pg_operator"]["version"],
        )

    def test_ha_migration_reads_runtime_database_url_from_secret(self) -> None:
        job = next(
            self.validator._documents(
                ROOT / "platform/apps/weltgewebe/migration/ha/job.yaml"
            )
        )
        container = job["spec"]["template"]["spec"]["containers"][0]
        database = next(item for item in container["env"] if item["name"] == "DATABASE_URL")
        self.assertEqual(
            database["valueFrom"].get("secretKeyRef"),
            {"name": "weltgewebe-ha-runtime", "key": "database-url"},
        )
        self.assertNotIn("configMapKeyRef", database["valueFrom"])

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
            {
                "barmanObjectName": "weltgewebe-ha-backup",
                "serverName": "postgres-ha",
            },
        )
        self.assertEqual(
            spec["plugins"],
            [
                {
                    "name": "barman-cloud.cloudnative-pg.io",
                    "isWALArchiver": True,
                    "parameters": {
                        "barmanObjectName": "weltgewebe-ha-backup"
                    },
                }
            ],
        )

    def test_barman_plugin_contract_replaces_native_backup(self) -> None:
        postgres = next(
            self.validator._documents(
                ROOT / "platform/infrastructure/ha-data/postgres.yaml"
            )
        )
        spec = postgres["spec"]
        self.assertNotIn("backup", spec)
        self.assertEqual(
            spec["plugins"],
            [
                {
                    "name": "barman-cloud.cloudnative-pg.io",
                    "isWALArchiver": True,
                    "parameters": {
                        "barmanObjectName": "weltgewebe-ha-backup"
                    },
                }
            ],
        )
        store = next(
            self.validator._documents(
                ROOT / "platform/infrastructure/ha-data/barman-object-store.yaml"
            )
        )
        self.assertEqual(store["apiVersion"], "barmancloud.cnpg.io/v1")
        self.assertEqual(store["kind"], "ObjectStore")
        self.assertEqual(store["spec"]["retentionPolicy"], "7d")
        source = (ROOT / "scripts/platform/ha_reference.py").read_text()
        self.assertIn('"method": "plugin"', source)
        self.assertIn('"target": "prefer-standby"', source)
        self.assertIn('"name": "barman-cloud.cloudnative-pg.io"', source)

    def test_restore_direct_manifests_are_explicitly_namespaced(self) -> None:
        for relative in (
            "platform/infrastructure/ha-data/object-store.yaml",
            "platform/infrastructure/ha-data/barman-object-store.yaml",
            "platform/infrastructure/ha-data/postgres-image-catalog.yaml",
        ):
            document = next(self.validator._documents(ROOT / relative))
            self.assertEqual(
                document["metadata"].get("namespace"),
                "weltgewebe-data",
                relative,
            )

    def test_ha_workflow_checks_out_the_immutable_pr_head(self) -> None:
        workflow = (ROOT / ".github/workflows/kubernetes-platform.yml").read_text()
        expected = (
            "ref: ${{ github.event_name == 'pull_request' && "
            "github.event.pull_request.head.sha || github.sha }}"
        )
        self.assertEqual(workflow.count(expected), 3)

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
        with mock.patch.object(self.ha.subprocess, "run", inspect), mock.patch.object(
            self.ha.ref, "output", return_value="foreign-commit"
        ):
            with self.assertRaisesRegex(self.ha.ref.ProofError, "foreign"):
                self.ha.delete_external_object_store("proof", "expected-commit")

    def test_external_object_store_start_cleans_partial_owned_resources(self) -> None:
        absent = mock.Mock(returncode=1)
        with mock.patch.object(
            self.ha.subprocess, "run", side_effect=[absent, absent]
        ), mock.patch.object(self.ha.ref, "run"), mock.patch.object(
            self.ha, "run_with_environment", side_effect=self.ha.ref.ProofError("container start failed")
        ), mock.patch.object(self.ha, "delete_external_object_store") as cleanup:
            with self.assertRaisesRegex(self.ha.ref.ProofError, "container start failed"):
                self.ha.start_external_object_store("proof", "a" * 40, "secret")
        cleanup.assert_called_once_with("proof", "a" * 40)

    def test_kind_cluster_creation_is_transactional(self) -> None:
        with mock.patch.object(self.ha.ref, "assert_available_cluster_name"), mock.patch.object(
            self.ha.ref, "write_marker"
        ) as marker, mock.patch.object(
            self.ha.ref, "run", side_effect=self.ha.ref.ProofError("kind failed")
        ), mock.patch.object(self.ha.ref, "delete_owned_cluster") as cleanup:
            with self.assertRaisesRegex(self.ha.ref.ProofError, "kind failed"):
                self.ha.create_kind_cluster("kind", "proof", "node-image", "cluster.yaml", "b" * 40)
        marker.assert_called_once_with("proof", "b" * 40)
        cleanup.assert_called_once_with("kind", "proof")

    def test_digest_locked_manifest_replaces_each_release_image_once(self) -> None:
        tagged = {
            "registry.example/controller:v1": "registry.example/controller@sha256:" + "a" * 64,
            "registry.example/webhook:v1": "registry.example/webhook@sha256:" + "b" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "release.yaml"
            artifact.write_text(
                "".join(f"---\nimage: {image}\n" for image in tagged),
                encoding="utf-8",
            )
            with mock.patch.object(self.ha.ref, "run") as run:
                self.ha.apply_digest_locked_manifest("kubectl", str(artifact), tagged)
        argv = run.call_args.args[0]
        payload = run.call_args.kwargs["input_text"]
        self.assertIn("--server-side", argv)
        self.assertIn("--force-conflicts", argv)
        self.assertIn("--field-manager=weltgewebe-ha-proof", argv)
        for source, digest in tagged.items():
            self.assertNotIn(source, payload)
            self.assertEqual(payload.count(digest), 1)

    def test_cert_manager_install_waits_and_verifies_digest_images(self) -> None:
        expected = list(self.ha.CERT_MANAGER_IMAGES.values())
        with mock.patch.object(
            self.ha, "apply_digest_locked_manifest"
        ) as apply_manifest, mock.patch.object(
            self.ha.ref, "run"
        ) as run, mock.patch.object(
            self.ha.ref, "wait_rollout"
        ) as wait_rollout, mock.patch.object(
            self.ha, "wait_until"
        ) as wait_until, mock.patch.object(
            self.ha.ref, "output", side_effect=expected
        ):
            self.ha.install_cert_manager("kubectl", "cert-manager.yaml")
        apply_manifest.assert_called_once_with(
            "kubectl", "cert-manager.yaml", self.ha.CERT_MANAGER_IMAGES
        )
        self.assertIn("crd/certificates.cert-manager.io", run.call_args.args[0])
        self.assertEqual(wait_rollout.call_count, 3)
        wait_until.assert_called_once()

    def test_barman_manifest_pins_operator_and_sidecar_images(self) -> None:
        sidecar_tag = (
            "ghcr.io/cloudnative-pg/plugin-barman-cloud-sidecar:v0.13.0"
        )
        encoded = self.ha.base64.b64encode(sidecar_tag.encode()).decode()
        source = (
            "apiVersion: v1\nkind: Secret\nmetadata:\n  name: sidecar\n"
            f'data:\n  SIDECAR_IMAGE: "{encoded}"\n---\n'
            "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n"
            "  name: barman-cloud\n  namespace: cnpg-system\nspec:\n"
            "  replicas: 1\n  strategy:\n    type: Recreate\n  template:\n"
            "    spec:\n      containers:\n        - name: controller\n"
            "          image: ghcr.io/cloudnative-pg/plugin-barman-cloud:v0.13.0\n"
        )
        rendered = self.ha.render_barman_cloud_manifest(source)
        documents = list(self.ha.yaml.safe_load_all(rendered))
        secret = next(item for item in documents if item.get("kind") == "Secret")
        deployment = next(
            item for item in documents if item.get("kind") == "Deployment"
        )
        self.assertEqual(
            self.ha.base64.b64decode(secret["data"]["SIDECAR_IMAGE"]).decode(),
            self.ha.BARMAN_CLOUD_SIDECAR_IMAGE,
        )
        self.assertEqual(
            deployment["spec"]["template"]["spec"]["containers"][0]["image"],
            self.ha.BARMAN_CLOUD_PLUGIN_IMAGE,
        )
        self.assertEqual(deployment["spec"]["replicas"], 3)
        self.assertEqual(deployment["spec"]["strategy"], {"type": "Recreate"})
        required = deployment["spec"]["template"]["spec"]["affinity"][
            "podAntiAffinity"
        ]["requiredDuringSchedulingIgnoredDuringExecution"]
        self.assertEqual(
            required,
            [
                {
                    "labelSelector": {"matchLabels": {"app": "barman-cloud"}},
                    "topologyKey": "kubernetes.io/hostname",
                }
            ],
        )
        self.assertFalse(
            any(item.get("kind") == "PodDisruptionBudget" for item in documents)
        )

    def barman_plugin_pod_payload(self, leader_index: int = 1) -> str:
        return json.dumps(
            {
                "items": [
                    {
                        "metadata": {"name": f"barman-cloud-{index}"},
                        "spec": {
                            "nodeName": f"worker-{index}",
                            "containers": [
                                {
                                    "name": "barman-cloud",
                                    "image": self.ha.BARMAN_CLOUD_PLUGIN_IMAGE,
                                }
                            ],
                        },
                        "status": {
                            "phase": "Running",
                            "containerStatuses": [
                                {
                                    "name": "barman-cloud",
                                    "ready": index == leader_index,
                                    "state": {
                                        "running": {
                                            "startedAt": "2026-07-18T11:32:39Z"
                                        }
                                    },
                                }
                            ],
                            "conditions": [
                                {
                                    "type": "Ready",
                                    "status": "True"
                                    if index == leader_index
                                    else "False",
                                }
                            ],
                        },
                    }
                    for index in range(1, 4)
                ]
            }
        )

    @staticmethod
    def barman_plugin_endpoint_payload(*indexes: int) -> str:
        return json.dumps(
            {
                "subsets": [
                    {
                        "addresses": [
                            {
                                "ip": f"10.0.0.{index}",
                                "targetRef": {"name": f"barman-cloud-{index}"},
                            }
                            for index in indexes
                        ]
                    }
                ]
            }
        )

    def test_barman_plugin_state_models_one_elected_leader(self) -> None:
        with mock.patch.object(
            self.ha.ref,
            "output",
            side_effect=[
                self.barman_plugin_pod_payload(2),
                self.barman_plugin_endpoint_payload(2),
            ],
        ):
            state = self.ha.barman_plugin_state(
                "kubectl", require_three_nodes=True
            )
        self.assertEqual(state["nodes"], ["worker-1", "worker-2", "worker-3"])
        self.assertEqual(
            state["leader"], {"pod": "barman-cloud-2", "node": "worker-2"}
        )

    def test_barman_plugin_state_ignores_stale_container_ready_after_node_loss(self) -> None:
        pods = json.loads(self.barman_plugin_pod_payload(2))
        old_leader = pods["items"][0]
        old_leader["status"]["containerStatuses"][0]["ready"] = True
        old_leader["status"]["conditions"] = [
            {"type": "Ready", "status": "False"}
        ]
        with mock.patch.object(
            self.ha.ref,
            "output",
            side_effect=[
                json.dumps(pods),
                self.barman_plugin_endpoint_payload(2),
            ],
        ):
            state = self.ha.barman_plugin_state(
                "kubectl", require_three_nodes=False
            )
        self.assertEqual(
            state["leader"], {"pod": "barman-cloud-2", "node": "worker-2"}
        )

    def test_barman_plugin_install_waits_and_verifies_digest_images(self) -> None:
        secret_payload = json.dumps(
            {
                "items": [
                    {
                        "data": {
                            "SIDECAR_IMAGE": self.ha.base64.b64encode(
                                self.ha.BARMAN_CLOUD_SIDECAR_IMAGE.encode()
                            ).decode()
                        }
                    }
                ]
            }
        )
        state = {
            "nodes": ["worker-1", "worker-2", "worker-3"],
            "pods": {
                "barman-cloud-1": "worker-1",
                "barman-cloud-2": "worker-2",
                "barman-cloud-3": "worker-3",
            },
            "leader": {"pod": "barman-cloud-1", "node": "worker-1"},
        }
        with mock.patch.object(
            self.ha, "apply_barman_cloud_manifest"
        ) as apply_manifest, mock.patch.object(
            self.ha.ref, "run"
        ) as run, mock.patch.object(
            self.ha.ref, "wait_condition"
        ) as wait_condition, mock.patch.object(
            self.ha, "verify_barman_plugin_ha", return_value=state
        ) as verify_ha, mock.patch.object(
            self.ha.ref,
            "output",
            side_effect=[secret_payload, self.ha.BARMAN_CLOUD_PLUGIN_IMAGE],
        ):
            observed = self.ha.install_barman_cloud_plugin(
                "kubectl", "barman.yaml"
            )
        apply_manifest.assert_called_once_with("kubectl", "barman.yaml")
        self.assertIn("crd/objectstores.barmancloud.cnpg.io", run.call_args.args[0])
        self.assertEqual(wait_condition.call_count, 2)
        verify_ha.assert_called_once_with("kubectl")
        self.assertEqual(observed, state)

    def test_barman_plugin_state_rejects_multiple_service_leaders(self) -> None:
        with mock.patch.object(
            self.ha.ref,
            "output",
            side_effect=[
                self.barman_plugin_pod_payload(1),
                self.barman_plugin_endpoint_payload(1, 2),
            ],
        ):
            with self.assertRaisesRegex(
                self.ha.ref.ProofError, "exactly its elected ready leader"
            ):
                self.ha.barman_plugin_state(
                    "kubectl", require_three_nodes=True
                )

    def test_barman_plugin_backup_proves_completed_plugin_rpc(self) -> None:
        completed = {
            "status": {
                "phase": "completed",
                "method": "plugin",
                "instanceID": {"podName": "postgres-ha-2"},
            }
        }
        with mock.patch.object(self.ha.ref, "apply_yaml") as apply_yaml, mock.patch.object(
            self.ha, "wait_backup_complete", return_value=completed
        ) as wait_backup:
            result = self.ha.prove_barman_plugin_backup(
                "kubectl", "postgres-ha", "probe-backup"
            )
        document = apply_yaml.call_args.args[1]
        self.assertEqual(document["spec"]["method"], "plugin")
        self.assertEqual(document["spec"]["target"], "primary")
        self.assertEqual(
            document["spec"]["pluginConfiguration"]["name"],
            "barman-cloud.cloudnative-pg.io",
        )
        wait_backup.assert_called_once_with("kubectl", "probe-backup")
        self.assertEqual(
            result,
            {
                "name": "probe-backup",
                "phase": "completed",
                "method": "plugin",
                "pod": "postgres-ha-2",
            },
        )

    def test_postgres_primary_alignment_promotes_to_existing_barman_leader(self) -> None:
        plugin_state = {
            "nodes": ["worker-1", "worker-2", "worker-3"],
            "pods": {
                "barman-cloud-1": "worker-1",
                "barman-cloud-2": "worker-2",
                "barman-cloud-3": "worker-3",
            },
            "leader": {"pod": "barman-cloud-2", "node": "worker-2"},
        }
        topology = {
            "postgres-ha-1": {"node": "worker-1", "zone": "zone-a"},
            "postgres-ha-2": {"node": "worker-2", "zone": "zone-b"},
            "postgres-ha-3": {"node": "worker-3", "zone": "zone-c"},
        }
        communication = {
            "name": "probe-backup",
            "phase": "completed",
            "method": "plugin",
            "pod": "postgres-ha-2",
        }
        with mock.patch.object(
            self.ha, "verify_barman_plugin_ha", side_effect=[plugin_state, plugin_state]
        ), mock.patch.object(
            self.ha, "current_primary", side_effect=["postgres-ha-1", "postgres-ha-2"]
        ), mock.patch.object(
            self.ha, "wait_until", return_value="postgres-ha-2"
        ) as wait_until, mock.patch.object(
            self.ha, "wait_cluster_ready"
        ) as wait_ready, mock.patch.object(
            self.ha, "prove_barman_plugin_backup", return_value=communication
        ) as prove_backup, mock.patch.object(self.ha.ref, "run") as run:
            result = self.ha.align_postgres_primary_with_barman_leader(
                "kubectl-cnpg",
                "kubectl",
                "postgres-ha",
                topology,
                "probe-backup",
            )
        run.assert_called_once_with(
            [
                "kubectl-cnpg",
                "--namespace",
                "weltgewebe-data",
                "promote",
                "postgres-ha",
                "postgres-ha-2",
            ],
            timeout=60,
        )
        self.assertNotIn("delete", run.call_args.args[0])
        wait_until.assert_called_once()
        wait_ready.assert_called_once_with("kubectl", "postgres-ha", "10m")
        prove_backup.assert_called_once_with(
            "kubectl", "postgres-ha", "probe-backup"
        )
        self.assertEqual(result["target_node"], "worker-2")
        self.assertEqual(result["postgres_primary_before"], "postgres-ha-1")
        self.assertEqual(result["postgres_primary_aligned"], "postgres-ha-2")
        self.assertEqual(result["communication"], communication)

    def test_barman_plugin_leader_after_node_loss_must_move(self) -> None:
        surviving = {
            "nodes": ["worker-1", "worker-2"],
            "pods": {
                "barman-cloud-1": "worker-1",
                "barman-cloud-2": "worker-2",
            },
            "leader": {"pod": "barman-cloud-2", "node": "worker-2"},
        }
        with mock.patch.object(
            self.ha, "barman_plugin_state", return_value=surviving
        ):
            leader = self.ha.wait_barman_plugin_leader_after_node_loss(
                "kubectl", "worker-3"
            )
        self.assertEqual(leader, surviving["leader"])

    def test_barman_instance_sidecars_are_running_ready_and_digest_bound(self) -> None:
        digest = self.ha.BARMAN_CLOUD_SIDECAR_IMAGE.rsplit("@", 1)[1]

        def pod(name: str) -> dict[str, object]:
            return {
                "metadata": {"name": name},
                "spec": {
                    "initContainers": [
                        {
                            "name": "plugin-barman-cloud",
                            "image": self.ha.BARMAN_CLOUD_SIDECAR_IMAGE,
                        }
                    ],
                    "containers": [],
                },
                "status": {
                    "initContainerStatuses": [
                        {
                            "name": "plugin-barman-cloud",
                            "imageID": f"ghcr.io/cloudnative-pg/sidecar@{digest}",
                            "ready": True,
                            "state": {
                                "running": {"startedAt": "2026-07-18T08:00:00Z"}
                            },
                        }
                    ]
                },
            }

        with mock.patch.object(
            self.ha.ref,
            "output",
            return_value=json.dumps(
                {"items": [pod("postgres-1"), pod("postgres-2"), pod("postgres-3")]}
            ),
        ):
            observed = self.ha.verify_barman_sidecar_images(
                "kubectl", "postgres-ha"
            )
        self.assertEqual(sorted(observed), ["postgres-1", "postgres-2", "postgres-3"])
        self.assertTrue(all(item["ready"] is True for item in observed.values()))

    def test_barman_instance_sidecar_validation_fails_closed_when_not_ready(self) -> None:
        payload = {
            "items": [
                {
                    "metadata": {"name": "postgres-1"},
                    "spec": {
                        "initContainers": [
                            {
                                "name": "plugin-barman-cloud",
                                "image": self.ha.BARMAN_CLOUD_SIDECAR_IMAGE,
                            }
                        ]
                    },
                    "status": {
                        "initContainerStatuses": [
                            {
                                "name": "plugin-barman-cloud",
                                "imageID": self.ha.BARMAN_CLOUD_SIDECAR_IMAGE,
                                "ready": False,
                                "state": {"waiting": {"reason": "Starting"}},
                            }
                        ]
                    },
                }
            ]
        }
        with mock.patch.object(
            self.ha.ref, "output", return_value=json.dumps(payload)
        ):
            with self.assertRaisesRegex(self.ha.ref.ProofError, "not running and ready"):
                self.ha.verify_barman_sidecar_images("kubectl", "postgres-ha")

    def cnpg_release_fixture(self) -> str:
        tagged = "ghcr.io/cloudnative-pg/cloudnative-pg:1.30.0"
        return f"""---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cnpg-controller-manager
  namespace: cnpg-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: cloudnative-pg
  template:
    metadata:
      labels:
        app.kubernetes.io/name: cloudnative-pg
    spec:
      containers:
        - name: manager
          image: {tagged}
---
apiVersion: batch/v1
kind: Job
metadata:
  name: cnpg-bootstrap
spec:
  template:
    spec:
      containers:
        - name: bootstrap
          image: {tagged}
      restartPolicy: Never
"""

    def test_cnpg_manifest_is_ha_before_first_apply(self) -> None:
        rendered = self.ha.render_cnpg_manifest(self.cnpg_release_fixture())
        documents = list(self.ha.yaml.safe_load_all(rendered))
        deployment = next(
            item for item in documents if item.get("kind") == "Deployment"
        )
        spec = deployment["spec"]
        self.assertEqual(spec["replicas"], 3)
        self.assertEqual(spec["strategy"]["rollingUpdate"]["maxSurge"], 0)
        self.assertEqual(spec["strategy"]["rollingUpdate"]["maxUnavailable"], 1)
        required = spec["template"]["spec"]["affinity"]["podAntiAffinity"][
            "requiredDuringSchedulingIgnoredDuringExecution"
        ]
        self.assertEqual(
            required,
            [
                {
                    "labelSelector": {"matchLabels": {"app.kubernetes.io/name": "cloudnative-pg"}},
                    "topologyKey": "kubernetes.io/hostname",
                }
            ],
        )
        self.assertNotIn(
            "ghcr.io/cloudnative-pg/cloudnative-pg:1.30.0", rendered
        )
        self.assertEqual(rendered.count(self.ha.CNPG_OPERATOR_IMAGE), 2)

    def test_cnpg_release_uses_server_side_apply(self) -> None:
        artifact = ROOT / ".cache/test-cnpg-release.yaml"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(self.cnpg_release_fixture())
        try:
            with mock.patch.object(self.ha.ref, "run") as run, mock.patch.object(
                self.ha,
                "verify_cnpg_operator_ha",
                return_value=["node-a", "node-b", "node-c"],
            ) as verify_ha, mock.patch.object(
                self.ha, "wait_until"
            ), mock.patch.object(
                self.ha.ref, "output", return_value=self.ha.CNPG_OPERATOR_IMAGE
            ):
                observed_nodes = self.ha.install_cnpg("kubectl", str(artifact))
            verify_ha.assert_called_once_with("kubectl")
            self.assertEqual(observed_nodes, ["node-a", "node-b", "node-c"])
            apply_argv = run.call_args_list[0].args[0]
            self.assertIn("--server-side", apply_argv)
            self.assertIn("--force-conflicts", apply_argv)
            self.assertIn("--field-manager=weltgewebe-ha-proof", apply_argv)
            payload = run.call_args_list[0].kwargs["input_text"]
            deployment = next(
                item
                for item in self.ha.yaml.safe_load_all(payload)
                if item.get("kind") == "Deployment"
            )
            self.assertEqual(deployment["spec"]["replicas"], 3)
        finally:
            artifact.unlink(missing_ok=True)

    def test_cnpg_operator_ha_requires_three_available_nodes(self) -> None:
        pods = json.dumps(
            {
                "items": [
                    {
                        "spec": {"nodeName": "node-a"},
                        "status": {"phase": "Running"},
                    },
                    {
                        "spec": {"nodeName": "node-b"},
                        "status": {"phase": "Running"},
                    },
                    {
                        "spec": {"nodeName": "node-c"},
                        "status": {"phase": "Running"},
                    },
                ]
            }
        )
        with mock.patch.object(
            self.ha.ref, "wait_rollout"
        ) as wait_rollout, mock.patch.object(
            self.ha.ref, "output", side_effect=["3", pods]
        ):
            observed_nodes = self.ha.verify_cnpg_operator_ha("kubectl")
        self.assertEqual(observed_nodes, ["node-a", "node-b", "node-c"])
        wait_rollout.assert_called_once_with(
            "kubectl", "cnpg-system", "deployment/cnpg-controller-manager", "8m"
        )

    def test_cnpg_webhook_probe_requires_endpoint_and_server_dry_run(self) -> None:
        endpoint = mock.Mock(returncode=0, stdout="10.0.0.12")
        dry_run = mock.Mock(returncode=0, stdout="cluster.postgresql.cnpg.io/probe serverside-applied")
        with mock.patch.object(self.ha.subprocess, "run", side_effect=[endpoint, dry_run]) as run:
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

    def test_ha_diagnostic_snapshot_captures_cnpg_and_storage_evidence(self) -> None:
        completed = mock.Mock(stdout="evidence\n", stderr="")
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.ha, "CACHE", Path(directory)
        ), mock.patch.object(
            self.ha.subprocess, "run", return_value=completed
        ) as run:
            self.ha.ha_diagnostic_snapshot("kubectl", "proof")
            target = Path(directory) / "failures" / "proof"
            self.assertEqual(
                {path.name for path in target.iterdir()},
                {
                    "cnpg-clusters.yaml",
                    "cnpg-pods-describe.txt",
                    "cnpg-pods-logs.txt",
                    "cnpg-pods-previous-logs.txt",
                    "cnpg-operator-deployment.yaml",
                    "cnpg-operator-replicasets.yaml",
                    "cnpg-operator-logs.txt",
                    "barman-plugin-deployment.yaml",
                    "barman-plugin-pods-describe.txt",
                    "barman-plugin-endpoints.yaml",
                    "barman-plugin-logs.txt",
                    "barman-objectstores.yaml",
                    "certificates.yaml",
                    "storage.txt",
                },
            )
        argv = [call.args[0] for call in run.call_args_list]
        self.assertIn(
            ["kubectl", "get", "clusters.postgresql.cnpg.io", "-A", "-o", "yaml"],
            argv,
        )
        self.assertTrue(any("--previous=true" in call for call in argv))
        self.assertTrue(
            any(
                "app.kubernetes.io/name=cloudnative-pg" in call
                and "--all-containers=true" in call
                for call in argv
            )
        )

    def test_success_receipt_records_operator_node_distribution(self) -> None:
        source = (ROOT / "scripts/platform/ha_reference.py").read_text()
        self.assertIn('"operator_nodes": {', source)
        self.assertIn('"primary": primary_operator_nodes', source)
        self.assertIn('"restore": restore_operator_nodes', source)

    def test_ha_api_rollout_is_schedulable_on_three_zoned_workers(self) -> None:
        documents = list(
            self.ha.yaml.safe_load_all(
                (
                    ROOT
                    / "platform/apps/weltgewebe/overlays/ha/deployment-patch.yaml"
                ).read_text()
            )
        )
        api = next(
            item
            for item in documents
            if item.get("metadata", {}).get("name") == "weltgewebe-api"
        )
        spec = api["spec"]
        self.assertEqual(spec["replicas"], 3)
        self.assertEqual(spec["strategy"]["type"], "RollingUpdate")
        self.assertEqual(spec["strategy"]["rollingUpdate"]["maxSurge"], 0)
        self.assertEqual(
            spec["strategy"]["rollingUpdate"]["maxUnavailable"], 1
        )
        required = spec["template"]["spec"]["affinity"][
            "podAntiAffinity"
        ]["requiredDuringSchedulingIgnoredDuringExecution"]
        self.assertEqual(
            required[0]["topologyKey"], "topology.kubernetes.io/zone"
        )

    def test_upgrade_candidate_is_distinct_and_loaded_into_kind(self) -> None:
        baseline = "sha256:" + "a" * 64
        candidate = "sha256:" + "b" * 64
        with mock.patch.object(self.ha.ref, "run") as run, mock.patch.object(
            self.ha.ref, "output", side_effect=[baseline, candidate]
        ):
            observed = self.ha.prepare_api_upgrade_candidate(
                "kind", "proof", "c" * 40
            )
        self.assertEqual(
            observed,
            {
                "api_baseline": baseline,
                "api_upgrade_candidate": candidate,
            },
        )
        build = run.call_args_list[0]
        self.assertEqual(build.args[0][:4], ["docker", "build", "--file", "-"])
        self.assertIn("org.opencontainers.image.revision=" + "c" * 40, build.kwargs["input_text"])
        self.assertEqual(
            run.call_args_list[1].args[0],
            [
                "kind",
                "load",
                "docker-image",
                "--name",
                "proof",
                self.ha.UPGRADE_API_IMAGE,
            ],
        )

    def test_gateway_availability_sample_is_one_bounded_request(self) -> None:
        completed = mock.Mock(
            returncode=0,
            stdout=json.dumps([{"id": "marker"}]),
        )
        with mock.patch.object(
            self.ha.subprocess, "run", return_value=completed
        ) as run:
            self.assertTrue(
                self.ha.gateway_projection_available(
                    "kind-worker", "10.0.0.10", 80, "marker"
                )
            )
        argv = run.call_args.args[0]
        self.assertEqual(argv[:3], ["docker", "exec", "kind-worker"])
        self.assertIn("--max-time", argv)
        self.assertEqual(run.call_args.kwargs["timeout"], 5)
        self.assertFalse(run.call_args.kwargs["check"])

    def test_error_budget_is_measured_from_upgrade_and_rollback(self) -> None:
        budget = self.ha.compute_error_budget(
            {
                "duration_seconds": 20.0,
                "observed_unavailable_seconds": 0.0,
            },
            {
                "duration_seconds": 30.0,
                "observed_unavailable_seconds": 0.0,
            },
        )
        self.assertEqual(budget["measurement_window_seconds"], 50.0)
        self.assertEqual(
            budget["objective"], self.ha.REFERENCE_AVAILABILITY_OBJECTIVE
        )
        self.assertEqual(budget["consumed_ratio"], 0.0)
        self.assertTrue(budget["within_budget"])

    def test_change_management_contract_uses_rollout_undo_and_receipt_fields(self) -> None:
        source = (ROOT / "scripts/platform/ha_reference.py").read_text()
        self.assertIn(
            '"rollout",\n            "undo"', source
        )
        self.assertIn('"change_management": change_management', source)
        self.assertIn('"failed_availability_samples"', source)
        self.assertIn('"within_budget"', source)
        self.assertIn('"measured_archive_rpo_upper_bound_seconds"', source)

    def test_restore_rto_stops_before_continuity_validation(self) -> None:
        source = (ROOT / "scripts/platform/ha_reference.py").read_text()
        ready = source.index(
            'wait_cluster_ready(restore_kubectl, "postgres-restore", "20m")'
        )
        rto = source.index(
            "restore_rto = time.monotonic() - restore_started", ready
        )
        sidecars = source.index(
            "restore_barman_sidecars = verify_barman_sidecar_images(", rto
        )
        archive = source.index(
            'restore_kubectl, cluster="postgres-restore"', sidecars
        )
        self.assertLess(ready, rto)
        self.assertLess(rto, sidecars)
        self.assertLess(sidecars, archive)
        self.assertIn('"continuity_validation_seconds"', source)

    def test_zone_rejoin_waits_for_cilium_before_database_readiness(self) -> None:
        source = (ROOT / "scripts/platform/ha_reference.py").read_text()
        node_ready = source.index('f"node/{primary_topology[\'node\']}"')
        cilium_ready = source.index('"daemonset/cilium"', node_ready)
        postgres_ready = source.index('wait_cluster_ready(kubectl, "postgres-ha", "15m")', cilium_ready)
        self.assertLess(node_ready, cilium_ready)
        self.assertLess(cilium_ready, postgres_ready)
        self.assertIn('["docker", "stop", "--timeout", "10", stopped_node]', source)

    def test_wal_archive_contract_requires_the_forced_segment_or_later(self) -> None:
        required = "000000020000000A000000FE"
        self.assertEqual(self.ha.wal_segment_position(required), (2, 10, 254))
        self.assertTrue(self.ha.wal_archived_at_or_after(required, required))
        self.assertTrue(self.ha.wal_archived_at_or_after("000000020000000A000000FF", required))
        self.assertTrue(self.ha.wal_archived_at_or_after("000000030000000000000001", required))
        self.assertFalse(self.ha.wal_archived_at_or_after("000000020000000A000000FD", required))
        with self.assertRaisesRegex(self.ha.ref.ProofError, "invalid PostgreSQL WAL"):
            self.ha.wal_segment_position("not-a-wal")
        source = (ROOT / "scripts/platform/ha_reference.py").read_text()
        self.assertIn("SELECT pg_walfile_name(pg_switch_wal())", source)
        self.assertIn(
            '"required_archived_wal": primary_wal_archive["required_wal"]',
            source,
        )
        self.assertIn(
            '"observed_archived_wal": primary_wal_archive["observed_wal"]',
            source,
        )
        self.assertIn('cluster="postgres-restore"', source)
        self.assertIn('"continued_wal_archiving": restore_wal_archive', source)
        self.assertIn("FROM pg_stat_archiver", source)
        self.assertNotIn("status.lastArchivedWAL", source)

    def test_ha_diagnostics_are_bounded_and_do_not_raise_on_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(
            self.ha, "CACHE", Path(directory)
        ), mock.patch.object(
            self.ha.subprocess, "run", side_effect=self.ha.subprocess.TimeoutExpired(["kubectl"], 30)
        ) as run:
            self.ha.ha_diagnostic_snapshot("kubectl", "timeout")
            target = Path(directory) / "failures" / "timeout"
            for evidence in target.iterdir():
                self.assertIn("diagnostic command failed", evidence.read_text())
        self.assertTrue(run.call_args_list)
        self.assertTrue(all(call.kwargs["timeout"] == 30 for call in run.call_args_list))

    def test_sensitive_environment_values_never_enter_argv(self) -> None:
        completed = mock.Mock(returncode=0)
        with mock.patch.object(self.ha.subprocess, "run", return_value=completed) as run:
            self.ha.run_with_environment(
                ["docker", "run", "--env", "PROOF_SECRET"],
                {"PROOF_SECRET": "ephemeral-sensitive-value"},
            )
        argv = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertNotIn("ephemeral-sensitive-value", argv)
        self.assertEqual(environment["PROOF_SECRET"], "ephemeral-sensitive-value")

    def test_pitr_boundary_uses_and_verifies_postgres_clock(self) -> None:
        with mock.patch.object(self.ha, "psql", side_effect=["", "t"]) as psql:
            self.ha.wait_for_pitr_boundary(
                "kubectl", "2026-07-18T08:00:00.000000Z"
            )
        self.assertEqual(psql.call_args_list[0].args[1], "SELECT pg_sleep(2)")
        self.assertIn("clock_timestamp()", psql.call_args_list[1].args[1])

    def test_pitr_boundary_fails_closed_before_the_database_clock_crosses(self) -> None:
        with mock.patch.object(self.ha, "psql", side_effect=["", "f"]):
            with self.assertRaisesRegex(
                self.ha.ref.ProofError, "did not cross PITR target"
            ):
                self.ha.wait_for_pitr_boundary(
                    "kubectl", "2026-07-18T08:00:00.000000Z"
                )

    def test_cluster_context_binding_uses_cluster_specific_kubeconfig(self) -> None:
        path = ROOT / ".cache/test-restore-kubeconfig.yaml"

        def configure(_kind: str, _cluster: str) -> Path:
            self.ha.os.environ["KUBECONFIG"] = str(path)
            return path

        with (
            mock.patch.object(
                self.ha.ref, "configure_cluster_access", side_effect=configure
            ),
            mock.patch.object(self.ha.ref, "output", return_value="kind-proof-restore"),
            mock.patch.dict(self.ha.os.environ, {}, clear=False),
        ):
            self.assertEqual(
                self.ha.require_active_cluster_context(
                    "kind", "kubectl", "proof-restore"
                ),
                "kubectl",
            )

    def test_main_redacts_subprocess_output_and_logs_constant_success(self) -> None:
        parser = mock.Mock()
        parser.parse_args.return_value = self.ha.argparse.Namespace(
            command="proof", cluster="proof", keep=False
        )
        secret = "ephemeral-sensitive-value"
        failure = self.ha.subprocess.CalledProcessError(
            23, ["tool"], output=secret, stderr=secret
        )
        with (
            mock.patch.object(self.ha, "argument_parser", return_value=parser),
            mock.patch.object(self.ha.ref, "tool_receipt", return_value={}),
            mock.patch.object(self.ha, "prove", side_effect=failure),
            mock.patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            self.assertEqual(self.ha.main(), 1)
        self.assertNotIn(secret, stderr.getvalue())
        self.assertIn("status 23", stderr.getvalue())

        with (
            mock.patch.object(self.ha, "argument_parser", return_value=parser),
            mock.patch.object(self.ha.ref, "tool_receipt", return_value={}),
            mock.patch.object(self.ha, "prove", return_value={"secret": secret}),
            mock.patch("sys.stdout", new_callable=io.StringIO) as stdout,
        ):
            self.assertEqual(self.ha.main(), 0)
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "pass"})

    def test_postgres_operand_keeps_version_and_digest(self) -> None:
        image = self.ha.POSTGRES_IMAGE
        self.assertIn(":16.14@sha256:", image)
        self.assertNotIn("postgresql@sha256:", image)
        catalog = (ROOT / "platform/infrastructure/ha-data/postgres-image-catalog.yaml").read_text()
        self.assertIn(image, catalog)
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
