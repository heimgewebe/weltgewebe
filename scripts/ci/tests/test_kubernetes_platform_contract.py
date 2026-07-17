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
