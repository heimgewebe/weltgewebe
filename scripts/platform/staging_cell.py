#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import stat
import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_ROOT = Path.home() / ".local/state/weltgewebe/staging-cell"
DEFAULT_CLUSTER = "weltgewebe-staging"
SOURCE_NAME = "weltgewebe-staging-source"
DATA_KUSTOMIZATION = "weltgewebe-staging-data"
DATA_NAMESPACE = "weltgewebe-data"
APP_NAMESPACE = "weltgewebe-staging"
DATABASE_SECRET = "weltgewebe-staging-database"
RUNTIME_SECRET = "weltgewebe-runtime"
PUBLIC_REPOSITORY = "https://github.com/heimgewebe/weltgewebe"
DATA_CLIENT_LABEL = "weltgewebe.net/data-client"  # commonthing-naming: legacy
SECRET_SOURCE_ANNOTATION = "commonthing.net/external-secret-source-sha256"
REQUIRED_TOOLS = ("kind", "kubectl", "kustomize", "flux", "helm")
REQUIRED_ARTIFACTS = (
    "gateway_api_gatewayclasses",
    "gateway_api_gateways",
    "gateway_api_httproutes",
    "gateway_api_referencegrants",
    "gateway_api_grpcroutes",
    "cilium_chart",
)

sys.path.insert(0, str(ROOT / "scripts/platform"))
import kind_reference as reference  # noqa: E402


class StagingCellError(RuntimeError):
    pass


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run(
    argv: list[str],
    *,
    input_text: str | None = None,
    capture: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    print("+ external command [arguments redacted]", flush=True)
    return subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        input=input_text,
        capture_output=capture,
        check=True,
        timeout=timeout,
    )


def output(argv: list[str], *, timeout: int | None = None) -> str:
    return run(argv, capture=True, timeout=timeout).stdout.strip()


def atomic_json(path: Path, payload: dict[str, Any], *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        handle = os.fdopen(fd, "w", encoding="utf-8")
        fd = -1
        with handle:
            os.fchmod(handle.fileno(), mode)
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, mode)
    finally:
        if fd >= 0:
            os.close(fd)
        tmp.unlink(missing_ok=True)


def atomic_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        handle = os.fdopen(fd, "w", encoding="utf-8")
        fd = -1
        with handle:
            os.fchmod(handle.fileno(), mode)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, mode)
    finally:
        if fd >= 0:
            os.close(fd)
        tmp.unlink(missing_ok=True)


def state_root(value: str | None) -> Path:
    resolved = Path(value).expanduser().resolve() if value else DEFAULT_STATE_ROOT.resolve()
    expected = DEFAULT_STATE_ROOT.resolve()
    if resolved != expected:
        raise StagingCellError(f"state root must be exactly {expected}")
    return resolved


def configure_reference_paths(root: Path) -> None:
    reference.CACHE = root
    reference.MARKERS = root / "clusters"
    reference.KUBECONFIGS = root / "kubeconfigs"
    reference.OCI_MIRROR_STATE = root / "oci-mirror"


def load_tool_receipt(root: Path) -> dict[str, Any]:
    receipt_path = root / "toolchain/receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise StagingCellError(
            "pinned toolchain receipt is missing; run bootstrap_tools.py into the T084 state root first"
        )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    lock_path = ROOT / "platform/toolchain.lock.json"
    expected_lock = sha256_file(lock_path)
    if receipt.get("schema_version") != 1 or receipt.get("lock_sha256") != expected_lock:
        raise StagingCellError("toolchain receipt is not bound to the current platform lock")
    tools = receipt.get("tools") if isinstance(receipt.get("tools"), dict) else {}
    artifacts = receipt.get("artifacts") if isinstance(receipt.get("artifacts"), dict) else {}
    missing_tools = [
        name for name in REQUIRED_TOOLS if not Path(str(tools.get(name, ""))).is_file()
    ]
    missing_artifacts = [
        name
        for name in REQUIRED_ARTIFACTS
        if not Path(str(artifacts.get(name, ""))).is_file()
    ]
    if missing_tools or missing_artifacts:
        raise StagingCellError(
            f"toolchain receipt incomplete: tools={missing_tools} artifacts={missing_artifacts}"
        )
    return receipt


