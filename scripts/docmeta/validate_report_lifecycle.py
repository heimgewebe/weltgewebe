#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import parse_frontmatter

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Finding:
    path: str
    code: str
    severity: str
    message: str
    field: str | None = None


def _string_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return ""
    return str(value).strip()


def _load_frontmatter(path: Path) -> dict[str, object]:
    fm = parse_frontmatter(str(path))
    if fm is None:
        return {}
    return fm


def _iter_report_paths(root: Path) -> list[Path]:
    reports_dir = root / "docs" / "reports"
    if not reports_dir.exists():
        return []
    return sorted([p for p in reports_dir.glob("*.md") if p.is_file()])


def _validate_report(path: Path, frontmatter: dict[str, object], root: Path) -> list[Finding]:
    try:
        rel_path = path.relative_to(root).as_posix()
    except ValueError:
        rel_path = str(path)

    doc_type = _string_value(frontmatter.get("doc_type")).strip().lower()
    if doc_type != "report":
        return []

    status = _string_value(frontmatter.get("status")).strip().lower()
    lifecycle_state = _string_value(frontmatter.get("lifecycle_state")).strip().lower()
    lifecycle = _string_value(frontmatter.get("lifecycle")).strip()
    owner_task = _string_value(frontmatter.get("owner_task")).strip()
    review_after = _string_value(frontmatter.get("review_after")).strip()
    superseded_by = _string_value(frontmatter.get("superseded_by")).strip()

    findings: list[Finding] = []
    added_codes = set()

    def add_finding(code: str, field: str, message: str):
        if code not in added_codes:
            findings.append(Finding(
                path=rel_path,
                code=code,
                severity="warn",
                field=field,
                message=message
            ))
            added_codes.add(code)

    # Regel 1 — doc_type: report braucht status
    if not status:
        add_finding("missing_status", "status", "report documents should define status")

    # Regel 2 — status: active braucht lifecycle
    if status == "active" and not lifecycle:
        add_finding("missing_lifecycle", "lifecycle", "active reports should define lifecycle")

    # Regel 3 — status: active oder status: draft braucht review_after
    if status in {"active", "draft"} and not review_after:
        add_finding("missing_review_after", "review_after", "active/draft reports should define review_after")

    # Regel 4 — lifecycle_state: active braucht Kernfelder
    if lifecycle_state == "active":
        if not lifecycle:
            add_finding("missing_lifecycle", "lifecycle", "active reports should define lifecycle")
        if not owner_task:
            add_finding("missing_owner_task", "owner_task", "active reports should define owner_task")
        if not review_after:
            add_finding("missing_review_after", "review_after", "active/draft reports should define review_after")

    # Regel 5 — lifecycle_state: superseded braucht superseded_by
    if lifecycle_state == "superseded" and not superseded_by:
        add_finding("missing_superseded_by", "superseded_by", "superseded reports should define superseded_by")

    return findings


def _build_summary(
    findings: list[Finding],
    files_scanned: int,
    reports_checked: int,
    reports_ignored_non_report: int
) -> dict[str, int]:
    summary = {
        "files_scanned": files_scanned,
        "reports_checked": reports_checked,
        "reports_ignored_non_report": reports_ignored_non_report,
        "findings_total": len(findings),
        "missing_status": 0,
        "missing_lifecycle": 0,
        "missing_owner_task": 0,
        "missing_review_after": 0,
        "missing_superseded_by": 0,
    }
    for f in findings:
        if f.code in summary:
            summary[f.code] += 1
    return summary


def _render_report(findings: list[Finding], summary: dict[str, int], mode: str) -> str:
    lines = [
        "# Report Lifecycle Validation",
        "",
        f"Mode: {mode}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| files_scanned | {summary['files_scanned']} |",
        f"| reports_checked | {summary['reports_checked']} |",
        f"| reports_ignored_non_report | {summary['reports_ignored_non_report']} |",
        f"| findings_total | {summary['findings_total']} |",
        f"| missing_status | {summary['missing_status']} |",
        f"| missing_lifecycle | {summary['missing_lifecycle']} |",
        f"| missing_owner_task | {summary['missing_owner_task']} |",
        f"| missing_review_after | {summary['missing_review_after']} |",
        f"| missing_superseded_by | {summary['missing_superseded_by']} |",
        "",
        "## Findings",
        "",
    ]
    if findings:
        lines.append("| Path | Severity | Code | Field | Message |")
        lines.append("| --- | --- | --- | --- | --- |")
        for f in findings:
            field_str = f.field if f.field else ""
            lines.append(f"| {f.path} | {f.severity} | {f.code} | {field_str} | {f.message} |")
    else:
        lines.append("No findings.")
    return "\n".join(lines) + "\n"


def run(root: Path, mode: str) -> tuple[str, int]:
    paths = _iter_report_paths(root)
    all_findings = []
    reports_checked = 0
    reports_ignored_non_report = 0

    for p in paths:
        fm = _load_frontmatter(p)
        doc_type = _string_value(fm.get("doc_type")).strip().lower()
        if doc_type == "report":
            reports_checked += 1
        else:
            reports_ignored_non_report += 1
        findings = _validate_report(p, fm, root)
        all_findings.extend(findings)

    all_findings.sort(key=lambda f: (f.path, f.code))

    summary = _build_summary(
        all_findings,
        files_scanned=len(paths),
        reports_checked=reports_checked,
        reports_ignored_non_report=reports_ignored_non_report,
    )
    report_str = _render_report(all_findings, summary, mode)
    return report_str, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate report lifecycle metadata.")
    parser.add_argument(
        "--mode",
        choices=["report"],
        default="report",
        help="Validation mode"
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Alternative repository root path"
    )
    args = parser.parse_args(argv)

    root_path = Path(args.root) if args.root else REPO_ROOT

    try:
        report_str, exit_code = run(root_path, args.mode)
        sys.stdout.write(report_str)
        return exit_code
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
