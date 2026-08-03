#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.generated_check import write_or_check
from scripts.docmeta.generate_report_lifecycle_inventory import (
    collect_reports,
    ReportRecord,
    InventoryConfig,
    _cell,
)
from scripts.docmeta.validate_report_lifecycle import _validate_report, _load_frontmatter
from scripts.docmeta.report_lifecycle_requirements import (
    build_truth_contract,
    missing_required_report_fields,
    parse_truth_contract_markdown,
    source_manifest,
    source_revision_metadata,
    string_value,
    truth_contract_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

HEADER = """\
---
id: docs.generated.report-lifecycle
title: Report Lifecycle Overview
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generierte Übersicht der Report-Lifecycle-Zustände.
---
# Report Lifecycle Overview

Generated automatically. Do not edit manually.

This overview is descriptive only. It surfaces lifecycle metadata and validator findings for planning; it is not a CI guard and not a policy judgement.
"""

@dataclass(frozen=True)
class LifecycleOverviewRow:
    path: str
    title: str
    doc_type: str
    status: str
    lifecycle_state: str
    lifecycle: str
    owner_task: str
    review_after: str
    superseded_by: str
    primary_refs: int
    derived_refs: int
    findings: tuple[str, ...]
    missing_required_fields: tuple[str, ...]

def collect_lifecycle_rows(root: Path, records: list[ReportRecord]) -> list[LifecycleOverviewRow]:
    rows = []
    for record in records:
        full_path = root / record.path
        frontmatter = _load_frontmatter(full_path)
        findings = _validate_report(full_path, frontmatter, root)
        finding_codes = tuple(sorted(f.code for f in findings))

        # Policy-visible values use the same parsed frontmatter and
        # normalization as validator findings. ReportRecord remains
        # the source for path, title, and reference metadata.
        rows.append(
            LifecycleOverviewRow(
                path=record.path,
                title=record.title,
                doc_type=string_value(frontmatter.get("doc_type")),
                status=string_value(frontmatter.get("status")),
                lifecycle_state=string_value(frontmatter.get("lifecycle_state")),
                lifecycle=string_value(frontmatter.get("lifecycle")),
                owner_task=string_value(frontmatter.get("owner_task")),
                review_after=string_value(frontmatter.get("review_after")),
                superseded_by=string_value(frontmatter.get("superseded_by")),
                primary_refs=record.referenced_by_count,
                derived_refs=len(record.derived_referenced_by_paths),
                findings=finding_codes,
                missing_required_fields=missing_required_report_fields(frontmatter),
            )
        )
    return rows

def _norm(value: str) -> str:
    return value.strip().lower()

def group_rows(rows: list[LifecycleOverviewRow]) -> dict[str, list[LifecycleOverviewRow]]:
    groups = defaultdict(list)
    for row in rows:
        doc_type = _norm(row.doc_type)
        if doc_type != "report":
            groups["non_report"].append(row)
        elif not row.lifecycle_state:
            groups["unclassified"].append(row)
        else:
            state = row.lifecycle_state.strip().lower()
            if state in {"active", "deferred", "superseded", "archived"}:
                groups[state].append(row)
            else:
                groups["other"].append(row)
    
    for key in groups:
        groups[key].sort(key=lambda r: r.path)
    return groups

def build_summary(rows: list[LifecycleOverviewRow]) -> dict[str, int]:
    summary = {
        "files_scanned": len(rows),
        "reports_checked": 0,
        "reports_ignored_non_report": 0,
        "reports_with_lifecycle_state": 0,
        "reports_missing_lifecycle_state": 0,
        "findings_total": 0,
    }
    
    for row in rows:
        doc_type = _norm(row.doc_type)
        if doc_type == "report":
            summary["reports_checked"] += 1
            if row.lifecycle_state:
                summary["reports_with_lifecycle_state"] += 1
            else:
                summary["reports_missing_lifecycle_state"] += 1
        else:
            summary["reports_ignored_non_report"] += 1
            
        summary["findings_total"] += len(row.findings)
        
    return summary

def render_markdown(
    rows: list[LifecycleOverviewRow],
    summary: dict[str, int],
    truth_contract: dict[str, object] | None = None,
) -> str:
    lines = [HEADER.rstrip(), ""]
    
    lines.extend([
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| files_scanned | {summary['files_scanned']} |",
        f"| reports_checked | {summary['reports_checked']} |",
        f"| reports_ignored_non_report | {summary['reports_ignored_non_report']} |",
        f"| reports_with_lifecycle_state | {summary['reports_with_lifecycle_state']} |",
        f"| reports_missing_lifecycle_state | {summary['reports_missing_lifecycle_state']} |",
        f"| findings_total | {summary['findings_total']} |",
        ""
    ])
    
    groups = group_rows(rows)
    
    lines.extend([
        "## Lifecycle State Summary",
        "",
        "| lifecycle_state | Count |",
        "| --- | ---: |",
        f"| active | {len(groups.get('active', []))} |",
        f"| deferred | {len(groups.get('deferred', []))} |",
        f"| superseded | {len(groups.get('superseded', []))} |",
        f"| archived | {len(groups.get('archived', []))} |",
        f"| missing | {len(groups.get('unclassified', []))} |",
        ""
    ])
    
    if "other" in groups and groups["other"]:
        lines.insert(-1, f"| other | {len(groups['other'])} |")
    
    finding_counts = defaultdict(int)
    for row in rows:
        for finding in row.findings:
            finding_counts[finding] += 1
            
    lines.extend([
        "## Finding Summary",
        "",
        "| Code | Count |",
        "| --- | ---: |",
    ])
    
    for code in sorted(finding_counts.keys()):
        lines.append(f"| {code} | {finding_counts[code]} |")
    if not finding_counts:
        lines.append("| _None_ | 0 |")
    lines.append("")
    
    def render_report_table(title: str, report_list: list[LifecycleOverviewRow]):
        lines.extend([
            f"## {title}",
            "",
            "| Report | status | lifecycle | owner_task | review_after | findings |",
            "| --- | --- | --- | --- | --- | --- |"
        ])
        if report_list:
            for r in report_list:
                findings_str = ", ".join(r.findings) if r.findings else ""
                lines.append(f"| {r.path} | {_cell(r.status)} | {_cell(r.lifecycle)} | {_cell(r.owner_task)} | {_cell(r.review_after)} | {_cell(findings_str)} |")
        else:
            lines.append("| _None_ | | | | | |")
        lines.append("")

    render_report_table("Active Reports", groups.get("active", []))
    render_report_table("Deferred Reports", groups.get("deferred", []))
    render_report_table("Superseded Reports", groups.get("superseded", []))
    render_report_table("Archived Reports", groups.get("archived", []))
    render_report_table("Unclassified Reports", groups.get("unclassified", []))
    
    reports_with_findings = [r for r in rows if r.findings and _norm(r.doc_type) == "report"]
    reports_with_findings.sort(key=lambda r: r.path)
    lines.extend([
        "## Reports With Findings",
        "",
        "| Report | lifecycle_state | status | findings |",
        "| --- | --- | --- | --- |"
    ])
    if reports_with_findings:
        for r in reports_with_findings:
            lines.append(f"| {r.path} | {_cell(r.lifecycle_state)} | {_cell(r.status)} | {_cell(', '.join(r.findings))} |")
    else:
        lines.append("| _None_ | | | |")
    lines.append("")

    reports_missing_fields = [
        r for r in rows
        if r.missing_required_fields and _norm(r.doc_type) == "report"
    ]
    reports_missing_fields.sort(key=lambda r: r.path)
    lines.extend([
        "## Reports With Missing Currently-Enforced Fields",
        "",
        (
            "Fields required by the currently implemented validator rules that are "
            + "absent, in rule-precedence order. This reflects field presence only; it "
            + "is not a full normative lifecycle judgement and does not cover enum, "
            + "date, owner, or relation checks. Future validator rules may surface "
            + "additional requirements."
        ),
        "",
        "| Report | status | lifecycle_state | Missing currently-enforced fields |",
        "| --- | --- | --- | --- |"
    ])
    if reports_missing_fields:
        for r in reports_missing_fields:
            lines.append(
                f"| {r.path} | {_cell(r.status)} | {_cell(r.lifecycle_state)} | "
                f"{_cell(', '.join(r.missing_required_fields))} |"
            )
    else:
        lines.append("| _None_ | | | |")
    lines.append("")

    non_reports = groups.get("non_report", [])
    lines.extend([
        "## Non-Report Files Under docs/reports",
        "",
        "| File | doc_type | status |",
        "| --- | --- | --- |"
    ])
    if non_reports:
        for r in non_reports:
            lines.append(f"| {r.path} | {_cell(r.doc_type)} | {_cell(r.status)} |")
    else:
        lines.append("| _None_ | | |")

    if truth_contract is not None:
        lines.extend(["", truth_contract_markdown(truth_contract).rstrip()])

    return "\n".join(lines).rstrip() + "\n"


def _existing_truth_contract(path: Path) -> Mapping[str, object] | None:
    if not path.is_file():
        return None
    value = parse_truth_contract_markdown(path.read_text(encoding="utf-8"))
    return value if isinstance(value, Mapping) else None


def build_overview_truth_contract(
    root: Path,
    records: list[ReportRecord],
    summary: dict[str, int],
    existing_contract: Mapping[str, object] | None = None,
) -> dict[str, object]:
    source_paths = [root / record.path for record in records]
    fallback_revision = (
        existing_contract.get("source_revision") if existing_contract is not None else None
    )
    fallback_generated_at = (
        existing_contract.get("generated_at") if existing_contract is not None else None
    )
    revision, generated_at, fresh = source_revision_metadata(
        root,
        source_paths,
        fallback_revision=fallback_revision if isinstance(fallback_revision, str) else None,
        fallback_generated_at=(
            fallback_generated_at if isinstance(fallback_generated_at, str) else None
        ),
    )
    failures = summary["findings_total"]
    status = "pass" if fresh and failures == 0 else ("fail" if failures else "unknown")
    return build_truth_contract(
        status=status,
        scope="all Markdown files discovered under docs/reports",
        complete=True,
        fresh=fresh,
        method="exact",
        checked_items=summary["files_scanned"],
        total_items=summary["files_scanned"],
        failures=failures,
        source_revision=revision,
        generated_at=generated_at,
        sources=source_manifest(root, source_paths),
        limitations=[
            "The report reflects repository files only and does not execute product runtime checks."
        ],
        does_not_establish=[
            "Runtime health, deployment health, or the correctness of claims inside individual reports."
        ],
     )


def generate(root: Path = REPO_ROOT, output_path: Path | None = None) -> Path:
    out_path = output_path or (root / "docs" / "_generated" / "report-lifecycle.md")
    
    config = InventoryConfig(
        repo_root=root,
        reports_dir=root / "docs" / "reports",
        output_path=out_path,
        primary_search_paths=(root / "docs",),
        derived_search_paths=(root / "docs" / "_generated",)
    )
    
    records = collect_reports(config)
    rows = collect_lifecycle_rows(root, records)
    summary = build_summary(rows)
    truth_contract = build_overview_truth_contract(
        root, records, summary, _existing_truth_contract(out_path)
    )
    content = render_markdown(rows, summary, truth_contract)
    
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    
    root_path = Path(args.root) if args.root else REPO_ROOT
    output_path = Path(args.output) if args.output else None

    if args.check:
        target = output_path or (root_path / "docs" / "_generated" / "report-lifecycle.md")
        config = InventoryConfig(
            repo_root=root_path,
            reports_dir=root_path / "docs" / "reports",
            output_path=target,
            primary_search_paths=(root_path / "docs",),
            derived_search_paths=(root_path / "docs" / "_generated",)
        )
        records = collect_reports(config)
        rows = collect_lifecycle_rows(root_path, records)
        summary = build_summary(rows)
        truth_contract = build_overview_truth_contract(
            root_path, records, summary, _existing_truth_contract(target)
        )
        content = render_markdown(rows, summary, truth_contract)
        return write_or_check(target, content, check=True, label=str(target.relative_to(root_path)))

    out = generate(root_path, output_path)
    try:
        rel = out.relative_to(root_path)
    except ValueError:
        rel = out
    print(f"Generated {rel}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