def require_clean_commit(
    source_commit: str | None,
    *,
    expected_commit: str | None = None,
    require_public_main: bool = True,
) -> str:
    if output(["git", "status", "--porcelain"]):
        raise StagingCellError("staging cell mutation requires a clean worktree")
    head = output(["git", "rev-parse", "HEAD"])
    if source_commit is not None and source_commit != head:
        raise StagingCellError(
            f"source commit {source_commit} does not equal worktree HEAD {head}"
        )
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise StagingCellError("worktree HEAD is not a canonical 40-hex commit")
    if expected_commit is not None:
        if len(expected_commit) != 40 or any(
            ch not in "0123456789abcdef" for ch in expected_commit
        ):
            raise StagingCellError("persisted bootstrap commit is not canonical 40-hex")
        if head != expected_commit:
            raise StagingCellError(
                "existing staging cell is pinned to bootstrap commit "
                f"{expected_commit}; current worktree HEAD is {head}"
            )
    if require_public_main:
        public = output(
            ["git", "ls-remote", PUBLIC_REPOSITORY, "refs/heads/main"],
            timeout=30,
        )
        remote_head = public.split()[0] if public else ""
        if remote_head != head:
            raise StagingCellError(
                f"staging bootstrap requires exact public main; local={head} "
                f"public-main={remote_head or 'missing'}"
            )
    return head


def require_singleton_cluster(cluster: str) -> None:
    if cluster != DEFAULT_CLUSTER:
        raise StagingCellError(
            f"staging persistent state is singleton; cluster must be exactly {DEFAULT_CLUSTER!r}"
        )


