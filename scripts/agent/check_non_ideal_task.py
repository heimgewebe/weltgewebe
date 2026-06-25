#!/usr/bin/env python3
"""Deterministic guard for non-ideal agent task contracts (AGENT-SAFE-004)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.agent.json_contract import (
    DuplicateKeyError,
    UnsupportedSchemaError,
    load_json_strict,
    loads_json_strict,
    validate_instance,
)
from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.validate_claim_registry import load_registry, validate_registry_data

TASK_ID_RE = re.compile(r"^[A-Z]+(-[A-Z]+)*-[0-9]{3}$")
TASK_TYPES = {"doc_change", "ci_change", "infra_change", "governance", "generated_refresh"}
TASK_REQUIRED_FIELDS = {
    "task_id",
    "goal",
    "task_type",
    "allowed_paths",
    "forbidden_paths",
    "claims",
    "expected_evidence",
    "validation_commands",
    "delete_allowed",
}
TASK_OPTIONAL_FIELDS = {"status", "decision", "repo_status"}
TASK_ALLOWED_FIELDS = TASK_REQUIRED_FIELDS | TASK_OPTIONAL_FIELDS

DISALLOWED_SCOPE_MARKERS = {
    "",
    ".",
    "/",
    "*",
    "**",
    "repo",
    "all",
    "root",
}

CONTRADICTORY_CLAIM_STATUSES = {
    "rejected",
    "contradicted",
    "superseded",
    "obsolete",
}


class _GuardArgumentParser(argparse.ArgumentParser):
    """Argument parser that raises ValueError instead of exiting directly."""

    def error(self, message: str) -> None:
        raise ValueError(message)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip()


def _trim_trailing(path: str) -> str:
    return _normalize_path(path).rstrip("/")


def _forbidden_blocks_allowed(allowed: str, forbidden: str) -> bool:
    normalized_allowed = _trim_trailing(allowed)
    normalized_forbidden = _trim_trailing(forbidden)
    if not normalized_allowed or not normalized_forbidden:
        return False
    if normalized_allowed == normalized_forbidden:
        return True
    return normalized_allowed.startswith(normalized_forbidden + "/")


def _is_generated_path(path: str) -> bool:
    normalized = _normalize_path(path).strip("/")
    return normalized == "docs/_generated" or normalized.startswith("docs/_generated/")


def _finding(code: str, message: str, field: str | None = None) -> dict[str, str]:
    item: dict[str, str] = {"code": code, "message": message}
    if field is not None:
        item["field"] = field
    return item


def _load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Datei kann nicht gelesen werden: {exc}"

    try:
        return loads_json_strict(raw), None
    except DuplicateKeyError as exc:
        return None, str(exc)
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


def _load_task_schema(schema_path: Path | None = None) -> dict[str, Any]:
    path = schema_path or (Path(REPO_ROOT) / "contracts/agent/task.schema.json")
    schema = load_json_strict(path)
    if not isinstance(schema, dict):
        raise UnsupportedSchemaError("task schema must be a JSON object")
    return schema


def _validate_task_schema(
    task: Any, *, task_schema: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    schema = task_schema or _load_task_schema()
    findings: list[dict[str, str]] = []
    for violation in validate_instance(task, schema):
        field = violation["path"].removeprefix("$.")
        findings.append(
            _finding(
                "TASK_SCHEMA_INVALID",
                violation["message"],
                field if field != "$" else None,
            )
        )
    return findings


def _find_status_done(task: Any, path: str = "") -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if isinstance(task, dict):
        for key, value in task.items():
            current_path = f"{path}.{key}" if path else key
            if key in {"status", "repo_status"} and isinstance(value, str):
                if value.strip().lower() == "done":
                    findings.append(
                        _finding(
                            "STATUS_DONE_BY_AGENT",
                            "Final status field is forbidden for agent tasks",
                            current_path,
                        )
                    )
            if key == "decision" and isinstance(value, str):
                if value.strip().lower() == "pass":
                    findings.append(
                        _finding(
                            "STATUS_DONE_BY_AGENT",
                            "Final decision 'pass' is forbidden for agent tasks",
                            current_path,
                        )
                    )
            findings.extend(_find_status_done(value, current_path))
    elif isinstance(task, list):
        for index, item in enumerate(task):
            current_path = f"{path}[{index}]" if path else f"[{index}]"
            findings.extend(_find_status_done(item, current_path))
    return findings


def _has_generator_command(commands: list[str]) -> bool:
    for command in commands:
        normalized = command.lower()
        if "scripts/docmeta/generate_" in normalized:
            return True
    return False


def _validate_scope_rules(task: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    allowed_paths = task.get("allowed_paths")
    if not isinstance(allowed_paths, list) or len(allowed_paths) == 0:
        findings.append(_finding("NO_ALLOWED_PATHS", "allowed_paths fehlt oder ist leer", "allowed_paths"))
        return findings

    for path in allowed_paths:
        marker = _trim_trailing(path).lower()
        if marker in DISALLOWED_SCOPE_MARKERS:
            findings.append(
                _finding("SCOPE_TOO_BROAD", f"allowed_paths entry '{path}' ist zu breit", "allowed_paths")
            )

    forbidden_paths = task.get("forbidden_paths")
    if not isinstance(forbidden_paths, list):
        forbidden_paths = []

    for allowed in allowed_paths:
        for forbidden in forbidden_paths:
            if _forbidden_blocks_allowed(allowed, forbidden):
                findings.append(
                    _finding(
                        "FORBIDDEN_PATH",
                        f"allowed_paths '{allowed}' wird durch forbidden_paths '{forbidden}' blockiert",
                        "forbidden_paths",
                    )
                )

    allows_generated = any(_is_generated_path(path) for path in allowed_paths)
    if allows_generated:
        task_type = task.get("task_type")
        commands = task.get("validation_commands")
        has_generator = isinstance(commands, list) and _has_generator_command(commands)
        if task_type != "generated_refresh" or not has_generator:
            findings.append(
                _finding(
                    "FORBIDDEN_PATH",
                    "docs/_generated/ darf nur in generated_refresh tasks mit Generator-Command erlaubt werden",
                    "allowed_paths",
                )
            )

    return findings


def _validate_task_requirements(task: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    validation = task.get("validation_commands")
    if not isinstance(validation, list) or len(validation) == 0:
        findings.append(
            _finding("NO_VALIDATION_COMMAND", "validation_commands fehlt oder ist leer", "validation_commands")
        )

    evidence = task.get("expected_evidence")
    if not isinstance(evidence, list) or len(evidence) == 0:
        findings.append(
            _finding("NO_EXPECTED_EVIDENCE", "expected_evidence fehlt oder ist leer", "expected_evidence")
        )

    return findings


def _load_claim_registry(registry_path: Path) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    data, parser_findings, parser_exit = load_registry(registry_path)
    if parser_exit != 0 or data is None:
        code = "CLAIM_REGISTRY_NOT_FOUND"
        message = "Claim-Registry nicht gefunden"
        if parser_findings:
            parser_code = parser_findings[0].get("code", "")
            if parser_code != "REGISTRY_MISSING":
                code = "CLAIM_REGISTRY_INVALID"
                message = "Claim-Registry ist nicht parsebar"
        return None, {"code": code, "message": message}

    registry_findings = validate_registry_data(data, Path(REPO_ROOT))
    if registry_findings:
        return None, {
            "code": "CLAIM_REGISTRY_INVALID",
            "message": "Claim-Registry ist nicht valide",
        }

    if not isinstance(data, dict):
        return None, {
            "code": "CLAIM_REGISTRY_INVALID",
            "message": "Claim-Registry Top-Level ist ungueltig",
        }

    return data, None


load_claim_registry = _load_claim_registry


def _validate_claims(task: dict[str, Any], registry: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    claims_raw = registry.get("claims", [])
    claims_map: dict[str, str] = {}
    if isinstance(claims_raw, list):
        for claim in claims_raw:
            if not isinstance(claim, dict):
                continue
            claim_id = claim.get("id")
            status = claim.get("status")
            if isinstance(claim_id, str) and isinstance(status, str):
                claims_map[claim_id] = status.lower()

    task_claims = task.get("claims")
    if not isinstance(task_claims, list):
        return findings

    for claim_id in task_claims:
        if not isinstance(claim_id, str):
            continue
        status = claims_map.get(claim_id)
        if status is None:
            findings.append(
                _finding(
                    "CLAIM_WITHOUT_REGISTRY_ENTRY",
                    f"Claim '{claim_id}' fehlt in docs/claims/registry.yml",
                    "claims",
                )
            )
            continue
        if status in CONTRADICTORY_CLAIM_STATUSES:
            findings.append(
                _finding(
                    "CONTRADICTION_FOUND",
                    f"Claim '{claim_id}' hat widerspruechlichen Status '{status}'",
                    "claims",
                )
            )

    return findings


def run_non_ideal_guard(
    task: Any,
    registry: dict[str, Any],
    *,
    task_schema: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    findings.extend(_validate_task_schema(task, task_schema=task_schema))

    if isinstance(task, dict):
        findings.extend(_validate_scope_rules(task))
        findings.extend(_validate_task_requirements(task))
        findings.extend(_find_status_done(task))
        findings.extend(_validate_claims(task, registry))

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for finding in findings:
        key = (
            finding.get("code", ""),
            finding.get("message", ""),
            finding.get("field", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)

    return deduped


def _build_parser() -> argparse.ArgumentParser:
    parser = _GuardArgumentParser(description="Check non-ideal agent tasks")
    parser.add_argument("--task-file", required=True, help="Path to task contract JSON file")
    parser.add_argument(
        "--claim-registry",
        default="docs/claims/registry.yml",
        help="Path to claim registry relative to repository root",
    )
    parser.add_argument(
        "--mode",
        choices=["report-only", "warn"],
        default="report-only",
        help="report-only keeps exit 0 with findings; warn exits 1 with findings",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except ValueError as exc:
        print(json.dumps({"error": f"Ungueltiger Aufruf: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 2
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return code if code == 0 else 2

    repo_root = Path(REPO_ROOT)
    try:
        task_file = _resolve_repo_relative(repo_root, args.task_file)
        claim_registry_file = _resolve_repo_relative(repo_root, args.claim_registry)
    except ValueError as exc:
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "code": "PATH_OUT_OF_REPO",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    if not task_file.is_file():
        print(
            json.dumps(
                {
                    "error": f"Task-Datei nicht gefunden: {args.task_file}",
                    "code": "TASK_FILE_NOT_FOUND",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    if not claim_registry_file.is_file():
        print(
            json.dumps(
                {
                    "error": f"Claim-Registry nicht gefunden: {args.claim_registry}",
                    "code": "CLAIM_REGISTRY_NOT_FOUND",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    task, task_error = _load_json(task_file)
    if task_error is not None:
        findings = [_finding("TASK_SCHEMA_INVALID", task_error)]
        result = {
            "mode": args.mode,
            "task_file": args.task_file,
            "findings_count": len(findings),
            "findings": findings,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.mode == "warn":
            return 1
        return 0

    registry_data, registry_error = _load_claim_registry(claim_registry_file)
    if registry_error is not None or registry_data is None:
        print(json.dumps(registry_error, ensure_ascii=False), file=sys.stderr)
        return 2

    try:
        findings = run_non_ideal_guard(task, registry_data)
    except (OSError, json.JSONDecodeError, DuplicateKeyError, UnsupportedSchemaError) as exc:
        print(
            json.dumps(
                {"code": "CONTRACT_SCHEMA_INVALID", "error": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    result = {
        "mode": args.mode,
        "task_file": args.task_file,
        "findings_count": len(findings),
        "findings": findings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.mode == "warn" and findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
