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
import time
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
SECRET_SOURCE_ANNOTATION = "commonthing.net/external-secret-source-sha256"
PVC_BIND_TIMEOUT_SECONDS = 45.0
ALLOWED_RETAINED_VOLUME_MODES = {"700", "770", "2770"}
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


def data_node_name(cluster: str) -> str:
    require_singleton_cluster(cluster)
    return f"{cluster}-worker"


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
    roles = [node.get("role") if isinstance(node, dict) else None for node in nodes]
    if roles != ["control-plane", "worker", "worker"]:
        raise StagingCellError("staging kind template node roles drift")
    data_root = str((root / "data").resolve())
    placeholder = "__COMMONTHING_STAGING_DATA_ROOT__"
    for index, node in enumerate(nodes):
        mounts = node.get("extraMounts", []) if isinstance(node, dict) else []
        if index != 1:
            if mounts:
                raise StagingCellError(
                    f"staging kind node {index} must not mount persistent data"
                )
            continue
        if not isinstance(mounts, list) or len(mounts) != 1:
            raise StagingCellError(
                "staging data worker must bind exactly one persistent host mount"
            )
        mount = mounts[0]
        if mount.get("hostPath") != placeholder:
            raise StagingCellError("staging data worker hostPath template drift")
        if mount.get("containerPath") != "/var/local/weltgewebe-staging":
            raise StagingCellError("staging data worker containerPath drift")
        if mount.get("readOnly") is not False:
            raise StagingCellError("staging data worker persistent mount must be writable")
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
    body = yaml.safe_dump_all(docs, sort_keys=False, explicit_start=True)
    run([kubectl, "apply", "-f", "-"], input_text=body, timeout=120)


def namespace(name: str) -> dict[str, Any]:
    labels = {
        "pod-security.kubernetes.io/enforce": "restricted",
        "pod-security.kubernetes.io/audit": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
    }
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
    apply_yaml(kubectl, [namespace(DATA_NAMESPACE), namespace(APP_NAMESPACE)])
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