def load_cell_receipt(root: Path) -> dict[str, Any]:
    path = root / "receipts/cell-bootstrap.json"
    if not path.exists():
        raise StagingCellError("cell bootstrap receipt is missing; refusing unbound operation")
    linked = path.lstat()
    if stat.S_ISLNK(linked.st_mode) or not stat.S_ISREG(linked.st_mode):
        raise StagingCellError("cell bootstrap receipt must be a regular file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise StagingCellError("cell bootstrap receipt is malformed")
    return payload


def require_receipt_cluster(cell: dict[str, Any], cluster: str) -> None:
    recorded = cell.get("cluster")
    if recorded != cluster:
        raise StagingCellError(
            f"--cluster {cluster!r} does not match persisted cluster {recorded!r}"
        )


def recorded_secret_source_sha(root: Path) -> str | None:
    receipt_path = root / "receipts/cell-bootstrap.json"
    if not receipt_path.exists():
        return None
    cell = load_cell_receipt(root)
    external = cell.get("external_secret")
    source_sha = external.get("source_sha256") if isinstance(external, dict) else None
    if (
        not isinstance(source_sha, str)
        or len(source_sha) != 64
        or any(ch not in "0123456789abcdef" for ch in source_sha)
    ):
        raise StagingCellError(
            "cell bootstrap receipt has no canonical external-secret source hash"
        )
    return source_sha


def retained_postgres_state_exists(root: Path) -> bool:
    if (root / "receipts/cell-bootstrap.json").is_file():
        return True
    pgdata = root / "data/postgres"
    if not pgdata.exists():
        return False
    linked = pgdata.lstat()
    if stat.S_ISLNK(linked.st_mode) or not stat.S_ISDIR(linked.st_mode):
        raise StagingCellError("staging PostgreSQL data path must be a regular directory")
    try:
        with os.scandir(pgdata) as entries:
            return next(entries, None) is not None
    except PermissionError:
        # A retained database directory may intentionally be 0700 and owned by
        # the container UID. Inability to inspect it is evidence to preserve,
        # never permission to mint replacement credentials.
        return True


def render_kind_config(root: Path) -> Path:
    template_path = ROOT / "platform/clusters/staging/kind.yaml"
    document = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("kind") != "Cluster":
        raise StagingCellError("staging kind template is malformed")
    nodes = document.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 3:
        raise StagingCellError("staging kind template must contain exactly three nodes")
    data_root = str((root / "data").resolve())
    placeholder = "__COMMONTHING_STAGING_DATA_ROOT__"
    for index, node in enumerate(nodes):
        mounts = node.get("extraMounts") if isinstance(node, dict) else None
        if not isinstance(mounts, list) or len(mounts) != 1:
            raise StagingCellError(
                f"staging kind node {index} mount contract is invalid"
            )
        mount = mounts[0]
        if mount.get("hostPath") != placeholder:
            raise StagingCellError(f"staging kind node {index} hostPath template drift")
        if mount.get("containerPath") != "/var/local/weltgewebe-staging":
            raise StagingCellError(f"staging kind node {index} containerPath drift")
        mount["hostPath"] = data_root
    rendered = yaml.safe_dump(document, sort_keys=False)
    path = root / "generated/kind.yaml"
    atomic_text(path, rendered, mode=0o600)
    return path


def load_or_create_secret_material(root: Path) -> tuple[dict[str, str], str]:
    path = root / "secrets/staging-runtime.json"
    if path.exists():
        linked = path.lstat()
        if stat.S_ISLNK(linked.st_mode) or not stat.S_ISREG(linked.st_mode):
            raise StagingCellError("staging secret source must be a regular file")
        if stat.S_IMODE(linked.st_mode) & 0o077:
            raise StagingCellError(
                "staging secret source must not be group/world accessible"
            )
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
        if retained_postgres_state_exists(root):
            raise StagingCellError(
                "staging secret source is missing while retained PostgreSQL state exists; "
                "restore the original secret source or perform an explicit backup/restore recovery"
            )
        payload = {
            "schema_version": 1,
            "database_user": "weltgewebe",
            "database_name": "weltgewebe",
            "database_password": secrets.token_urlsafe(36),
        }
        atomic_json(path, payload, mode=0o600)
    required = ("database_user", "database_name", "database_password")
    if payload.get("schema_version") != 1 or any(
        not isinstance(payload.get(key), str) or not payload[key] for key in required
    ):
        raise StagingCellError("staging secret source is malformed")
    source_sha = sha256_file(path)
    recorded_sha = recorded_secret_source_sha(root)
    if recorded_sha is not None and not hmac.compare_digest(source_sha, recorded_sha):
        raise StagingCellError(
            "staging secret source differs from the bootstrap receipt while retained PostgreSQL "
            "state exists; restore the original source or use an explicit credential-rotation recovery"
        )
    return {key: str(payload[key]) for key in required}, source_sha


def database_url(material: dict[str, str]) -> str:
    encoded_user = urllib.parse.quote(material["database_user"], safe="")
    encoded_password = urllib.parse.quote(material["database_password"], safe="")
    encoded_db = urllib.parse.quote(material["database_name"], safe="")
    return (
        f"postgres://{encoded_user}:{encoded_password}@postgres.{DATA_NAMESPACE}.svc.cluster.local:5432/"
        f"{encoded_db}?sslmode=disable"
    )


def secret_document_matches(
    document: dict[str, Any],
    *,
    name: str,
    namespace_name: str,
    source_sha: str,
    expected_values: dict[str, str],
) -> bool:
    metadata = document.get("metadata") if isinstance(document, dict) else None
    if not isinstance(metadata, dict):
        return False
    annotations = metadata.get("annotations")
    if (
        metadata.get("name") != name
        or metadata.get("namespace") != namespace_name
        or not isinstance(annotations, dict)
        or annotations.get(SECRET_SOURCE_ANNOTATION) != source_sha
    ):
        return False
    data = document.get("data")
    if not isinstance(data, dict):
        return False
    for key, expected in expected_values.items():
        encoded = data.get(key)
        if not isinstance(encoded, str):
            return False
        try:
            observed = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            return False
        if not hmac.compare_digest(observed, expected.encode("utf-8")):
            return False
    return True


def verify_external_secret_binding(kubectl: str, root: Path) -> dict[str, Any]:
    material, source_sha = load_or_create_secret_material(root)
    expected = {
        "database": (
            DATA_NAMESPACE,
            DATABASE_SECRET,
            {
                "username": material["database_user"],
                "password": material["database_password"],
                "database": material["database_name"],
            },
        ),
        "runtime": (
            APP_NAMESPACE,
            RUNTIME_SECRET,
            {"database-url": database_url(material)},
        ),
    }
    matches: dict[str, bool] = {}
    for label, (namespace_name, name, expected_values) in expected.items():
        document = json.loads(
            output(
                [
                    kubectl,
                    "-n",
                    namespace_name,
                    "get",
                    "secret",
                    name,
                    "-o",
                    "json",
                ]
            )
        )
        matches[label] = secret_document_matches(
            document,
            name=name,
            namespace_name=namespace_name,
            source_sha=source_sha,
            expected_values=expected_values,
        )
    return {
        "database": matches.get("database", False),
        "runtime": matches.get("runtime", False),
        "ready": bool(matches) and all(matches.values()),
    }


def flux_revision_matches_commit(revision: str, commit: str) -> bool:
    if len(commit) != 40 or any(ch not in "0123456789abcdef" for ch in commit):
        return False
    return revision in {commit, f"sha1:{commit}"} or revision.endswith(
        f"@sha1:{commit}"
    )


def apply_yaml(kubectl: str, documents: list[dict[str, Any]] | dict[str, Any]) -> None:
    docs = documents if isinstance(documents, list) else [documents]
    body = "\n---\n".join(
        yaml.safe_dump(doc, sort_keys=False).strip() for doc in docs
    ) + "\n"
    run([kubectl, "apply", "-f", "-"], input_text=body, timeout=120)


def namespace(name: str, *, data_client: bool = False) -> dict[str, Any]:
    labels = {
        "pod-security.kubernetes.io/enforce": "restricted",
        "pod-security.kubernetes.io/audit": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
    }
    if data_client:
        labels[DATA_CLIENT_LABEL] = "true"
    return {
        "apiVersion": "v1",
        "kind": "Namespace",
        "metadata": {"name": name, "labels": labels},
    }


def inject_external_secrets(kubectl: str, root: Path) -> dict[str, str]:
    material, source_sha = load_or_create_secret_material(root)
    username = material["database_user"]
    password = material["database_password"]
    database = material["database_name"]
    runtime_database_url = database_url(material)
    annotations = {SECRET_SOURCE_ANNOTATION: source_sha}
    apply_yaml(kubectl, [namespace(DATA_NAMESPACE), namespace(APP_NAMESPACE, data_client=True)])
    apply_yaml(
        kubectl,
        [
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": DATABASE_SECRET,
                    "namespace": DATA_NAMESPACE,
                    "annotations": annotations,
                },
                "type": "Opaque",
                "stringData": {
                    "username": username,
                    "password": password,
                    "database": database,
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {
                    "name": RUNTIME_SECRET,
                    "namespace": APP_NAMESPACE,
                    "annotations": annotations,
                },
                "type": "Opaque",
                "stringData": {"database-url": runtime_database_url},
            },
        ],
    )
    return {"source_sha256": source_sha, "required_keys": ["database-url"]}


