#!/usr/bin/env python3
"""Validate docs/claims/registry.yml (JSON-compatible YAML subset)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import REPO_ROOT

VALID_STATUSES = {"proposed", "established", "superseded", "rejected"}
CLAIM_ID_PATTERN = re.compile(r"^CLAIM-[A-Z0-9]+(?:-[A-Z0-9]+)*-[0-9]{3}$")
REQUIRED_CLAIM_FIELDS = (
    "id",
    "status",
    "subject",
    "statement",
    "evidence",
    "validation",
    "updated",
)


def _finding(
    code: str,
    claim_id: str | None,
    message: str,
    path: str | None = None,
    field: str | None = None,
) -> dict[str, str]:
    finding: dict[str, str] = {
        "code": code,
        "claim_id": claim_id or "-",
        "message": message,
    }
    if path is not None:
        finding["path"] = path
    if field is not None:
        finding["field"] = field
    return finding


def load_registry(registry_path: Path) -> tuple[dict | None, list[dict[str, str]], int]:
    if not registry_path.exists():
        return None, [_finding("REGISTRY_MISSING", None, "Registry file does not exist", str(registry_path))], 2

    try:
        raw = registry_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [_finding("REGISTRY_PARSE_ERROR", None, f"Registry is not readable: {exc}", str(registry_path))], 2

    normalized = raw.lstrip("\ufeff").strip()
    if normalized.startswith("---"):
        lines = normalized.splitlines()
        normalized = "\n".join(lines[1:]).strip()
    if normalized.endswith("..."):
        normalized = normalized[:-3].strip()

    try:
        data = json.loads(normalized)
    except json.JSONDecodeError as exc:
        return None, [_finding("REGISTRY_PARSE_ERROR", None, f"Registry parse error: {exc.msg}", str(registry_path))], 2

    return data, [], 0


def validate_registry_data(data: dict, repo_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    if not isinstance(data, dict):
        return [_finding("INVALID_TOP_LEVEL", None, "Top-level registry must be an object")]

    if "version" not in data:
        findings.append(_finding("MISSING_VERSION", None, "Top-level field 'version' is required"))

    claims = data.get("claims")
    if not isinstance(claims, list) or not claims:
        findings.append(_finding("MISSING_CLAIMS", None, "Top-level field 'claims' must be a non-empty array"))
        return findings

    seen_ids: set[str] = set()
    for claim in claims:
        if not isinstance(claim, dict):
            findings.append(_finding("CLAIM_MISSING_FIELD", None, "Claim entry must be an object"))
            continue

        claim_id = claim.get("id") if isinstance(claim.get("id"), str) else None

        for field in REQUIRED_CLAIM_FIELDS:
            value = claim.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                findings.append(
                    _finding(
                        "CLAIM_MISSING_FIELD",
                        claim_id,
                        f"Claim field '{field}' is required",
                        field=field,
                    )
                )

        if isinstance(claim_id, str):
            if not CLAIM_ID_PATTERN.match(claim_id):
                findings.append(_finding("CLAIM_INVALID_ID", claim_id, "Claim ID format is invalid", field="id"))
            if claim_id in seen_ids:
                findings.append(_finding("CLAIM_DUPLICATE_ID", claim_id, "Duplicate claim ID", field="id"))
            seen_ids.add(claim_id)

        status = claim.get("status")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            findings.append(
                _finding(
                    "CLAIM_INVALID_STATUS",
                    claim_id,
                    "Claim status must be one of: proposed, established, superseded, rejected",
                    field="status",
                )
            )

        evidence = claim.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            findings.append(_finding("CLAIM_MISSING_EVIDENCE", claim_id, "Claim evidence must be a non-empty array"))
            evidence_items: list[dict] = []
        else:
            evidence_items = [item for item in evidence if isinstance(item, dict)]
            if len(evidence_items) != len(evidence):
                findings.append(_finding("EVIDENCE_MISSING_FIELD", claim_id, "Each evidence entry must be an object"))

        for item in evidence_items:
            path = item.get("path")
            kind = item.get("kind")
            if not isinstance(path, str) or not path.strip():
                findings.append(
                    _finding(
                        "EVIDENCE_MISSING_FIELD",
                        claim_id,
                        "Evidence field 'path' is required",
                        field="path",
                    )
                )
                continue
            if not isinstance(kind, str) or not kind.strip():
                findings.append(
                    _finding(
                        "EVIDENCE_MISSING_FIELD",
                        claim_id,
                        "Evidence field 'kind' is required",
                        path=path,
                        field="kind",
                    )
                )
            if status == "established" and not (repo_root / path).exists():
                findings.append(
                    _finding(
                        "EVIDENCE_PATH_MISSING",
                        claim_id,
                        "Evidence path does not exist",
                        path=path,
                    )
                )

        validation = claim.get("validation")
        if not isinstance(validation, list) or not validation:
            findings.append(
                _finding(
                    "CLAIM_MISSING_VALIDATION",
                    claim_id,
                    "Validation commands must be a non-empty array",
                    field="validation",
                )
            )

    return findings


def run_validation(registry: str) -> tuple[dict[str, object], int]:
    repo_root = Path(REPO_ROOT)
    registry_path = repo_root / registry

    data, parser_findings, parser_exit = load_registry(registry_path)
    if parser_exit != 0:
        output = {
            "registry": registry,
            "claims_count": 0,
            "findings_count": len(parser_findings),
            "findings": parser_findings,
        }
        return output, parser_exit

    if data is None:
        output = {
            "registry": registry,
            "claims_count": 0,
            "findings_count": 1,
            "findings": [_finding("REGISTRY_PARSE_ERROR", None, "Unknown parser failure", str(registry_path))],
        }
        return output, 2

    findings = validate_registry_data(data, repo_root)
    claims = data.get("claims") if isinstance(data, dict) else []
    claims_count = len(claims) if isinstance(claims, list) else 0
    output = {
        "registry": registry,
        "claims_count": claims_count,
        "findings_count": len(findings),
        "findings": findings,
    }

    return output, (0 if not findings else 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate claim registry")
    parser.add_argument(
        "--registry",
        default="docs/claims/registry.yml",
        help="Path relative to repository root",
    )
    args = parser.parse_args(argv)

    output, exit_code = run_validation(args.registry)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
