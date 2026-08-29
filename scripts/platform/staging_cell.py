#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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
    print("+", " ".join(argv), flush=True)
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
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        os.chmod(path, mode)
    finally:
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
    missing_tools = [name for name in REQUIRED_TOOLS if not Path(str(tools.get(name, ""))).is_file()]
    missing_artifacts = [
        name for name in REQUIRED_ARTIFACTS if not Path(str(artifacts.get(name, ""))).is_file()
    ]
    if missing_tools or missing_artifacts:
        raise StagingCellError(
            f"toolchain receipt incomplete: tools={missing_tools} artifacts={missing_artifacts}"
        )
    return receipt


def require_clean_commit(source_commit: str | None) -> str:
    if output(["git", "status", "--porcelain"]):
        raise StagingCellError("staging cell mutation requires a clean worktree")
    head = output(["git", "rev-parse", "HEAD"])
    if source_commit is not None and source_commit != head:
        raise StagingCellError(f"source commit {source_commit} does not equal worktree HEAD {head}")
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise StagingCellError("worktree HEAD is not a canonical 40-hex commit")
    public = output(
        ["git", "ls-remote", "https://github.com/heimgewebe/weltgewebe.git", "refs/heads/main"],
        timeout=30,
    )
    remote_head = public.split()[0] if public else ""
    if remote_head != head:
        raise StagingCellError(
            f"staging bootstrap requires exact public main; local={head} public-main={remote_head or 'missing'}"
        )
    return head


def load_or_create_secret_material(root: Path) -> tuple[dict[str, str], str]:
    path = root / "secrets/staging-runtime.json"
    if path.exists():
        linked = path.lstat()
        if stat.S_ISLNK(linked.st_mode) or not stat.S_ISREG(linked.st_mode):
            raise StagingCellError("staging secret source must be a regular file")
        if stat.S_IMODE(linked.st_mode) & 0o077:
            raise StagingCellError("staging secret source must not be group/world accessible")
        payload = json.loads(path.read_text(encoding="utf-8"))
    else:
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
    return {key: str(payload[key]) for key in required}, sha256_file(path)


def apply_yaml(kubectl: str, documents: list[dict[str, Any]] | dict[str, Any]) -> None:
    docs = documents if isinstance(documents, list) else [documents]
    body = "\n---\n".join(yaml.safe_dump(doc, sort_keys=False).strip() for doc in docs) + "\n"
    run([kubectl, "apply", "-f", "-"], input_text=body, timeout=120)


def namespace(name: str, *, data_client: bool = False) -> dict[str, Any]:
    labels = {
        "pod-security.kubernetes.io/enforce": "restricted",
        "pod-security.kubernetes.io/audit": "restricted",
        "pod-security.kubernetes.io/warn": "restricted",
    }
    if data_client:
        labels["commonthing.net/data-client"] = "true"
    return {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": name, "labels": labels}}


def inject_external_secrets(kubectl: str, root: Path) -> dict[str, str]:
    material, source_sha = load_or_create_secret_material(root)
    username = material["database_user"]
    password = material["database_password"]
    database = material["database_name"]
    encoded_user = urllib.parse.quote(username, safe="")
    encoded_password = urllib.parse.quote(password, safe="")
    encoded_db = urllib.parse.quote(database, safe="")
    database_url = (
        f"postgres://{encoded_user}:{encoded_password}@postgres.{DATA_NAMESPACE}.svc.cluster.local:5432/"
        f"{encoded_db}?sslmode=disable"
    )
    annotations = {"commonthing.net/external-secret-source-sha256": source_sha}
    apply_yaml(kubectl, [namespace(DATA_NAMESPACE), namespace(APP_NAMESPACE, data_client=True)])
    apply_yaml(
        kubectl,
        [
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": DATABASE_SECRET, "namespace": DATA_NAMESPACE, "annotations": annotations},
                "type": "Opaque",
                "stringData": {"username": username, "password": password, "database": database},
            },
            {
                "apiVersion": "v1",
                "kind": "Secret",
                "metadata": {"name": RUNTIME_SECRET, "namespace": APP_NAMESPACE, "annotations": annotations},
                "type": "Opaque",
                "stringData": {"database-url": database_url},
            },
        ],
    )
    return {"source_sha256": source_sha, "required_keys": ["database-url"]}


