#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache/weltgewebe-platform"
MARKERS = CACHE / "clusters"
KUBECONFIGS = CACHE / "kubeconfigs"
DEFAULT_CLUSTER = "weltgewebe-reference"
FULL_GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
GATEWAY_API_ARTIFACTS = (
    "gateway_api_gatewayclasses",
    "gateway_api_gateways",
    "gateway_api_httproutes",
    "gateway_api_referencegrants",
    "gateway_api_grpcroutes",
)


class ProofError(RuntimeError):
    pass


def run(
    argv: list[str],
    *,
    input_text: str | None = None,
    capture: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(argv), flush=True)
    return subprocess.run(
        argv,
        cwd=ROOT,
        input=input_text,
        text=True,
        check=True,
        capture_output=capture,
        timeout=timeout,
    )


def output(argv: list[str]) -> str:
    return run(argv, capture=True).stdout.strip()


def control_plane_address(cluster: str) -> str:
    raw = json.loads(output(["docker", "inspect", f"{cluster}-control-plane"]))
    try:
        networks = raw[0]["NetworkSettings"]["Networks"]
    except (IndexError, KeyError, TypeError) as exc:
        raise ProofError("kind control-plane network metadata is missing") from exc
    preferred = networks.get("kind", {}).get("IPAddress")
    candidates = [
        details.get("IPAddress")
        for details in networks.values()
        if details.get("IPAddress")
    ]
    address = preferred or (candidates[0] if candidates else "")
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError as exc:
        raise ProofError("kind control-plane IPv4 address is missing or invalid") from exc
    if parsed.version != 4:
        raise ProofError("kind control-plane address must be IPv4")
    return str(parsed)


def tool_receipt() -> dict[str, Any]:
    raw = output(
        [
            sys.executable,
            "scripts/platform/bootstrap_tools.py",
            "--json",
            "--tool",
            "kind",
            "--tool",
            "kubectl",
            "--tool",
            "kustomize",
            "--tool",
            "flux",
            "--tool",
            "helm",
            "--tool",
            "kubectl_cnpg",
        ]
    )
    return json.loads(raw)


def require_host_tools() -> None:
    missing = [name for name in ("docker",) if shutil.which(name) is None]
    if missing:
        raise ProofError(f"missing host tools: {', '.join(missing)}")
    run(["docker", "info"], capture=True, timeout=30)


def marker_path(name: str) -> Path:
    return MARKERS / f"{name}.json"


def ownership_lock_path(name: str) -> Path:
    return MARKERS / f".{name}.ownership.lock"


def kubeconfig_path(name: str) -> Path:
    return KUBECONFIGS / f"{name}.yaml"


def generate_owner_id(prefix: str) -> str:
    return f"{prefix}-{os.getpid()}-{secrets.token_hex(8)}"


def _validate_ownership_binding(commit: str, owner_id: str) -> None:
    if not FULL_GIT_OBJECT_ID.fullmatch(commit):
        raise ProofError("cluster ownership requires a full lowercase Git object id")
    if (
        not owner_id
        or len(owner_id) > 128
        or re.fullmatch(r"[A-Za-z0-9._:@-]+", owner_id) is None
    ):
        raise ProofError("cluster ownership requires a stable owner id")


@contextmanager
def cluster_ownership_lock(name: str):
    MARKERS.mkdir(parents=True, exist_ok=True)
    path = ownership_lock_path(name)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_marker(name: str) -> dict[str, Any]:
    marker = marker_path(name)
    if marker.is_symlink() or not marker.is_file():
        raise ProofError(f"cluster {name!r} has no regular ownership marker")
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProofError(f"cluster {name!r} ownership marker is unreadable: {error}") from error
    if not isinstance(data, dict):
        raise ProofError(f"cluster {name!r} ownership marker is not an object")
    return data


