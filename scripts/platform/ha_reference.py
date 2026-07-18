#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


import kind_reference as ref

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".cache/weltgewebe-platform"
DEFAULT_CLUSTER = "weltgewebe-ha-reference"
CNPG_OPERATOR_IMAGE = "ghcr.io/cloudnative-pg/cloudnative-pg@sha256:a2701eb97cdd2a34b1fdb2cb51987f544b706e40bec72ae7146cd8580efefebb"
POSTGRES_IMAGE = "ghcr.io/cloudnative-pg/postgresql:16.14@sha256:05eae7037dc6a7077cc3fc91a65fe023279060572a237d11aa83e11179443ad1"
NATS_BOX_IMAGE = "natsio/nats-box@sha256:9d5f35d286c3dcfca18bb2339b51345f9f89b580b237ab16ddfe609bdca9c72d"
SEAWEEDFS_IMAGE = "chrislusf/seaweedfs@sha256:f898c91e42d7da5f4bb13f1efd424ff03ba85b420312eb929708a384e8a8b03d"
BARMAN_PLUGIN_IMAGE = "ghcr.io/cloudnative-pg/plugin-barman-cloud@sha256:71589dbac582333442812b07b31f7ea4d00324a8358aac7ca507dabf9f4b6c96"
BARMAN_PLUGIN_SIDECAR_IMAGE = "ghcr.io/cloudnative-pg/plugin-barman-cloud-sidecar@sha256:990361af3319f9e23aafa0f6d7981f99bf1f69b4e6a85cf1bc7d71d6f09bb288"
CERT_MANAGER_IMAGES = {
    "quay.io/jetstack/cert-manager-cainjector:v1.21.0": "quay.io/jetstack/cert-manager-cainjector@sha256:ad1dcc5b2fccc420f9b3fbee7ce8a869450c540fd4f2f41de2d95b1ca0c4d701",
    "quay.io/jetstack/cert-manager-controller:v1.21.0": "quay.io/jetstack/cert-manager-controller@sha256:e370f7800a53078e9d74324287a7d52b553864e55f5b4e521f911c3f6c7da203",
    "quay.io/jetstack/cert-manager-webhook:v1.21.0": "quay.io/jetstack/cert-manager-webhook@sha256:c33cca307541e2d58861a55b1af5f390b7e19c8741e48b433693b73a7cce88b3",
}
APP_USER = "welt"
S3_ACCESS_KEY = "weltgewebe-ha-proof"
S3_BUCKET = "weltgewebe-postgres"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_with_environment(
    argv: list[str], values: dict[str, str], *, timeout: int | None = None
) -> None:
    print("+", " ".join(argv), f"[env: {','.join(sorted(values))}]", flush=True)
    environment = os.environ.copy()
    environment.update(values)
    subprocess.run(
        argv, cwd=ROOT, check=True, text=True, env=environment, timeout=timeout
    )


def wait_until(
    description: str, probe, *, timeout_seconds: int = 600, interval: float = 2.0
):
    deadline = time.monotonic() + timeout_seconds
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = probe()
            if last:
                return last
        except (subprocess.CalledProcessError, json.JSONDecodeError, ref.ProofError):
            pass
        time.sleep(interval)
    raise ref.ProofError(f"timed out waiting for {description}; last={last!r}")


def create_kind_cluster(
    kind: str, name: str, image: str, config: str, commit: str
) -> None:
    ref.assert_available_cluster_name(kind, name)
    ref.write_marker(name, commit)
    try:
        ref.run(
            [
                kind,
                "create",
                "cluster",
                "--name",
                name,
                "--image",
                image,
                "--config",
                config,
            ],
            timeout=900,
        )
        ref.configure_cluster_access(kind, name)
    except Exception as error:
        try:
            ref.delete_owned_cluster(kind, name)
        except Exception as cleanup_error:
            raise ref.ProofError(
                "kind cluster creation failed and owned cleanup also failed: "
                f"creation={error!r}; cleanup={cleanup_error!r}"
            ) from cleanup_error
        raise


def apply_secret_contracts(kubectl: str, app_password: str, s3_secret_key: str) -> None:
    ref.apply_yaml(
        kubectl,
        [
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": "weltgewebe-ha-s3",
                    "namespace": "weltgewebe-data",
                },
                "type": "Opaque",
                "stringData": {
                    "ACCESS_KEY_ID": S3_ACCESS_KEY,
                    "ACCESS_SECRET_KEY": s3_secret_key,
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": "weltgewebe-ha-app",
                    "namespace": "weltgewebe-data",
                },
                "type": "kubernetes.io/basic-auth",
                "stringData": {"username": APP_USER, "password": app_password},
            },
        ],
    )


def apply_runtime_secret(
    kubectl: str, app_password: str, *, postgres_service: str = "postgres-ha-rw"
) -> None:
    database_url = f"postgres://{APP_USER}:{app_password}@{postgres_service}.weltgewebe-data.svc.cluster.local:5432/weltgewebe"
    ref.apply_yaml(
        kubectl,
        {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "weltgewebe-ha-runtime", "namespace": "weltgewebe"},
            "type": "Opaque",
            "stringData": {"database-url": database_url},
        },
    )


def external_object_store_names(cluster: str) -> tuple[str, str]:
    normalized = cluster.replace("_", "-").replace(".", "-")
    return f"{normalized}-object-store", f"{normalized}-object-store-data"


