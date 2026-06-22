#!/usr/bin/env python3
from __future__ import annotations

import datetime
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.docmeta.validate_report_lifecycle import (
    Finding,
    main,
    run,
    _validate_report,
    _gha_escape_data,
    _gha_escape_property,
    _render_github_warnings,
)


VALID_REPORT_FRONTMATTER = """
id: reports.example
title: Example
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: OPT-ARC-001
review_after: 2026-07-13
"""


def write_report(root: Path, name: str, frontmatter: str, body: str = "Body\n") -> Path:
    path = root / "docs" / "reports" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter.strip()}\n---\n\n{body}", encoding="utf-8")
    return path


class TestValidateReportLifecycle(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_main(self, args: list[str]) -> tuple[int, str, str]:
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture), patch("sys.stderr", stderr_capture):
            exit_code = main(args)
        return exit_code, stdout_capture.getvalue(), stderr_capture.getvalue()

    def test_report_mode_exits_zero_even_with_findings(self) -> None:
        # Fixture
        write_report(
            self.tmp_root,
            "example.md",
            """
id: reports.example
title: Example
doc_type: report
status: active
            """
        )

        exit_code, stdout, stderr = self.run_main(["--mode", "report", "--root", str(self.tmp_root)])
        self.assertEqual(exit_code, 0)
        self.assertIn("missing_lifecycle", stdout)
        self.assertIn("missing_review_after", stdout)
        self.assertEqual(stderr, "")

    def test_warn_mode_exits_zero_and_emits_github_warnings(self) -> None:
        # Fixture with at least one lifecycle finding (missing lifecycle_state)
        write_report(
            self.tmp_root,
            "example.md",
            """
id: reports.example
title: Example
doc_type: report
status: active
            """
        )

        exit_code, stdout, stderr = self.run_main(["--mode", "warn", "--root", str(self.tmp_root)])
        self.assertEqual(exit_code, 0)
        self.assertIn("::warning", stdout)
        self.assertIn("docs/reports/example.md", stdout)
        self.assertIn("missing_lifecycle_state", stdout)
        # Markdown report (summary) is still emitted alongside the annotations.
        self.assertIn("## Summary", stdout)
        self.assertEqual(stderr, "")

    def test_warn_mode_exits_zero_without_findings(self) -> None:
        # Fixture: minimal valid report (no findings).
        write_report(self.tmp_root, "example.md", VALID_REPORT_FRONTMATTER)

        exit_code, stdout, stderr = self.run_main(["--mode", "warn", "--root", str(self.tmp_root)])
        self.assertEqual(exit_code, 0)
        self.assertNotIn("::warning", stdout)
        self.assertIn("| findings_total | 0 |", stdout)
        self.assertIn("No findings.", stdout)
        self.assertEqual(stderr, "")

    def test_strict_mode_exits_one_with_findings(self) -> None:
        # Fixture with at least one lifecycle finding.
        write_report(
            self.tmp_root,
            "example.md",
            """
id: reports.example
title: Example
doc_type: report
status: active
            """
        )

        exit_code, stdout, stderr = self.run_main(["--mode", "strict", "--root", str(self.tmp_root)])
        self.assertEqual(exit_code, 1)
        self.assertIn("## Summary", stdout)
        self.assertIn("missing_lifecycle_state", stdout)
        self.assertEqual(stderr, "")

    def test_strict_mode_exits_zero_without_findings(self) -> None:
        # Fixture: minimal valid report (no findings).
        write_report(self.tmp_root, "example.md", VALID_REPORT_FRONTMATTER)

        exit_code, stdout, stderr = self.run_main(["--mode", "strict", "--root", str(self.tmp_root)])
        self.assertEqual(exit_code, 0)
        self.assertIn("| findings_total | 0 |", stdout)
        self.assertIn("No findings.", stdout)
        self.assertEqual(stderr, "")

    def test_run_rejects_invalid_mode(self) -> None:
        # run(root, mode) should reject unsupported modes directly.
        with self.assertRaises(ValueError) as ctx:
            run(self.tmp_root, "nonsense")
        self.assertIn("unsupported report lifecycle mode", str(ctx.exception))

    def test_github_warning_annotation_escapes_special_characters(self) -> None:
        # Data escaping: percent first, then CR/LF.
        self.assertEqual(_gha_escape_data("100%"), "100%25")
        self.assertEqual(_gha_escape_data("line1\nline2"), "line1%0Aline2")
        self.assertEqual(_gha_escape_data("a\rb"), "a%0Db")
        # Property escaping additionally handles ":" and ",".
        self.assertEqual(_gha_escape_property("a:b"), "a%3Ab")
        self.assertEqual(_gha_escape_property("a,b"), "a%2Cb")
        # Percent is escaped first, so no double-escaping of the "%0A"/"%3A" markers.
        self.assertEqual(_gha_escape_property("%\n:"), "%25%0A%3A")

        # End-to-end: the rendered annotation escapes path (property) and message (data).
        finding = Finding(
            path="docs/reports/weird,name.md",
            code="missing_lifecycle_state",
            severity="warn",
            field="lifecycle_state",
            message="needs 100% coverage: now",
        )
        rendered = _render_github_warnings([finding])
        self.assertIn("::warning ", rendered)
        self.assertIn("file=docs/reports/weird%2Cname.md", rendered)
        self.assertIn("title=Report lifecycle finding", rendered)
        # The message uses data escaping, so ":" stays but "%" becomes "%25".
        self.assertIn("missing_lifecycle_state: needs 100%25 coverage: now", rendered)

    def test_invalid_mode_is_rejected(self) -> None:
        # argparse `choices` rejects unknown modes with a non-zero SystemExit.
        with self.assertRaises(SystemExit) as ctx:
            self.run_main(["--mode", "nonsense", "--root", str(self.tmp_root)])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_active_report_missing_lifecycle_and_review_after(self) -> None:
        # Fixture
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "active"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_lifecycle", codes)
        self.assertIn("missing_review_after", codes)

    def test_lifecycle_state_active_missing_owner_task(self) -> None:
        # Fixture
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "active",
            "lifecycle_state": "active",
            "lifecycle": "audit",
            "review_after": "2026-07-13"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertEqual(codes, ["missing_owner_task"])

    def test_superseded_needs_superseded_by(self) -> None:
        # Fixture
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "deprecated",
            "lifecycle_state": "superseded"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_superseded_by", codes)

    def test_archived_does_not_need_superseded_by(self) -> None:
        # Fixture
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "deprecated",
            "lifecycle_state": "archived"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertNotIn("missing_superseded_by", codes)

    def test_deprecated_without_lifecycle_state_is_not_supersession(self) -> None:
        # Fixture
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "deprecated"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertNotIn("missing_superseded_by", codes)

    def test_case_insensitive_lifecycle_state(self) -> None:
        # Fixture
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "deprecated",
            "lifecycle_state": "Superseded"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_superseded_by", codes)

    def test_non_report_doc_type_in_docs_reports_does_not_trigger_required_lifecycle_findings(self) -> None:
        # Fixture
        fm = {
            "id": "reports.reference",
            "title": "Reference",
            "doc_type": "reference",
            "status": "active"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        self.assertEqual(findings, [])

    def test_pilot_shaped_report_passes_active_lifecycle_checks(self) -> None:
        # Fixture
        fm = {
            "id": "reports.domain-account-email-uniqueness-audit",
            "title": "Domain Account E-Mail Uniqueness Audit",
            "doc_type": "report",
            "status": "active",
            "lifecycle_state": "active",
            "lifecycle": "audit",
            "owner_task": "OPT-ARC-001",
            "review_after": "2026-07-13"
        }
        path = self.tmp_root / "docs" / "reports" / "domain-account-email-uniqueness-audit.md"
        findings = _validate_report(path, fm, self.tmp_root)
        self.assertEqual(findings, [])

    def test_render_output_contains_expected_structure(self) -> None:
        write_report(
            self.tmp_root,
            "example.md",
            """
id: reports.example
title: Example
doc_type: report
status: active
            """
        )

        rendered, exit_code = run(self.tmp_root, "report")
        self.assertEqual(exit_code, 0)
        self.assertIn("# Report Lifecycle Validation", rendered)
        self.assertIn("Mode: report", rendered)
        self.assertIn("| files_scanned |", rendered)
        self.assertIn("| reports_checked |", rendered)
        self.assertIn("| reports_ignored_non_report |", rendered)
        self.assertIn("| findings_total |", rendered)
        self.assertIn("| missing_lifecycle_state |", rendered)
        self.assertIn("| Path | Severity | Code | Field | Message |", rendered)

    def test_findings_are_deterministically_sorted_by_path_and_code(self) -> None:
        write_report(
            self.tmp_root,
            "b_example.md",
            """
id: reports.b
title: B
doc_type: report
status: active
lifecycle_state: active
            """
        )
        write_report(
            self.tmp_root,
            "a_example.md",
            """
id: reports.a
title: A
doc_type: report
status: active
lifecycle_state: active
            """
        )
        rendered, exit_code = run(self.tmp_root, "report")
        self.assertEqual(exit_code, 0)

        lines = [
            line
            for line in rendered.splitlines()
            if line.startswith("| docs/reports/")
        ]
        self.assertEqual(len(lines), 6)

        extracted = []
        for line in lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 5:
                extracted.append((parts[1], parts[3]))

        self.assertEqual(
            extracted,
            [
                ("docs/reports/a_example.md", "missing_lifecycle"),
                ("docs/reports/a_example.md", "missing_owner_task"),
                ("docs/reports/a_example.md", "missing_review_after"),
                ("docs/reports/b_example.md", "missing_lifecycle"),
                ("docs/reports/b_example.md", "missing_owner_task"),
                ("docs/reports/b_example.md", "missing_review_after"),
            ]
        )

        rendered_again, exit_code_again = run(self.tmp_root, "report")
        self.assertEqual(exit_code_again, exit_code)
        self.assertEqual(rendered_again, rendered)

    def test_validate_report_with_datetime_date_review_after(self) -> None:
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "active",
            "review_after": datetime.date(2026, 7, 13),
            "lifecycle": "audit"
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertNotIn("missing_review_after", codes)

    def test_run_with_unquoted_date_in_frontmatter(self) -> None:
        write_report(
            self.tmp_root,
            "example.md",
            """
id: reports.example
title: Example
doc_type: report
status: active
lifecycle: audit
review_after: 2026-07-13
            """
        )
        rendered, exit_code = run(self.tmp_root, "report")
        self.assertEqual(exit_code, 0)
        self.assertIn("| missing_review_after | 0 |", rendered)

    def test_run_scans_and_checks_precise_metrics(self) -> None:
        # Fixture 1: a report
        write_report(
            self.tmp_root,
            "example_report.md",
            """
id: reports.example_report
title: Example Report
doc_type: report
status: active
lifecycle: audit
review_after: 2026-07-13
            """
        )
        # Fixture 2: a reference (non-report)
        write_report(
            self.tmp_root,
            "example_ref.md",
            """
id: reports.example_ref
title: Example Reference
doc_type: reference
status: active
            """
        )

        rendered, exit_code = run(self.tmp_root, "report")
        self.assertEqual(exit_code, 0)
        self.assertIn("| files_scanned | 2 |", rendered)
        self.assertIn("| reports_checked | 1 |", rendered)
        self.assertIn("| reports_ignored_non_report | 1 |", rendered)

    def test_blank_frontmatter_values_are_missing(self) -> None:
        write_report(
            self.tmp_root,
            "example.md",
            """
id: reports.example
title: Example
doc_type: report
status: active
lifecycle:
review_after:
            """
        )
        rendered, exit_code = run(self.tmp_root, "report")
        self.assertEqual(exit_code, 0)
        self.assertIn("missing_lifecycle", rendered)
        self.assertIn("missing_review_after", rendered)

    def test_blank_owner_task_is_missing_for_lifecycle_state_active(self) -> None:
        write_report(
            self.tmp_root,
            "example.md",
            """
id: reports.example
title: Example
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task:
review_after: 2026-07-13
            """
        )
        rendered, exit_code = run(self.tmp_root, "report")
        self.assertEqual(exit_code, 0)
        self.assertIn("missing_owner_task", rendered)

    def test_report_without_lifecycle_state_yields_finding(self) -> None:
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "active",
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_lifecycle_state", codes)

    def test_deferred_lifecycle_state_missing_owner_task_and_review_after(self) -> None:
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "active",
            "lifecycle_state": "deferred",
            "lifecycle": "audit",
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_owner_task", codes)
        self.assertIn("missing_review_after", codes)

    def test_superseded_lifecycle_state_with_only_superseded_by(self) -> None:
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "deprecated",
            "lifecycle_state": "superseded",
            "superseded_by": "reports.new_one",
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_lifecycle", codes)
        self.assertIn("missing_owner_task", codes)
        self.assertNotIn("missing_superseded_by", codes)

    def test_archived_lifecycle_state_missing_owner_task(self) -> None:
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "deprecated",
            "lifecycle_state": "archived",
            "lifecycle": "audit",
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_owner_task", codes)
        self.assertNotIn("missing_superseded_by", codes)

    def test_deferred_lifecycle_state_missing_lifecycle(self) -> None:
        fm = {
            "id": "reports.example",
            "title": "Example",
            "doc_type": "report",
            "status": "active",
            "lifecycle_state": "deferred",
            "owner_task": "OPT-ARC-001",
            "review_after": "2026-07-13",
        }
        path = self.tmp_root / "docs" / "reports" / "example.md"
        findings = _validate_report(path, fm, self.tmp_root)
        codes = [f.code for f in findings]
        self.assertIn("missing_lifecycle", codes)


if __name__ == "__main__":
    unittest.main()