def public_external_secret_state() -> dict[str, Any]:
    return {"bound": True, "required_keys": ["database-url"]}


def prepare_volume_permissions(kind: str, cluster: str) -> None:
    nodes = reference.kind_nodes(kind, cluster)
    if len(nodes) != 3:
        raise StagingCellError(
            f"staging cluster must expose exactly three kind nodes; observed {len(nodes)}"
        )
    owner_node = nodes[0]
    for path, identity in (
        ("/var/local/weltgewebe-staging/postgres", "999:999"),
        ("/var/local/weltgewebe-staging/nats", "1000:1000"),
    ):
        run(["docker", "exec", owner_node, "mkdir", "-p", path], timeout=30)
        run(["docker", "exec", owner_node, "chown", "-R", identity, path], timeout=30)
        run(["docker", "exec", owner_node, "chmod", "0700", path], timeout=30)
        expected = f"{identity}:700"
        for node in nodes:
            observed = output(
                ["docker", "exec", node, "stat", "-c", "%u:%g:%a", path],
                timeout=30,
            )
            if observed != expected:
                raise StagingCellError(
                    f"staging host mount is not shared consistently on kind node {node!r}"
                )


def flux_documents(commit: str) -> list[dict[str, Any]]:
    return [
        {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": {"name": SOURCE_NAME, "namespace": "flux-system"},
            "spec": {
                "interval": "1m",
                "url": PUBLIC_REPOSITORY,
                "ref": {"commit": commit},
            },
        },
        {
            "apiVersion": "kustomize.toolkit.fluxcd.io/v1",
            "kind": "Kustomization",
            "metadata": {"name": DATA_KUSTOMIZATION, "namespace": "flux-system"},
            "spec": {
                "interval": "2m",
                "retryInterval": "20s",
                "timeout": "8m",
                "prune": True,
                "wait": True,
                "sourceRef": {"kind": "GitRepository", "name": SOURCE_NAME},
                "path": "./platform/clusters/staging/data",
                "healthChecks": [
                    {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": "postgres",
                        "namespace": DATA_NAMESPACE,
                    },
                    {
                        "apiVersion": "apps/v1",
                        "kind": "Deployment",
                        "name": "nats",
                        "namespace": DATA_NAMESPACE,
                    },
                ],
            },
        },
    ]


