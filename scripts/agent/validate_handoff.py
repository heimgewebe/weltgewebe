#!/usr/bin/env python3
"""Validate an agent handoff against its task contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import REPO_ROOT

TASK_REQUIRED_FIELDS = {
    "task_id",
    "allowed_paths",
    "forbidden_paths",
    "claims",
    "expected_evidence",
    "validation_commands",
    "delete_allowed",
}
HANDOFF_REQUIRED_FIELDS = {
    "handoff_id",
    "task_id",
    "task_contract_sha256",
    "source_revision",
    "producer",
    "outcome",
    "changed_paths",
    "deleted_paths",
    "claims_addressed",
    "evidence_produced",
    "missing_evidence",
    "validation_results",
    "blockers",
    "residual_gaps",
}
HANDOFF_ALLOWED_FIELDS = HANDOFF_REQUIRED_FIELDS
HANDOFF_OUTCOMES = {"ready_for_review", "blocked", "incomplete"}
VALIDATION_STATUSES = {"passed", "failed", "not_run"}
TASK_ID_RE = re.compile(r"^[A-Z]+(?:-[A-Z]+)*-[0-9]{3}$")
HANDOFF_ID_RE = re.compile(r"^[A-Z0-9]+(?:-[A-Z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_REVISION_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def _finding(code: str, message: str, field: str | None = None) -> dict[str, str]:
    finding = {"code": code, "message": message}
    if field is not None:
        finding["field"] = field
    return finding


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except OSError as exc:
        return None, f"Datei kann nicht gelesen werden: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc.msg}"


def _resolve_repo_relative(repo_root: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        raise ValueError(f"Path must be repository-relative: {value}")

    root = repo_root.resolve()
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes repository root: {value}") from exc
    return resolved


def _normalize_repo_path(value: str) -> str | None:
    normalized = value.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/"):
        return None
    parts = [part for part in normalized.split("/") if part not in {"", "."}]
    if not parts or ".." in parts:
        return None
    return "/".join(parts)


def _path_matches_scope(path: str, scope: str) -> bool:
    normalized_path = _normalize_repo_path(path)
    normalized_scope = _normalize_repo_path(scope)
    if normalized_path is None or normalized_scope is None:
        return False
    return normalized_path == normalized_scope or normalized_path.startswith(
        normalized_scope.rstrip("/") + "/"
    )


def _validate_string_array(
    payload: dict[str, Any], field: str, *, allow_empty: bool
) -> list[dict[str, str]]:
    value = payload.get(field)
    if not isinstance(value, list):
        return [_finding("HANDOFF_SCHEMA_INVALID", f"{field} must be an array", field)]
    if not allow_empty and not value:
        return [_finding("HANDOFF_SCHEMA_INVALID", f"{field} must not be empty", field)]
    if any(not isinstance(item, str) or not item.strip() for item in value):
        return [
            _finding(
                "HANDOFF_SCHEMA_INVALID",
                f"{field} entries must be non-empty strings",
                field,
            )
        ]
    if len(value) != len(set(value)):
        return [_finding("HANDOFF_SCHEMA_INVALID", f"{field} must be unique", field)]
    return []


def _validate_task_shape(task: Any) -> list[dict[str, str]]:
    if not isinstance(task, dict):
        return [_finding("TASK_SCHEMA_INVALID", "Task contract must be a JSON object")]

    findings: list[dict[str, str]] = []
    missing = sorted(TASK_REQUIRED_FIELDS - set(task))
    for field in missing:
        findings.append(_finding("TASK_SCHEMA_INVALID", f"Missing required field: {field}", field))

    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        findings.append(
            _finding(
                "TASK_SCHEMA_INVALID",
                "task_id must match [A-Z]+(-[A-Z]+)*-[0-9]{3}",
                "task_id",
            )
        )

    for field in (
        "allowed_paths",
        "forbidden_paths",
        "claims",
        "expected_evidence",
        "validation_commands",
    ):
        value = task.get(field)
        if not isinstance(value, list) or any(
            not isinstance(item, str) or not item.strip() for item in value
        ):
            findings.append(
                _finding(
                    "TASK_SCHEMA_INVALID",
                    f"{field} must be an array of non-empty strings",
                    field,
                )
            )

    if not isinstance(task.get("delete_allowed"), bool):
        findings.append(
            _finding("TASK_SCHEMA_INVALID", "delete_allowed must be a boolean", "delete_allowed")
        )
    return findings


def _validate_handoff_shape(handoff: Any) -> list[dict[str, str]]:
    if not isinstance(handoff, dict):
        return [_finding("HANDOFF_SCHEMA_INVALID", "Handoff must be a JSON object")]

    findings: list[dict[str, str]] = []
    missing = sorted(HANDOFF_REQUIRED_FIELDS - set(handoff))
    unexpected = sorted(set(handoff) - HANDOFF_ALLOWED_FIELDS)
    for field in missing:
        findings.append(
            _finding("HANDOFF_SCHEMA_INVALID", f"Missing required field: {field}", field)
        )
    for field in unexpected:
        findings.append(
            _finding("HANDOFF_SCHEMA_INVALID", f"Unexpected field: {field}", field)
        )

    handoff_id = handoff.get("handoff_id")
    if not isinstance(handoff_id, str) or not HANDOFF_ID_RE.fullmatch(handoff_id):
        findings.append(
            _finding(
                "HANDOFF_SCHEMA_INVALID",
                "handoff_id must contain uppercase letters, digits and hyphens",
                "handoff_id",
            )
        )

    task_id = handoff.get("task_id")
    if not isinstance(task_id, str) or not TASK_ID_RE.fullmatch(task_id):
        findings.append(
            _finding("HANDOFF_SCHEMA_INVALID", "task_id has invalid format", "task_id")
        )

    digest = handoff.get("task_contract_sha256")
    if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
        findings.append(
            _finding(
                "HANDOFF_SCHEMA_INVALID",
                "task_contract_sha256 must be 64 lowercase hex characters",
                "task_contract_sha256",
            )
        )

    revision = handoff.get("source_revision")
    if not isinstance(revision, str) or not SOURCE_REVISION_RE.fullmatch(revision):
        findings.append(
            _finding(
                "HANDOFF_SCHEMA_INVALID",
                "source_revision must be a 40- or 64-character lowercase hex revision",
                "source_revision",
            )
        )

    producer = handoff.get("producer")
    if not isinstance(producer, str) or not producer.strip():
        findings.append(
            _finding("HANDOFF_SCHEMA_INVALID", "producer must be non-empty", "producer")
        )

    outcome = handoff.get("outcome")
    if outcome not in HANDOFF_OUTCOMES:
        findings.append(
            _finding(
                "HANDOFF_SCHEMA_INVALID",
                f"outcome must be one of {sorted(HANDOFF_OUTCOMES)}",
                "outcome",
            )
        )

    for field in (
        "changed_paths",
        "deleted_paths",
        "evidence_produced",
        "missing_evidence",
        "blockers",
        "residual_gaps",
    ):
        findings.extend(_validate_string_array(handoff, field, allow_empty=True))
    findings.extend(_validate_string_array(handoff, "claims_addressed", allow_empty=False))

    results = handoff.get("validation_results")
    if not isinstance(results, list):
        findings.append(
            _finding(
                "HANDOFF_SCHEMA_INVALID",
                "validation_results must be an array",
                "validation_results",
            )
        )
    else:
        seen_commands: set[str] = set()
        for index, result in enumerate(results):
            field = f"validation_results[{index}]"
            if not isinstance(result, dict):
                findings.append(
                    _finding("HANDOFF_SCHEMA_INVALID", "validation result must be an object", field)
                )
                continue
            if set(result) != {"command", "status"}:
                findings.append(
                    _finding(
                        "HANDOFF_SCHEMA_INVALID",
                        "validation result requires only command and status",
                        field,
                    )
                )
                continue
            command = result.get("command")
            status = result.get("status")
            if not isinstance(command, str) or not command.strip():
                findings.append(
                    _finding("HANDOFF_SCHEMA_INVALID", "command must be non-empty", field)
                )
            elif command in seen_commands:
                findings.append(
                    _finding("HANDOFF_SCHEMA_INVALID", "validation commands must be unique", field)
                )
            else:
                seen_commands.add(command)
            if status not in VALIDATION_STATUSES:
                findings.append(
                    _finding(
                        "HANDOFF_SCHEMA_INVALID",
                        f"status must be one of {sorted(VALIDATION_STATUSES)}",
                        field,
                    )
                )
    return findings


def _validate_binding(
    task: dict[str, Any], handoff: dict[str, Any], task_bytes: bytes
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    if handoff.get("task_id") != task.get("task_id"):
        findings.append(
            _finding("TASK_ID_MISMATCH", "Handoff task_id does not match task contract", "task_id")
        )

    expected_digest = hashlib.sha256(task_bytes).hexdigest()
    if handoff.get("task_contract_sha256") != expected_digest:
        findings.append(
            _finding(
                "TASK_DIGEST_MISMATCH",
                "Handoff task_contract_sha256 does not match task file bytes",
                "task_contract_sha256",
            )
        )

    allowed_paths = task.get("allowed_paths", [])
    forbidden_paths = task.get("forbidden_paths", [])
    for field in ("changed_paths", "deleted_paths"):
        values = handoff.get(field, [])
        if not isinstance(values, list):
            continue
        for path in values:
            normalized = _normalize_repo_path(path) if isinstance(path, str) else None
            if normalized is None:
                findings.append(
                    _finding("PATH_OUT_OF_REPO", f"Invalid repository-relative path: {path}", field)
                )
                continue
            if not any(_path_matches_scope(normalized, scope) for scope in allowed_paths):
                findings.append(
                    _finding("PATH_OUT_OF_SCOPE", f"Path is not allowed by task: {path}", field)
                )
            if any(_path_matches_scope(normalized, scope) for scope in forbidden_paths):
                findings.append(
                    _finding("FORBIDDEN_PATH", f"Path is forbidden by task: {path}", field)
                )

    deleted_paths = handoff.get("deleted_paths", [])
    if isinstance(deleted_paths, list) and deleted_paths and not task.get("delete_allowed"):
        findings.append(
            _finding(
                "DELETE_WITHOUT_PERMISSION",
                "Handoff declares deletions although task forbids deletion",
                "deleted_paths",
            )
        )

    task_claims = set(task.get("claims", []))
    addressed = handoff.get("claims_addressed", [])
    if isinstance(addressed, list):
        for claim in addressed:
            if claim not in task_claims:
                findings.append(
                    _finding(
                        "CLAIM_NOT_DECLARED",
                        f"Handoff addresses undeclared claim: {claim}",
                        "claims_addressed",
                    )
                )

    expected_evidence = set(task.get("expected_evidence", []))
    produced = set(handoff.get("evidence_produced", []))
    missing = set(handoff.get("missing_evidence", []))
    for evidence in sorted(expected_evidence - produced - missing):
        findings.append(
            _finding(
                "EXPECTED_EVIDENCE_UNACCOUNTED",
                f"Expected evidence is neither produced nor declared missing: {evidence}",
                "evidence_produced",
            )
        )

    required_commands = set(task.get("validation_commands", []))
    result_map = {
        item.get("command"): item.get("status")
        for item in handoff.get("validation_results", [])
        if isinstance(item, dict)
    }
    for command in sorted(required_commands - set(result_map)):
        findings.append(
            _finding(
                "VALIDATION_RESULT_MISSING",
                f"No result recorded for required validation command: {command}",
                "validation_results",
            )
        )

    outcome = handoff.get("outcome")
    blockers = handoff.get("blockers", [])
    residual_gaps = handoff.get("residual_gaps", [])
    required_statuses = [result_map.get(command) for command in required_commands]
    if outcome == "ready_for_review":
        if blockers or missing or residual_gaps:
            findings.append(
                _finding(
                    "CONTRADICTORY_OUTCOME",
                    "ready_for_review requires no blockers, missing evidence or residual gaps",
                    "outcome",
                )
            )
        if any(status != "passed" for status in required_statuses):
            findings.append(
                _finding(
                    "CONTRADICTORY_OUTCOME",
                    "ready_for_review requires every task validation to pass",
                    "outcome",
                )
            )
    elif outcome == "blocked" and not blockers:
        findings.append(
            _finding(
                "CONTRADICTORY_OUTCOME",
                "blocked requires at least one blocker",
                "blockers",
            )
        )
    elif outcome == "incomplete" and not (missing or residual_gaps):
        findings.append(
            _finding(
                "CONTRADICTORY_OUTCOME",
                "incomplete requires missing evidence or residual gaps",
                "outcome",
            )
        )

    return findings


def validate_handoff(
    task: Any, handoff: Any, *, task_bytes: bytes
) -> list[dict[str, str]]:
    findings = _validate_task_shape(task) + _validate_handoff_shape(handoff)
    if not findings and isinstance(task, dict) and isinstance(handoff, dict):
        findings.extend(_validate_binding(task, handoff, task_bytes))

    unique = {
        (item.get("code", ""), item.get("field", ""), item.get("message", "")): item
        for item in findings
    }
    return [unique[key] for key in sorted(unique)]


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Validate an agent handoff")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--handoff-file", required=True)
    return parser


def _emit_error(code: str, message: str) -> int:
    print(json.dumps({"code": code, "message": message}, sort_keys=True), file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except ValueError as exc:
        return _emit_error("INVALID_ARGUMENTS", str(exc))

    repo_root = Path(REPO_ROOT)
    try:
        task_path = _resolve_repo_relative(repo_root, args.task_file)
        handoff_path = _resolve_repo_relative(repo_root, args.handoff_file)
    except ValueError as exc:
        return _emit_error("PATH_OUT_OF_REPO", str(exc))

    if not task_path.is_file():
        return _emit_error("TASK_FILE_NOT_FOUND", args.task_file)
    if not handoff_path.is_file():
        return _emit_error("HANDOFF_FILE_NOT_FOUND", args.handoff_file)

    task, task_error = _load_json(task_path)
    if task_error is not None:
        return _emit_error("TASK_JSON_INVALID", task_error)
    handoff, handoff_error = _load_json(handoff_path)
    if handoff_error is not None:
        return _emit_error("HANDOFF_JSON_INVALID", handoff_error)

    findings = validate_handoff(task, handoff, task_bytes=task_path.read_bytes())
    payload = {
        "status": "valid" if not findings else "invalid",
        "task_file": args.task_file,
        "handoff_file": args.handoff_file,
        "findings_count": len(findings),
        "findings": findings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not findings else 1


if __name__ == "__main__":
    sys.exit(main())
