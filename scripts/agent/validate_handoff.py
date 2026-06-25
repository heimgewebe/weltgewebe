#!/usr/bin/env python3
"""Validate an agent review handoff against its canonical task contract."""

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

from scripts.agent.check_non_ideal_task import load_claim_registry, run_non_ideal_guard
from scripts.agent.json_contract import (
    DuplicateKeyError,
    UnsupportedSchemaError,
    load_json_strict,
    validate_instance,
)
from scripts.docmeta.docmeta import REPO_ROOT

WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:/")


class CliInputError(Exception):
    """Stable machine-readable CLI input error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliInputError("INVALID_ARGUMENTS", message)


def _finding(code: str, message: str, field: str | None = None) -> dict[str, str]:
    finding = {"code": code, "message": message}
    if field is not None:
        finding["field"] = field
    return finding


def _resolve_repo_relative(repo_root: Path, value: str) -> Path:
    raw_text = value.replace("\\", "/").strip()
    if not raw_text or raw_text.startswith("/") or WINDOWS_DRIVE_RE.match(raw_text):
        raise ValueError(f"Path must be repository-relative: {value}")
    raw = Path(raw_text)
    root = repo_root.resolve()
    resolved = (root / raw).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes repository root: {value}") from exc
    return resolved


def _normalize_repo_path(value: str, *, allow_directory: bool = False) -> str | None:
    if not isinstance(value, str):
        return None
    raw = value.replace("\\", "/").strip()
    if not raw or raw.startswith("/") or WINDOWS_DRIVE_RE.match(raw):
        return None

    is_directory = raw.endswith("/")
    if is_directory:
        raw = raw[:-1]
    parts = raw.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    if is_directory and not allow_directory:
        return None

    normalized = "/".join(parts)
    return f"{normalized}/" if is_directory else normalized


def _path_matches_scope(path: str, scope: str) -> bool:
    normalized_path = _normalize_repo_path(path)
    normalized_scope = _normalize_repo_path(scope, allow_directory=True)
    if normalized_path is None or normalized_scope is None:
        return False
    if normalized_scope.endswith("/"):
        return normalized_path.startswith(normalized_scope)
    return normalized_path == normalized_scope


def _schema_findings(
    payload: Any,
    schema: dict[str, Any],
    *,
    code: str,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for violation in validate_instance(payload, schema):
        field = violation["path"].removeprefix("$.")
        findings.append(
            _finding(code, violation["message"], field if field != "$" else None)
        )
    return findings


def _load_schema(repo_root: Path, name: str) -> dict[str, Any]:
    schema = load_json_strict(repo_root / "contracts/agent" / name)
    if not isinstance(schema, dict):
        raise UnsupportedSchemaError(f"{name} must contain a JSON object")
    return schema


def _normalized_file_set(values: list[str]) -> set[str]:
    return {
        normalized
        for value in values
        if (normalized := _normalize_repo_path(value)) is not None
    }


def _validate_paths(
    task: dict[str, Any], handoff: dict[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    allowed_paths = task["allowed_paths"]
    forbidden_paths = task["forbidden_paths"]

    for field in ("changed_paths", "deleted_paths"):
        for declared_path in handoff[field]:
            normalized = _normalize_repo_path(declared_path)
            if normalized is None:
                findings.append(
                    _finding(
                        "PATH_OUT_OF_REPO",
                        f"Invalid repository-relative file path: {declared_path}",
                        field,
                    )
                )
                continue
            if not any(_path_matches_scope(normalized, scope) for scope in allowed_paths):
                findings.append(
                    _finding(
                        "PATH_OUT_OF_SCOPE",
                        f"Path is not allowed by task: {declared_path}",
                        field,
                    )
                )
            if any(_path_matches_scope(normalized, scope) for scope in forbidden_paths):
                findings.append(
                    _finding(
                        "FORBIDDEN_PATH",
                        f"Path is forbidden by task: {declared_path}",
                        field,
                    )
                )

    changed = _normalized_file_set(handoff["changed_paths"])
    deleted = _normalized_file_set(handoff["deleted_paths"])
    for path in sorted(changed & deleted):
        findings.append(
            _finding(
                "PATH_STATE_CONTRADICTION",
                f"Path cannot be both changed and deleted: {path}",
                "deleted_paths",
            )
        )

    if deleted and not task["delete_allowed"]:
        findings.append(
            _finding(
                "DELETE_WITHOUT_PERMISSION",
                "Handoff declares deletions although task forbids deletion",
                "deleted_paths",
            )
        )
    return findings


def _validate_claims(
    task: dict[str, Any], handoff: dict[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    task_claims = set(task["claims"])
    addressed = set(handoff["claims_addressed"])
    for claim in sorted(addressed - task_claims):
        findings.append(
            _finding(
                "CLAIM_NOT_DECLARED",
                f"Handoff addresses undeclared claim: {claim}",
                "claims_addressed",
            )
        )
    for claim in sorted(task_claims - addressed):
        findings.append(
            _finding(
                "CLAIM_NOT_ADDRESSED",
                f"Task claim is not addressed by handoff: {claim}",
                "claims_addressed",
            )
        )
    return findings


def _validate_evidence(
    task: dict[str, Any],
    handoff: dict[str, Any],
    *,
    repo_root: Path,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    expected_values = task["expected_evidence"]
    produced_values = handoff["evidence_produced"]
    missing_values = handoff["missing_evidence"]

    normalized_expected = _normalized_file_set(expected_values)
    normalized_produced = _normalized_file_set(produced_values)
    normalized_missing = _normalized_file_set(missing_values)

    for evidence in sorted(normalized_produced & normalized_missing):
        findings.append(
            _finding(
                "EVIDENCE_STATE_CONTRADICTION",
                f"Evidence cannot be both produced and missing: {evidence}",
                "missing_evidence",
            )
        )

    for evidence in sorted(
        normalized_expected - normalized_produced - normalized_missing
    ):
        findings.append(
            _finding(
                "EXPECTED_EVIDENCE_UNACCOUNTED",
                f"Expected evidence is neither produced nor declared missing: {evidence}",
                "evidence_produced",
            )
        )

    for evidence in sorted(normalized_missing - normalized_expected):
        findings.append(
            _finding(
                "UNEXPECTED_MISSING_EVIDENCE",
                f"Missing evidence was not required by task: {evidence}",
                "missing_evidence",
            )
        )

    root = repo_root.resolve()
    for field, values in (
        ("evidence_produced", produced_values),
        ("missing_evidence", missing_values),
    ):
        for evidence in values:
            normalized = _normalize_repo_path(evidence)
            if normalized is None:
                findings.append(
                    _finding(
                        "EVIDENCE_PATH_INVALID",
                        f"Evidence must be a repository-relative file path: {evidence}",
                        field,
                    )
                )
                continue
            if field == "evidence_produced":
                candidate = repo_root / normalized
                try:
                    candidate.resolve().relative_to(root)
                    valid_local_file = candidate.is_file()
                except (OSError, ValueError):
                    valid_local_file = False
                if not valid_local_file:
                    findings.append(
                        _finding(
                            "EVIDENCE_NOT_FOUND",
                            "Produced evidence file does not exist inside the "
                            f"repository: {evidence}",
                            field,
                        )
                    )
    return findings


def _validate_results_and_outcome(
    task: dict[str, Any], handoff: dict[str, Any]
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    result_map: dict[str, str] = {}
    for index, item in enumerate(handoff["validation_results"]):
        command = item["command"]
        if command in result_map:
            findings.append(
                _finding(
                    "VALIDATION_RESULT_DUPLICATE",
                    f"Validation command is recorded more than once: {command}",
                    f"validation_results[{index}]",
                )
            )
        result_map[command] = item["status"]

    required = set(task["validation_commands"])
    missing_results = required - set(result_map)
    for command in sorted(missing_results):
        findings.append(
            _finding(
                "VALIDATION_RESULT_MISSING",
                f"No result recorded for required validation command: {command}",
                "validation_results",
            )
        )

    outcome = handoff["outcome"]
    blockers = handoff["blockers"]
    residual_gaps = handoff["residual_gaps"]
    missing_evidence = handoff["missing_evidence"]
    non_passed = sorted(
        command for command, status in result_map.items() if status != "passed"
    )
    unaddressed = set(task["claims"]) - set(handoff["claims_addressed"])

    if outcome == "ready_for_review":
        if blockers or missing_evidence:
            findings.append(
                _finding(
                    "CONTRADICTORY_OUTCOME",
                    "ready_for_review requires no blockers or missing evidence",
                    "outcome",
                )
            )
        if non_passed or missing_results:
            findings.append(
                _finding(
                    "CONTRADICTORY_OUTCOME",
                    "ready_for_review requires every recorded and required "
                    "validation to pass",
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
    elif outcome == "incomplete" and not (
        missing_evidence
        or residual_gaps
        or non_passed
        or missing_results
        or unaddressed
    ):
        findings.append(
            _finding(
                "CONTRADICTORY_OUTCOME",
                "incomplete requires explicitly accounted missing evidence, "
                "a failed or not-run validation, or a residual gap",
                "outcome",
            )
        )
    return findings


def _validate_binding(
    task: dict[str, Any],
    handoff: dict[str, Any],
    task_bytes: bytes,
    *,
    repo_root: Path,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if handoff["task_id"] != task["task_id"]:
        findings.append(
            _finding(
                "TASK_ID_MISMATCH",
                "Handoff task_id does not match task contract",
                "task_id",
            )
        )

    expected_digest = hashlib.sha256(task_bytes).hexdigest()
    if handoff["task_contract_sha256"] != expected_digest:
        findings.append(
            _finding(
                "TASK_DIGEST_MISMATCH",
                "Handoff task_contract_sha256 does not match task file bytes",
                "task_contract_sha256",
            )
        )

    findings.extend(_validate_paths(task, handoff))
    findings.extend(_validate_claims(task, handoff))
    findings.extend(_validate_evidence(task, handoff, repo_root=repo_root))
    findings.extend(_validate_results_and_outcome(task, handoff))
    return findings


def validate_handoff(
    task: Any,
    handoff: Any,
    *,
    task_bytes: bytes,
    repo_root: Path | None = None,
    claim_registry: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    root = Path(repo_root or REPO_ROOT)
    task_schema = _load_schema(root, "task.schema.json")
    handoff_schema = _load_schema(root, "handoff.schema.json")

    if claim_registry is None:
        claim_registry, registry_error = load_claim_registry(
            root / "docs/claims/registry.yml"
        )
        if registry_error is not None or claim_registry is None:
            code = (
                registry_error.get("code", "CLAIM_REGISTRY_INVALID")
                if registry_error
                else "CLAIM_REGISTRY_INVALID"
            )
            message = (
                registry_error.get("message", "Claim registry is invalid")
                if registry_error
                else "Claim registry is invalid"
            )
            return [_finding(code, message)]

    findings = _schema_findings(task, task_schema, code="TASK_SCHEMA_INVALID")
    findings.extend(
        _schema_findings(handoff, handoff_schema, code="HANDOFF_SCHEMA_INVALID")
    )
    if isinstance(task, dict):
        findings.extend(
            run_non_ideal_guard(task, claim_registry, task_schema=task_schema)
        )

    has_shape_error = any(
        item["code"] in {"TASK_SCHEMA_INVALID", "HANDOFF_SCHEMA_INVALID"}
        for item in findings
    )
    if not has_shape_error and isinstance(task, dict) and isinstance(handoff, dict):
        findings.extend(_validate_binding(task, handoff, task_bytes, repo_root=root))

    unique = {
        (item.get("code", ""), item.get("field", ""), item.get("message", "")): item
        for item in findings
    }
    return [unique[key] for key in sorted(unique)]


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(description="Validate an agent handoff")
    parser.add_argument("--task-file", required=True)
    parser.add_argument("--handoff-file", required=True)
    parser.add_argument(
        "--claim-registry",
        default="docs/claims/registry.yml",
        help="Path to claim registry relative to repository root",
    )
    return parser


def _emit_error(code: str, message: str) -> int:
    print(
        json.dumps(
            {"code": code, "message": message},
            ensure_ascii=False,
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 2


def _read_json(path: Path, *, kind: str) -> Any:
    try:
        return load_json_strict(path)
    except DuplicateKeyError as exc:
        raise CliInputError("DUPLICATE_JSON_KEY", str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise CliInputError(
            f"{kind}_JSON_INVALID",
            f"JSON parse error: {exc.msg}",
        ) from exc
    except OSError as exc:
        raise CliInputError(f"{kind}_FILE_UNREADABLE", str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    try:
        args = _build_parser().parse_args(argv)
    except CliInputError as exc:
        return _emit_error(exc.code, exc.message)

    repo_root = Path(REPO_ROOT)
    try:
        task_path = _resolve_repo_relative(repo_root, args.task_file)
        handoff_path = _resolve_repo_relative(repo_root, args.handoff_file)
        registry_path = _resolve_repo_relative(repo_root, args.claim_registry)
    except ValueError as exc:
        return _emit_error("PATH_OUT_OF_REPO", str(exc))

    if not task_path.is_file():
        return _emit_error("TASK_FILE_NOT_FOUND", args.task_file)
    if not handoff_path.is_file():
        return _emit_error("HANDOFF_FILE_NOT_FOUND", args.handoff_file)
    if not registry_path.is_file():
        return _emit_error("CLAIM_REGISTRY_NOT_FOUND", args.claim_registry)

    try:
        task = _read_json(task_path, kind="TASK")
        handoff = _read_json(handoff_path, kind="HANDOFF")
        claim_registry, registry_error = load_claim_registry(registry_path)
        if registry_error is not None or claim_registry is None:
            code = (
                registry_error.get("code", "CLAIM_REGISTRY_INVALID")
                if registry_error
                else "CLAIM_REGISTRY_INVALID"
            )
            message = (
                registry_error.get("message", "Claim registry is invalid")
                if registry_error
                else "Claim registry is invalid"
            )
            return _emit_error(code, message)
        findings = validate_handoff(
            task,
            handoff,
            task_bytes=task_path.read_bytes(),
            repo_root=repo_root,
            claim_registry=claim_registry,
        )
    except CliInputError as exc:
        return _emit_error(exc.code, exc.message)
    except DuplicateKeyError as exc:
        return _emit_error("CONTRACT_SCHEMA_INVALID", str(exc))
    except json.JSONDecodeError as exc:
        return _emit_error("CONTRACT_SCHEMA_INVALID", str(exc))
    except UnsupportedSchemaError as exc:
        return _emit_error("CONTRACT_SCHEMA_UNSUPPORTED", str(exc))
    except OSError as exc:
        return _emit_error("CONTRACT_FILE_UNREADABLE", str(exc))

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
    raise SystemExit(main())
