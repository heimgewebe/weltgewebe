#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FULL_GIT_OBJECT_ID = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
SUITE_INPUTS = {
    "kind-gitops": (
        ".github/workflows/kubernetes-platform.yml",
        ".github/workflows/kubernetes-platform-proof.yml",
        ".dockerignore",
        "Cargo.toml",
        "Cargo.lock",
        "toolchain.versions.yml",
        "apps/api/",
        "apps/web/",
        "scripts/dev/",
        "policies/",
        "infra/compose/compose.prod.yml",
        "platform/",
        "scripts/platform/",
        "scripts/security/",
        "scripts/ci/tests/test_kubernetes_platform_contract.py",
        "scripts/ci/tests/test_trivy_rendered_manifests.py",
        "scripts/ci/tests/test_kubernetes_ha_contract.py",
        "repo.meta.yaml",
    ),
    "ha-recovery": (
        ".github/workflows/kubernetes-platform.yml",
        ".github/workflows/kubernetes-platform-proof.yml",
        ".dockerignore",
        "Cargo.toml",
        "Cargo.lock",
        "toolchain.versions.yml",
        "apps/api/",
        "apps/web/",
        "scripts/dev/",
        "policies/",
        "infra/compose/compose.prod.yml",
        "platform/",
        "scripts/platform/",
        "scripts/security/",
        "scripts/ci/tests/test_kubernetes_platform_contract.py",
        "scripts/ci/tests/test_trivy_rendered_manifests.py",
        "scripts/ci/tests/test_kubernetes_ha_contract.py",
        "repo.meta.yaml",
    ),
}