def prepare_volume_permissions(kind: str, cluster: str) -> None:
    nodes = reference.kind_nodes(kind, cluster)
    node = nodes[0]
    for path, identity in (("/var/local/weltgewebe-staging/postgres", "999:999"), ("/var/local/weltgewebe-staging/nats", "1000:1000")):
        run(["docker", "exec", node, "mkdir", "-p", path], timeout=30)
        run(["docker", "exec", node, "chown", "-R", identity, path], timeout=30)
        run(["docker", "exec", node, "chmod", "0700", path], timeout=30)


def flux_documents(commit: str) -> list[dict[str, Any]]:
    return [
        {
            "apiVersion": "source.toolkit.fluxcd.io/v1",
            "kind": "GitRepository",
            "metadata": {"name": SOURCE_NAME, "namespace": "flux-system"},
            "spec": {
                "interval": "1m",
                "url": "https://github.com/heimgewebe/weltgewebe",
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
                    {"apiVersion": "apps/v1", "kind": "Deployment", "name": "postgres", "namespace": DATA_NAMESPACE},
                    {"apiVersion": "apps/v1", "kind": "Deployment", "name": "nats", "namespace": DATA_NAMESPACE},
                ],
            },
        },
    ]


def wait_data(kubectl: str) -> None:
    reference.wait_condition(kubectl, "flux-system", f"gitrepository/{SOURCE_NAME}", "Ready")
    reference.wait_condition(kubectl, "flux-system", f"kustomization/{DATA_KUSTOMIZATION}", "Ready")
    reference.wait_rollout(kubectl, DATA_NAMESPACE, "deployment/postgres", "8m")
    reference.wait_rollout(kubectl, DATA_NAMESPACE, "deployment/nats", "8m")
    for pvc in ("postgres-data", "nats-data"):
        phase = output([kubectl, "-n", DATA_NAMESPACE, "get", "pvc", pvc, "-o", "jsonpath={.status.phase}"])
        if phase != "Bound":
            raise StagingCellError(f"PVC {pvc} is not Bound: {phase!r}")


def image_promotion_state() -> dict[str, Any]:
    contract = json.loads((ROOT / "platform/image-promotion.contract.json").read_text(encoding="utf-8"))
    return {
        "status": contract.get("status"),
        "production_activation": contract.get("production_activation"),
        "required_images": contract.get("required_images", []),
    }