def start_external_object_store(
    cluster: str, commit: str, s3_secret_key: str
) -> tuple[str, str, str]:
    container, volume = external_object_store_names(cluster)
    if (
        subprocess.run(
            ["docker", "container", "inspect", container], capture_output=True
        ).returncode
        == 0
    ):
        raise ref.ProofError(
            f"external object-store container already exists: {container}"
        )
    if (
        subprocess.run(
            ["docker", "volume", "inspect", volume], capture_output=True
        ).returncode
        == 0
    ):
        raise ref.ProofError(f"external object-store volume already exists: {volume}")
    try:
        ref.run(
            [
                "docker",
                "volume",
                "create",
                "--label",
                f"weltgewebe.net/proof-commit={commit}",
                volume,
            ]
        )
        run_with_environment(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                container,
                "--label",
                f"weltgewebe.net/proof-commit={commit}",
                "--network",
                "kind",
                "--env",
                "AWS_ACCESS_KEY_ID",
                "--env",
                "AWS_SECRET_ACCESS_KEY",
                "--env",
                "S3_BUCKET",
                "--volume",
                f"{volume}:/data",
                SEAWEEDFS_IMAGE,
                "mini",
                "-dir=/data",
                "-ip=0.0.0.0",
            ],
            {
                "AWS_ACCESS_KEY_ID": S3_ACCESS_KEY,
                "AWS_SECRET_ACCESS_KEY": s3_secret_key,
                "S3_BUCKET": S3_BUCKET,
            },
            timeout=120,
        )

        def address_probe() -> str | bool:
            address = ref.output(
                [
                    "docker",
                    "inspect",
                    "--format",
                    '{{(index .NetworkSettings.Networks "kind").IPAddress}}',
                    container,
                ]
            )
            return address if address else False

        address = str(
            wait_until(
                "external object-store address", address_probe, timeout_seconds=60
            )
        )

        def port_probe() -> bool:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "sh",
                    "-c",
                    "wget -qO- http://127.0.0.1:9333/cluster/status >/dev/null",
                ],
                capture_output=True,
            )
            return result.returncode == 0

        wait_until("external object-store readiness", port_probe, timeout_seconds=180)
        return container, volume, address
    except Exception as error:
        try:
            delete_external_object_store(cluster, commit)
        except Exception as cleanup_error:
            raise ref.ProofError(
                "external object-store setup failed and owned cleanup also failed: "
                f"setup={error!r}; cleanup={cleanup_error!r}"
            ) from cleanup_error
        raise


def delete_external_object_store(cluster: str, commit: str) -> None:
    container, volume = external_object_store_names(cluster)
    if (
        subprocess.run(
            ["docker", "container", "inspect", container], capture_output=True
        ).returncode
        == 0
    ):
        label = ref.output(
            [
                "docker",
                "inspect",
                "--format",
                '{{index .Config.Labels "weltgewebe.net/proof-commit"}}',
                container,
            ]
        )
        if label != commit:
            raise ref.ProofError(
                f"refusing to delete foreign object-store container {container}"
            )
        ref.run(["docker", "rm", "--force", container])
    if (
        subprocess.run(
            ["docker", "volume", "inspect", volume], capture_output=True
        ).returncode
        == 0
    ):
        label = ref.output(
            [
                "docker",
                "volume",
                "inspect",
                "--format",
                '{{index .Labels "weltgewebe.net/proof-commit"}}',
                volume,
            ]
        )
        if label != commit:
            raise ref.ProofError(
                f"refusing to delete foreign object-store volume {volume}"
            )
        ref.run(["docker", "volume", "rm", volume])


def apply_ha_data_file(kubectl: str, path: Path) -> None:
    ref.run(
        [
            kubectl,
            "-n",
            "weltgewebe-data",
            "apply",
            "-f",
            str(path),
        ]
    )


def require_restore_prerequisites(kubectl: str) -> None:
    for resource in (
        "service/seaweedfs-s3",
        "objectstore/postgres-ha",
        "imagecatalog/weltgewebe-postgres",
    ):
        observed = ref.output(
            [
                kubectl,
                "-n",
                "weltgewebe-data",
                "get",
                resource,
                "-o",
                "name",
            ]
        )
        if not observed:
            raise ref.ProofError(
                f"restore prerequisite missing from weltgewebe-data: {resource}"
            )


def apply_object_store_endpoint(kubectl: str, address: str) -> None:
    ref.apply_yaml(
        kubectl,
        {
            "apiVersion": "discovery.k8s.io/v1",
            "kind": "EndpointSlice",
            "metadata": {
                "name": "seaweedfs-s3",
                "namespace": "weltgewebe-data",
                "labels": {"kubernetes.io/service-name": "seaweedfs-s3"},
            },
            "addressType": "IPv4",
            "ports": [{"name": "s3", "protocol": "TCP", "port": 8333}],
            "endpoints": [{"addresses": [address], "conditions": {"ready": True}}],
        },
    )


