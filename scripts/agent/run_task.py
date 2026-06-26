#!/usr/bin/env python3
"""Deterministic read-only dry-run runner for agent task contracts."""

from __future__ import annotations

import argparse
import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent.check_non_ideal_task import run_non_ideal_guard
from scripts.agent.json_contract import (
    DuplicateKeyError,
    UnsupportedSchemaError,
    load_json_strict,
    loads_json_strict,
    validate_instance,
)
from scripts.agent.validate_handoff import validate_handoff
from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.validate_claim_registry import (
    load_registry,
    validate_registry_data,
)

STAGE_NAMES = [
    "capture_repository_state",
    "load_task",
    "validate_task_schema",
    "load_claim_registry",
    "run_non_ideal_guard",
    "resolve_source_revision",
    "prepare_execution_plan",
    "account_expected_evidence",
    "build_handoff",
    "validate_handoff",
    "verify_repository_unchanged",
    "finalize_result",
]

SOURCE_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")
PRODUCER = "scripts.agent.run_task"
RESIDUAL_GAPS = [
    "dry-run does not execute task validation commands",
    "dry-run does not apply repository changes",
    "run-evidence-lite persists only successfully planned dry-runs",
    "run-evidence-lite is not a CI attestation or write-mode authorization",
]

RUN_ID_RE = re.compile(r"^RUN-[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")
EVIDENCE_FILES = ("task.yml", "handoff.json", "validation.json", "run-result.json")

RepositoryStateReader = Callable[[Path], bytes]
SourceRevisionResolver = Callable[[Path], str]