def _require_marker_binding(
    data: dict[str, Any],
    name: str,
    *,
    expected_commit: str,
    expected_owner_id: str,
) -> None:
    _validate_ownership_binding(expected_commit, expected_owner_id)
    expected = {
        "schema_version": 2,
        "cluster": name,
        "repository": str(ROOT),
        "commit": expected_commit,
        "owner_id": expected_owner_id,
    }
    mismatched = {
        key: {"expected": value, "observed": data.get(key)}
        for key, value in expected.items()
        if data.get(key) != value
    }
    if mismatched:
        raise ProofError(
            f"cluster {name!r} ownership marker does not match exact owner binding: "
            f"{json.dumps(mismatched, sort_keys=True)}"
        )


def configure_cluster_access(kind: str, name: str) -> Path:
    KUBECONFIGS.mkdir(parents=True, exist_ok=True)
    path = kubeconfig_path(name)
    run([kind, "export", "kubeconfig", "--name", name, "--kubeconfig", str(path)])
    os.environ["KUBECONFIG"] = str(path)
    return path


def require_owned_cluster(
    kind: str,
    name: str,
    *,
    expected_commit: str,
    expected_owner_id: str,
) -> dict[str, Any]:
    with cluster_ownership_lock(name):
        if name not in clusters(kind):
            raise ProofError(f"owned cluster {name!r} is absent")
        data = _read_marker(name)
        _require_marker_binding(
            data,
            name,
            expected_commit=expected_commit,
            expected_owner_id=expected_owner_id,
        )
    configure_cluster_access(kind, name)
    return data


def clusters(kind: str) -> set[str]:
    result = run([kind, "get", "clusters"], capture=True)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def assert_available_cluster_name(kind: str, name: str) -> None:
    with cluster_ownership_lock(name):
        if name in clusters(kind):
            raise ProofError(
                f"cluster {name!r} already exists; it is never adopted or deleted by this proof"
            )
        if os.path.lexists(marker_path(name)):
            raise ProofError(
                f"cluster {name!r} has a stale ownership marker; "
                "explicit exact-owner cleanup is required"
            )


def write_marker(name: str, commit: str, owner_id: str) -> None:
    _validate_ownership_binding(commit, owner_id)
    MARKERS.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 2,
        "cluster": name,
        "repository": str(ROOT),
        "commit": commit,
        "owner_id": owner_id,
        "pid": os.getpid(),
    }
    try:
        with marker_path(name).open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as error:
        raise ProofError(f"cluster {name!r} ownership marker already exists") from error


def reserve_cluster_name(kind: str, name: str, commit: str, owner_id: str) -> None:
    _validate_ownership_binding(commit, owner_id)
    with cluster_ownership_lock(name):
        if name in clusters(kind):
            raise ProofError(
                f"cluster {name!r} already exists; it is never adopted or deleted by this proof"
            )
        if os.path.lexists(marker_path(name)):
            raise ProofError(
                f"cluster {name!r} has a stale ownership marker; "
                "explicit exact-owner cleanup is required"
            )
        write_marker(name, commit, owner_id)


def delete_owned_cluster(
    kind: str,
    name: str,
    *,
    expected_commit: str,
    expected_owner_id: str,
) -> None:
    with cluster_ownership_lock(name):
        data = _read_marker(name)
        _require_marker_binding(
            data,
            name,
            expected_commit=expected_commit,
            expected_owner_id=expected_owner_id,
        )
        if name in clusters(kind):
            run([kind, "delete", "cluster", "--name", name])
        marker_path(name).unlink()
        kubeconfig_path(name).unlink(missing_ok=True)


def delete_owned_cluster_if_present(
    kind: str,
    name: str,
    *,
    expected_commit: str,
    expected_owner_id: str,
) -> bool:
    if os.path.lexists(marker_path(name)):
        delete_owned_cluster(
            kind,
            name,
            expected_commit=expected_commit,
            expected_owner_id=expected_owner_id,
        )
        return True
    if name in clusters(kind):
        raise ProofError(
            f"refusing to delete cluster {name!r}: cluster exists without ownership marker"
        )
    return False

def apply_yaml(kubectl: str, document: dict[str, Any] | list[dict[str, Any]]) -> None:
    documents = document if isinstance(document, list) else [document]
    payload = yaml.safe_dump_all(documents, sort_keys=False)
    run([kubectl, "apply", "-f", "-"], input_text=payload)


def apply_file(kubectl: str, path: Path) -> None:
    run([kubectl, "apply", "-f", str(path)])