class IdentityError(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def _canonical_json(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _tracked_files() -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        item.decode("utf-8")
        for item in result.stdout.split(b"\0")
        if item
    )


def _matches(path: str, selectors: tuple[str, ...]) -> bool:
    return any(path == selector or (selector.endswith("/") and path.startswith(selector)) for selector in selectors)


def input_manifest(suite: str) -> list[dict[str, str]]:
    try:
        selectors = SUITE_INPUTS[suite]
    except KeyError as error:
        raise IdentityError(f"unsupported proof suite: {suite}") from error
    selected = sorted(path for path in _tracked_files() if _matches(path, selectors))
    missing = [
        selector
        for selector in selectors
        if not selector.endswith("/") and selector not in selected
    ]
    if missing:
        raise IdentityError(f"proof invalidation inputs are missing: {missing}")
    return [
        {
            "path": path,
            "sha256": _sha256_bytes((ROOT / path).read_bytes()),
        }
        for path in selected
    ]


def compute_identity(suite: str, source_commit: str) -> dict[str, Any]:
    if not FULL_GIT_OBJECT_ID.fullmatch(source_commit):
        raise IdentityError("proof source commit must be a full lowercase Git object id")
    manifest = input_manifest(suite)
    manifest_sha256 = _sha256_bytes(_canonical_json({"files": manifest}))
    payload = {
        "schema_version": 1,
        "suite": suite,
        "source_commit": source_commit,
        "input_manifest_sha256": manifest_sha256,
        "tool_lock_sha256": _sha256_bytes(
            (ROOT / "platform/toolchain.lock.json").read_bytes()
        ),
        "oci_mirror_lock_sha256": _sha256_bytes(
            (ROOT / "platform/oci-proof-mirror.lock.json").read_bytes()
        ),
        "invalidation_contract": list(SUITE_INPUTS[suite]),
    }
    payload["identity_sha256"] = _sha256_bytes(_canonical_json(payload))
    return payload


def _checkout_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if not FULL_GIT_OBJECT_ID.fullmatch(commit):
        raise IdentityError("checked-out commit is not a full lowercase Git object id")
    return commit


def _read_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise IdentityError(f"invalid proof evidence {path}: {error}") from error
    if not isinstance(payload, dict):
        raise IdentityError(f"proof evidence is not an object: {path}")
    return payload


BLOCKED_REGISTRIES = frozenset(
    {
        "registry-1.docker.io",
        "auth.docker.io",
        "production.cloudflare.docker.com",
        "quay.io",
        "ghcr.io",
    }
)


def _validate_receipt_header(
    receipt: Any,
    *,
    label: str,
    lock_sha256: str,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise IdentityError(f"reusable proof {label} OCI receipt is missing")
    if receipt.get("status") != "pass" or receipt.get("strict") is not True:
        raise IdentityError(f"reusable proof {label} OCI receipt is not strictly passing")
    if receipt.get("lock_sha256") != lock_sha256:
        raise IdentityError(f"reusable proof {label} OCI receipt uses a different mirror lock")
    return receipt


def _validate_registry_blockades(receipt: dict[str, Any], *, label: str) -> None:
    blockades = receipt.get("registry_blockades")
    if not isinstance(blockades, list) or not blockades:
        raise IdentityError(f"reusable proof {label} lacks registry blockade evidence")
    observed_nodes: set[str] = set()
    for blockade in blockades:
        if not isinstance(blockade, dict):
            raise IdentityError(f"reusable proof {label} registry blockade is malformed")
        node = blockade.get("node")
        registries = blockade.get("registries")
        if not isinstance(node, str) or not node or node in observed_nodes:
            raise IdentityError(f"reusable proof {label} registry blockade nodes are invalid")
        observed_nodes.add(node)
        if not isinstance(registries, dict) or set(registries) != BLOCKED_REGISTRIES:
            raise IdentityError(f"reusable proof {label} registry blockade inventory drifted")
        for registry, addresses in registries.items():
            if not isinstance(addresses, dict):
                raise IdentityError(
                    f"reusable proof {label} registry blockade for {registry} is malformed"
                )
            if addresses.get("ipv4") != ["127.0.0.1"]:
                raise IdentityError(
                    f"reusable proof {label} registry IPv4 blockade did not pass for {registry}"
                )
            if addresses.get("ipv6") not in ([], ["::1"]):
                raise IdentityError(
                    f"reusable proof {label} registry IPv6 blockade did not pass for {registry}"
                )


def _validate_controlled_oci_proof(
    identity: dict[str, Any], proof: dict[str, Any]
) -> None:
    suite = identity.get("suite")
    if suite not in SUITE_INPUTS:
        raise IdentityError(f"reusable proof has unsupported OCI suite: {suite}")
    lock_path = ROOT / "platform/oci-proof-mirror.lock.json"
    try:
        lock_bytes = lock_path.read_bytes()
        lock = json.loads(lock_bytes)
    except (OSError, json.JSONDecodeError) as error:
        raise IdentityError(f"current OCI mirror lock is unreadable: {error}") from error
    lock_sha256 = _sha256_bytes(lock_bytes)
    if identity.get("oci_mirror_lock_sha256") != lock_sha256:
        raise IdentityError("proof identity OCI mirror lock does not match current inputs")
    images = lock.get("images")
    if not isinstance(images, dict) or not images:
        raise IdentityError("current OCI mirror lock image inventory is invalid")
    requested_suites = {suite, "app-build"}
    expected_host = {
        name
        for name, spec in images.items()
        if isinstance(spec, dict)
        and isinstance(spec.get("suites"), list)
        and set(spec["suites"]).intersection(requested_suites)
    }
    expected_cluster = {
        name
        for name in expected_host
        if images[name].get("load_into_kind") is True
    }
    if not expected_host or not expected_cluster:
        raise IdentityError("current OCI mirror suite inventory is incomplete")

    controlled = proof.get("oci_controlled_source")
    if not isinstance(controlled, dict) or controlled.get("strict") is not True:
        raise IdentityError("reusable proof lacks strict controlled OCI source evidence")
    host = _validate_receipt_header(
        controlled.get("host"), label="host", lock_sha256=lock_sha256
    )
    host_images = host.get("images")
    if not isinstance(host_images, dict) or set(host_images) != expected_host:
        raise IdentityError("reusable proof host OCI image inventory drifted")
    if host.get("selected_count") != len(expected_host) or host.get("failures") != {}:
        raise IdentityError("reusable proof host OCI count or failure contract drifted")
    for name, observed in host_images.items():
        if (
            not isinstance(observed, dict)
            or observed.get("source") != "local-verified"
            or not isinstance(observed.get("image_id"), str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", observed["image_id"])
        ):
            raise IdentityError(f"reusable proof host OCI image binding is invalid: {name}")

    cluster_fields = (
        (("cluster", proof.get("cluster")),)
        if suite == "kind-gitops"
        else (
            ("primary_cluster", proof.get("primary_cluster")),
            ("restore_cluster", proof.get("restore_cluster")),
        )
    )
    for field, expected_cluster_name in cluster_fields:
        receipt = _validate_receipt_header(
            controlled.get(field), label=field, lock_sha256=lock_sha256
        )
        if not isinstance(expected_cluster_name, str) or not expected_cluster_name:
            raise IdentityError(f"reusable proof {field} cluster binding is missing")
        if receipt.get("cluster") != expected_cluster_name:
            raise IdentityError(f"reusable proof {field} cluster binding drifted")
        cluster_images = receipt.get("images")
        if not isinstance(cluster_images, dict) or set(cluster_images) != expected_cluster:
            raise IdentityError(f"reusable proof {field} OCI image inventory drifted")
        if receipt.get("loaded_count") != len(expected_cluster):
            raise IdentityError(f"reusable proof {field} OCI image count drifted")
        for name, observed in cluster_images.items():
            spec = images[name]
            if (
                not isinstance(observed, dict)
                or observed.get("canonical") != spec.get("canonical")
                or observed.get("local_ref") != spec.get("local_ref")
                or observed.get("locked_index_digest") != spec.get("digest")
                or not isinstance(observed.get("cri_image_id"), str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", observed["cri_image_id"])
                or not isinstance(observed.get("platform_target_digest"), str)
                or not re.fullmatch(
                    r"sha256:[0-9a-f]{64}", observed["platform_target_digest"]
                )
            ):
                raise IdentityError(
                    f"reusable proof {field} OCI image binding is invalid: {name}"
                )
        _validate_registry_blockades(receipt, label=field)


def record(identity_path: Path, proof_receipt: Path, output_dir: Path) -> dict[str, Any]:
    identity = _read_object(identity_path)
    expected = compute_identity(identity.get("suite", ""), identity.get("source_commit", ""))
    if identity != expected:
        raise IdentityError("proof identity no longer matches the checked-out inputs")
    proof = _read_object(proof_receipt)
    if proof.get("status") != "pass":
        raise IdentityError("only a passing proof receipt may be reused")
    if proof.get("tool_lock_sha256") != identity["tool_lock_sha256"]:
        raise IdentityError("proof receipt tool lock does not match the proof identity")
    checkout_commit = _checkout_commit()
    if proof.get("commit") != checkout_commit:
        raise IdentityError("proof receipt is not bound to the current checkout commit")
    if proof.get("production_changed") is not False:
        raise IdentityError("reusable proof must explicitly assert production_changed=false")
    _validate_controlled_oci_proof(identity, proof)
    output_dir.mkdir(parents=True, exist_ok=True)
    proof_bytes = _canonical_json(proof)
    proof_path = output_dir / "proof.json"
    _atomic_write(proof_path, proof_bytes)
    reusable = {
        "schema_version": 1,
        "status": "pass",
        "identity": identity,
        "proof_receipt_sha256": _sha256_bytes(proof_bytes),
        "proof_commit": proof.get("commit"),
        "proof_source_commit": proof.get("source_commit"),
        "production_changed": proof.get("production_changed"),
    }
    _atomic_write(output_dir / "record.json", _canonical_json(reusable))
    return reusable


def validate(identity_path: Path, record_path: Path, proof_path: Path) -> dict[str, Any]:
    identity = _read_object(identity_path)
    expected = compute_identity(identity.get("suite", ""), identity.get("source_commit", ""))
    if identity != expected:
        raise IdentityError("current proof inputs do not match the requested identity")
    reusable = _read_object(record_path)
    if reusable.get("schema_version") != 1 or reusable.get("status") != "pass":
        raise IdentityError("reusable proof record is not a passing v1 record")
    if reusable.get("identity") != identity:
        raise IdentityError("reusable proof record is bound to a different identity")
    proof_bytes = proof_path.read_bytes()
    if _sha256_bytes(proof_bytes) != reusable.get("proof_receipt_sha256"):
        raise IdentityError("reusable proof receipt digest mismatch")
    proof = _read_object(proof_path)
    if proof.get("status") != "pass":
        raise IdentityError("reusable proof payload is not passing")
    if proof.get("tool_lock_sha256") != identity["tool_lock_sha256"]:
        raise IdentityError("reusable proof payload uses a different tool lock")
    if proof.get("production_changed") is not False:
        raise IdentityError("reusable proof payload must assert production_changed=false")
    if reusable.get("production_changed") is not False:
        raise IdentityError("reusable proof record must assert production_changed=false")
    if reusable.get("proof_commit") != proof.get("commit"):
        raise IdentityError("reusable proof record commit does not match the proof payload")
    if reusable.get("proof_source_commit") != proof.get("source_commit"):
        raise IdentityError("reusable proof record source commit does not match the proof payload")
    _validate_controlled_oci_proof(identity, proof)
    return reusable


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    compute = sub.add_parser("compute")
    compute.add_argument("--suite", choices=tuple(SUITE_INPUTS), required=True)
    compute.add_argument("--source-commit", required=True)
    compute.add_argument("--output", type=Path, required=True)
    compute.add_argument("--github-output", type=Path)
    create = sub.add_parser("record")
    create.add_argument("--identity", type=Path, required=True)
    create.add_argument("--proof-receipt", type=Path, required=True)
    create.add_argument("--output-dir", type=Path, required=True)
    check = sub.add_parser("validate")
    check.add_argument("--identity", type=Path, required=True)
    check.add_argument("--record", type=Path, required=True)
    check.add_argument("--proof", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "compute":
            payload = compute_identity(args.suite, args.source_commit)
            _atomic_write(args.output, _canonical_json(payload))
            if args.github_output:
                with args.github_output.open("a", encoding="utf-8") as handle:
                    handle.write(f"identity={payload['identity_sha256']}\n")
            print(json.dumps(payload, sort_keys=True))
        elif args.command == "record":
            print(json.dumps(record(args.identity, args.proof_receipt, args.output_dir), sort_keys=True))
        else:
            print(json.dumps(validate(args.identity, args.record, args.proof), sort_keys=True))
    except (IdentityError, OSError, subprocess.CalledProcessError) as error:
        print(f"proof identity failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
