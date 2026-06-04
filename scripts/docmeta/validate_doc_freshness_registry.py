#!/usr/bin/env python3
"""Validate docs/doc-freshness-registry.yml (JSON-compatible YAML subset).

This validator is a gatekeeper, not a priest. It checks the structural and
slice-scoped integrity of the freshness registry. It does NOT decide whether a
claim is true, whether evidence proves a claim, whether CI ran, or whether a
review happened.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta import validate_claim_registry
from scripts.docmeta.docmeta import REPO_ROOT

VALID_STATUSES = {"active", "draft", "superseded"}
SLICE_STATUS = "active"
VALID_REVIEW_POLICIES = {"manual", "ci", "generated"}
SLICE_REVIEW_POLICY = "manual"
SLICE_MAX_AGE_DAYS = 90
VALID_EVIDENCE_KINDS = {
    "documentation",
    "implementation",
    "test",
    "ci",
    "guard",
    "contract",
    "report",
}
IN_SCOPE_CLAIMS = {
    "CLAIM-AGENT-SAFE-001",
    "CLAIM-AGENT-SAFE-002",
    "CLAIM-AGENT-SAFE-003",
}
EXPECTED_ENTRY_COUNT = 3
ENTRY_ID_PATTERN = re.compile(r"^freshness\.claim\.agent_safe_00[1-3]$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _finding(code: str, entry_id: str | None, message: str, path: str | None = None) -> dict[str, str]:
    finding: dict[str, str] = {
        "code": code,
        "entry_id": entry_id or "-",
        "message": message,
    }
    if path is not None:
        finding["path"] = path
    return finding


def load_yaml_json(path: Path) -> tuple[object | None, str | None]:
    """Load a JSON-compatible YAML subset (optional leading ``---``)."""
    if not path.exists():
        return None, f"Registry file does not exist: {path}"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Registry is not readable: {exc}"

    normalized = raw.lstrip("\ufeff").strip()
    if normalized.startswith("---"):
        lines = normalized.splitlines()
        normalized = "\n".join(lines[1:]).strip()
    if normalized.endswith("..."):
        normalized = normalized[:-3].strip()

    try:
        return json.loads(normalized), None
    except json.JSONDecodeError as exc:
        return None, f"Registry parse error: {exc.msg}"


def _load_claim_ids(claims_path: Path) -> tuple[set[str], str | None]:
    data, _findings, exit_code = validate_claim_registry.load_registry(claims_path)
    if exit_code != 0 or not isinstance(data, dict):
        return set(), f"Claim registry could not be loaded: {claims_path}"
    claims = data.get("claims")
    if not isinstance(claims, list):
        return set(), "Claim registry has no 'claims' list"
    ids = {
        claim["id"]
        for claim in claims
        if isinstance(claim, dict) and isinstance(claim.get("id"), str)
    }
    return ids, None


def _is_positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_evidence(entry_id: str | None, evidence: object, repo_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(evidence, list) or not evidence:
        findings.append(_finding("EVIDENCE_EMPTY", entry_id, "Evidence must be a non-empty list"))
        return findings

    for item in evidence:
        if not isinstance(item, dict):
            findings.append(_finding("EVIDENCE_NOT_OBJECT", entry_id, "Each evidence item must be an object"))
            continue

        path = item.get("path")
        if not isinstance(path, str) or not path.strip():
            findings.append(_finding("EVIDENCE_PATH_NOT_STRING", entry_id, "Evidence 'path' must be a non-empty string"))
        elif path.startswith("/") or Path(path).is_absolute():
            findings.append(_finding("EVIDENCE_PATH_ABSOLUTE", entry_id, "Evidence path must be repo-relative", path=path))
        elif ".." in Path(path).parts:
            findings.append(_finding("EVIDENCE_PATH_TRAVERSAL", entry_id, "Evidence path must not contain '..'", path=path))
        elif not (repo_root / path).exists():
            findings.append(_finding("EVIDENCE_PATH_MISSING", entry_id, "Evidence path does not exist", path=path))

        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in VALID_EVIDENCE_KINDS:
            findings.append(
                _finding(
                    "EVIDENCE_KIND_INVALID",
                    entry_id,
                    f"Evidence 'kind' must be one of: {', '.join(sorted(VALID_EVIDENCE_KINDS))}",
                    path=path if isinstance(path, str) else None,
                )
            )

    return findings


def _validate_freshness(entry_id: str | None, freshness: object) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(freshness, dict):
        findings.append(_finding("FRESHNESS_NOT_OBJECT", entry_id, "'freshness' must be an object"))
        return findings

    review_policy = freshness.get("review_policy")
    if not isinstance(review_policy, str) or review_policy not in VALID_REVIEW_POLICIES:
        findings.append(
            _finding(
                "REVIEW_POLICY_INVALID",
                entry_id,
                f"'review_policy' must be one of: {', '.join(sorted(VALID_REVIEW_POLICIES))}",
            )
        )
    elif review_policy != SLICE_REVIEW_POLICY:
        findings.append(
            _finding("REVIEW_POLICY_NOT_MANUAL", entry_id, "'review_policy' must be 'manual' in this slice")
        )

    max_age_days = freshness.get("max_age_days")
    if max_age_days is None or _is_positive_int(max_age_days):
        if max_age_days != SLICE_MAX_AGE_DAYS:
            findings.append(
                _finding("MAX_AGE_DAYS_NOT_90", entry_id, "'max_age_days' must be 90 in this slice")
            )
    else:
        findings.append(
            _finding("MAX_AGE_DAYS_INVALID", entry_id, "'max_age_days' must be a positive integer or null")
        )

    last_reviewed = freshness.get("last_reviewed", "__missing__")
    if last_reviewed == "__missing__":
        findings.append(_finding("LAST_REVIEWED_INVALID", entry_id, "'last_reviewed' is required (null in this slice)"))
    elif last_reviewed is None:
        pass
    elif isinstance(last_reviewed, str) and DATE_PATTERN.match(last_reviewed):
        findings.append(_finding("LAST_REVIEWED_NOT_NULL", entry_id, "'last_reviewed' must be null in this slice"))
    else:
        findings.append(_finding("LAST_REVIEWED_INVALID", entry_id, "'last_reviewed' must be null or a YYYY-MM-DD string"))

    return findings


def validate_registry_data(data: object, claim_ids: set[str], repo_root: Path) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    if not isinstance(data, dict):
        return [_finding("INVALID_TOP_LEVEL", None, "Top-level registry must be an object")]

    if data.get("version") != 1:
        findings.append(_finding("INVALID_VERSION", None, "Top-level field 'version' must equal 1"))

    entries = data.get("entries")
    if not isinstance(entries, list):
        findings.append(_finding("INVALID_ENTRIES", None, "Top-level field 'entries' must be a list"))
        return findings

    if len(entries) != EXPECTED_ENTRY_COUNT:
        findings.append(
            _finding(
                "WRONG_ENTRY_COUNT",
                None,
                f"Registry must contain exactly {EXPECTED_ENTRY_COUNT} entries, found {len(entries)}",
            )
        )

    seen_ids: set[str] = set()
    seen_claim_refs: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            findings.append(_finding("ENTRY_NOT_OBJECT", None, "Each entry must be an object"))
            continue

        entry_id = entry.get("id") if isinstance(entry.get("id"), str) else None

        if entry_id is None:
            findings.append(_finding("INVALID_ID", None, "Entry 'id' must be a string"))
        else:
            if not ENTRY_ID_PATTERN.match(entry_id):
                findings.append(
                    _finding("INVALID_ID", entry_id, "Entry 'id' must match freshness.claim.agent_safe_00[1-3]")
                )
            if entry_id in seen_ids:
                findings.append(_finding("DUPLICATE_ID", entry_id, "Duplicate entry id"))
            seen_ids.add(entry_id)

        status = entry.get("status")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            findings.append(
                _finding(
                    "INVALID_STATUS",
                    entry_id,
                    f"'status' must be one of: {', '.join(sorted(VALID_STATUSES))}",
                )
            )
        elif status != SLICE_STATUS:
            findings.append(_finding("STATUS_NOT_ACTIVE", entry_id, "'status' must be 'active' in this slice"))

        claim_ref = entry.get("claim_ref")
        if claim_ref is None:
            findings.append(_finding("CLAIM_REF_NULL", entry_id, "'claim_ref' must not be null"))
        elif not isinstance(claim_ref, str):
            findings.append(_finding("CLAIM_REF_INVALID", entry_id, "'claim_ref' must be a string"))
        else:
            if claim_ref not in IN_SCOPE_CLAIMS:
                findings.append(
                    _finding(
                        "CLAIM_REF_OUT_OF_SCOPE",
                        entry_id,
                        "'claim_ref' must be one of CLAIM-AGENT-SAFE-001..003",
                    )
                )
            if claim_ref not in claim_ids:
                findings.append(
                    _finding("CLAIM_REF_UNKNOWN", entry_id, f"'claim_ref' {claim_ref} not found in claim registry")
                )
            if claim_ref in seen_claim_refs:
                findings.append(_finding("CLAIM_REF_DUPLICATE", entry_id, f"Duplicate claim_ref {claim_ref}"))
            seen_claim_refs.add(claim_ref)

        subject = entry.get("subject")
        if not isinstance(subject, dict):
            findings.append(_finding("SUBJECT_INVALID", entry_id, "'subject' must be an object"))
        else:
            if subject.get("kind") != "claim":
                findings.append(_finding("SUBJECT_KIND_INVALID", entry_id, "'subject.kind' must be 'claim'"))
            if subject.get("ref") != claim_ref:
                findings.append(
                    _finding("SUBJECT_REF_MISMATCH", entry_id, "'subject.ref' must equal 'claim_ref'")
                )

        findings.extend(_validate_evidence(entry_id, entry.get("evidence"), repo_root))
        findings.extend(_validate_freshness(entry_id, entry.get("freshness")))

    return findings


def run_validation(
    registry: str = "docs/doc-freshness-registry.yml",
    claims: str = "docs/claims/registry.yml",
    repo_root: str | Path | None = None,
) -> tuple[dict[str, object], int]:
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    registry_path = root / registry
    claims_path = root / claims

    data, load_error = load_yaml_json(registry_path)
    if load_error is not None:
        finding = _finding("REGISTRY_LOAD_ERROR", None, load_error)
        return {"registry": registry, "entries_count": 0, "findings_count": 1, "findings": [finding]}, 1

    claim_ids, claim_error = _load_claim_ids(claims_path)
    findings: list[dict[str, str]] = []
    if claim_error is not None:
        findings.append(_finding("CLAIM_REGISTRY_LOAD_ERROR", None, claim_error))

    findings.extend(validate_registry_data(data, claim_ids, root))

    entries = data.get("entries") if isinstance(data, dict) else []
    entries_count = len(entries) if isinstance(entries, list) else 0
    output = {
        "registry": registry,
        "entries_count": entries_count,
        "findings_count": len(findings),
        "findings": findings,
    }
    return output, (0 if not findings else 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate doc freshness registry")
    parser.add_argument(
        "--registry",
        default="docs/doc-freshness-registry.yml",
        help="Path relative to repository root",
    )
    parser.add_argument(
        "--claims",
        default="docs/claims/registry.yml",
        help="Path relative to repository root",
    )
    args = parser.parse_args(argv)

    output, exit_code = run_validation(args.registry, args.claims)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