def wait_rollout(kubectl: str, namespace: str, resource: str, timeout: str = "8m") -> None:
    run([kubectl, "-n", namespace, "rollout", "status", resource, f"--timeout={timeout}"])


def wait_condition(
    kubectl: str, namespace: str, resource: str, condition: str, timeout: str = "8m"
) -> None:
    run(
        [
            kubectl,
            "-n",
            namespace,
            "wait",
            resource,
            f"--for=condition={condition}",
            f"--timeout={timeout}",
        ]
    )


def wait_http_route_parent_condition(
    kubectl: str,
    namespace: str,
    route: str,
    condition: str,
    *,
    parent_name: str,
    parent_namespace: str,
    timeout_seconds: int = 480,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_parents: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        document = json.loads(
            output(
                [
                    kubectl,
                    "-n",
                    namespace,
                    "get",
                    f"httproute/{route}",
                    "-o",
                    "json",
                ]
            )
        )
        generation = document.get("metadata", {}).get("generation")
        last_parents = document.get("status", {}).get("parents", [])
        for parent in last_parents:
            reference = parent.get("parentRef", {})
            if (
                reference.get("name") != parent_name
                or reference.get("namespace", namespace) != parent_namespace
            ):
                continue
            for observed in parent.get("conditions", []):
                if (
                    observed.get("type") == condition
                    and observed.get("status") == "True"
                    and observed.get("observedGeneration") == generation
                ):
                    return
        time.sleep(2)
    raise ProofError(
        f"HTTPRoute {namespace}/{route} parent condition {condition} was not true: "
        f"{json.dumps(last_parents, sort_keys=True)}"
    )


def build_images(kind: str, cluster: str, commit: str, timestamp: str) -> dict[str, str]:
    images = {
        "api": "weltgewebe-api:local",
        "web": "weltgewebe-web:local",
    }
    run(
        [
            "docker",
            "build",
            "--file",
            "apps/api/Dockerfile",
            "--build-arg",
            f"GIT_COMMIT_SHA={commit}",
            "--build-arg",
            f"BUILD_TIMESTAMP={timestamp}",
            "--tag",
            images["api"],
            ".",
        ],
        timeout=3600,
    )
    run(
        [
            "docker",
            "build",
            "--file",
            "apps/web/Dockerfile",
            "--build-arg",
            f"GIT_COMMIT_SHA={commit}",
            "--build-arg",
            f"BUILD_TIMESTAMP={timestamp}",
            "--tag",
            images["web"],
            ".",
        ],
        timeout=1800,
    )
    for image in images.values():
        run([kind, "load", "docker-image", "--name", cluster, image], timeout=600)
    return {
        name: output(["docker", "image", "inspect", "--format", "{{.Id}}", image])
        for name, image in images.items()
    }


def install_platform_components(
    kubectl: str,
    flux: str,
    helm: str,
    artifacts: dict[str, str],
    api_server_host: str,
) -> None:
    for artifact in GATEWAY_API_ARTIFACTS:
        apply_file(kubectl, Path(artifacts[artifact]))
    run(
        [
            helm,
            "upgrade",
            "--install",
            "cilium",
            artifacts["cilium_chart"],
            "--namespace",
            "kube-system",
            "--set",
            "gatewayAPI.enabled=true",
            "--set",
            "nodeIPAM.enabled=true",
            "--set",
            "defaultLBServiceIPAM=nodeipam",
            "--set",
            "kubeProxyReplacement=true",
            "--set",
            f"k8sServiceHost={api_server_host}",
            "--set",
            "k8sServicePort=6443",
            "--set",
            "hubble.relay.enabled=true",
            "--set",
            "hubble.ui.enabled=false",
            "--set",
            "operator.replicas=1",
            "--wait",
            "--timeout",
            "10m",
        ],
        timeout=900,
    )
    wait_rollout(kubectl, "kube-system", "daemonset/cilium")
    wait_rollout(kubectl, "kube-system", "deployment/cilium-operator")
    wait_rollout(kubectl, "kube-system", "deployment/hubble-relay")
    run(
        [
            flux,
            "install",
            "--namespace=flux-system",
            "--components=source-controller,kustomize-controller,helm-controller,notification-controller",
        ],
        timeout=600,
    )
    for deployment in (
        "source-controller",
        "kustomize-controller",
        "helm-controller",
        "notification-controller",
    ):
        wait_rollout(kubectl, "flux-system", f"deployment/{deployment}")


def namespace_document(name: str, *, data_client: bool = False) -> dict[str, Any]:
    labels = {
        "pod-security.kubernetes.io/enforce": "restricted",
        "pod-security.kubernetes.io/audit": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
    }
    if data_client:
        labels["weltgewebe.net/data-client"] = "true"
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": name, "labels": labels},
    }