class RunnerError(Exception):
    """Stable machine-readable operational error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.cleanup_errors: list[str] = []


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise RunnerError("INVALID_ARGUMENTS", message)


@dataclass(frozen=True)
class DryRunOutcome:
    result: dict[str, Any]
    exit_code: int


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _error(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def _stage_status(
    current: dict[str, str], name: str, status: str, message: str | None = None
) -> None:
    current[name] = status
    if message is not None:
        current[f"{name}:message"] = message


def _render_stages(statuses: dict[str, str]) -> list[dict[str, str]]:
    rendered: list[dict[str, str]] = []
    for name in STAGE_NAMES:
        item = {"name": name, "status": statuses.get(name, "not_run")}
        message = statuses.get(f"{name}:message")
        if message:
            item["message"] = message
        rendered.append(item)
    return rendered


def _normalize_task_path_arg(value: str) -> str:
    return value.replace("\\", "/").strip()


def resolve_task_path(repo_root: Path, value: str) -> tuple[Path, str]:
    raw_text = _normalize_task_path_arg(value)
    if not raw_text or raw_text.startswith("/") or WINDOWS_DRIVE_RE.match(raw_text):
        raise RunnerError("TASK_PATH_INVALID", "Task path must be repository-relative")

    raw = Path(raw_text)
    if any(part in {"", ".", ".."} for part in raw.parts):
        raise RunnerError(
            "TASK_PATH_INVALID",
            "Task path must not contain empty, current, or parent segments",
        )

    root = repo_root.resolve()
    candidate = repo_root / raw
    try:
        resolved = candidate.resolve()
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise RunnerError(
            "TASK_PATH_INVALID",
            "Task path resolves outside repository root",
        ) from exc

    if not candidate.is_file():
        raise RunnerError("TASK_FILE_NOT_FOUND", f"Task file not found: {raw_text}")

    return candidate, raw_text


def _load_task_bytes(task_path: Path) -> tuple[bytes, str, Any]:
    try:
        raw_task = task_path.read_bytes()
    except OSError as exc:
        raise RunnerError("TASK_FILE_UNREADABLE", str(exc)) from exc

    digest = hashlib.sha256(raw_task).hexdigest()
    try:
        task_text = raw_task.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerError("TASK_UTF8_INVALID", "Task file must be valid UTF-8") from exc

    try:
        task = loads_json_strict(task_text)
    except DuplicateKeyError as exc:
        raise RunnerError("TASK_JSON_DUPLICATE_KEY", str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise RunnerError("TASK_JSON_INVALID", f"JSON parse error: {exc.msg}") from exc

    return raw_task, digest, task


def _load_task_schema(repo_root: Path) -> dict[str, Any]:
    try:
        schema = load_json_strict(repo_root / "contracts/agent/task.schema.json")
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise RunnerError("CONTRACT_SCHEMA_INVALID", str(exc)) from exc
    if not isinstance(schema, dict):
        raise RunnerError("CONTRACT_SCHEMA_INVALID", "Task schema must be an object")
    return schema


def _schema_findings(task: Any, schema: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    try:
        violations = validate_instance(task, schema)
    except UnsupportedSchemaError as exc:
        raise RunnerError("CONTRACT_SCHEMA_UNSUPPORTED", str(exc)) from exc
    for violation in violations:
        field = violation["path"].removeprefix("$.")
        finding = {
            "code": "TASK_SCHEMA_INVALID",
            "message": violation["message"],
        }
        if field != "$":
            finding["field"] = field
        findings.append(finding)
    return findings


def _load_claim_registry(repo_root: Path) -> dict[str, Any]:
    registry_path = repo_root / "docs/claims/registry.yml"
    data, parser_findings, parser_exit = load_registry(registry_path)
    if parser_exit != 0 or data is None:
        code = "CLAIM_REGISTRY_NOT_FOUND"
        message = "Claim registry not found"
        if parser_findings:
            first = parser_findings[0]
            parser_code = first.get("code", "")
            if parser_code != "REGISTRY_MISSING":
                code = "CLAIM_REGISTRY_INVALID"
                message = first.get("message", "Claim registry is invalid")
        raise RunnerError(code, message)

    registry_findings = validate_registry_data(data, repo_root)
    if registry_findings:
        first = registry_findings[0]
        raise RunnerError(
            "CLAIM_REGISTRY_INVALID",
            first.get("message", "Claim registry is invalid"),
        )
    if not isinstance(data, dict):
        raise RunnerError("CLAIM_REGISTRY_INVALID", "Claim registry must be an object")
    return data


def validate_source_revision(source_revision: str) -> None:
    if not SOURCE_REVISION_RE.fullmatch(source_revision):
        raise RunnerError(
            "SOURCE_REVISION_INVALID",
            "Source revision must be the current 40-character lowercase Git HEAD",
        )


def resolve_git_head(repo_root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=repo_root,
            check=False,
            text=True,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RunnerError("SOURCE_REVISION_UNAVAILABLE", str(exc)) from exc

    revision = completed.stdout.strip()
    if completed.returncode != 0 or not SOURCE_REVISION_RE.fullmatch(revision):
        raise RunnerError(
            "SOURCE_REVISION_UNAVAILABLE",
            "Unable to resolve current Git HEAD",
        )
    if revision == "0" * 40:
        raise RunnerError("SOURCE_REVISION_UNAVAILABLE", "Git HEAD is invalid")
    return revision


def _git_output(repo_root: Path, arguments: list[str]) -> bytes:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=repo_root,
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RunnerError("GIT_STATE_UNAVAILABLE", str(exc)) from exc

    if completed.returncode != 0:
        raise RunnerError(
            "GIT_STATE_UNAVAILABLE",
            f"Unable to read Git-visible repository state: {' '.join(arguments)}",
        )
    return completed.stdout


def _hash_record(hasher: Any, label: bytes, payload: bytes) -> None:
    for part in (label, payload):
        hasher.update(len(part).to_bytes(8, byteorder="big", signed=False))
        hasher.update(part)


def _untracked_record(root: Path, raw_path: bytes) -> tuple[bytes, bytes, bytes]:
    candidate = root / Path(os.fsdecode(raw_path))
    try:
        before = candidate.lstat()
        mode = stat.S_IMODE(before.st_mode)
        if stat.S_ISLNK(before.st_mode):
            kind = b"symlink"
            content_digest = hashlib.sha256(
                os.fsencode(os.readlink(candidate))
            ).digest()
        elif stat.S_ISREG(before.st_mode):
            kind = b"file"
            content_hasher = hashlib.sha256()
            with candidate.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    content_hasher.update(chunk)
            content_digest = content_hasher.digest()
        else:
            kind = f"special:{stat.S_IFMT(before.st_mode):o}".encode("ascii")
            content_digest = hashlib.sha256(b"").digest()
        after = candidate.lstat()
    except OSError as exc:
        raise RunnerError(
            "GIT_STATE_UNAVAILABLE",
            f"Unable to fingerprint untracked path: {os.fsdecode(raw_path)}",
        ) from exc

    before_identity = (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
    )
    if before_identity != after_identity:
        raise RunnerError(
            "GIT_STATE_UNAVAILABLE",
            f"Untracked path changed while fingerprinting: {os.fsdecode(raw_path)}",
        )
    return kind, f"{mode:o}".encode("ascii"), content_digest


def repository_state_bytes(repo_root: Path) -> bytes:
    """Return a content-sensitive fingerprint of non-ignored Git-visible state."""

    root = repo_root.resolve()
    head_before = resolve_git_head(root)
    index_diff = _git_output(
        root,
        [
            "diff",
            "--cached",
            "--no-ext-diff",
            "--binary",
            "--full-index",
            "HEAD",
            "--",
        ],
    )
    worktree_diff = _git_output(
        root,
        ["diff", "--no-ext-diff", "--binary", "--full-index", "--"],
    )
    untracked_raw = _git_output(
        root, ["ls-files", "--others", "--exclude-standard", "-z"]
    )

    hasher = hashlib.sha256()
    _hash_record(hasher, b"head", head_before.encode("ascii"))
    _hash_record(hasher, b"index-diff", index_diff)
    _hash_record(hasher, b"worktree-diff", worktree_diff)

    for raw_path in sorted(path for path in untracked_raw.split(b"\0") if path):
        kind, mode, content_digest = _untracked_record(root, raw_path)
        _hash_record(hasher, b"untracked-path", raw_path)
        _hash_record(hasher, b"untracked-kind", kind)
        _hash_record(hasher, b"untracked-mode", mode)
        _hash_record(hasher, b"untracked-content-sha256", content_digest)
    head_after = resolve_git_head(root)
    if head_before != head_after:
        raise RunnerError(
            "GIT_STATE_UNAVAILABLE",
            "Git HEAD changed while fingerprinting repository state",
        )

    return hasher.digest()


def _assert_repository_unchanged(
    repo_root: Path,
    before_state: bytes,
    repository_state_reader: RepositoryStateReader,
) -> None:
    if before_state != repository_state_reader(repo_root):
        raise RunnerError(
            "REPO_MUTATED_DURING_DRY_RUN",
            "Git-visible repository content changed during dry run",
        )


def _execution_plan(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "allowed_paths": list(task["allowed_paths"]),
        "forbidden_paths": list(task["forbidden_paths"]),
        "delete_allowed": bool(task["delete_allowed"]),
        "planned_changed_paths": [],
        "planned_deleted_paths": [],
    }


def _evidence_accounting(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "expected_evidence": list(task["expected_evidence"]),
        "evidence_produced": [],
        "missing_evidence": list(task["expected_evidence"]),
    }


def _validate_evidence_accounting(
    task: dict[str, Any], accounting: dict[str, Any]
) -> None:
    expected = set(task["expected_evidence"])
    produced = set(accounting.get("evidence_produced", []))
    missing = set(accounting.get("missing_evidence", []))
    if expected - produced - missing:
        raise RunnerError(
            "EVIDENCE_ACCOUNTING_INCOMPLETE",
            "Expected evidence is not fully accounted",
        )
    if missing - expected:
        raise RunnerError(
            "EVIDENCE_ACCOUNTING_INVALID",
            "Missing evidence contains entries not required by the task",
        )


def _handoff_id(task_id: str, task_digest: str) -> str:
    return f"DRY-RUN-{task_id}-{task_digest[:12].upper()}"


def _handoff(
    task: dict[str, Any], task_digest: str, source_revision: str
) -> dict[str, Any]:
    return {
        "handoff_id": _handoff_id(task["task_id"], task_digest),
        "task_id": task["task_id"],
        "task_contract_sha256": task_digest,
        "source_revision": source_revision,
        "producer": PRODUCER,
        "outcome": "incomplete",
        "changed_paths": [],
        "deleted_paths": [],
        "claims_addressed": list(task["claims"]),
        "evidence_produced": [],
        "missing_evidence": list(task["expected_evidence"]),
        "validation_results": [
            {"command": command, "status": "not_run"}
            for command in task["validation_commands"]
        ],
        "blockers": [],
        "residual_gaps": list(RESIDUAL_GAPS),
    }


def _base_result(
    *,
    status: str,
    task_file: str,
    source_revision: str | None,
    stages: list[dict[str, str]],
    findings: list[dict[str, str]],
    task_id: str | None = None,
    task_digest: str | None = None,
    execution_plan: dict[str, Any] | None = None,
    evidence_accounting: dict[str, Any] | None = None,
    handoff: dict[str, Any] | None = None,
    repository_unchanged: bool = False,
) -> dict[str, Any]:
    return {
        "mode": "dry_run",
        "status": status,
        "task_file": task_file,
        "task_id": task_id,
        "task_contract_sha256": task_digest,
        "source_revision": source_revision,
        "stages": stages,
        "findings": findings,
        "execution_plan": execution_plan or {},
        "evidence_accounting": evidence_accounting or {},
        "handoff": handoff or {},
        "repository_unchanged": repository_unchanged,
    }


def _repo_contains(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve())
        return True
    except (OSError, RuntimeError, ValueError):
        return False


def _ensure_no_symlink_parents(path: Path, *, stop_at: Path | None = None) -> None:
    current = path if path.exists() else path.parent
    stop = stop_at.resolve() if stop_at is not None else None
    while True:
        if current.is_symlink():
            raise RunnerError(
                "OUTPUT_DIR_INVALID",
                "Output path and its parents must not be symlinks",
            )
        if stop is not None and current.resolve(strict=False) == stop:
            break
        parent = current.parent
        if parent == current:
            break
        current = parent


def _utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"RUN-{timestamp}-{secrets.token_hex(6)}"


def _load_evidence_schema(repo_root: Path, name: str) -> dict[str, Any]:
    try:
        schema = load_json_strict(repo_root / "contracts/agent" / name)
    except (OSError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise RunnerError("CONTRACT_SCHEMA_INVALID", str(exc)) from exc
    if not isinstance(schema, dict):
        raise RunnerError("CONTRACT_SCHEMA_INVALID", f"{name} must be an object")
    return schema


def _validate_evidence_payload(
    payload: dict[str, Any], schema: dict[str, Any], *, label: str
) -> None:
    try:
        violations = validate_instance(payload, schema)
    except UnsupportedSchemaError as exc:
        raise RunnerError("CONTRACT_SCHEMA_UNSUPPORTED", str(exc)) from exc
    if violations:
        first = violations[0]
        raise RunnerError(
            "RUN_EVIDENCE_SCHEMA_INVALID",
            f"{label} failed schema validation at {first['path']}: {first['message']}",
        )


def _json_bytes(data: Any) -> bytes:
    return _json(data).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_file_sync(path: Path, data: bytes) -> None:
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_noreplace(source: Path, target: Path) -> None:
    """Atomically publish one directory without replacing an existing target."""

    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise RunnerError(
            "OUTPUT_ATOMIC_PUBLISH_UNAVAILABLE",
            "renameat2(RENAME_NOREPLACE) is required for atomic publication",
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        -100,
        os.fsencode(source),
        -100,
        os.fsencode(target),
        1,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise RunnerError(
            "OUTPUT_DIR_EXISTS",
            "Output directory must not already exist",
        )
    raise RunnerError("OUTPUT_WRITE_FAILED", os.strerror(error_number))


def _default_evidence_target(repo_root: Path, run_id: str) -> tuple[Path, str]:
    if not RUN_ID_RE.fullmatch(run_id):
        raise RunnerError("RUN_ID_INVALID", "Generated run_id has an invalid format")
    evidence_root = repo_root / "artifacts" / "agent-runs"
    _ensure_no_symlink_parents(evidence_root, stop_at=repo_root)
    evidence_root.mkdir(parents=True, exist_ok=True)
    _ensure_no_symlink_parents(evidence_root, stop_at=repo_root)
    return evidence_root / run_id, f"artifacts/agent-runs/{run_id}"


def validate_output_dir(repo_root: Path, output_dir: Path) -> Path:
    if ".." in output_dir.parts:
        raise RunnerError(
            "OUTPUT_DIR_INVALID",
            "Relative output directory must not contain parent traversal",
        )
    candidate = output_dir if output_dir.is_absolute() else (Path.cwd() / output_dir)
    candidate = candidate.absolute()
    root = repo_root.resolve()

    resolved_candidate = candidate.resolve(strict=False)
    if resolved_candidate == root or _repo_contains(root, resolved_candidate):
        raise RunnerError(
            "OUTPUT_DIR_IN_REPOSITORY",
            "Custom output directory must be outside the repository root",
        )
    if candidate.is_symlink():
        raise RunnerError(
            "OUTPUT_DIR_INVALID", "Output directory must not be a symlink"
        )
    if not candidate.parent.exists() or not candidate.parent.is_dir():
        raise RunnerError(
            "OUTPUT_DIR_INVALID",
            "Output directory parent must be an existing directory",
        )
    _ensure_no_symlink_parents(candidate)
    if candidate.exists():
        raise RunnerError(
            "OUTPUT_DIR_EXISTS",
            "Output directory must not already exist",
        )
    return candidate


def _validation_payload(
    *,
    run_id: str,
    task: dict[str, Any],
    task_digest: str,
    source_revision: str,
    repository_state_sha256: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "created_at": created_at,
        "task_id": task["task_id"],
        "task_contract_sha256": task_digest,
        "source_revision": source_revision,
        "repository_state_sha256": repository_state_sha256,
        "status": "passed",
        "checks": [
            {"name": "task_schema", "status": "passed"},
            {"name": "claim_registry", "status": "passed"},
            {"name": "non_ideal_guard", "status": "passed"},
            {"name": "handoff_contract", "status": "passed"},
            {"name": "repository_unchanged", "status": "passed"},
        ],
    }


def publish_evidence_bundle(
    repo_root: Path,
    output_dir: Path | None,
    *,
    run_id: str,
    raw_task: bytes,
    task: dict[str, Any],
    task_digest: str,
    source_revision: str,
    repository_state_sha256: str,
    started_at: str,
    completed_at: str,
    run_result: dict[str, Any],
    handoff: dict[str, Any],
) -> tuple[Path, str]:
    if output_dir is None:
        target, display_path = _default_evidence_target(repo_root, run_id)
    else:
        target = validate_output_dir(repo_root, output_dir)
        display_path = str(output_dir)

    parent = target.parent
    if target.exists() or target.is_symlink():
        raise RunnerError(
            "OUTPUT_DIR_EXISTS", "Output directory must not already exist"
        )

    handoff_bytes = _json_bytes(handoff)
    validation = _validation_payload(
        run_id=run_id,
        task=task,
        task_digest=task_digest,
        source_revision=source_revision,
        repository_state_sha256=repository_state_sha256,
        created_at=completed_at,
    )
    validation_schema = _load_evidence_schema(repo_root, "validation.schema.json")
    _validate_evidence_payload(validation, validation_schema, label="validation.json")
    validation_bytes = _json_bytes(validation)

    persisted_result = {
        **run_result,
        "schema_version": "1.0",
        "run_id": run_id,
        "outcome": handoff["outcome"],
        "started_at": started_at,
        "completed_at": completed_at,
        "repository_state_sha256": repository_state_sha256,
        "repository_state": {
            "source_revision": source_revision,
            "git_visible_sha256": repository_state_sha256,
        },
        "artifacts": {
            "task": {"path": "task.yml", "sha256": _sha256(raw_task)},
            "handoff": {"path": "handoff.json", "sha256": _sha256(handoff_bytes)},
            "validation": {
                "path": "validation.json",
                "sha256": _sha256(validation_bytes),
            },
            "run_result": {"path": "run-result.json"},
        },
        "residual_gaps": list(RESIDUAL_GAPS),
    }
    result_schema = _load_evidence_schema(repo_root, "run-result.schema.json")
    _validate_evidence_payload(persisted_result, result_schema, label="run-result.json")
    result_bytes = _json_bytes(persisted_result)

    staged_payloads = {
        "task.yml": raw_task,
        "handoff.json": handoff_bytes,
        "validation.json": validation_bytes,
        "run-result.json": result_bytes,
    }
    staging = Path(tempfile.mkdtemp(prefix=".agent-run-staging-", dir=parent))
    published = False
    pending_error: RunnerError | None = None
    try:
        os.chmod(staging, 0o700)
        for name, payload in staged_payloads.items():
            _write_file_sync(staging / name, payload)
        actual_names = {path.name for path in staging.iterdir()}
        if actual_names != set(EVIDENCE_FILES):
            raise RunnerError(
                "RUN_EVIDENCE_INCOMPLETE",
                "Staged evidence bundle does not contain exactly four files",
            )
        for name, expected in staged_payloads.items():
            if (staging / name).read_bytes() != expected:
                raise RunnerError(
                    "RUN_EVIDENCE_WRITE_MISMATCH",
                    f"Staged evidence file does not match serialized payload: {name}",
                )
        _fsync_directory(staging)
        _rename_noreplace(staging, target)
        published = True
        _fsync_directory(parent)
    except RunnerError as exc:
        pending_error = exc
        if published and target.is_dir() and not target.is_symlink():
            try:
                shutil.rmtree(target)
                _fsync_directory(parent)
            except OSError as cleanup_error:
                exc.cleanup_errors.append(str(cleanup_error))
        raise
    except OSError as exc:
        runner_error = RunnerError("OUTPUT_WRITE_FAILED", str(exc))
        pending_error = runner_error
        if published and target.is_dir() and not target.is_symlink():
            try:
                shutil.rmtree(target)
                _fsync_directory(parent)
            except OSError as cleanup_error:
                runner_error.cleanup_errors.append(str(cleanup_error))
        raise runner_error from exc
    finally:
        if staging.exists():
            try:
                shutil.rmtree(staging)
            except OSError as cleanup_error:
                if pending_error is not None:
                    pending_error.cleanup_errors.append(str(cleanup_error))
                else:
                    raise RunnerError(
                        "OUTPUT_CLEANUP_FAILED", str(cleanup_error)
                    ) from cleanup_error
    return target, display_path


def _remove_published_output(target: Path) -> None:
    if target.is_symlink():
        target.unlink()
        return
    if target.is_dir():
        shutil.rmtree(target)


def _run_dry_run(
    *,
    repo_root: Path,
    task_file: str,
    output_dir: Path | None = None,
    persist: bool = False,
    run_id_factory: Callable[[], str] | None = None,
    repository_state_reader: RepositoryStateReader | None = None,
    source_revision_resolver: SourceRevisionResolver | None = None,
) -> DryRunOutcome:
    root = repo_root.resolve()
    state_reader = repository_state_reader or repository_state_bytes
    revision_resolver = source_revision_resolver or resolve_git_head
    statuses: dict[str, str] = {}
    published_target: Path | None = None
    started_at = _utc_timestamp()
    should_persist = persist or output_dir is not None

    before_state = state_reader(root)
    _stage_status(statuses, "capture_repository_state", "passed")

    try:
        task_path, task_rel = resolve_task_path(root, task_file)
        raw_task, task_digest, task = _load_task_bytes(task_path)
        _stage_status(statuses, "load_task", "passed")

        task_schema = _load_task_schema(root)
        schema_findings = _schema_findings(task, task_schema)
        if schema_findings:
            _stage_status(statuses, "validate_task_schema", "blocked")
            _assert_repository_unchanged(root, before_state, state_reader)
            _stage_status(statuses, "verify_repository_unchanged", "passed")
            _stage_status(statuses, "finalize_result", "passed")
            result = _base_result(
                status="blocked",
                task_file=task_rel,
                source_revision=None,
                stages=_render_stages(statuses),
                findings=schema_findings,
                task_id=task.get("task_id") if isinstance(task, dict) else None,
                task_digest=task_digest,
                repository_unchanged=True,
            )
            return DryRunOutcome(result=result, exit_code=1)
        _stage_status(statuses, "validate_task_schema", "passed")

        registry = _load_claim_registry(root)
        _stage_status(statuses, "load_claim_registry", "passed")

        guard_findings = run_non_ideal_guard(task, registry, task_schema=task_schema)
        if guard_findings:
            _stage_status(statuses, "run_non_ideal_guard", "blocked")
            _assert_repository_unchanged(root, before_state, state_reader)
            _stage_status(statuses, "verify_repository_unchanged", "passed")
            _stage_status(statuses, "finalize_result", "passed")
            result = _base_result(
                status="blocked",
                task_file=task_rel,
                source_revision=None,
                stages=_render_stages(statuses),
                findings=guard_findings,
                task_id=task["task_id"] if isinstance(task, dict) else None,
                task_digest=task_digest,
                repository_unchanged=True,
            )
            return DryRunOutcome(result=result, exit_code=1)
        _stage_status(statuses, "run_non_ideal_guard", "passed")

        revision = revision_resolver(root)
        validate_source_revision(revision)
        _stage_status(statuses, "resolve_source_revision", "passed")

        if not isinstance(task, dict):
            raise RunnerError("TASK_SCHEMA_INVALID", "Task must be a JSON object")

        execution_plan = _execution_plan(task)
        _stage_status(statuses, "prepare_execution_plan", "passed")

        evidence_accounting = _evidence_accounting(task)
        _validate_evidence_accounting(task, evidence_accounting)
        _stage_status(statuses, "account_expected_evidence", "passed")

        handoff = _handoff(task, task_digest, revision)
        _stage_status(statuses, "build_handoff", "passed")

        handoff_findings = validate_handoff(
            task,
            handoff,
            task_bytes=raw_task,
            repo_root=root,
            claim_registry=registry,
        )
        if handoff_findings:
            first = handoff_findings[0]
            raise RunnerError(
                "HANDOFF_VALIDATION_FAILED",
                first.get("message", "Generated dry-run handoff failed validation"),
            )
        _stage_status(statuses, "validate_handoff", "passed")

        if revision_resolver(root) != revision:
            raise RunnerError(
                "SOURCE_REVISION_CHANGED_DURING_DRY_RUN",
                "Git HEAD changed during dry run",
            )
        _assert_repository_unchanged(root, before_state, state_reader)
        _stage_status(statuses, "verify_repository_unchanged", "passed")
        _stage_status(statuses, "finalize_result", "passed")

        result = _base_result(
            status="planned",
            task_file=task_rel,
            task_id=task["task_id"],
            task_digest=task_digest,
            source_revision=revision,
            stages=_render_stages(statuses),
            findings=[],
            execution_plan=execution_plan,
            evidence_accounting=evidence_accounting,
            handoff=handoff,
            repository_unchanged=True,
        )
        if should_persist:
            run_id = (run_id_factory or _new_run_id)()
            if not RUN_ID_RE.fullmatch(run_id):
                raise RunnerError("RUN_ID_INVALID", "run_id has an invalid format")
            completed_at = _utc_timestamp()
            published_target, evidence_path = publish_evidence_bundle(
                root,
                output_dir,
                run_id=run_id,
                raw_task=raw_task,
                task=task,
                task_digest=task_digest,
                source_revision=revision,
                repository_state_sha256=hashlib.sha256(before_state).hexdigest(),
                started_at=started_at,
                completed_at=completed_at,
                run_result=result,
                handoff=handoff,
            )
            result = {**result, "run_id": run_id, "evidence_path": evidence_path}

        if revision_resolver(root) != revision:
            raise RunnerError(
                "SOURCE_REVISION_CHANGED_DURING_DRY_RUN",
                "Git HEAD changed during dry run",
            )
        _assert_repository_unchanged(root, before_state, state_reader)
        return DryRunOutcome(result=result, exit_code=0)
    except Exception as exc:
        guarded_codes = {
            "REPO_MUTATED_DURING_DRY_RUN",
            "SOURCE_REVISION_CHANGED_DURING_DRY_RUN",
        }
        if isinstance(exc, RunnerError) and exc.code in guarded_codes:
            if published_target is not None:
                try:
                    _remove_published_output(published_target)
                except OSError as cleanup_error:
                    exc.cleanup_errors.append(str(cleanup_error))
            raise
        try:
            _assert_repository_unchanged(root, before_state, state_reader)
        except RunnerError as mutation_error:
            if published_target is not None:
                try:
                    _remove_published_output(published_target)
                except OSError as cleanup_error:
                    mutation_error.cleanup_errors.append(str(cleanup_error))
            raise mutation_error from exc
        raise


def run_dry_run(
    *,
    repo_root: Path,
    task_file: str,
    output_dir: Path | None = None,
    persist: bool = True,
) -> DryRunOutcome:
    return _run_dry_run(
        repo_root=repo_root,
        task_file=task_file,
        output_dir=output_dir,
        persist=persist,
        repository_state_reader=repository_state_bytes,
        source_revision_resolver=resolve_git_head,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Dry-run an agent task contract")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly select dry-run mode. Dry-run is also the default.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional single evidence-bundle target outside the repository root",
    )
    parser.add_argument(
        "--no-persist",
        action="store_true",
        help="Emit the dry-run result to stdout without writing run evidence",
    )
    parser.add_argument("task_file", help="Repository-relative task JSON file")
    return parser


def _emit_error(code: str, message: str) -> int:
    sys.stderr.write(_json(_error(code, message)))
    return 2


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
        root = Path(REPO_ROOT)
        if args.no_persist and args.output_dir:
            raise RunnerError(
                "INVALID_ARGUMENTS",
                "--no-persist and --output-dir cannot be used together",
            )
        outcome = run_dry_run(
            repo_root=root,
            task_file=args.task_file,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            persist=not args.no_persist,
        )
    except RunnerError as exc:
        return _emit_error(exc.code, exc.message)
    except (OSError, ValueError, UnsupportedSchemaError) as exc:
        return _emit_error("RUNNER_ERROR", str(exc))

    sys.stdout.write(_json(outcome.result))
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