def write_cell_receipt(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path = root / "receipts/cell-bootstrap.json"
    atomic_json(path, payload, mode=0o600)
    return {**payload, "receipt_path": str(path), "receipt_sha256": sha256_file(path)}


def command_up(args: argparse.Namespace) -> dict[str, Any]:
    root = state_root(args.state_root)
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o700)
    data_root = root / "data"
    data_root.mkdir(parents=True, exist_ok=True)
    os.chmod(data_root, 0o755)
    (data_root / "postgres").mkdir(parents=True, exist_ok=True)
    (data_root / "nats").mkdir(parents=True, exist_ok=True)
    commit = require_clean_commit(args.source_commit)
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

    if args.cluster in reference.clusters(kind):
        reference.require_owned_cluster(
            kind,
            args.cluster,
            expected_commit=commit,
            expected_owner_id=owner_id,
        )
        created = False
    else:
        reference.create_kind_cluster(
            kind,
            args.cluster,
            receipt["kubernetes"]["kind_node_image"],
            "platform/clusters/staging/kind.yaml",
            commit,
            owner_id,
            timeout=900,
        )
        created = True

    prepare_volume_permissions(kind, args.cluster)
    api_server_host = reference.control_plane_address(args.cluster)
    reference.install_platform_components(kubectl, flux, helm, receipt["artifacts"], api_server_host)
    run([kubectl, "wait", "--for=condition=Ready", "nodes", "--all", "--timeout=5m"], timeout=360)
    secret_receipt = inject_external_secrets(kubectl, root)
    apply_yaml(kubectl, flux_documents(commit))
    wait_data(kubectl)
    node_count = int(output([kubectl, "get", "nodes", "-o", "name"]).count("\n") + 1)
    result = {
        "schema_version": 1,
        "status": "infrastructure-ready-image-promotion-blocked",
        "cluster": args.cluster,
        "owner_id": owner_id,
        "bootstrap_commit": commit,
        "public_source": "https://github.com/heimgewebe/weltgewebe",
        "gitops_source_commit": commit,
        "cluster_created": created,
        "node_count": node_count,
        "toolchain_lock_sha256": receipt["lock_sha256"],
        "kubeconfig": str(reference.kubeconfig_path(args.cluster)),
        "external_secret": secret_receipt,
        "persistent_storage": {"postgres": "Bound", "nats": "Bound", "host_state_root": str(root / "data")},
        "flux": {"source": SOURCE_NAME, "data_kustomization": DATA_KUSTOMIZATION, "ready": True},
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
    return write_cell_receipt(root, result)


def command_status(args: argparse.Namespace) -> dict[str, Any]:
    root = state_root(args.state_root)
    configure_reference_paths(root)
    receipt = load_tool_receipt(root)
    kind = receipt["tools"]["kind"]
    kubectl = receipt["tools"]["kubectl"]
    owner_path = root / "receipts/cell-bootstrap.json"
    if not owner_path.is_file():
        return {"schema_version": 1, "status": "not-bootstrapped", "cluster": args.cluster}
    owner = json.loads(owner_path.read_text(encoding="utf-8"))
    commit = str(owner.get("bootstrap_commit") or "")
    owner_id = str(owner.get("owner_id") or "")
    reference.require_owned_cluster(
        kind,
        args.cluster,
        expected_commit=commit,
        expected_owner_id=owner_id,
    )
    source_revision = output(
        [kubectl, "-n", "flux-system", "get", "gitrepository", SOURCE_NAME, "-o", "jsonpath={.status.artifact.revision}"]
    )
    data_ready = output(
        [kubectl, "-n", "flux-system", "get", "kustomization", DATA_KUSTOMIZATION, "-o", "jsonpath={.status.conditions[?(@.type=='Ready')].status}"]
    )
    pvcs = {
        pvc: output([kubectl, "-n", DATA_NAMESPACE, "get", "pvc", pvc, "-o", "jsonpath={.status.phase}"])
        for pvc in ("postgres-data", "nats-data")
    }
    return {
        "schema_version": 1,
        "status": "ready" if data_ready == "True" and all(v == "Bound" for v in pvcs.values()) else "degraded",
        "cluster": args.cluster,
        "owner_id": owner_id,
        "bootstrap_commit": commit,
        "source_revision": source_revision,
        "data_ready": data_ready,
        "pvcs": pvcs,
        "image_promotion": image_promotion_state(),
        "app_activation": False,
        "production_changed": False,
    }


def command_down(args: argparse.Namespace) -> dict[str, Any]:
    root = state_root(args.state_root)
    configure_reference_paths(root)
    receipt = load_tool_receipt(root)
    cell_path = root / "receipts/cell-bootstrap.json"
    if not cell_path.is_file():
        raise StagingCellError("cell bootstrap receipt is missing; refusing unbound deletion")
    cell = json.loads(cell_path.read_text(encoding="utf-8"))
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
    return {**result, "receipt_path": str(path), "receipt_sha256": sha256_file(path)}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Persistent owner-bound T084 staging GewebeZelle controller")
    sub = p.add_subparsers(dest="command", required=True)
    up = sub.add_parser("up")
    up.add_argument("--state-root")
    up.add_argument("--cluster", default=DEFAULT_CLUSTER)
    up.add_argument("--owner-id", required=True)
    up.add_argument("--source-commit")
    status = sub.add_parser("status")
    status.add_argument("--state-root")
    status.add_argument("--cluster", default=DEFAULT_CLUSTER)
    down = sub.add_parser("down")
    down.add_argument("--state-root")
    down.add_argument("--cluster", default=DEFAULT_CLUSTER)
    down.add_argument("--owner-id", required=True)
    return p


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "up":
            result = command_up(args)
        elif args.command == "status":
            result = command_status(args)
        else:
            result = command_down(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except (StagingCellError, reference.ProofError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        print(f"staging cell failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