def has_exactly_one_value(*values: str | None) -> bool:
    return sum(bool(value) for value in values) == 1


def validate_source_binding(
    mode: str, *, source_ref: str | None, source_commit: str | None
) -> None:
    if mode not in {"direct", "gitops"}:
        raise ProofError(f"unsupported proof mode: {mode}")
    if mode == "direct":
        if source_ref or source_commit:
            raise ProofError(
                "--source-ref and --source-commit are invalid for direct mode"
            )
        return
    if not has_exactly_one_value(source_ref, source_commit):
        raise ProofError(
            "exactly one of --source-ref or --source-commit is required "
            "for gitops mode"
        )
    if source_commit and FULL_GIT_OBJECT_ID.fullmatch(source_commit) is None:
        raise ProofError("--source-commit must be a full lowercase Git object id")


def validate_workspace_binding(
    *, source_commit: str | None, workspace_commit: str
) -> None:
    if source_commit and source_commit != workspace_commit:
        raise ProofError(
            "--source-commit must equal the exact local workspace HEAD "
            f"({workspace_commit})"
        )


def flux_source_document(
    *, branch: str | None = None, commit: str | None = None
) -> dict[str, Any]:
    if not has_exactly_one_value(branch, commit):
        raise ProofError("exactly one Flux source branch or commit is required")
    document = yaml.safe_load((ROOT / "platform/clusters/local/source.yaml").read_text())
    document["spec"]["ref"] = {"branch": branch} if branch else {"commit": commit}
    return document


def apply_direct(kubectl: str, kustomize: str, path: str) -> None:
    rendered = output([kustomize, "build", path])
    run([kubectl, "apply", "-f", "-"], input_text=rendered)


def apply_flux_data(
    kubectl: str, *, source_ref: str | None = None, source_commit: str | None = None
) -> None:
    apply_yaml(
        kubectl,
        flux_source_document(branch=source_ref, commit=source_commit),
    )
    apply_file(kubectl, ROOT / "platform/clusters/local/local-data.yaml")
    apply_file(kubectl, ROOT / "platform/clusters/local/migration.yaml")
    wait_condition(kubectl, "flux-system", "gitrepository/weltgewebe", "Ready")
    wait_condition(kubectl, "flux-system", "kustomization/weltgewebe-local-data", "Ready")
    wait_condition(kubectl, "flux-system", "kustomization/weltgewebe-migration", "Ready")


def migrate_direct(kubectl: str, kustomize: str) -> None:
    run(
        [
            kubectl,
            "-n",
            "weltgewebe",
            "delete",
            "job",
            "weltgewebe-migration",
            "--ignore-not-found=true",
            "--wait=true",
        ]
    )
    apply_direct(kubectl, kustomize, "platform/apps/weltgewebe/migration/local")
    wait_condition(
        kubectl,
        "weltgewebe",
        "job/weltgewebe-migration",
        "Complete",
        "8m",
    )


def apply_app_and_gateway(
    kubectl: str, kustomize: str, mode: str
) -> None:
    if mode == "gitops":
        apply_file(kubectl, ROOT / "platform/clusters/local/app.yaml")
        apply_file(kubectl, ROOT / "platform/clusters/local/gateway.yaml")
        wait_condition(kubectl, "flux-system", "kustomization/weltgewebe-app", "Ready")
        wait_condition(kubectl, "flux-system", "kustomization/weltgewebe-gateway", "Ready")
    else:
        apply_direct(kubectl, kustomize, "platform/apps/weltgewebe/overlays/local")
        apply_direct(kubectl, kustomize, "platform/infrastructure/gateway")


