#!/usr/bin/env python3
"""Validate docs/doc-freshness-registry.yml as a Lenskit doc_freshness_registry bridge.

This validator checks:
1. The bridge file conforms to the lenskit.doc_freshness_registry v1.0 contract.
2. Each entry's evidence set exactly mirrors the mapped evidence from docs/claims/registry.yml.

Evidence kind mapping (Weltgewebe claim-registry -> Lenskit bridge):
    implementation, documentation, ci, generated-report, registry  ->  file
    test                                                            ->  test
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta import validate_claim_registry
from scripts.docmeta.docmeta import REPO_ROOT

CLAIM_EVIDENCE_KIND_TO_LENSKIT: dict[str, str] = {
    "implementation": "file",
    "documentation": "file",
    "ci": "file",
    "generated-report": "file",
    "registry": "file",
    "test": "test",
}

VALID_LENSKIT_EVIDENCE_KINDS = {"symbol", "file", "text", "absent_text", "proof", "test"}
EVIDENCE_KINDS_CHECK_PATH = {"file", "test", "proof"}

VALID_STATUSES = {"none", "partial", "done", "stale", "historical"}
SLICE_STATUS = "partial"

EXPECTED_ENTRY_COUNT = 3
VALID_ENTRY_IDS = {"claim-agent-safe-001", "claim-agent-safe-002", "claim-agent-safe-003"}
ENTRY_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
LOCATOR_PATTERN = re.compile(r"^claims\[id=([A-Z0-9-]+)\]$")
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EXPECTED_DOC = "docs/claims/registry.yml"


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


def _load_claim_evidence(
    claims_path: Path,
) -> tuple[dict[str, dict[str, object]], str | None]:
    """Load claims from docs/claims/registry.yml.

    Returns a dict keyed by claim id, each value containing:
        - statement: str
        - mapped_pairs: set of (target, lenskit_kind)
        - unmappable: list of (path, kind) that have no lenskit mapping
    """
    data, _findings, exit_code = validate_claim_registry.load_registry(claims_path)
    if exit_code != 0 or not isinstance(data, dict):
        return {}, f"Claim registry could not be loaded: {claims_path}"
    claims = data.get("claims")
    if not isinstance(claims, list):
        return {}, "Claim registry has no 'claims' list"

    result: dict[str, dict[str, object]] = {}
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get("id"), str):
            continue
        cid = claim["id"]
        statement = claim.get("statement", "")
        mapped_pairs: set[tuple[str, str]] = set()
        unmappable: list[tuple[str, str]] = []
        for ev in claim.get("evidence", []):
            if not isinstance(ev, dict):
                continue
            path = ev.get("path")
            kind = ev.get("kind")
            if not isinstance(path, str) or not isinstance(kind, str):
                continue
            lenskit_kind = CLAIM_EVIDENCE_KIND_TO_LENSKIT.get(kind)
            if lenskit_kind is None:
                unmappable.append((path, kind))
            else:
                mapped_pairs.add((path, lenskit_kind))
        result[cid] = {
            "statement": statement,
            "mapped_pairs": mapped_pairs,
            "unmappable": unmappable,
        }
    return result, None


def _claim_id_from_entry_id(entry_id: str) -> str:
    """Derive CLAIM-AGENT-SAFE-00N from claim-agent-safe-00n."""
    return entry_id.upper()


def _claim_id_from_locator(locator: str) -> str | None:
    m = LOCATOR_PATTERN.match(locator)
    return m.group(1) if m else None


def _validate_evidence(
    entry_id: str | None,
    evidence: object,
    repo_root: Path,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    if not isinstance(evidence, list) or not evidence:
        findings.append(_finding("EVIDENCE_EMPTY", entry_id, "Evidence must be a non-empty list"))
        return findings

    for item in evidence:
        if not isinstance(item, dict):
            findings.append(_finding("EVIDENCE_NOT_OBJECT", entry_id, "Each evidence item must be an object"))
            continue

        target = item.get("target")
        if not isinstance(target, str) or not target.strip():
            findings.append(_finding("EVIDENCE_TARGET_NOT_STRING", entry_id, "Evidence 'target' must be a non-empty string"))
        elif target.startswith("/") or Path(target).is_absolute():
            findings.append(_finding("EVIDENCE_TARGET_ABSOLUTE", entry_id, "Evidence target must be repo-relative", path=target))
        elif ".." in Path(target).parts:
            findings.append(_finding("EVIDENCE_TARGET_TRAVERSAL", entry_id, "Evidence target must not contain '..'", path=target))
        else:
            kind = item.get("kind")
            if isinstance(kind, str) and kind in EVIDENCE_KINDS_CHECK_PATH:
                if not (repo_root / target).exists():
                    findings.append(_finding("EVIDENCE_TARGET_MISSING", entry_id, "Evidence target does not exist", path=target))

        kind = item.get("kind")
        if not isinstance(kind, str) or kind not in VALID_LENSKIT_EVIDENCE_KINDS:
            findings.append(
                _finding(
                    "EVIDENCE_KIND_INVALID",
                    entry_id,
                    f"Evidence 'kind' must be one of: {', '.join(sorted(VALID_LENSKIT_EVIDENCE_KINDS))}",
                    path=target if isinstance(target, str) else None,
                )
            )

    return findings


def _cross_check_evidence(
    entry_id: str | None,
    claim_id: str,
    evidence: object,
    claim_info: dict[str, object],
) -> list[dict[str, str]]:
    """Verify bridge evidence == mapped claim evidence, (target, lenskit_kind) set equality."""
    findings: list[dict[str, str]] = []

    for path, kind in claim_info.get("unmappable", []):  # type: ignore[union-attr]
        findings.append(
            _finding(
                "EVIDENCE_KIND_MAPPING_INVALID",
                entry_id,
                f"Claim evidence kind '{kind}' has no Lenskit mapping for {claim_id}",
                path=path,
            )
        )

    expected_pairs: set[tuple[str, str]] = claim_info.get("mapped_pairs", set())  # type: ignore[assignment]
    actual_pairs: set[tuple[str, str]] = set()
    if isinstance(evidence, list):
        for item in evidence:
            if not isinstance(item, dict):
                continue
            target = item.get("target")
            kind = item.get("kind")
            if isinstance(target, str) and isinstance(kind, str):
                actual_pairs.add((target, kind))

    for target, kind in sorted(actual_pairs - expected_pairs):
        findings.append(
            _finding(
                "EVIDENCE_NOT_IN_CLAIM_REGISTRY",
                entry_id,
                f"Evidence pair (kind={kind}) is not in the mapped claim evidence for {claim_id}",
                path=target,
            )
        )
    for target, kind in sorted(expected_pairs - actual_pairs):
        findings.append(
            _finding(
                "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY",
                entry_id,
                f"Mapped claim evidence pair (kind={kind}) is missing from bridge for {claim_id}",
                path=target,
            )
        )
    return findings


def validate_registry_data(
    data: object,
    claim_data: dict[str, dict[str, object]],
    repo_root: Path,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    if not isinstance(data, dict):
        return [_finding("INVALID_TOP_LEVEL", None, "Top-level registry must be an object")]

    if data.get("kind") != "lenskit.doc_freshness_registry":
        findings.append(_finding("INVALID_KIND", None, "Top-level 'kind' must be 'lenskit.doc_freshness_registry'"))

    if data.get("version") != "1.0":
        findings.append(_finding("INVALID_VERSION", None, "Top-level 'version' must be the string \"1.0\""))

    entries = data.get("entries")
    if not isinstance(entries, list):
        findings.append(_finding("INVALID_ENTRIES", None, "Top-level 'entries' must be a list"))
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
    seen_claim_ids: set[str] = set()

    for entry in entries:
        if not isinstance(entry, dict):
            findings.append(_finding("ENTRY_NOT_OBJECT", None, "Each entry must be an object"))
            continue

        entry_id = entry.get("id") if isinstance(entry.get("id"), str) else None

        if entry_id is None:
            findings.append(_finding("INVALID_ID", None, "Entry 'id' must be a string"))
        else:
            if not ENTRY_ID_PATTERN.match(entry_id):
                findings.append(_finding("INVALID_ID", entry_id, "Entry 'id' must match ^[a-z0-9][a-z0-9-]*$"))
            if entry_id not in VALID_ENTRY_IDS:
                findings.append(
                    _finding("INVALID_ID", entry_id, f"Entry 'id' must be one of: {', '.join(sorted(VALID_ENTRY_IDS))}")
                )
            if entry_id in seen_ids:
                findings.append(_finding("DUPLICATE_ID", entry_id, "Duplicate entry id"))
            seen_ids.add(entry_id)

        doc = entry.get("doc")
        if doc != EXPECTED_DOC:
            findings.append(
                _finding("DOC_MISMATCH", entry_id, f"'doc' must be '{EXPECTED_DOC}', got: {doc!r}")
            )

        locator = entry.get("locator")
        claim_id_from_locator: str | None = None
        if not isinstance(locator, str) or not locator.strip():
            findings.append(_finding("LOCATOR_MISSING", entry_id, "'locator' must be a non-empty string"))
        else:
            claim_id_from_locator = _claim_id_from_locator(locator)
            if claim_id_from_locator is None:
                findings.append(
                    _finding("LOCATOR_MISMATCH", entry_id, f"'locator' must match claims[id=CLAIM-ID], got: {locator!r}")
                )

        claim_id_from_id = _claim_id_from_entry_id(entry_id) if entry_id else None

        if claim_id_from_id and claim_id_from_locator and claim_id_from_id != claim_id_from_locator:
            findings.append(
                _finding(
                    "ENTRY_ID_CLAIM_MISMATCH",
                    entry_id,
                    f"Entry id implies {claim_id_from_id} but locator implies {claim_id_from_locator}",
                )
            )

        claim_id = claim_id_from_id or claim_id_from_locator

        claim_text = entry.get("claim")
        if not isinstance(claim_text, str) or not claim_text.strip():
            findings.append(_finding("CLAIM_MISSING", entry_id, "'claim' must be a non-empty string"))
        elif claim_id and claim_id in claim_data:
            expected_statement = claim_data[claim_id].get("statement", "")
            if claim_text != expected_statement:
                findings.append(
                    _finding(
                        "CLAIM_STATEMENT_MISMATCH",
                        entry_id,
                        f"'claim' does not match statement in docs/claims/registry.yml for {claim_id}",
                    )
                )

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
            findings.append(
                _finding("STATUS_NOT_PARTIAL", entry_id, f"'status' must be '{SLICE_STATUS}' in this slice")
            )

        owner = entry.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            findings.append(_finding("OWNER_MISSING", entry_id, "'owner' must be a non-empty string"))

        last_verified = entry.get("last_verified")
        if not isinstance(last_verified, str) or not DATE_PATTERN.match(last_verified):
            findings.append(
                _finding("LAST_VERIFIED_INVALID", entry_id, "'last_verified' must be a YYYY-MM-DD date string")
            )
        else:
            try:
                date.fromisoformat(last_verified)
            except ValueError:
                findings.append(
                    _finding("LAST_VERIFIED_INVALID", entry_id, "'last_verified' must be a valid calendar date")
                )

        findings.extend(_validate_evidence(entry_id, entry.get("evidence"), repo_root))

        if claim_id and claim_id in claim_data:
            if claim_id in seen_claim_ids:
                findings.append(_finding("DUPLICATE_CLAIM_ID", entry_id, f"Duplicate claim id {claim_id}"))
            seen_claim_ids.add(claim_id)
            findings.extend(
                _cross_check_evidence(entry_id, claim_id, entry.get("evidence"), claim_data[claim_id])
            )
        elif claim_id:
            findings.append(
                _finding("CLAIM_ID_UNKNOWN", entry_id, f"Claim {claim_id} not found in docs/claims/registry.yml")
            )

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

    claim_data: dict[str, dict[str, object]] = {}
    findings: list[dict[str, str]] = []
    claim_data_raw, claim_error = _load_claim_evidence(claims_path)
    if claim_error is not None:
        findings.append(_finding("CLAIM_REGISTRY_LOAD_ERROR", None, claim_error))
    else:
        claim_data = claim_data_raw

    findings.extend(validate_registry_data(data, claim_data, root))

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
    parser = argparse.ArgumentParser(description="Validate doc freshness registry (Lenskit bridge form)")
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
