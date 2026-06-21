#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.docmeta.generate_report_lifecycle import generate


class TestGenerateReportLifecycleRequirementsSection(unittest.TestCase):
    def test_section_is_precise_and_excludes_non_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reports_dir = root / "docs" / "reports"
            reports_dir.mkdir(parents=True)
            output = root / "output.md"

            (reports_dir / "unclass.md").write_text(
                "---\ndoc_type: report\nstatus: active\n---",
                encoding="utf-8",
            )
            (reports_dir / "reference.md").write_text(
                "---\ndoc_type: reference\nstatus: active\n---",
                encoding="utf-8",
            )

            generate(root, output)
            content = output.read_text(encoding="utf-8")
            section = content.split(
                "## Reports With Missing Currently-Enforced Fields",
                1,
            )[1].split("\n## ", 1)[0]

            self.assertIn(
                "| docs/reports/unclass.md | active |  | "
                "lifecycle_state, lifecycle, review_after |",
                section,
            )
            self.assertIn("field presence only", section)
            self.assertNotIn("Complete Reports", section)
            self.assertNotIn("docs/reports/reference.md", section)


if __name__ == "__main__":
    unittest.main()
