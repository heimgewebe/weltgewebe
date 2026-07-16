#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache/weltgewebe-platform"
MARKERS = CACHE / "clusters"
KUBECONFIGS = CACHE / "kubeconfigs"
DEFAULT_CLUSTER = "weltgewebe-reference"
LOCAL_APP_FIXTURE = (
    ROOT / "platform/apps/weltgewebe/overlays/local/fixture-config-map.yaml"
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


def tool_receipt() -> dict[str, Any]:
    raw = output([sys.executable, "scripts/platform/bootstrap_tools.py", "--json"])
    return json.loads(raw)


def require_host_tools() -> None:
    missing = [name for name in ("docker",) if shutil.which(name) is None]
    if missing:
        raise ProofError(f"missing host tools: {', '.join(missing)}")
    run(["docker", "info"], capture=True, timeout=30)


def marker_path(name: str) -> Path:
    return MARKERS / f"{name}.json"


def kubeconfig_path(name: str) -> Path:
    return KUBECONFIGS / f"{name}.yaml"


def configure_cluster_access(kind: str, name: str) -> Path:
    KUBECONFIGS.mkdir(parents=True, exist_ok=True)
    path = kubeconfig_path(name)
    run([kind, "export", "kubeconfig", "--name", name, "--kubeconfig", str(path)])
    os.environ["KUBECONFIG"] = str(path)
    return path


def require_owned_cluster(kind: str, name: str) -> dict[str, Any]:
    marker = marker_path(name)
    if name not in clusters(kind):
        raise ProofError(f"owned cluster {name!r} is absent")
    if not marker.is_file():
        raise ProofError(f"cluster {name!r} has no ownership marker")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data.get("cluster") != name or data.get("repository") != str(ROOT):
        raise ProofError(f"cluster {name!r} ownership marker does not match")
    configure_cluster_access(kind, name)
    return data


def clusters(kind: str) -> set[str]:
    result = run([kind, "get", "clusters"], capture=True)
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def assert_available_cluster_name(kind: str, name: str) -> None:
    existing = clusters(kind)
    marker = marker_path(name)
    if name in existing:
        raise ProofError(
            f"cluster {name!r} already exists; it is never adopted or deleted by this proof"
        )
    if marker.exists():
        marker.unlink()


def write_marker(name: str, commit: str) -> None:
    MARKERS.mkdir(parents=True, exist_ok=True)
    marker_path(name).write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cluster": name,
                "repository": str(ROOT),
                "commit": commit,
                "pid": os.getpid(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def delete_owned_cluster(kind: str, name: str) -> None:
    marker = marker_path(name)
    if not marker.is_file():
        raise ProofError(f"refusing to delete unowned cluster {name!r}: marker missing")
    data = json.loads(marker.read_text(encoding="utf-8"))
    if data.get("cluster") != name or data.get("repository") != str(ROOT):
        raise ProofError(f"refusing to delete cluster {name!r}: marker mismatch")
    if name in clusters(kind):
        run([kind, "delete", "cluster", "--name", name])
    marker.unlink(missing_ok=True)
    kubeconfig_path(name).unlink(missing_ok=True)


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
) -> None:
    apply_file(kubectl, Path(artifacts["gateway_api_standard"]))
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


def local_fixture_database_url() -> str:
    fixture = yaml.safe_load(LOCAL_APP_FIXTURE.read_text(encoding="utf-8"))
    database_url = fixture.get("data", {}).get("database-url")
    if not isinstance(database_url, str) or not database_url:
        raise ProofError("local fixture database-url is missing")
    return database_url


def runtime_secret_document(app_namespace: str) -> dict[str, Any]:
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "weltgewebe-runtime", "namespace": app_namespace},
        "type": "Opaque",
        "stringData": {"database-url": local_fixture_database_url()},
    }


def apply_runtime_secret(kubectl: str, app_namespace: str) -> None:
    apply_yaml(kubectl, runtime_secret_document(app_namespace))


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


def flux_source_document(branch: str) -> dict[str, Any]:
    document = yaml.safe_load((ROOT / "platform/clusters/local/source.yaml").read_text())
    document["spec"]["ref"] = {"branch": branch}
    return document


def apply_direct(kubectl: str, kustomize: str, path: str) -> None:
    rendered = output([kustomize, "build", path])
    run([kubectl, "apply", "-f", "-"], input_text=rendered)