def wait_data(kubectl: str) -> None:
    reference.wait_condition(
        kubectl, "flux-system", f"gitrepository/{SOURCE_NAME}", "Ready"
    )
    reference.wait_condition(
        kubectl,
        "flux-system",
        f"kustomization/{DATA_KUSTOMIZATION}",
        "Ready",
    )
    reference.wait_rollout(kubectl, DATA_NAMESPACE, "deployment/postgres", "8m")
    reference.wait_rollout(kubectl, DATA_NAMESPACE, "deployment/nats", "8m")
    for pvc in ("postgres-data", "nats-data"):
        phase = output(
            [
                kubectl,
                "-n",
                DATA_NAMESPACE,
                "get",
                "pvc",
                pvc,
                "-o",
                "jsonpath={.status.phase}",
            ]
        )
        if phase != "Bound":
            raise StagingCellError(f"PVC {pvc} is not Bound: {phase!r}")


def image_promotion_state() -> dict[str, Any]:
    contract = json.loads(
        (ROOT / "platform/image-promotion.contract.json").read_text(encoding="utf-8")
    )
    return {
        "status": contract.get("status"),
        "production_activation": contract.get("production_activation"),
        "required_images": contract.get("required_images", []),
    }


def write_cell_receipt(root: Path, payload: dict[str, Any]) -> str:
    path = root / "receipts/cell-bootstrap.json"
    atomic_json(path, payload, mode=0o600)
    return str(path)