def wait_apps(kubectl: str, namespace: str) -> None:
    wait_rollout(kubectl, namespace, "deployment/weltgewebe-api")
    wait_rollout(kubectl, namespace, "deployment/weltgewebe-web")
    available = output(
        [
            kubectl,
            "-n",
            namespace,
            "get",
            "deployment/weltgewebe-api",
            "-o",
            "jsonpath={.status.availableReplicas}",
        ]
    )
    if available != "2":
        raise ProofError(f"expected two available API replicas, got {available!r}")


def ready_api_pods(kubectl: str, namespace: str) -> list[tuple[str, str]]:
    document = json.loads(
        output(
            [
                kubectl,
                "-n",
                namespace,
                "get",
                "pod",
                "-l",
                "app.kubernetes.io/name=weltgewebe-api",
                "-o",
                "json",
            ]
        )
    )
    ready: list[tuple[str, str]] = []
    for item in document.get("items", []):
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        if metadata.get("deletionTimestamp") is not None:
            continue
        if status.get("phase") != "Running":
            continue
        conditions = status.get("conditions", [])
        if not any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in conditions
        ):
            continue
        container_statuses = status.get("containerStatuses", [])
        if not container_statuses or not all(
            container.get("ready") is True for container in container_statuses
        ):
            continue
        name = metadata.get("name")
        uid = metadata.get("uid")
        if isinstance(name, str) and name and isinstance(uid, str) and uid:
            ready.append((name, uid))
    return sorted(ready)


def api_version(kubectl: str, namespace: str) -> str:
    last_error: BaseException | None = None
    for attempt in range(30):
        try:
            pods = ready_api_pods(kubectl, namespace)
        except subprocess.CalledProcessError as error:
            pods = []
            last_error = error
        for pod, _ in pods:
            try:
                return output(
                    [
                        kubectl,
                        "-n",
                        namespace,
                        "exec",
                        pod,
                        "--",
                        "wget",
                        "-qO-",
                        "-T",
                        "5",
                        "http://weltgewebe-api:8080/version",
                    ]
                )
            except subprocess.CalledProcessError as error:
                last_error = error
        if attempt == 29:
            raise ProofError(
                "API service did not become reachable from a current ready API pod"
            ) from last_error
        time.sleep(1)
    raise AssertionError("unreachable API service retry state")


def ready_api_pod_uids(kubectl: str, namespace: str) -> set[str]:
    pods = ready_api_pods(kubectl, namespace)
    if len(pods) != 2:
        raise ProofError(
            f"expected exactly two current ready API pods, got {len(pods)}"
        )
    return {uid for _, uid in pods}


def prove_restart(kubectl: str, namespace: str) -> dict[str, str]:
    before_pods = ready_api_pod_uids(kubectl, namespace)
    before = api_version(kubectl, namespace)
    run([kubectl, "-n", namespace, "rollout", "restart", "deployment/weltgewebe-api"])
    wait_rollout(kubectl, namespace, "deployment/weltgewebe-api")
    after_pods = ready_api_pod_uids(kubectl, namespace)
    overlap = before_pods & after_pods
    if overlap:
        raise ProofError(
            "API rollout did not replace every ready pod: "
            + ", ".join(sorted(overlap))
        )
    after = api_version(kubectl, namespace)
    if json.loads(before).get("git_commit") != json.loads(after).get("git_commit"):
        raise ProofError("API commit changed across restart")
    return {
        "before": hashlib.sha256(before.encode()).hexdigest(),
        "after": hashlib.sha256(after.encode()).hexdigest(),
        "before_pods_sha256": hashlib.sha256(
            "\n".join(sorted(before_pods)).encode()
        ).hexdigest(),
        "after_pods_sha256": hashlib.sha256(
            "\n".join(sorted(after_pods)).encode()
        ).hexdigest(),
        "replaced_replicas": str(len(after_pods)),
    }