def apply_flux_data(kubectl: str, branch: str) -> None:
    apply_yaml(kubectl, flux_source_document(branch))
    apply_file(kubectl, ROOT / "platform/clusters/local/local-data.yaml")
    wait_condition(kubectl, "flux-system", "gitrepository/weltgewebe", "Ready")
    wait_condition(kubectl, "flux-system", "kustomization/weltgewebe-local-data", "Ready")


def migration_pod(image: str, namespace: str) -> dict[str, Any]:
    runtime_reference = {
        "secretKeyRef": {
            "name": "weltgewebe-runtime",
            "key": "database-url",
        }
    }
    environment = {
        "API_BIND": "0.0.0.0:8080",
        "APP_BASE_URL": "http://weltgewebe.localhost",
        "AUTH_COOKIE_SECURE": "0",
        "AUTH_PUBLIC_LOGIN": "0",
        "GEWEBE_IN_DIR": "/data",
        "GEWEBE_SEED_DEMO": "false",
        "GEWEBE_SEED_REAL": "false",
        "NATS_URL": "nats://nats.weltgewebe-data.svc.cluster.local:4222",
        "RUST_LOG": "info",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS": "run",
        "WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE": "postgres",
        "WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE": "postgres",
        "WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE": "postgres",
        "WELTGEWEBE_DOMAIN_READ_SOURCE": "postgres",
        "WELTGEWEBE_PASSKEY_CREDENTIAL_SOURCE": "postgres",
    }
    return {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {
            "name": "weltgewebe-migration-bootstrap",
            "namespace": namespace,
            "labels": {"app.kubernetes.io/name": "weltgewebe-migration-bootstrap"},
        },
        "spec": {
            "restartPolicy": "Never",
            "automountServiceAccountToken": False,
            "securityContext": {
                "runAsNonRoot": True,
                "runAsUser": 10001,
                "runAsGroup": 10001,
                "fsGroup": 10001,
                "seccompProfile": {"type": "RuntimeDefault"},
            },
            "containers": [
                {
                    "name": "api",
                    "image": image,
                    "imagePullPolicy": "Never",
                    "env": [
                        {"name": key, "value": value}
                        for key, value in environment.items()
                    ]
                    + [
                        {
                            "name": "DATABASE_URL",
                            "valueFrom": runtime_reference,
                        }
                    ],
                    "readinessProbe": {
                        "httpGet": {"path": "/health/ready", "port": 8080},
                        "periodSeconds": 2,
                        "failureThreshold": 60,
                    },
                    "resources": {
                        "requests": {"cpu": "100m", "memory": "128Mi"},
                        "limits": {"cpu": "1", "memory": "512Mi"},
                    },
                    "securityContext": {
                        "allowPrivilegeEscalation": False,
                        "privileged": False,
                        "readOnlyRootFilesystem": True,
                        "capabilities": {"drop": ["ALL"]},
                    },
                    "volumeMounts": [
                        {"name": "data", "mountPath": "/data"},
                        {"name": "tmp", "mountPath": "/tmp"},
                    ],
                }
            ],
            "volumes": [
                {"name": "data", "emptyDir": {}},
                {"name": "tmp", "emptyDir": {}},
            ],
        },
    }


def migrate(kubectl: str, namespace: str) -> None:
    pod = migration_pod("weltgewebe-api:local", namespace)
    run(
        [
            kubectl,
            "-n",
            namespace,
            "delete",
            "pod",
            pod["metadata"]["name"],
            "--ignore-not-found=true",
        ]
    )
    apply_yaml(kubectl, pod)
    wait_condition(kubectl, namespace, f"pod/{pod['metadata']['name']}", "Ready", "8m")
    run([kubectl, "-n", namespace, "delete", "pod", pod["metadata"]["name"], "--wait=true"])


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


def api_version(kubectl: str, namespace: str) -> str:
    pod = output(
        [
            kubectl,
            "-n",
            namespace,
            "get",
            "pod",
            "-l",
            "app.kubernetes.io/name=weltgewebe-api",
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ]
    )
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
            "http://weltgewebe-api:8080/version",
        ]
    )


def prove_restart(kubectl: str, namespace: str) -> dict[str, str]:
    before = api_version(kubectl, namespace)
    run([kubectl, "-n", namespace, "rollout", "restart", "deployment/weltgewebe-api"])
    wait_rollout(kubectl, namespace, "deployment/weltgewebe-api")
    after = api_version(kubectl, namespace)
    if json.loads(before).get("git_commit") != json.loads(after).get("git_commit"):
        raise ProofError("API commit changed across restart")
    return {"before": hashlib.sha256(before.encode()).hexdigest(), "after": hashlib.sha256(after.encode()).hexdigest()}


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


