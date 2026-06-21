#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import parse_frontmatter
from scripts.docmeta.report_lifecycle_requirements import (
    missing_required_report_field_rules,
    string_value as _string_value,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
VALID_MODES = ("report", "warn", "strict")


@dataclass(frozen=True)
class Finding:
    path: str
    code: str
    severity: str
    message: str
    field: str | None = None


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

    return [
        Finding(
            path=rel_path,
            code=requirement.code,
            severity="warn",
            field=requirement.field,
            message=requirement.message,
        )
        for requirement in missing_required_report_field_rules(frontmatter)
    ]


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
        "missing_lifecycle_state": 0,
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
        f"| missing_lifecycle_state | {summary['missing_lifecycle_state']} |",
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


def _gha_escape_data(value: str) -> str:
    return (
        value
        .replace("%", "%25")
        .replace("\r", "%0D")
        .replace("\n", "%0A")
    )


def _gha_escape_property(value: str) -> str:
    return (
        _gha_escape_data(value)
        .replace(":", "%3A")
        .replace(",", "%2C")
    )


def _render_github_warnings(findings: list[Finding]) -> str:
    lines: list[str] = []
    for finding in findings:
        file_prop = _gha_escape_property(str(finding.path))
        title_prop = _gha_escape_property("Report lifecycle finding")
        message = _gha_escape_data(f"{finding.code}: {finding.message}")
        lines.append(f"::warning file={file_prop},title={title_prop}::{message}")
    return "\n".join(lines)


def run(root: Path, mode: str) -> tuple[str, int]:
    if mode not in VALID_MODES:
        raise ValueError(f"unsupported report lifecycle mode: {mode}")
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
    output = _render_report(all_findings, summary, mode)

    if mode == "warn":
        warnings = _render_github_warnings(all_findings)
        if warnings:
            output = output + "\n" + warnings + "\n"

    if mode == "strict" and summary["findings_total"] > 0:
        return output, 1

    return output, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate report lifecycle metadata.")
    parser.add_argument(
        "--mode",
        choices=VALID_MODES,
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
