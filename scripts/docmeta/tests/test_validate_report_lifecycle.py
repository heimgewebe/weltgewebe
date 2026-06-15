#!/usr/bin/env python3
from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.docmeta.validate_report_lifecycle import main, run, _validate_report, Finding


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

    def test_render_output_is_stable(self) -> None:
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
        self.assertIn("| reports_checked |", rendered)
        self.assertIn("| findings_total |", rendered)
        self.assertIn("| Path | Severity | Code | Field | Message |", rendered)


if __name__ == "__main__":
    unittest.main()