def command_up(args: argparse.Namespace) -> dict[str, Any]:
    require_singleton_cluster(args.cluster)
    root = state_root(getattr(args, "state_root", None))
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    data_root = root / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    os.chmod(data_root, 0o755)
    (data_root / "postgres").mkdir(parents=True, exist_ok=True)
    (data_root / "nats").mkdir(parents=True, exist_ok=True)
    configure_reference_paths(root)
    receipt = load_tool_receipt(root)
    tools = receipt["tools"]
    kind = tools["kind"]
    kubectl = tools["kubectl"]
    flux = tools["flux"]
    helm = tools["helm"]
    owner_id = args.owner_id
    if not owner_id:
        raise StagingCellError("--owner-id is required for real staging ownership")

    existing = args.cluster in reference.clusters(kind)
    if existing:
        cell = load_cell_receipt(root)
        require_receipt_cluster(cell, args.cluster)
        persisted_owner = str(cell.get("owner_id") or "")
        persisted_commit = str(cell.get("bootstrap_commit") or "")
        if owner_id != persisted_owner:
            raise StagingCellError("--owner-id does not match the persisted cluster owner")
        commit = require_clean_commit(
            args.source_commit,
            expected_commit=persisted_commit,
            require_public_main=False,
        )
        reference.require_owned_cluster(
            kind,
            args.cluster,
            expected_commit=persisted_commit,
            expected_owner_id=owner_id,
        )
        created = False
    else:
        commit = require_clean_commit(args.source_commit)
        rendered_kind_config = render_kind_config(root)
        reference.create_kind_cluster(
            kind,
            args.cluster,
            receipt["kubernetes"]["kind_node_image"],
            str(rendered_kind_config),
            commit,
            owner_id,
            timeout=900,
        )
        created = True

    secret_path = root / "secrets/staging-runtime.json"
    if secret_path.exists() or retained_postgres_state_exists(root):
        load_or_create_secret_material(root)

    prepare_volume_permissions(kind, args.cluster)
    api_server_host = reference.control_plane_address(args.cluster)
    reference.install_platform_components(
        kubectl, flux, helm, receipt["artifacts"], api_server_host
    )
    run(
        [
            kubectl,
            "wait",
            "--for=condition=Ready",
            "nodes",
            "--all",
            "--timeout=5m",
        ],
        timeout=360,
    )
    secret_receipt = inject_external_secrets(kubectl, root)
    apply_yaml(kubectl, flux_documents(commit))
    wait_data(kubectl)
    node_names = output([kubectl, "get", "nodes", "-o", "name"]).splitlines()
    if len(node_names) != 3:
        raise StagingCellError(
            f"staging Kubernetes node count drift: expected 3, observed {len(node_names)}"
        )
    node_count = len(node_names)
    base_result = {
        "schema_version": 1,
        "status": "infrastructure-ready-image-promotion-blocked",
        "cluster": args.cluster,
        "owner_id": owner_id,
        "bootstrap_commit": commit,
        "public_source": PUBLIC_REPOSITORY,
        "gitops_source_commit": commit,
        "cluster_created": created,
        "node_count": node_count,
        "toolchain_lock_sha256": receipt["lock_sha256"],
        "kubeconfig": str(reference.kubeconfig_path(args.cluster)),
        "persistent_storage": {
            "postgres": "Bound",
            "nats": "Bound",
            "host_state_root": str(root / "data"),
        },
        "flux": {
            "source": SOURCE_NAME,
            "data_kustomization": DATA_KUSTOMIZATION,
            "ready": True,
        },
        "image_promotion": image_promotion_state(),
        "app_activation": False,
        "production_changed": False,
        "does_not_establish": [
            "first-party GHCR image promotion",
            "staging app rollout",
            "staging gateway proof",
            "delete-to-prove",
            "production Kubernetes cutover",
        ],
    }
    private_result = {**base_result, "external_secret": secret_receipt}
    receipt_path = write_cell_receipt(root, private_result)
    return {
        **base_result,
        "external_secret": public_external_secret_state(),
        "receipt_path": receipt_path,
    }


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    require_singleton_cluster(args.cluster)
    root = state_root(getattr(args, "state_root", None))
    configure_reference_paths(root)
    receipt = load_tool_receipt(root)
    kind = receipt["tools"]["kind"]
    kubectl = receipt["tools"]["kubectl"]
    owner_path = root / "receipts/cell-bootstrap.json"
    if not owner_path.exists():
        return {
            "schema_version": 1,
            "status": "not-bootstrapped",
            "cluster": args.cluster,
        }
    owner = load_cell_receipt(root)
    require_receipt_cluster(owner, args.cluster)
    commit = str(owner.get("bootstrap_commit") or "")
    owner_id = str(owner.get("owner_id") or "")
    reference.require_owned_cluster(
        kind,
        args.cluster,
        expected_commit=commit,
        expected_owner_id=owner_id,
    )
    source_revision = output(
        [
            kubectl,
            "-n",
            "flux-system",
            "get",
            "gitrepository",
            SOURCE_NAME,
            "-o",
            "jsonpath={.status.artifact.revision}",
        ]
    )
    source_matches_commit = flux_revision_matches_commit(source_revision, commit)
    data_ready = output(
        [
            kubectl,
            "-n",
            "flux-system",
            "get",
            "kustomization",
            DATA_KUSTOMIZATION,
            "-o",
            "jsonpath={.status.conditions[?(@.type=='Ready')].status}",
        ]
    )
    pvcs = {
        pvc: output(
            [
                kubectl,
                "-n",
                DATA_NAMESPACE,
                "get",
                "pvc",
                pvc,
                "-o",
                "jsonpath={.status.phase}",
            ]
        )
        for pvc in ("postgres-data", "nats-data")
    }
    external_secret = verify_external_secret_binding(kubectl, root)
    ready = (
        source_matches_commit
        and data_ready == "True"
        and all(value == "Bound" for value in pvcs.values())
        and external_secret["ready"]
    )
    return {
        "schema_version": 1,
        "status": "ready" if ready else "degraded",
        "cluster": args.cluster,
        "owner_id": owner_id,
        "bootstrap_commit": commit,
        "source_revision": source_revision,
        "source_matches_commit": source_matches_commit,
        "data_ready": data_ready,
        "pvcs": pvcs,
        "external_secret": external_secret,
        "image_promotion": image_promotion_state(),
        "app_activation": False,
        "production_changed": False,
    }