def prove_flux_drift(kubectl: str, flux: str, namespace: str) -> None:
    run([kubectl, "-n", namespace, "scale", "deployment/weltgewebe-api", "--replicas=1"])
    run([flux, "reconcile", "kustomization", "weltgewebe-app", "--with-source", "--timeout=5m"])
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        replicas = output(
            [
                kubectl,
                "-n",
                namespace,
                "get",
                "deployment/weltgewebe-api",
                "-o",
                "jsonpath={.spec.replicas}",
            ]
        )
        if replicas == "2":
            wait_rollout(kubectl, namespace, "deployment/weltgewebe-api")
            return
        time.sleep(3)
    raise ProofError("Flux did not repair replica drift")


def gateway_addresses(kubectl: str) -> list[str]:
    document = json.loads(output([kubectl, "-n", "weltgewebe-gateway", "get", "gateway", "weltgewebe", "-o", "json"]))
    addresses: list[str] = []
    for entry in document.get("status", {}).get("addresses", []):
        if entry.get("type") != "IPAddress" or not isinstance(entry.get("value"), str):
            continue
        try:
            address = ipaddress.ip_address(entry["value"])
        except ValueError:
            continue
        if address.version == 4 and not address.is_unspecified:
            value = str(address)
            if value not in addresses:
                addresses.append(value)
    if not addresses:
        raise ProofError("Gateway has no usable IPv4 status address")
    return addresses


def gateway_listener_port(kubectl: str) -> int:
    document = json.loads(
        output(
            [
                kubectl,
                "-n",
                "weltgewebe-gateway",
                "get",
                "gateway",
                "weltgewebe",
                "-o",
                "json",
            ]
        )
    )
    ports = [
        listener.get("port")
        for listener in document.get("spec", {}).get("listeners", [])
        if listener.get("protocol") == "HTTP"
    ]
    if len(ports) != 1 or not isinstance(ports[0], int):
        raise ProofError(f"Gateway must expose exactly one HTTP listener: {ports!r}")
    port = ports[0]
    if not 1 <= port <= 65535:
        raise ProofError(f"Gateway listener port is out of range: {port}")
    return port


def gateway_service_listener_port(
    kubectl: str, service: str, expected_port: int
) -> int:
    document = json.loads(
        output(
            [
                kubectl,
                "-n",
                "weltgewebe-gateway",
                "get",
                "service",
                service,
                "-o",
                "json",
            ]
        )
    )
    spec = document.get("spec", {})
    if spec.get("type") != "LoadBalancer":
        raise ProofError("Gateway service is not a LoadBalancer")
    matches = [
        port
        for port in spec.get("ports", [])
        if port.get("protocol", "TCP") == "TCP" and port.get("port") == expected_port
    ]
    if len(matches) != 1:
        raise ProofError(
            "Gateway LoadBalancer service does not expose its HTTP listener port: "
            f"{expected_port}"
        )
    return expected_port



def kind_nodes(kind: str, cluster: str) -> list[str]:
    nodes = [
        node.strip()
        for node in output([kind, "get", "nodes", "--name", cluster]).splitlines()
        if node.strip()
    ]
    if not nodes:
        raise ProofError(f"kind cluster has no nodes: {cluster}")
    return nodes


