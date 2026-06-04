#!/usr/bin/env python3
"""Generate the deterministic Claim Evidence Map from the freshness registry.

Reads ``docs/doc-freshness-registry.yml`` and renders two report-only outputs:

* ``docs/_generated/claim-evidence-map.md`` (human navigable overview)
* ``artifacts/docmeta/claim_evidence_map.json`` (machine readable artifact)

This generator is report-only. It surfaces the claim -> evidence linkage and the
conservative freshness metadata. It does NOT prove any claim true and it does NOT
assert that a review happened.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.validate_doc_freshness_registry import load_yaml_json

REGISTRY_REL = "docs/doc-freshness-registry.yml"
MARKDOWN_REL = "docs/_generated/claim-evidence-map.md"
JSON_REL = "artifacts/docmeta/claim_evidence_map.json"
GENERATOR_REL = "scripts/docmeta/generate_claim_evidence_map.py"


def _as_date(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")


def compute_freshness_status(last_reviewed: object, max_age_days: object, today: object = None) -> str:
    """Conservatively derive a freshness status.

    * ``last_reviewed`` is None                       -> ``unknown``
    * reviewed set and ``max_age_days`` is None        -> ``current``
    * reviewed set and age <= ``max_age_days``         -> ``current``
    * reviewed set and age >  ``max_age_days``         -> ``stale``
    """
    reviewed = _as_date(last_reviewed)
    if reviewed is None:
        return "unknown"
    current_day = _as_date(today) if today is not None else date.today()
    if max_age_days is None:
        return "current"
    age_days = (current_day - reviewed).days
    return "current" if age_days <= max_age_days else "stale"


def _build_entries(data: object, today: object = None) -> list[dict[str, object]]:
    raw_entries = data.get("entries", []) if isinstance(data, dict) else []
    entries: list[dict[str, object]] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        evidence = raw.get("evidence") or []
        evidence_items = [item for item in evidence if isinstance(item, dict)]
        evidence_paths = [item.get("path") for item in evidence_items]
        evidence_kinds = [item.get("kind") for item in evidence_items]

        freshness = raw.get("freshness") or {}
        review_policy = freshness.get("review_policy") if isinstance(freshness, dict) else None
        max_age_days = freshness.get("max_age_days") if isinstance(freshness, dict) else None
        last_reviewed = freshness.get("last_reviewed") if isinstance(freshness, dict) else None
        freshness_status = compute_freshness_status(last_reviewed, max_age_days, today=today)

        subject = raw.get("subject") or {}
        subject_kind = subject.get("kind") if isinstance(subject, dict) else None
        subject_ref = subject.get("ref") if isinstance(subject, dict) else None

        entries.append(
            {
                "id": raw.get("id"),
                "claim_ref": raw.get("claim_ref"),
                "subject": {"kind": subject_kind, "ref": subject_ref},
                "evidence_paths": evidence_paths,
                "evidence_kinds": evidence_kinds,
                "freshness": {
                    "review_policy": review_policy,
                    "max_age_days": max_age_days,
                    "last_reviewed": last_reviewed,
                    "freshness_status": freshness_status,
                },
                "status": raw.get("status"),
            }
        )

    entries.sort(key=lambda entry: str(entry.get("id") or ""))
    return entries


def build_json_object(data: object, today: object = None) -> dict[str, object]:
    return {
        "version": 1,
        "source": REGISTRY_REL,
        "generated_by": GENERATOR_REL,
        "entries": _build_entries(data, today=today),
    }


def render_json(data: object, today: object = None) -> str:
    obj = build_json_object(data, today=today)
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def render_markdown(data: object, today: object = None) -> str:
    entries = _build_entries(data, today=today)
    lines: list[str] = []
    lines.append("---")
    lines.append("id: docs.generated.claim-evidence-map")
    lines.append("title: Claim Evidence Map")
    lines.append("doc_type: generated")
    lines.append("status: active")
    lines.append("summary: Automatisch generierte Claim-Evidence-Freshness-Map.")
    lines.append("---")
    lines.append("")
    lines.append("# Claim Evidence Map")
    lines.append("")
    lines.append("Generated automatically. Do not edit.")
    lines.append("")
    lines.append("| id | claim_ref | subject | evidence | freshness | status |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for entry in entries:
        subject = entry["subject"]
        subject_cell = f"{subject['kind']}:{subject['ref']}"
        evidence_cell = f"{len(entry['evidence_paths'])} paths"
        freshness_cell = entry["freshness"]["freshness_status"]
        lines.append(
            f"| {entry['id']} | {entry['claim_ref']} | {subject_cell} "
            f"| {evidence_cell} | {freshness_cell} | {entry['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def _load_registry(root: Path) -> object:
    data, error = load_yaml_json(root / REGISTRY_REL)
    if error is not None:
        raise ValueError(error)
    return data


def generate(repo_root: str | Path | None = None, today: object = None) -> tuple[Path, Path]:
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    data = _load_registry(root)

    md_content = render_markdown(data, today=today)
    json_content = render_json(data, today=today)

    md_path = root / MARKDOWN_REL
    json_path = root / JSON_REL
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_content, encoding="utf-8")
    json_path.write_text(json_content, encoding="utf-8")
    return md_path, json_path


def check(repo_root: str | Path | None = None, today: object = None) -> list[str]:
    """Return the list of output paths that drift from the registry (empty = ok)."""
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    data = _load_registry(root)

    expected_md = render_markdown(data, today=today)
    expected_json = render_json(data, today=today)

    drift: list[str] = []
    md_path = root / MARKDOWN_REL
    json_path = root / JSON_REL

    actual_md = md_path.read_text(encoding="utf-8") if md_path.exists() else None
    actual_json = json_path.read_text(encoding="utf-8") if json_path.exists() else None

    if actual_md != expected_md:
        drift.append(MARKDOWN_REL)
    if actual_json != expected_json:
        drift.append(JSON_REL)
    return drift


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the claim evidence map")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify generated outputs match the registry without writing files",
    )
    args = parser.parse_args(argv)

    if args.check:
        try:
            drift = check()
        except ValueError as exc:
            print(f"Error reading freshness registry: {exc}", file=sys.stderr)
            return 1
        if drift:
            print("Claim evidence map drift detected in: " + ", ".join(drift), file=sys.stderr)
            print("Run: python3 -m scripts.docmeta.generate_claim_evidence_map", file=sys.stderr)
            return 1
        print("Claim evidence map is up to date.")
        return 0

    try:
        generate()
    except ValueError as exc:
        print(f"Error generating claim evidence map: {exc}", file=sys.stderr)
        return 1
    print(f"Generated {MARKDOWN_REL} and {JSON_REL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