def command_down(args: argparse.Namespace) -> dict[str, Any]:
    require_singleton_cluster(args.cluster)
    root = state_root(getattr(args, "state_root", None))
    configure_reference_paths(root)
    receipt = load_tool_receipt(root)
    cell = load_cell_receipt(root)
    require_receipt_cluster(cell, args.cluster)
    commit = str(cell.get("bootstrap_commit") or "")
    owner_id = str(cell.get("owner_id") or "")
    if args.owner_id != owner_id:
        raise StagingCellError("--owner-id does not match the persisted cluster owner")
    reference.delete_owned_cluster(
        receipt["tools"]["kind"],
        args.cluster,
        expected_commit=commit,
        expected_owner_id=owner_id,
    )
    result = {
        "schema_version": 1,
        "status": "cluster-deleted-state-preserved",
        "cluster": args.cluster,
        "owner_id": owner_id,
        "bootstrap_commit": commit,
        "state_preserved": ["data", "secrets", "toolchain", "receipts"],
        "production_changed": False,
    }
    path = root / "receipts/cell-down.json"
    atomic_json(path, result)
    return {
        **result,
        "receipt_path": str(path),
        "receipt_sha256": sha256_file(path),
    }


def command_self_check() -> dict[str, Any]:
    require_singleton_cluster(DEFAULT_CLUSTER)
    try:
        require_singleton_cluster(f"{DEFAULT_CLUSTER}-other")
    except StagingCellError:
        pass
    else:
        raise StagingCellError(
            "self-check accepted a second cluster over singleton persistent state"
        )

    if state_root(None) != DEFAULT_STATE_ROOT.resolve():
        raise StagingCellError("self-check default state root drift")
    try:
        state_root(str(DEFAULT_STATE_ROOT.parent / "unexpected-root"))
    except StagingCellError:
        pass
    else:
        raise StagingCellError("self-check accepted a non-canonical state root")

    public_secret = public_external_secret_state()
    if public_secret != {"bound": True, "required_keys": ["database-url"]}:
        raise StagingCellError(
            "self-check public external-secret state exposes unexpected fields"
        )

    commit = "a" * 40
    if not (
        flux_revision_matches_commit(commit, commit)
        and flux_revision_matches_commit(f"sha1:{commit}", commit)
        and flux_revision_matches_commit(f"main@sha1:{commit}", commit)
        and not flux_revision_matches_commit(f"sha1:{'b' * 40}", commit)
    ):
        raise StagingCellError("self-check Flux revision binding is invalid")

    with tempfile.TemporaryDirectory(
        prefix="commonthing-staging-cell-self-check-"
    ) as tmp_name:
        root = Path(tmp_name)
        (root / "data/postgres").mkdir(parents=True)
        material, source_sha = load_or_create_secret_material(root)
        secret_path = root / "secrets/staging-runtime.json"
        if not secret_path.is_file() or stat.S_IMODE(secret_path.stat().st_mode) != 0o600:
            raise StagingCellError("self-check secret source permissions are invalid")
        if len(source_sha) != 64 or not material.get("database_password"):
            raise StagingCellError("self-check secret source binding is invalid")

        annotations = {SECRET_SOURCE_ANNOTATION: source_sha}
        database_document = {
            "metadata": {
                "name": DATABASE_SECRET,
                "namespace": DATA_NAMESPACE,
                "annotations": annotations,
            },
            "data": {
                key: base64.b64encode(value.encode("utf-8")).decode("ascii")
                for key, value in {
                    "username": material["database_user"],
                    "password": material["database_password"],
                    "database": material["database_name"],
                }.items()
            },
        }
        if not secret_document_matches(
            database_document,
            name=DATABASE_SECRET,
            namespace_name=DATA_NAMESPACE,
            source_sha=source_sha,
            expected_values={
                "username": material["database_user"],
                "password": material["database_password"],
                "database": material["database_name"],
            },
        ):
            raise StagingCellError(
                "self-check rejected a valid injected database Secret"
            )
        database_document["data"]["password"] = base64.b64encode(b"wrong").decode(
            "ascii"
        )
        if secret_document_matches(
            database_document,
            name=DATABASE_SECRET,
            namespace_name=DATA_NAMESPACE,
            source_sha=source_sha,
            expected_values={
                "username": material["database_user"],
                "password": material["database_password"],
                "database": material["database_name"],
            },
        ):
            raise StagingCellError("self-check accepted changed injected Secret data")

        atomic_json(
            root / "receipts/cell-bootstrap.json",
            {
                "schema_version": 1,
                "cluster": DEFAULT_CLUSTER,
                "external_secret": {"source_sha256": source_sha},
            },
        )
        changed = dict(material)
        changed["schema_version"] = 1
        changed["database_password"] = "replacement-password"
        atomic_json(secret_path, changed)
        try:
            load_or_create_secret_material(root)
        except StagingCellError as error:
            if "differs from the bootstrap receipt" not in str(error):
                raise
        else:
            raise StagingCellError(
                "self-check accepted credential rotation over retained PostgreSQL state"
            )

        atomic_json(
            secret_path,
            {"schema_version": 1, **material},
        )
        secret_path.unlink()
        (root / "data/postgres/PG_VERSION").write_text("16\n", encoding="utf-8")
        try:
            load_or_create_secret_material(root)
        except StagingCellError as error:
            if "retained PostgreSQL state exists" not in str(error):
                raise
        else:
            raise StagingCellError(
                "self-check regenerated credentials over retained PostgreSQL state"
            )

        rendered_path = render_kind_config(root)
        rendered = yaml.safe_load(rendered_path.read_text(encoding="utf-8"))
        expected = str((root / "data").resolve())
        observed = [
            mount.get("hostPath")
            for node in rendered.get("nodes", [])
            for mount in node.get("extraMounts", [])
        ]
        if observed != [expected, expected, expected]:
            raise StagingCellError(
                "self-check rendered kind host mounts do not bind the state root"
            )
    return {
        "schema_version": 1,
        "status": "pass",
        "checks": [
            "singleton-cluster",
            "fixed-state-root",
            "flux-source-exact-commit",
            "retained-secret-fail-closed",
            "retained-secret-rotation-fail-closed",
            "injected-secret-integrity",
            "public-secret-output-redaction",
            "state-root-kind-render",
        ],
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Persistent owner-bound T084 staging GewebeZelle controller"
    )
    sub = p.add_subparsers(dest="command", required=True)
    up = sub.add_parser("up")
    up.add_argument("--cluster", default=DEFAULT_CLUSTER)
    up.add_argument("--owner-id", required=True)
    up.add_argument("--source-commit")
    status = sub.add_parser("status")
    status.add_argument("--cluster", default=DEFAULT_CLUSTER)
    down = sub.add_parser("down")
    down.add_argument("--cluster", default=DEFAULT_CLUSTER)
    down.add_argument("--owner-id", required=True)
    sub.add_parser("self-check")
    return p