def probe_gateway_http(
    kind: str,
    cluster: str,
    addresses: list[str],
    port: int,
    timeout_seconds: int = 30,
) -> tuple[str, str, bytes, bytes, bytes]:
    nodes = kind_nodes(kind, cluster)
    deadline = time.monotonic() + timeout_seconds
    last_error: BaseException | None = None
    while True:
        for node in nodes:
            for address in addresses:
                common = [
                    "docker",
                    "exec",
                    node,
                    "curl",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--max-time",
                    "10",
                ]
                try:
                    health = subprocess.run(
                        [*common, f"http://{address}:{port}/health/live"],
                        cwd=ROOT,
                        text=False,
                        capture_output=True,
                        check=True,
                        timeout=15,
                    ).stdout
                    web = subprocess.run(
                        [*common, f"http://{address}:{port}/"],
                        cwd=ROOT,
                        text=False,
                        capture_output=True,
                        check=True,
                        timeout=15,
                    ).stdout[:1024]
                    api_nodes = subprocess.run(
                        [*common, f"http://{address}:{port}/api/nodes"],
                        cwd=ROOT,
                        text=False,
                        capture_output=True,
                        check=True,
                        timeout=15,
                    ).stdout
                    try:
                        api_payload = json.loads(api_nodes)
                    except (UnicodeDecodeError, json.JSONDecodeError) as error:
                        raise ProofError(
                            "Gateway /api/nodes route did not return valid JSON"
                        ) from error
                    if not isinstance(api_payload, list):
                        raise ProofError(
                            "Gateway /api/nodes route did not preserve the API list contract"
                        )
                    if health and web:
                        return node, address, health, web, api_nodes
                    last_error = ProofError("Gateway route returned empty content")
                except (
                    subprocess.CalledProcessError,
                    subprocess.TimeoutExpired,
                    ProofError,
                ) as error:
                    last_error = error
        if time.monotonic() >= deadline:
            raise ProofError(
                "Gateway status address did not serve listener HTTP from a kind node: "
                f"nodes={nodes!r} addresses={addresses!r} port={port}"
            ) from last_error
        time.sleep(1)


def prove_gateway(kubectl: str, kind: str, cluster: str) -> dict[str, str]:
    wait_condition(kubectl, "weltgewebe-gateway", "gateway/weltgewebe", "Programmed")
    wait_http_route_parent_condition(
        kubectl,
        "weltgewebe",
        "weltgewebe",
        "Accepted",
        parent_name="weltgewebe",
        parent_namespace="weltgewebe-gateway",
    )
    wait_http_route_parent_condition(
        kubectl,
        "weltgewebe",
        "weltgewebe",
        "ResolvedRefs",
        parent_name="weltgewebe",
        parent_namespace="weltgewebe-gateway",
    )
    service = output(
        [
            kubectl,
            "-n",
            "weltgewebe-gateway",
            "get",
            "service",
            "-l",
            "gateway.networking.k8s.io/gateway-name=weltgewebe",
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ]
    )
    if not service:
        raise ProofError("Gateway service was not created")
    listener_port = gateway_listener_port(kubectl)
    probe_node, address, health, web, api_nodes = probe_gateway_http(
        kind,
        cluster,
        gateway_addresses(kubectl),
        gateway_service_listener_port(kubectl, service, listener_port),
    )
    return {
        "service": service,
        "probe_node": probe_node,
        "address": address,
        "listener_port": str(listener_port),
        "health_sha256": hashlib.sha256(health).hexdigest(),
        "web_prefix_sha256": hashlib.sha256(web).hexdigest(),
        "api_nodes_sha256": hashlib.sha256(api_nodes).hexdigest(),
    }


def diagnostic_snapshot(kubectl: str, name: str) -> None:
    target = CACHE / "failures" / name
    target.mkdir(parents=True, exist_ok=True)
    commands = {
        "nodes.txt": [kubectl, "get", "nodes", "-o", "wide"],
        "pods.txt": [kubectl, "get", "pods", "-A", "-o", "wide"],
        "events.txt": [kubectl, "get", "events", "-A", "--sort-by=.lastTimestamp"],
        "flux.txt": [kubectl, "-n", "flux-system", "get", "gitrepositories,kustomizations"],
        "gateway.txt": [kubectl, "get", "gateway,httproute", "-A", "-o", "yaml"],
    }
    for filename, argv in commands.items():
        result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True)
        (target / filename).write_text(result.stdout + result.stderr, encoding="utf-8")


