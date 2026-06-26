#!/usr/bin/env python3
"""Deterministic read-only dry-run runner for agent task contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
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
    "load_task",
    "validate_task_schema",
    "load_claim_registry",
    "run_non_ideal_guard",
    "resolve_source_revision",
    "capture_repository_state",
    "prepare_execution_plan",
    "account_expected_evidence",
    "build_handoff",
    "validate_handoff",
    "verify_repository_unchanged",
    "emit_result",
]

SOURCE_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")
PRODUCER = "scripts.agent.run_task"
RESIDUAL_GAPS = [
    "dry-run does not execute task validation commands",
    "dry-run does not apply repository changes",
]

RepositoryStatusReader = Callable[[Path], bytes]


class RunnerError(Exception):
    """Stable machine-readable operational error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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


def git_status_bytes(repo_root: Path) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RunnerError("GIT_STATUS_UNAVAILABLE", str(exc)) from exc

    if completed.returncode != 0:
        raise RunnerError("GIT_STATUS_UNAVAILABLE", "Unable to read Git status")
    return completed.stdout


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


def _ensure_no_symlink_parents(path: Path) -> None:
    current = path if path.exists() else path.parent
    while True:
        if current.exists() and current.is_symlink():
            raise RunnerError(
                "OUTPUT_DIR_INVALID",
                "Output path and its parents must not be symlinks",
            )
        parent = current.parent
        if parent == current:
            break
        current = parent


def validate_output_dir(repo_root: Path, output_dir: Path) -> Path:
    candidate = output_dir if output_dir.is_absolute() else (Path.cwd() / output_dir)
    candidate = candidate.absolute()
    root = repo_root.resolve()

    resolved_candidate = candidate.resolve(strict=False)
    if resolved_candidate == root or _repo_contains(root, resolved_candidate):
        raise RunnerError(
            "OUTPUT_DIR_IN_REPOSITORY",
            "Output directory must be outside the repository root",
        )
    if candidate.exists() and candidate.is_symlink():
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
        if not candidate.is_dir():
            raise RunnerError("OUTPUT_DIR_INVALID", "Output path must be a directory")
        if any(candidate.iterdir()):
            raise RunnerError(
                "OUTPUT_DIR_NOT_EMPTY",
                "Output directory must be new or empty",
            )
    return candidate


def publish_output_dir(
    repo_root: Path,
    output_dir: Path,
    *,
    run_result: dict[str, Any],
    handoff: dict[str, Any],
) -> Path:
    target = validate_output_dir(repo_root, output_dir)
    parent = target.parent
    staging_raw = tempfile.mkdtemp(prefix=".run-task-", dir=parent)
    staging = Path(staging_raw)
    try:
        (staging / "handoff.json").write_text(_json(handoff), encoding="utf-8")
        (staging / "run-result.json").write_text(_json(run_result), encoding="utf-8")
        os.replace(staging, target)
    except OSError as exc:
        raise RunnerError("OUTPUT_WRITE_FAILED", str(exc)) from exc
    finally:
        if staging.exists():
            for child in staging.iterdir():
                child.unlink(missing_ok=True)
            staging.rmdir()
    return target


def _remove_published_output(target: Path) -> None:
    for name in ("handoff.json", "run-result.json"):
        candidate = target / name
        if candidate.exists() or candidate.is_symlink():
            candidate.unlink()
    try:
        target.rmdir()
    except OSError:
        pass


def run_dry_run(
    *,
    repo_root: Path,
    task_file: str,
    source_revision: str,
    output_dir: Path | None = None,
    repository_status_reader: RepositoryStatusReader = git_status_bytes,
) -> DryRunOutcome:
    root = repo_root.resolve()
    statuses: dict[str, str] = {}
    task_path, task_rel = resolve_task_path(root, task_file)

    raw_task, task_digest, task = _load_task_bytes(task_path)
    _stage_status(statuses, "load_task", "passed")

    task_schema = _load_task_schema(root)
    schema_findings = _schema_findings(task, task_schema)
    if schema_findings:
        _stage_status(statuses, "validate_task_schema", "blocked")
        result = _base_result(
            status="blocked",
            task_file=task_rel,
            source_revision=source_revision,
            stages=_render_stages(statuses),
            findings=schema_findings,
            task_id=task.get("task_id") if isinstance(task, dict) else None,
            task_digest=task_digest,
        )
        return DryRunOutcome(result=result, exit_code=1)
    _stage_status(statuses, "validate_task_schema", "passed")

    registry = _load_claim_registry(root)
    _stage_status(statuses, "load_claim_registry", "passed")

    guard_findings = run_non_ideal_guard(task, registry, task_schema=task_schema)
    if guard_findings:
        _stage_status(statuses, "run_non_ideal_guard", "blocked")
        result = _base_result(
            status="blocked",
            task_file=task_rel,
            source_revision=source_revision,
            stages=_render_stages(statuses),
            findings=guard_findings,
            task_id=task["task_id"] if isinstance(task, dict) else None,
            task_digest=task_digest,
        )
        return DryRunOutcome(result=result, exit_code=1)
    _stage_status(statuses, "run_non_ideal_guard", "passed")

    validate_source_revision(source_revision)
    _stage_status(statuses, "resolve_source_revision", "passed")

    before_status = repository_status_reader(root)
    _stage_status(statuses, "capture_repository_state", "passed")

    if not isinstance(task, dict):
        raise RunnerError("TASK_SCHEMA_INVALID", "Task must be a JSON object")

    execution_plan = _execution_plan(task)
    _stage_status(statuses, "prepare_execution_plan", "passed")

    evidence_accounting = _evidence_accounting(task)
    _validate_evidence_accounting(task, evidence_accounting)
    _stage_status(statuses, "account_expected_evidence", "passed")

    handoff = _handoff(task, task_digest, source_revision)
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

    after_status = repository_status_reader(root)
    if before_status != after_status:
        raise RunnerError(
            "REPO_MUTATED_DURING_DRY_RUN",
            "Repository status changed during dry run",
        )
    _stage_status(statuses, "verify_repository_unchanged", "passed")
    _stage_status(statuses, "emit_result", "passed")

    result = _base_result(
        status="planned",
        task_file=task_rel,
        task_id=task["task_id"],
        task_digest=task_digest,
        source_revision=source_revision,
        stages=_render_stages(statuses),
        findings=[],
        execution_plan=execution_plan,
        evidence_accounting=evidence_accounting,
        handoff=handoff,
        repository_unchanged=True,
    )
    if output_dir is not None:
        target = publish_output_dir(
            root, output_dir, run_result=result, handoff=handoff
        )
        after_output_status = repository_status_reader(root)
        if before_status != after_output_status:
            _remove_published_output(target)
            raise RunnerError(
                "REPO_MUTATED_DURING_DRY_RUN",
                "Repository status changed during dry run",
            )
    return DryRunOutcome(result=result, exit_code=0)


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Dry-run an agent task contract")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicitly select dry-run mode. Dry-run is also the default.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory outside the repository root",
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
        source_revision = resolve_git_head(root)
        outcome = run_dry_run(
            repo_root=root,
            task_file=args.task_file,
            source_revision=source_revision,
            output_dir=Path(args.output_dir) if args.output_dir else None,
        )
    except RunnerError as exc:
        return _emit_error(exc.code, exc.message)
    except (OSError, ValueError, UnsupportedSchemaError) as exc:
        return _emit_error("RUNNER_ERROR", str(exc))

    sys.stdout.write(_json(outcome.result))
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