def cnpg_webhook_ready(kubectl: str) -> bool:
    endpoint = subprocess.run(
        [
            kubectl,
            "-n",
            "cnpg-system",
            "get",
            "endpoints",
            "cnpg-webhook-service",
            "-o",
            "jsonpath={.subsets[0].addresses[0].ip}",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=15,
    )
    if endpoint.returncode != 0 or not endpoint.stdout.strip():
        return False
    probe = {
        "apiVersion": "postgresql.cnpg.io/v1",
        "kind": "Cluster",
        "metadata": {"name": "weltgewebe-cnpg-webhook-probe", "namespace": "default"},
        "spec": {"instances": 1, "storage": {"size": "1Gi"}},
    }
    result = subprocess.run(
        [
            kubectl,
            "apply",
            "--server-side",
            "--dry-run=server",
            "--field-manager=weltgewebe-ha-proof",
            "-f",
            "-",
        ],
        cwd=ROOT,
        input=json.dumps(probe),
        text=True,
        capture_output=True,
        timeout=20,
    )
    return result.returncode == 0


def install_cnpg(kubectl: str, artifact: str) -> None:
    source = Path(artifact).read_text(encoding="utf-8")
    tagged = "ghcr.io/cloudnative-pg/cloudnative-pg:1.30.0"
    if source.count(tagged) != 2:
        raise ref.ProofError(
            "CloudNativePG release image reference changed unexpectedly"
        )
    ref.run(
        [
            kubectl,
            "apply",
            "--server-side",
            "--force-conflicts",
            "--field-manager=weltgewebe-ha-proof",
            "-f",
            "-",
        ],
        input_text=source.replace(tagged, CNPG_OPERATOR_IMAGE),
    )
    ref.run(
        [
            kubectl,
            "wait",
            "--for=condition=Established",
            "crd/clusters.postgresql.cnpg.io",
            "--timeout=3m",
        ]
    )
    ref.wait_rollout(kubectl, "cnpg-system", "deployment/cnpg-controller-manager", "8m")
    wait_until(
        "CloudNativePG admission webhook",
        lambda: cnpg_webhook_ready(kubectl),
        timeout_seconds=180,
        interval=2,
    )
    observed = ref.output(
        [
            kubectl,
            "-n",
            "cnpg-system",
            "get",
            "deployment/cnpg-controller-manager",
            "-o",
            "jsonpath={.spec.template.spec.containers[0].image}",
        ]
    )
    if observed != CNPG_OPERATOR_IMAGE:
        raise ref.ProofError(
            f"CloudNativePG operator image is not digest-bound: {observed}"
        )


def apply_digest_bound_release(
    kubectl: str, artifact: str, replacements: dict[str, str], release_name: str
) -> None:
    source = Path(artifact).read_text(encoding="utf-8")
    for tagged, digest_bound in replacements.items():
        if source.count(tagged) != 1:
            raise ref.ProofError(
                f"{release_name} image reference changed unexpectedly: {tagged}"
            )
        source = source.replace(tagged, digest_bound)
    ref.run(
        [
            kubectl,
            "apply",
            "--server-side",
            "--force-conflicts",
            "--field-manager=weltgewebe-ha-proof",
            "-f",
            "-",
        ],
        input_text=source,
        timeout=600,
    )


def install_cert_manager(kubectl: str, artifact: str) -> None:
    apply_digest_bound_release(
        kubectl, artifact, CERT_MANAGER_IMAGES, "cert-manager release"
    )
    ref.run(
        [
            kubectl,
            "wait",
            "--for=condition=Established",
            "crd/certificates.cert-manager.io",
            "--timeout=3m",
        ]
    )
    deployments = ("cert-manager", "cert-manager-cainjector", "cert-manager-webhook")
    for deployment in deployments:
        ref.wait_rollout(kubectl, "cert-manager", f"deployment/{deployment}", "8m")
    expected = {
        "cert-manager": CERT_MANAGER_IMAGES[
            "quay.io/jetstack/cert-manager-controller:v1.21.0"
        ],
        "cert-manager-cainjector": CERT_MANAGER_IMAGES[
            "quay.io/jetstack/cert-manager-cainjector:v1.21.0"
        ],
        "cert-manager-webhook": CERT_MANAGER_IMAGES[
            "quay.io/jetstack/cert-manager-webhook:v1.21.0"
        ],
    }
    observed = {
        name: ref.output(
            [
                kubectl,
                "-n",
                "cert-manager",
                "get",
                f"deployment/{name}",
                "-o",
                "jsonpath={.spec.template.spec.containers[0].image}",
            ]
        )
        for name in deployments
    }
    if observed != expected:
        raise ref.ProofError(
            f"cert-manager release images are not digest-bound: {observed}"
        )


def barman_cloud_release_source(artifact: str) -> str:
    source = Path(artifact).read_text(encoding="utf-8")
    controller_tagged = "ghcr.io/cloudnative-pg/plugin-barman-cloud:v0.13.0"
    if source.count(controller_tagged) != 1:
        raise ref.ProofError(
            "Barman Cloud plugin controller image reference changed unexpectedly"
        )

    lines = source.splitlines(keepends=True)
    markers = [
        index for index, line in enumerate(lines) if line.strip() == "SIDECAR_IMAGE: |"
    ]
    if len(markers) != 1:
        raise ref.ProofError(
            f"Barman Cloud plugin sidecar image secret changed unexpectedly: {len(markers)} markers"
        )
    start = markers[0] + 1
    end = start
    while end < len(lines) and lines[end].startswith("    "):
        end += 1
    encoded = "".join(line.strip() for line in lines[start:end])
    try:
        observed = base64.b64decode(encoded, validate=True).decode("utf-8")
    except Exception as error:
        raise ref.ProofError(
            "Barman Cloud plugin sidecar image secret is not valid base64 UTF-8"
        ) from error
    sidecar_tagged = "ghcr.io/cloudnative-pg/plugin-barman-cloud-sidecar:v0.13.0"
    if observed != sidecar_tagged:
        raise ref.ProofError(
            f"Barman Cloud plugin sidecar image reference changed unexpectedly: {observed}"
        )
    replacement = base64.b64encode(BARMAN_PLUGIN_SIDECAR_IMAGE.encode("utf-8")).decode(
        "ascii"
    )
    lines[start:end] = [
        f"    {replacement[offset : offset + 76]}\n"
        for offset in range(0, len(replacement), 76)
    ]
    return "".join(lines).replace(controller_tagged, BARMAN_PLUGIN_IMAGE, 1)


def install_barman_cloud_plugin(kubectl: str, artifact: str) -> dict[str, str]:
    source = barman_cloud_release_source(artifact)
    ref.run(
        [
            kubectl,
            "apply",
            "--server-side",
            "--force-conflicts",
            "--field-manager=weltgewebe-ha-proof",
            "-f",
            "-",
        ],
        input_text=source,
        timeout=600,
    )
    ref.run(
        [
            kubectl,
            "wait",
            "--for=condition=Established",
            "crd/objectstores.barmancloud.cnpg.io",
            "--timeout=3m",
        ]
    )
    ref.wait_rollout(kubectl, "cnpg-system", "deployment/barman-cloud", "8m")
    deployment = json.loads(
        ref.output(
            [
                kubectl,
                "-n",
                "cnpg-system",
                "get",
                "deployment/barman-cloud",
                "-o",
                "json",
            ]
        )
    )
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    observed_controller = container.get("image", "")
    if observed_controller != BARMAN_PLUGIN_IMAGE:
        raise ref.ProofError(
            f"Barman Cloud plugin image is not digest-bound: {observed_controller}"
        )
    try:
        secret_name = next(
            item["valueFrom"]["secretKeyRef"]["name"]
            for item in container.get("env", [])
            if item.get("name") == "SIDECAR_IMAGE"
        )
    except (KeyError, StopIteration, TypeError) as error:
        raise ref.ProofError(
            "Barman Cloud plugin deployment lacks its sidecar image secret reference"
        ) from error
    encoded_sidecar = ref.output(
        [
            kubectl,
            "-n",
            "cnpg-system",
            "get",
            f"secret/{secret_name}",
            "-o",
            "jsonpath={.data.SIDECAR_IMAGE}",
        ]
    )
    try:
        observed_sidecar = base64.b64decode(encoded_sidecar, validate=True).decode(
            "utf-8"
        )
    except Exception as error:
        raise ref.ProofError(
            "Barman Cloud plugin sidecar image secret is unreadable"
        ) from error
    if observed_sidecar != BARMAN_PLUGIN_SIDECAR_IMAGE:
        raise ref.ProofError(
            f"Barman Cloud plugin sidecar image is not digest-bound: {observed_sidecar}"
        )
    return {
        "controller_image": observed_controller,
        "sidecar_image": observed_sidecar,
        "sidecar_secret": secret_name,
    }


def current_primary(kubectl: str, cluster: str = "postgres-ha") -> str:
    return ref.output(
        [
            kubectl,
            "-n",
            "weltgewebe-data",
            "get",
            f"cluster/{cluster}",
            "-o",
            "jsonpath={.status.currentPrimary}",
        ]
    )


def wait_cluster_ready(kubectl: str, cluster: str, timeout: str = "15m") -> None:
    ref.wait_condition(
        kubectl, "weltgewebe-data", f"cluster/{cluster}", "Ready", timeout
    )


def psql(kubectl: str, sql: str, *, cluster: str = "postgres-ha") -> str:
    primary = current_primary(kubectl, cluster)
    if not primary:
        raise ref.ProofError(f"PostgreSQL cluster {cluster} has no current primary")
    return ref.output(
        [
            kubectl,
            "-n",
            "weltgewebe-data",
            "exec",
            primary,
            "--",
            "psql",
            "-d",
            "weltgewebe",
            "-Atqc",
            sql,
        ]
    )


def postgres_archiver_state(
    kubectl: str, *, cluster: str = "postgres-ha"
) -> dict[str, Any]:
    sql = (
        "SELECT json_build_object("
        "'archived_count',archived_count,"
        "'last_archived_wal',last_archived_wal,"
        "'last_archived_time',to_char(last_archived_time AT TIME ZONE 'UTC',"
        '\'YYYY-MM-DD"T"HH24:MI:SS.US"Z"\'),'
        "'failed_count',failed_count,"
        "'last_failed_wal',last_failed_wal,"
        "'last_failed_time',to_char(last_failed_time AT TIME ZONE 'UTC',"
        '\'YYYY-MM-DD"T"HH24:MI:SS.US"Z"\'),'
        "'stats_reset',to_char(stats_reset AT TIME ZONE 'UTC',"
        '\'YYYY-MM-DD"T"HH24:MI:SS.US"Z"\'))::text '
        "FROM pg_stat_archiver"
    )
    document = json.loads(psql(kubectl, sql, cluster=cluster))
    required = {"archived_count", "failed_count", "stats_reset"}
    if not isinstance(document, dict) or not required.issubset(document):
        raise ref.ProofError(f"invalid pg_stat_archiver payload: {document!r}")
    document["archived_count"] = int(document["archived_count"])
    document["failed_count"] = int(document["failed_count"])
    return document


def wait_postgres_archive_progress(
    kubectl: str,
    before: dict[str, Any],
    *,
    cluster: str = "postgres-ha",
    timeout_seconds: int = 300,
    interval: float = 2.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last = postgres_archiver_state(kubectl, cluster=cluster)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            time.sleep(interval)
            continue
        if last.get("stats_reset") != before.get("stats_reset"):
            raise ref.ProofError(
                "PostgreSQL archiver statistics reset during the WAL proof"
            )
        if int(last["failed_count"]) > int(before["failed_count"]):
            raise ref.ProofError(
                "PostgreSQL WAL archiving reported a new failure: "
                f"before={before!r}; after={last!r}"
            )
        if (
            int(last["archived_count"]) > int(before["archived_count"])
            and last.get("last_archived_wal")
            and last.get("last_archived_wal") != before.get("last_archived_wal")
        ):
            return last
        time.sleep(interval)
    raise ref.ProofError(
        "timed out waiting for PostgreSQL WAL archive progress; "
        f"before={before!r}; last={last!r}"
    )


def barman_sidecar_images(kubectl: str, cluster: str) -> dict[str, dict[str, object]]:
    document = json.loads(
        ref.output(
            [
                kubectl,
                "-n",
                "weltgewebe-data",
                "get",
                "pods",
                "-l",
                f"cnpg.io/cluster={cluster}",
                "-o",
                "json",
            ]
        )
    )
    result: dict[str, dict[str, object]] = {}
    for pod in document.get("items", []):
        name = pod.get("metadata", {}).get("name", "")
        spec = pod.get("spec", {})
        containers = [
            *spec.get("initContainers", []),
            *spec.get("containers", []),
        ]
        sidecars = [
            item for item in containers if item.get("name") == "plugin-barman-cloud"
        ]
        if len(sidecars) != 1:
            raise ref.ProofError(
                f"PostgreSQL pod {name} has {len(sidecars)} Barman sidecars"
            )
        declared = sidecars[0].get("image", "")
        if declared != BARMAN_PLUGIN_SIDECAR_IMAGE:
            raise ref.ProofError(
                f"PostgreSQL pod {name} has an unbound Barman sidecar: {declared}"
            )
        statuses = [
            *pod.get("status", {}).get("initContainerStatuses", []),
            *pod.get("status", {}).get("containerStatuses", []),
        ]
        status = next(
            (item for item in statuses if item.get("name") == "plugin-barman-cloud"),
            {},
        )
        image_id = str(status.get("imageID", ""))
        if "@sha256:" not in image_id:
            raise ref.ProofError(
                f"PostgreSQL pod {name} lacks a digest runtime image ID: {image_id}"
            )
        ready = status.get("ready") is True
        running = status.get("state", {}).get("running")
        started_at = (
            str(running.get("startedAt", "")) if isinstance(running, dict) else ""
        )
        if not ready or not started_at:
            raise ref.ProofError(
                f"PostgreSQL pod {name} Barman sidecar is not ready and running: {status}"
            )
        result[name] = {
            "declared_image": declared,
            "runtime_image_id": image_id,
            "ready": ready,
            "running_started_at": started_at,
        }
    if len(result) != 3:
        raise ref.ProofError(
            f"expected three digest-bound Barman sidecars for {cluster}, got {result}"
        )
    return result


def pod_topology(
    kubectl: str, namespace: str, selector: str
) -> dict[str, dict[str, str]]:
    pods = json.loads(
        ref.output(
            [kubectl, "-n", namespace, "get", "pods", "-l", selector, "-o", "json"]
        )
    )
    nodes = json.loads(ref.output([kubectl, "get", "nodes", "-o", "json"]))
    zones = {
        item["metadata"]["name"]: item["metadata"]
        .get("labels", {})
        .get("topology.kubernetes.io/zone", "")
        for item in nodes["items"]
    }
    result: dict[str, dict[str, str]] = {}
    for item in pods["items"]:
        node = item.get("spec", {}).get("nodeName", "")
        if node:
            result[item["metadata"]["name"]] = {
                "node": node,
                "zone": zones.get(node, ""),
            }
    return result


def require_zones(
    topology: dict[str, dict[str, str]], expected: int, component: str
) -> None:
    zones = {item["zone"] for item in topology.values() if item["zone"]}
    if len(topology) < expected or len(zones) != expected:
        raise ref.ProofError(
            f"{component} is not spread across {expected} zones: {topology}"
        )


def require_container_stopped(name: str) -> None:
    running = ref.output(["docker", "inspect", "--format", "{{.State.Running}}", name])
    if running != "false":
        raise ref.ProofError(
            f"failure-domain container unexpectedly running during degraded proof: {name}"
        )


def wait_api_replicas(kubectl: str, expected: int = 3) -> None:
    ref.wait_rollout(kubectl, "weltgewebe", "deployment/weltgewebe-api", "10m")
    available = ref.output(
        [
            kubectl,
            "-n",
            "weltgewebe",
            "get",
            "deployment/weltgewebe-api",
            "-o",
            "jsonpath={.status.availableReplicas}",
        ]
    )
    if available != str(expected):
        raise ref.ProofError(
            f"expected {expected} available API replicas, got {available!r}"
        )
    ref.wait_rollout(kubectl, "weltgewebe", "deployment/weltgewebe-web", "10m")


def insert_domain_node(
    kubectl: str, node_id: str, title: str, *, cluster: str = "postgres-ha"
) -> None:
    payload = json.dumps(
        {"summary": "HA recovery proof", "tags": ["ha-proof"]}, separators=(",", ":")
    )
    sql = (
        "INSERT INTO domain_nodes (id,kind,title,lat,lon,created_at,updated_at,payload) VALUES ("
        + "'"
        + node_id
        + "','Werkstatt','"
        + title.replace("'", "''")
        + "',53.55,9.99,clock_timestamp(),clock_timestamp(),'"
        + payload.replace("'", "''")
        + "'::jsonb) ON CONFLICT (id) DO NOTHING"
    )
    psql(kubectl, sql, cluster=cluster)


def node_exists(kubectl: str, node_id: str, *, cluster: str = "postgres-ha") -> bool:
    return (
        psql(
            kubectl,
            f"SELECT count(*) FROM domain_nodes WHERE id='{node_id}'",
            cluster=cluster,
        )
        == "1"
    )


def gateway_contains_node(kubectl: str, kind: str, cluster: str, node_id: str) -> bool:
    ref.wait_condition(
        kubectl, "weltgewebe-gateway", "gateway/weltgewebe", "Programmed", "5m"
    )
    service = ref.output(
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
    port = ref.gateway_listener_port(kubectl)
    _, _, _, _, body = ref.probe_gateway_http(
        kind,
        cluster,
        ref.gateway_addresses(kubectl),
        ref.gateway_service_listener_port(kubectl, service, port),
        timeout_seconds=30,
    )
    payload = json.loads(body)
    return any(isinstance(item, dict) and item.get("id") == node_id for item in payload)


def create_nats_box(kubectl: str, zone: str) -> None:
    ref.apply_yaml(
        kubectl,
        {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": "nats-box", "namespace": "weltgewebe-data"},
            "spec": {
                "automountServiceAccountToken": False,
                "nodeSelector": {"topology.kubernetes.io/zone": zone},
                "restartPolicy": "Never",
                "securityContext": {
                    "runAsNonRoot": True,
                    "runAsUser": 1000,
                    "runAsGroup": 1000,
                    "seccompProfile": {"type": "RuntimeDefault"},
                },
                "containers": [
                    {
                        "name": "nats-box",
                        "image": NATS_BOX_IMAGE,
                        "command": ["/bin/sh", "-c", "sleep 7200"],
                        "securityContext": {
                            "allowPrivilegeEscalation": False,
                            "capabilities": {"drop": ["ALL"]},
                        },
                        "resources": {
                            "requests": {"cpu": "20m", "memory": "32Mi"},
                            "limits": {"cpu": "200m", "memory": "128Mi"},
                        },
                    }
                ],
            },
        },
    )
    ref.wait_condition(kubectl, "weltgewebe-data", "pod/nats-box", "Ready", "5m")


def nats(
    kubectl: str, args: list[str], *, check: bool = True
) -> subprocess.CompletedProcess[str]:
    argv = [
        kubectl,
        "-n",
        "weltgewebe-data",
        "exec",
        "nats-box",
        "--",
        "nats",
        "--server",
        "nats://nats:4222",
        "--js-domain",
        "weltgewebe-ha",
        *args,
    ]
    return (
        ref.run(argv, capture=True)
        if check
        else subprocess.run(argv, cwd=ROOT, text=True, capture_output=True)
    )


def nats_message_count(kubectl: str) -> int:
    document = json.loads(
        nats(kubectl, ["stream", "info", "WG_PROOF", "--json"]).stdout
    )
    return int(document.get("state", {}).get("messages", -1))


def backup_document(name: str) -> dict[str, Any]:
    return {
        "apiVersion": "postgresql.cnpg.io/v1",
        "kind": "Backup",
        "metadata": {"name": name, "namespace": "weltgewebe-data"},
        "spec": {
            "method": "plugin",
            "target": "primary",
            "cluster": {"name": "postgres-ha"},
            "pluginConfiguration": {"name": "barman-cloud.cloudnative-pg.io"},
        },
    }


def wait_backup_complete(
    kubectl: str,
    name: str,
    *,
    timeout_seconds: int = 1200,
    interval: float = 5,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_status: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            document = json.loads(
                ref.output(
                    [
                        kubectl,
                        "-n",
                        "weltgewebe-data",
                        "get",
                        f"backup/{name}",
                        "-o",
                        "json",
                    ]
                )
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            time.sleep(interval)
            continue
        last_status = document.get("status", {})
        phase = str(last_status.get("phase", "")).lower()
        if phase == "completed":
            return document
        if phase in {"failed", "error"}:
            raise ref.ProofError(
                f"CloudNativePG backup {name} entered terminal phase {phase}: "
                f"{json.dumps(last_status, sort_keys=True)}"
            )
        time.sleep(interval)
    raise ref.ProofError(
        f"timed out waiting for CloudNativePG backup {name}; "
        f"last_status={json.dumps(last_status, sort_keys=True)}"
    )


def ha_diagnostic_snapshot(kubectl: str, name: str) -> None:
    ref.diagnostic_snapshot(kubectl, name)
    target = CACHE / "failures" / name
    target.mkdir(parents=True, exist_ok=True)
    commands = {
        "postgres-backup-and-cluster.yaml": [
            kubectl,
            "-n",
            "weltgewebe-data",
            "get",
            "backups,clusters",
            "-o",
            "yaml",
        ],
        "barman-object-store.yaml": [
            kubectl,
            "-n",
            "weltgewebe-data",
            "get",
            "objectstore/postgres-ha",
            "-o",
            "yaml",
        ],
        "barman-plugin.log": [
            kubectl,
            "-n",
            "cnpg-system",
            "logs",
            "deployment/barman-cloud",
            "--all-containers=true",
            "--tail=2000",
        ],
        "cnpg-operator.log": [
            kubectl,
            "-n",
            "cnpg-system",
            "logs",
            "deployment/cnpg-controller-manager",
            "--all-containers=true",
            "--tail=2000",
        ],
        "postgres-instances.log": [
            kubectl,
            "-n",
            "weltgewebe-data",
            "logs",
            "-l",
            "cnpg.io/cluster",
            "--all-containers=true",
            "--prefix=true",
            "--tail=2000",
            "--max-log-requests=10",
        ],
    }
    for filename, argv in commands.items():
        result = subprocess.run(argv, cwd=ROOT, text=True, capture_output=True)
        (target / filename).write_text(result.stdout + result.stderr, encoding="utf-8")


def restore_cluster_document(target_time: str) -> dict[str, Any]:
    return {
        "apiVersion": "postgresql.cnpg.io/v1",
        "kind": "Cluster",
        "metadata": {"name": "postgres-restore", "namespace": "weltgewebe-data"},
        "spec": {
            "instances": 3,
            "imageCatalogRef": {
                "apiGroup": "postgresql.cnpg.io",
                "kind": "ImageCatalog",
                "name": "weltgewebe-postgres",
                "major": 16,
            },
            "bootstrap": {
                "recovery": {
                    "source": "postgres-ha",
                    "database": "weltgewebe",
                    "owner": APP_USER,
                    "secret": {"name": "weltgewebe-ha-app"},
                    "recoveryTarget": {"targetTime": target_time, "exclusive": True},
                }
            },
            "externalClusters": [
                {
                    "name": "postgres-ha",
                    "plugin": {
                        "name": "barman-cloud.cloudnative-pg.io",
                        "parameters": {
                            "barmanObjectName": "postgres-ha",
                            "serverName": "postgres-ha",
                        },
                    },
                }
            ],
            "storage": {"size": "1Gi"},
            "resources": {
                "requests": {"cpu": "100m", "memory": "256Mi"},
                "limits": {"cpu": "1", "memory": "1Gi"},
            },
            "affinity": {
                "enablePodAntiAffinity": True,
                "podAntiAffinityType": "required",
                "topologyKey": "topology.kubernetes.io/zone",
                "nodeSelector": {"weltgewebe.net/data-node": "true"},
            },
        },
    }


def prove(args: argparse.Namespace) -> dict[str, Any]:
    if ref.output(["git", "status", "--porcelain"]):
        raise ref.ProofError(
            "HA recovery proof requires a clean, commit-bound worktree"
        )
    commit = ref.output(["git", "rev-parse", "HEAD"])
    timestamp = ref.output(["git", "show", "-s", "--format=%cI", "HEAD"])
    ref.require_host_tools()
    receipt = ref.tool_receipt()
    tools = receipt["tools"]
    kind, kubectl, kustomize, flux, helm = (
        tools[name] for name in ("kind", "kubectl", "kustomize", "flux", "helm")
    )
    restore_name = f"{args.cluster}-restore"
    ref.assert_available_cluster_name(kind, args.cluster)
    ref.assert_available_cluster_name(kind, restore_name)
    created_primary = created_restore = object_store_created = False
    stopped_node = ""
    object_store_address = ""
    app_password = secrets.token_urlsafe(24)
    s3_secret_key = secrets.token_urlsafe(32)
    try:
        create_kind_cluster(
            kind,
            args.cluster,
            receipt["kubernetes"]["kind_node_image"],
            "platform/clusters/ha/kind.yaml",
            commit,
        )
        created_primary = True
        image_ids = ref.build_images(kind, args.cluster, commit, timestamp)
        ref.install_platform_components(
            kubectl,
            flux,
            helm,
            receipt["artifacts"],
            ref.control_plane_address(args.cluster),
        )
        ref.run(
            [kubectl, "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=8m"]
        )
        _, _, object_store_address = start_external_object_store(
            args.cluster, commit, s3_secret_key
        )
        object_store_created = True
        ref.apply_file(kubectl, ROOT / "platform/infrastructure/ha-data/namespace.yaml")
        apply_secret_contracts(kubectl, app_password, s3_secret_key)
        ref.apply_file(
            kubectl, ROOT / "platform/infrastructure/ha-data/object-store.yaml"
        )
        apply_object_store_endpoint(kubectl, object_store_address)
        install_cnpg(kubectl, receipt["artifacts"]["cloudnative_pg_operator"])
        install_cert_manager(kubectl, receipt["artifacts"]["cert_manager"])
        plugin_release = install_barman_cloud_plugin(
            kubectl, receipt["artifacts"]["barman_cloud_plugin"]
        )
        ref.apply_direct(kubectl, kustomize, "platform/infrastructure/ha-data")
        ref.wait_rollout(kubectl, "weltgewebe-data", "statefulset/nats", "12m")
        wait_cluster_ready(kubectl, "postgres-ha", "15m")
        primary_sidecars = barman_sidecar_images(kubectl, "postgres-ha")
        ref.apply_file(
            kubectl, ROOT / "platform/apps/weltgewebe/migration/ha/namespace.yaml"
        )
        apply_runtime_secret(kubectl, app_password)
        ref.apply_direct(kubectl, kustomize, "platform/apps/weltgewebe/migration/ha")
        ref.wait_condition(
            kubectl, "weltgewebe", "job/weltgewebe-migration", "Complete", "10m"
        )
        ref.apply_direct(kubectl, kustomize, "platform/apps/weltgewebe/overlays/ha")
        ref.apply_direct(kubectl, kustomize, "platform/infrastructure/gateway")
        wait_api_replicas(kubectl)
        gateway_before = ref.prove_gateway(kubectl, kind, args.cluster)

        topology = {
            "postgres": pod_topology(
                kubectl, "weltgewebe-data", "cnpg.io/cluster=postgres-ha"
            ),
            "nats": pod_topology(
                kubectl, "weltgewebe-data", "app.kubernetes.io/name=nats"
            ),
            "api": pod_topology(
                kubectl, "weltgewebe", "app.kubernetes.io/name=weltgewebe-api"
            ),
        }
        for component, observed in topology.items():
            require_zones(observed, 3, component)

        marker = "00000000-0000-4000-8000-00000000a004"
        insert_domain_node(kubectl, marker, "T004 acknowledged domain mutation")
        wait_until(
            "domain mutation in API projection",
            lambda: gateway_contains_node(kubectl, kind, args.cluster, marker),
            timeout_seconds=180,
        )

        primary_before = current_primary(kubectl)
        primary_topology = topology["postgres"].get(primary_before)
        if not primary_topology:
            raise ref.ProofError(f"primary pod missing from topology: {primary_before}")
        failure_zone = primary_topology["zone"]
        stopped_node = primary_topology["node"]
        alternate_zone = next(
            zone for zone in ("zone-a", "zone-b", "zone-c") if zone != failure_zone
        )
        create_nats_box(kubectl, alternate_zone)
        nats(
            kubectl,
            [
                "stream",
                "add",
                "WG_PROOF",
                "--subjects",
                "wg.proof",
                "--storage",
                "file",
                "--replicas",
                "3",
                "--retention",
                "limits",
                "--max-msgs",
                "100",
                "--defaults",
            ],
        )
        nats(kubectl, ["pub", "wg.proof", "before-zone-failure"])
        if nats_message_count(kubectl) != 1:
            raise ref.ProofError("JetStream did not acknowledge the baseline message")

        failure_started = time.monotonic()
        ref.run(["docker", "stop", "--time", "10", stopped_node], timeout=60)

        def new_primary_probe():
            candidate = current_primary(kubectl)
            return candidate if candidate and candidate != primary_before else False

        primary_after = str(
            wait_until(
                "PostgreSQL primary failover", new_primary_probe, timeout_seconds=180
            )
        )
        postgres_rto = time.monotonic() - failure_started
        wait_until(
            "acknowledged domain mutation after failover",
            lambda: node_exists(kubectl, marker),
            timeout_seconds=60,
        )
        wait_until(
            "API projection after zone failure",
            lambda: gateway_contains_node(kubectl, kind, args.cluster, marker),
            timeout_seconds=180,
        )
        api_rto = time.monotonic() - failure_started

        def nats_publish_probe():
            result = nats(
                kubectl, ["pub", "wg.proof", "after-zone-failure"], check=False
            )
            return result.returncode == 0

        wait_until(
            "JetStream publish after zone failure",
            nats_publish_probe,
            timeout_seconds=120,
            interval=1,
        )
        nats_rto = time.monotonic() - failure_started
        if nats_message_count(kubectl) != 2:
            raise ref.ProofError(
                "JetStream lost an acknowledged message during zone failure"
            )

        require_container_stopped(stopped_node)

        before_id = "00000000-0000-4000-8000-00000000b004"
        after_id = "00000000-0000-4000-8000-00000000c004"
        insert_domain_node(kubectl, before_id, "T004 before PITR target")
        backup_name = f"t004-{commit[:8]}"
        ref.apply_yaml(kubectl, backup_document(backup_name))
        backup = wait_backup_complete(kubectl, backup_name)
        target_time = psql(
            kubectl,
            "SELECT to_char(clock_timestamp() AT TIME ZONE 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')",
        )
        time.sleep(2)
        insert_domain_node(kubectl, after_id, "T004 after PITR target")
        archiver_before = postgres_archiver_state(kubectl)
        psql(kubectl, "SELECT pg_switch_wal()")
        archiver_after = wait_postgres_archive_progress(kubectl, archiver_before)

        create_kind_cluster(
            kind,
            restore_name,
            receipt["kubernetes"]["kind_node_image"],
            "platform/clusters/ha/restore-kind.yaml",
            commit,
        )
        created_restore = True
        restore_kubectl = kubectl
        ref.run(
            [
                restore_kubectl,
                "wait",
                "--for=condition=Ready",
                "nodes",
                "--all",
                "--timeout=8m",
            ]
        )
        ref.apply_file(
            restore_kubectl, ROOT / "platform/infrastructure/ha-data/namespace.yaml"
        )
        apply_secret_contracts(restore_kubectl, app_password, s3_secret_key)
        apply_ha_data_file(
            restore_kubectl, ROOT / "platform/infrastructure/ha-data/object-store.yaml"
        )
        apply_object_store_endpoint(restore_kubectl, object_store_address)
        install_cnpg(restore_kubectl, receipt["artifacts"]["cloudnative_pg_operator"])
        install_cert_manager(restore_kubectl, receipt["artifacts"]["cert_manager"])
        install_barman_cloud_plugin(
            restore_kubectl, receipt["artifacts"]["barman_cloud_plugin"]
        )
        apply_ha_data_file(
            restore_kubectl,
            ROOT / "platform/infrastructure/ha-data/barman-object-store.yaml",
        )
        apply_ha_data_file(
            restore_kubectl,
            ROOT / "platform/infrastructure/ha-data/postgres-image-catalog.yaml",
        )
        require_restore_prerequisites(restore_kubectl)
        restore_started = time.monotonic()
        ref.apply_yaml(restore_kubectl, restore_cluster_document(target_time))
        wait_cluster_ready(restore_kubectl, "postgres-restore", "20m")
        restore_sidecars = barman_sidecar_images(restore_kubectl, "postgres-restore")
        restore_rto = time.monotonic() - restore_started
        restored_topology = pod_topology(
            restore_kubectl, "weltgewebe-data", "cnpg.io/cluster=postgres-restore"
        )
        require_zones(restored_topology, 3, "restored postgres")
        preserved = {
            marker: node_exists(restore_kubectl, marker, cluster="postgres-restore"),
            before_id: node_exists(
                restore_kubectl, before_id, cluster="postgres-restore"
            ),
            after_id: node_exists(
                restore_kubectl, after_id, cluster="postgres-restore"
            ),
        }
        if preserved != {marker: True, before_id: True, after_id: False}:
            raise ref.ProofError(f"PITR data comparison failed: {preserved}")
        require_container_stopped(stopped_node)

        result = {
            "schema_version": 1,
            "status": "pass",
            "commit": commit,
            "primary_cluster": args.cluster,
            "restore_cluster": restore_name,
            "tool_lock_sha256": receipt["lock_sha256"],
            "image_ids": image_ids,
            "topology": topology,
            "restored_topology": restored_topology,
            "zone_failure": {
                "zone": failure_zone,
                "node": primary_topology["node"],
                "postgres_primary_before": primary_before,
                "postgres_primary_after": primary_after,
                "postgres_rto_seconds": round(postgres_rto, 3),
                "api_rto_seconds": round(api_rto, 3),
                "nats_rto_seconds": round(nats_rto, 3),
                "acknowledged_domain_mutation_preserved": True,
                "acknowledged_jetstream_messages": 2,
                "remained_unavailable_through_backup_and_restore": True,
            },
            "backup": {
                "name": backup_name,
                "phase": backup.get("status", {}).get("phase"),
                "method": backup.get("spec", {}).get("method"),
                "target": backup.get("spec", {}).get("target"),
                "plugin": backup.get("spec", {})
                .get("pluginConfiguration", {})
                .get("name"),
                "object_store": "postgres-ha",
                "target_time": target_time,
                "plugin_release": plugin_release,
                "sidecar_images": primary_sidecars,
                "wal_archive": {"before": archiver_before, "after": archiver_after},
            },
            "restore": {
                "rto_seconds": round(restore_rto, 3),
                "pitr_comparison": preserved,
                "blank_kind_cluster": True,
                "sidecar_images": restore_sidecars,
            },
            "gateway_before": gateway_before,
            "production_changed": False,
            "does_not_establish": [
                "production rollout",
                "managed multi-region object-store durability",
                "RTO or RPO under production load",
                "survival of two simultaneous failure domains",
                "automatic reintegration of the failed zone",
            ],
        }
        target = CACHE / "receipts"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"{args.cluster}-{commit}-ha-recovery.json"
        path.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        result["receipt_path"] = str(path)
        result["receipt_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result
    except Exception:
        if created_primary:
            ref.configure_cluster_access(kind, args.cluster)
            ha_diagnostic_snapshot(kubectl, args.cluster)
        if created_restore:
            ref.configure_cluster_access(kind, restore_name)
            ha_diagnostic_snapshot(kubectl, restore_name)
        raise
    finally:
        if stopped_node:
            subprocess.run(["docker", "start", stopped_node], capture_output=True)
        if created_restore and not args.keep:
            ref.delete_owned_cluster(kind, restore_name)
        if created_primary and not args.keep:
            ref.delete_owned_cluster(kind, args.cluster)
        if object_store_created and not args.keep:
            delete_external_object_store(args.cluster, commit)


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    proof_parser = sub.add_parser("proof")
    proof_parser.add_argument("--cluster", default=DEFAULT_CLUSTER)
    proof_parser.add_argument("--keep", action="store_true")
    down = sub.add_parser("down")
    down.add_argument("--cluster", default=DEFAULT_CLUSTER)
    down.add_argument("--commit", required=True)
    return parser


def main() -> int:
    args = argument_parser().parse_args()
    try:
        receipt = ref.tool_receipt()
        if args.command == "down":
            kind = receipt["tools"]["kind"]
            for name in (f"{args.cluster}-restore", args.cluster):
                if ref.marker_path(name).exists():
                    ref.delete_owned_cluster(kind, name)
            delete_external_object_store(args.cluster, args.commit)
            print(json.dumps({"status": "deleted", "cluster": args.cluster}))
            return 0
        prove(args)
    except (
        ref.ProofError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as error:
        if isinstance(error, subprocess.CalledProcessError):
            detail = f"subprocess exited with status {error.returncode}"
        elif isinstance(error, subprocess.TimeoutExpired):
            detail = "subprocess timed out"
        else:
            detail = str(error)
        print(f"HA recovery proof failed: {detail}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "pass"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