def emit_public_success(command: str, result: dict[str, Any]) -> None:
    if command == "up":
        print(
            '{"command":"up","schema_version":1,'
            '"status":"infrastructure-ready-image-promotion-blocked"}'
        )
        return
    if command == "status":
        status = str(result.get("status") or "degraded")
        safe: dict[str, Any] = {
            "command": "status",
            "schema_version": 1,
            "status": status,
            "cluster": str(result.get("cluster") or DEFAULT_CLUSTER),
        }
        if status != "not-bootstrapped":
            pvcs = result.get("pvcs") if isinstance(result.get("pvcs"), dict) else {}
            external = (
                result.get("external_secret")
                if isinstance(result.get("external_secret"), dict)
                else {}
            )
            safe.update(
                {
                    "bootstrap_commit": str(result.get("bootstrap_commit") or ""),
                    "source_revision": str(result.get("source_revision") or ""),
                    "source_matches_commit": bool(result.get("source_matches_commit")),
                    "data_ready": result.get("data_ready") == "True",
                    "pvcs": {
                        "postgres-data": str(pvcs.get("postgres-data") or "missing"),
                        "nats-data": str(pvcs.get("nats-data") or "missing"),
                    },
                    "external_secret": {
                        "database": bool(external.get("database")),
                        "runtime": bool(external.get("runtime")),
                        "ready": bool(external.get("ready")),
                    },
                }
            )
        print(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        return
    if command == "down":
        print(
            '{"command":"down","schema_version":1,'
            '"status":"cluster-deleted-state-preserved"}'
        )
        return
    print('{"command":"self-check","schema_version":1,"status":"pass"}')


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "up":
            result = command_up(args)
        elif args.command == "status":
            result = command_status(args)
        elif args.command == "down":
            result = command_down(args)
        else:
            result = command_self_check()
        emit_public_success(args.command, result)
        return 0
    except StagingCellError as error:
        print(f"staging cell failed: {error}", file=sys.stderr)
        return 1
    except reference.ProofError:
        print("staging cell failed: platform proof operation failed", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(
            f"staging cell failed: external command exited with status {error.returncode}",
            file=sys.stderr,
        )
        return 1
    except subprocess.TimeoutExpired:
        print("staging cell failed: external command timed out", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