@contextmanager
def port_forward(kubectl: str, namespace: str, service: str, remote_port: int) -> Iterator[int]:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        local_port = probe.getsockname()[1]
    process = subprocess.Popen(
        [
            kubectl,
            "-n",
            namespace,
            "port-forward",
            f"service/{service}",
            f"{local_port}:{remote_port}",
            "--address=127.0.0.1",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            with socket.socket() as client:
                if client.connect_ex(("127.0.0.1", local_port)) == 0:
                    break
            if process.poll() is not None:
                raise ProofError("kubectl port-forward exited early")
            time.sleep(0.25)
        else:
            raise ProofError("kubectl port-forward did not become ready")
        yield local_port
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def prove_gateway(kubectl: str) -> dict[str, str]:
    wait_condition(kubectl, "weltgewebe-gateway", "gateway/weltgewebe", "Programmed")
    wait_condition(kubectl, "weltgewebe", "httproute/weltgewebe", "Accepted")
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
    with port_forward(kubectl, "weltgewebe-gateway", service, 80) as port:
        health = urllib.request.urlopen(f"http://127.0.0.1:{port}/health/live", timeout=10).read()
        web = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).read(1024)
    if not health or not web:
        raise ProofError("Gateway route returned empty content")
    return {
        "service": service,
        "health_sha256": hashlib.sha256(health).hexdigest(),
        "web_prefix_sha256": hashlib.sha256(web).hexdigest(),
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
    require_host_tools()
    receipt = tool_receipt()
    tools = receipt["tools"]
    kind = tools["kind"]
    kubectl = tools["kubectl"]
    kustomize = tools["kustomize"]
    flux = tools["flux"]
    helm = tools["helm"]
    assert_available_cluster_name(kind, args.cluster)
    if output(["git", "status", "--porcelain"]):
        raise ProofError("reference proof requires a clean, commit-bound worktree")
    commit = output(["git", "rev-parse", "HEAD"])
    timestamp = output(["git", "show", "-s", "--format=%cI", "HEAD"])
    app_namespace = "weltgewebe"
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
        write_marker(args.cluster, commit)
        configure_cluster_access(kind, args.cluster)
        created = True
        image_ids = build_images(kind, args.cluster, commit, timestamp)
        install_platform_components(kubectl, flux, helm, receipt["artifacts"])
        run([kubectl, "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=5m"])
        apply_yaml(kubectl, namespace_document(app_namespace, data_client=True))
        if args.mode == "gitops":
            if not args.source_ref:
                raise ProofError("--source-ref is required for gitops mode")
            apply_flux_data(kubectl, args.source_ref)
        else:
            apply_direct(kubectl, kustomize, "platform/infrastructure/local-data")
            wait_rollout(kubectl, "weltgewebe-data", "deployment/postgres")
            wait_rollout(kubectl, "weltgewebe-data", "deployment/nats")
        apply_runtime_secret(kubectl, app_namespace)
        migrate(kubectl, app_namespace)
        apply_app_and_gateway(kubectl, kustomize, args.mode)
        wait_apps(kubectl, app_namespace)
        restart = prove_restart(kubectl, app_namespace)
        if args.mode == "gitops":
            prove_flux_drift(kubectl, flux, app_namespace)
        gateway = prove_gateway(kubectl)
        result = {
            "schema_version": 1,
            "status": "pass",
            "cluster": args.cluster,
            "mode": args.mode,
            "source_ref": args.source_ref,
            "commit": commit,
            "tool_lock_sha256": receipt["lock_sha256"],
            "image_ids": image_ids,
            "api_restart": restart,
            "gateway": gateway,
            "api_replicas": 2,
            "migration_credential_class": (
                "ephemeral-runtime-secret-from-public-local-fixture"
            ),
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
        if created and not args.keep:
            delete_owned_cluster(kind, args.cluster)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    proof_parser = subparsers.add_parser("proof")
    proof_parser.add_argument("--cluster", default=DEFAULT_CLUSTER)
    proof_parser.add_argument("--mode", choices=("direct", "gitops"), default="direct")
    proof_parser.add_argument("--source-ref")
    proof_parser.add_argument("--keep", action="store_true")
    down_parser = subparsers.add_parser("down")
    down_parser.add_argument("--cluster", default=DEFAULT_CLUSTER)
    args = parser.parse_args()
    try:
        receipt = tool_receipt()
        if args.command == "down":
            delete_owned_cluster(receipt["tools"]["kind"], args.cluster)
            print(json.dumps({"status": "deleted", "cluster": args.cluster}))
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
