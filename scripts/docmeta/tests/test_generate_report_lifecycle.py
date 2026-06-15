#!/usr/bin/env python3
import tempfile
from pathlib import Path
import unittest

from scripts.docmeta.generate_report_lifecycle import generate

class TestGenerateReportLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.reports_dir = self.root / "docs" / "reports"
        self.reports_dir.mkdir(parents=True)
        self.output_path = self.root / "output.md"
        
        (self.root / "docs" / "_generated").mkdir(parents=True, exist_ok=True)
        
    def tearDown(self):
        self.temp_dir.cleanup()
        
    def _write_report(self, name: str, content: str):
        (self.reports_dir / name).write_text(content, encoding="utf-8")

    def test_generate_writes_output(self):
        self._write_report("empty.md", "")
        generate(self.root, self.output_path)
        
        self.assertTrue(self.output_path.exists())
        content = self.output_path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---"))
        self.assertIn("Generated automatically.", content)
        self.assertIn("# Report Lifecycle Overview", content)

    def test_summary_counts_reports_and_non_reports(self):
        self._write_report("report1.md", "---\ndoc_type: report\n---")
        self._write_report("ref.md", "---\ndoc_type: reference\n---")
        
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        
        self.assertIn("| files_scanned | 2 |", content)
        self.assertIn("| reports_checked | 1 |", content)
        self.assertIn("| reports_ignored_non_report | 1 |", content)

    def test_doc_type_is_case_insensitive_for_report_grouping(self):
        self._write_report(
            "mixed.md",
            "---\ndoc_type: Report\nstatus: active\nlifecycle_state: active\nlifecycle: audit\nowner_task: T1\nreview_after: 2026-01-01\n---"
        )
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("| reports_checked | 1 |", content)
        self.assertIn("docs/reports/mixed.md", content)

    def test_active_report_group(self):
        self._write_report("active1.md", "---\ndoc_type: report\nlifecycle_state: active\nstatus: active\nlifecycle: production\nowner_task: T123\nreview_after: 2026-01-01\n---")
        
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        
        self.assertIn("## Active Reports", content)
        self.assertRegex(content, r"\|\s*docs/reports/active1\.md\s*\|")

    def test_unclassified_report_group(self):
        self._write_report("unclass.md", "---\ndoc_type: report\nstatus: draft\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        
        self.assertIn("## Unclassified Reports", content)
        self.assertRegex(content, r"\|\s*docs/reports/unclass\.md\s*\|")
        
        self.assertIn("## Reports With Findings", content)
        self.assertIn("missing_lifecycle_state", content)

    def test_non_report_section(self):
        self._write_report("status.md", "---\ndoc_type: status-matrix\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        
        self.assertIn("## Non-Report Files Under docs/reports", content)
        self.assertRegex(content, r"\|\s*docs/reports/status\.md\s*\|\s*status-matrix\s*\|")

    def test_superseded_report_with_missing_superseded_by(self):
        self._write_report("super.md", "---\ndoc_type: report\nstatus: archived\nlifecycle_state: superseded\nlifecycle: eol\nowner_task: T123\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        
        self.assertIn("## Superseded Reports", content)
        self.assertIn("## Reports With Findings", content)
        self.assertIn("missing_superseded_by", content)

    def test_deferred_and_archived_groups(self):
        self._write_report("def.md", "---\ndoc_type: report\nstatus: draft\nlifecycle_state: deferred\nlifecycle: backlog\nowner_task: T1\nreview_after: 2026-01-01\n---")
        self._write_report("arch.md", "---\ndoc_type: report\nstatus: archived\nlifecycle_state: archived\nlifecycle: eol\nowner_task: T2\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        
        self.assertIn("## Deferred Reports", content)
        self.assertRegex(content, r"\|\s*docs/reports/def\.md\s*\|")
        
        self.assertIn("## Archived Reports", content)
        self.assertRegex(content, r"\|\s*docs/reports/arch\.md\s*\|")
        
        self.assertNotIn("missing_superseded_by", content)

    def test_markdown_cells_escape_pipes(self):
        self._write_report("pipes.md", "---\ndoc_type: report\nlifecycle_state: active\nstatus: active\nlifecycle: production\nowner_task: \"Team | Task\"\nreview_after: 2026-01-01\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        self.assertIn("Team &#124; Task", content)

    def test_output_is_deterministically_sorted(self):
        self._write_report("b.md", "---\ndoc_type: report\nlifecycle_state: active\n---")
        self._write_report("a.md", "---\ndoc_type: report\nlifecycle_state: active\n---")
        self._write_report("c.md", "---\ndoc_type: report\nlifecycle_state: active\n---")
        
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")
        
        pos_a = content.find("docs/reports/a.md")
        pos_b = content.find("docs/reports/b.md")
        pos_c = content.find("docs/reports/c.md")
        
        self.assertTrue(pos_a < pos_b < pos_c)

    def test_no_real_repo_mutation_when_output_is_temp(self):
        import time
        start_time = time.time()
        
        self._write_report("fake.md", "---\ndoc_type: report\n---")
        generate(self.root, self.output_path)
        
        real_output = Path(__file__).resolve().parents[3] / "docs" / "_generated" / "report-lifecycle.md"
        
        if real_output.exists():
            stat = real_output.stat()
            self.assertTrue(stat.st_mtime < start_time, "Real repo file was modified!")

if __name__ == "__main__":
    unittest.main()