def proof(args: argparse.Namespace) -> dict[str, Any]:
    validate_source_binding(
        args.mode,
        source_ref=args.source_ref,
        source_commit=args.source_commit,
    )
    if output(["git", "status", "--porcelain"]):
        raise ProofError("reference proof requires a clean, commit-bound worktree")
    commit = output(["git", "rev-parse", "HEAD"])
    validate_workspace_binding(
        source_commit=args.source_commit,
        workspace_commit=commit,
    )
    timestamp = output(["git", "show", "-s", "--format=%cI", "HEAD"])
    require_host_tools()
    receipt = tool_receipt()
    tools = receipt["tools"]
    kind = tools["kind"]
    kubectl = tools["kubectl"]
    kustomize = tools["kustomize"]
    flux = tools["flux"]
    helm = tools["helm"]
    owner_id = args.owner_id or generate_owner_id("kind-proof")
    reserve_cluster_name(kind, args.cluster, commit, owner_id)
    app_namespace = "weltgewebe"
    reserved = True
    created = False
    try:
        run(
            [
                kind,
                "create",
                "cluster",
                "--name",
                args.cluster,
                "--image",
                receipt["kubernetes"]["kind_node_image"],
                "--config",
                "platform/clusters/local/kind.yaml",
            ],
            timeout=600,
        )
        configure_cluster_access(kind, args.cluster)
        api_server_host = control_plane_address(args.cluster)
        created = True
        image_ids = build_images(kind, args.cluster, commit, timestamp)
        install_platform_components(
            kubectl, flux, helm, receipt["artifacts"], api_server_host
        )
        run([kubectl, "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=5m"])
        if args.mode == "gitops":
            apply_flux_data(
                kubectl,
                source_ref=args.source_ref,
                source_commit=args.source_commit,
            )
        else:
            apply_direct(kubectl, kustomize, "platform/infrastructure/local-data")
            wait_rollout(kubectl, "weltgewebe-data", "deployment/postgres")
            wait_rollout(kubectl, "weltgewebe-data", "deployment/nats")
            migrate_direct(kubectl, kustomize)
        apply_app_and_gateway(kubectl, kustomize, args.mode)
        wait_apps(kubectl, app_namespace)
        restart = prove_restart(kubectl, app_namespace)
        if args.mode == "gitops":
            prove_flux_drift(kubectl, flux, app_namespace)
        gateway = prove_gateway(kubectl, kind, args.cluster)
        result = {
            "schema_version": 1,
            "status": "pass",
            "cluster": args.cluster,
            "mode": args.mode,
            "source_ref": args.source_ref,
            "source_commit": args.source_commit,
            "commit": commit,
            "owner_id": owner_id,
            "tool_lock_sha256": receipt["lock_sha256"],
            "image_ids": image_ids,
            "bootstrap_api_server": {"host": api_server_host, "port": 6443},
            "api_restart": restart,
            "gateway": gateway,
            "api_replicas": 2,
            "migration_credential_class": "public-local-configmap",
            "migration_workload": "batch/v1 Job/weltgewebe-migration",
            "production_changed": False,
        }
        target = CACHE / "receipts"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{args.cluster}-{commit}.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["receipt_path"] = str(path)
        result["receipt_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result
    except Exception:
        if created:
            diagnostic_snapshot(kubectl, args.cluster)
        raise
    finally:
        if reserved and not args.keep:
            delete_owned_cluster(
                kind,
                args.cluster,
                expected_commit=commit,
                expected_owner_id=owner_id,
            )


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    proof_parser = subparsers.add_parser("proof")
    proof_parser.add_argument("--cluster", default=DEFAULT_CLUSTER)
    proof_parser.add_argument("--mode", choices=("direct", "gitops"), default="direct")
    source_group = proof_parser.add_mutually_exclusive_group()
    source_group.add_argument("--source-ref")
    source_group.add_argument("--source-commit")
    proof_parser.add_argument("--keep", action="store_true")
    proof_parser.add_argument("--owner-id")
    down_parser = subparsers.add_parser("down")
    down_parser.add_argument("--cluster", default=DEFAULT_CLUSTER)
    down_parser.add_argument("--commit", required=True)
    down_parser.add_argument("--owner-id", required=True)
    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        receipt = tool_receipt()
        if args.command == "down":
            deleted = delete_owned_cluster_if_present(
                receipt["tools"]["kind"],
                args.cluster,
                expected_commit=args.commit,
                expected_owner_id=args.owner_id,
            )
            print(json.dumps({
                "status": "deleted" if deleted else "absent",
                "cluster": args.cluster,
                "commit": args.commit,
                "owner_id": args.owner_id,
            }, sort_keys=True))
            return 0
        result = proof(args)
    except (ProofError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"kind reference proof failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stdout or "", file=sys.stderr)
            print(error.stderr or "", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