def prepare_volume_permissions(kind: str, cluster: str, root: Path) -> None:
    nodes = reference.kind_nodes(kind, cluster)
    if len(nodes) != 3:
        raise StagingCellError(
            f"staging cluster must expose exactly three kind nodes; observed {len(nodes)}"
        )
    data_node = data_node_name(cluster)
    if data_node not in nodes:
        raise StagingCellError(
            f"staging data worker {data_node!r} is missing from kind nodes {nodes!r}"
        )

    expected_source = str((root / "data").resolve())
    for node in nodes:
        raw_mounts = output(
            ["docker", "inspect", "--format", "{{json .Mounts}}", node],
            timeout=30,
        )
        try:
            mounts = json.loads(raw_mounts)
        except json.JSONDecodeError as error:
            raise StagingCellError(
                f"cannot inspect staging kind mount topology for node {node!r}"
            ) from error
        data_mounts = [
            mount
            for mount in mounts
            if isinstance(mount, dict)
            and mount.get("Destination") == "/var/local/weltgewebe-staging"
        ]
        if node == data_node:
            if (
                len(data_mounts) != 1
                or data_mounts[0].get("Source") != expected_source
                or data_mounts[0].get("RW") is not True
            ):
                raise StagingCellError(
                    "staging data worker does not expose the exact writable retained host mount"
                )
        elif data_mounts:
            raise StagingCellError(
                f"staging non-data node {node!r} unexpectedly exposes retained host storage"
            )

    for volume_path, identity in (
        ("/var/local/weltgewebe-staging/postgres", "999:999"),
        ("/var/local/weltgewebe-staging/nats", "1000:1000"),
    ):
        run(["docker", "exec", data_node, "mkdir", "-p", volume_path], timeout=30)
        observed = output(
            ["docker", "exec", data_node, "stat", "-c", "%u:%g:%a", volume_path],
            timeout=30,
        )
        uid_gid, _, mode = observed.rpartition(":")
        if uid_gid == identity and mode in ALLOWED_RETAINED_VOLUME_MODES:
            continue

        first_entry = output(
            [
                "docker",
                "exec",
                data_node,
                "find",
                volume_path,
                "-mindepth",
                "1",
                "-maxdepth",
                "1",
                "-print",
                "-quit",
            ],
            timeout=30,
        )
        if first_entry:
            raise StagingCellError(
                f"retained staging volume {volume_path!r} has unexpected permissions {observed!r}; "
                "refusing recursive ownership or mode changes over live data"
            )
        run(["docker", "exec", data_node, "chown", identity, volume_path], timeout=30)
        run(["docker", "exec", data_node, "chmod", "0700", volume_path], timeout=30)
        initialized = output(
            ["docker", "exec", data_node, "stat", "-c", "%u:%g:%a", volume_path],
            timeout=30,
        )
        if initialized != f"{identity}:700":
            raise StagingCellError(
                f"staging volume {volume_path!r} permission initialization failed: {initialized!r}"
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


def wait_pvcs_bound(
    kubectl: str, *, timeout_seconds: float = PVC_BIND_TIMEOUT_SECONDS
) -> None:
    pvcs = ("postgres-data", "nats-data")
    deadline = time.monotonic() + timeout_seconds
    observed: dict[str, str] = {}
    while True:
        for pvc in pvcs:
            phase = output(
                [
                    kubectl,
                    "-n",
                    DATA_NAMESPACE,
                    "get",
                    "pvc",
                    pvc,
                    "--ignore-not-found",
                    "-o",
                    "jsonpath={.status.phase}",
                ]
            )
            observed[pvc] = phase or "missing"
        if all(observed[pvc] == "Bound" for pvc in pvcs):
            return
        unexpected = {
            pvc: phase
            for pvc, phase in observed.items()
            if phase not in {"missing", "Pending", "Bound"}
        }
        if unexpected:
            raise StagingCellError(f"staging PVC entered unexpected phase: {unexpected!r}")
        if time.monotonic() >= deadline:
            raise StagingCellError(
                f"staging PVCs did not bind within {timeout_seconds:g}s: {observed!r}"
            )
        time.sleep(1)


def wait_data(kubectl: str) -> None:
    reference.wait_condition(
        kubectl, "flux-system", f"gitrepository/{SOURCE_NAME}", "Ready"
    )
    wait_pvcs_bound(kubectl)
    reference.wait_condition(
        kubectl,
        "flux-system",
        f"kustomization/{DATA_KUSTOMIZATION}",
        "Ready",
    )


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
    cell_path = root / "receipts/cell-bootstrap.json"
    cell = load_cell_receipt(root) if cell_path.exists() else None
    if existing and cell is None:
        raise StagingCellError(
            "staging cluster exists without a bootstrap receipt; refusing unbound recovery"
        )
    if cell is None and retained_postgres_state_exists(root):
        raise StagingCellError(
            "retained staging data exists without a bootstrap receipt; explicit recovery is required"
        )
    if cell is not None:
        require_receipt_cluster(cell, args.cluster)
        persisted_owner = str(cell.get("owner_id") or "")
        if owner_id != persisted_owner:
            raise StagingCellError("--owner-id does not match the persisted cluster owner")

    _, source_sha = load_or_create_secret_material(root)

    if cell is not None:
        persisted_commit = str(cell.get("bootstrap_commit") or "")
        commit = require_clean_commit(
            args.source_commit,
            expected_commit=persisted_commit,
            require_public_main=False,
        )
    else:
        commit = require_clean_commit(args.source_commit)

    if existing:
        reference.require_owned_cluster(
            kind,
            args.cluster,
            expected_commit=commit,
            expected_owner_id=owner_id,
        )
        created = False
    else:
        if cell is None:
            write_cell_receipt(
                root,
                {
                    "schema_version": 1,
                    "status": "bootstrap-in-progress",
                    "cluster": args.cluster,
                    "owner_id": owner_id,
                    "bootstrap_commit": commit,
                    "public_source": PUBLIC_REPOSITORY,
                    "external_secret": {
                        "source_sha256": source_sha,
                        "required_keys": ["database-url"],
                    },
                    "production_changed": False,
                },
            )
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

    prepare_volume_permissions(kind, args.cluster, root)
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
    if args.cluster not in reference.clusters(kind):
        return {
            "schema_version": 1,
            "status": "cluster-absent-state-preserved",
            "cluster": args.cluster,
            "owner_id": owner_id,
            "bootstrap_commit": commit,
            "production_changed": False,
        }
    reference.require_owned_cluster(
        kind,
        args.cluster,
        expected_commit=commit,
        expected_owner_id=owner_id,
    )
    if owner.get("status") == "bootstrap-in-progress":
        return {
            "schema_version": 1,
            "status": "bootstrap-in-progress",
            "cluster": args.cluster,
            "owner_id": owner_id,
            "bootstrap_commit": commit,
            "production_changed": False,
        }
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
    try:
        external_secret = verify_external_secret_binding(kubectl, root)
    except StagingCellError:
        external_secret = {
            "database": False,
            "runtime": False,
            "ready": False,
        }
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
    kind = receipt["tools"]["kind"]
    cluster_present = args.cluster in reference.clusters(kind)
    if cluster_present:
        reference.delete_owned_cluster(
            kind,
            args.cluster,
            expected_commit=commit,
            expected_owner_id=owner_id,
        )
    result = {
        "schema_version": 1,
        "status": (
            "cluster-deleted-state-preserved"
            if cluster_present
            else "cluster-absent-state-preserved"
        ),
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
        if observed != [expected]:
            raise StagingCellError(
                "self-check rendered kind data-worker mount does not bind the state root"
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
            "single-data-worker-kind-render",
        ],
    }


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Persistent owner-bound T084 staging GewebeZelle controller"
    )
    sub = p.add_subparsers(dest="command", required=True)
    up = sub.add_parser("up")
    up.set_defaults(cluster=DEFAULT_CLUSTER)
    up.add_argument("--owner-id", required=True)
    up.add_argument("--source-commit")
    status = sub.add_parser("status")
    status.set_defaults(cluster=DEFAULT_CLUSTER)
    down = sub.add_parser("down")
    down.set_defaults(cluster=DEFAULT_CLUSTER)
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
        if status in {"ready", "degraded"}:
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
        elif result.get("bootstrap_commit"):
            safe["bootstrap_commit"] = str(result.get("bootstrap_commit") or "")
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
