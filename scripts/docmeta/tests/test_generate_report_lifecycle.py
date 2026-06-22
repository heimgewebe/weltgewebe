#!/usr/bin/env python3
import tempfile
from dataclasses import replace
from pathlib import Path
import unittest

from scripts.docmeta.generate_report_lifecycle import (
    generate,
    collect_lifecycle_rows,
    group_rows,
    build_summary,
)
from scripts.docmeta.generate_report_lifecycle_inventory import collect_reports, InventoryConfig
from scripts.docmeta.validate_report_lifecycle import _load_frontmatter

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

    def test_missing_currently_enforced_fields_section(self):
        self._write_report("unclass.md", "---\ndoc_type: report\nstatus: active\n---")
        self._write_report("reference.md", "---\ndoc_type: reference\nstatus: active\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        self.assertIn("## Reports With Missing Currently-Enforced Fields", content)
        section = content.split(
            "## Reports With Missing Currently-Enforced Fields", 1
        )[1].split("\n## ", 1)[0]
        # Exact row: field names in rule-precedence order (not finding codes).
        self.assertIn(
            "| docs/reports/unclass.md | active |  | "
            "lifecycle_state, lifecycle, review_after |",
            section,
        )
        # Presence-only caveat present; no completeness overclaim.
        self.assertIn("field presence only", section)
        self.assertNotIn("Complete Reports", section)
        # Non-reports never appear in the section.
        self.assertNotIn("docs/reports/reference.md", section)

    def test_classified_report_absent_from_missing_fields_section(self):
        self._write_report(
            "arch.md",
            "---\ndoc_type: report\nstatus: deprecated\nlifecycle_state: archived\n"
            "lifecycle: audit\nowner_task: T1\n---",
        )
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = content.split("## Reports With Missing Currently-Enforced Fields", 1)[1]
        section = section.split("\n## ", 1)[0]
        self.assertIn("| _None_ |", section)
        self.assertNotIn("docs/reports/arch.md", section)

    def test_no_real_repo_mutation_when_output_is_temp(self):
        import time
        start_time = time.time()

        self._write_report("fake.md", "---\ndoc_type: report\n---")
        generate(self.root, self.output_path)

        real_output = Path(__file__).resolve().parents[3] / "docs" / "_generated" / "report-lifecycle.md"

        if real_output.exists():
            stat = real_output.stat()
            self.assertTrue(stat.st_mtime < start_time, "Real repo file was modified!")

    def _make_config(self) -> InventoryConfig:
        return InventoryConfig(
            repo_root=self.root,
            reports_dir=self.reports_dir,
            output_path=self.output_path,
            primary_search_paths=(self.root / "docs",),
            derived_search_paths=(self.root / "docs" / "_generated",),
        )

    def test_policy_fields_source_is_frontmatter(self):
        """Seven policy-visible fields use parsed frontmatter; title and refs use ReportRecord."""
        self._write_report(
            "real.md",
            "---\n"
            "title: File Title\n"
            "doc_type: report\n"
            "status: deprecated\n"
            "lifecycle_state: archived\n"
            "lifecycle: audit\n"
            "owner_task: TASK-REAL\n"
            "review_after: 2026-07-01\n"
            "superseded_by: docs/reports/replacement.md\n"
            "---\n"
            "# File Title\n",
        )
        config = self._make_config()
        record = collect_reports(config)[0]
        conflicting_record = replace(
            record,
            title="Record Title",
            doc_type="reference",
            status="[draft]",
            lifecycle_state="[superseded]",
            lifecycle="[fake]",
            owner_task="[TASK-FAKE]",
            review_after="[never]",
            superseded_by="[nowhere]",
            primary_referenced_by_paths=("docs/source-a.md",),
            derived_referenced_by_paths=(
                "docs/_generated/source-b.md",
                "docs/_generated/source-c.md",
            ),
        )

        row = collect_lifecycle_rows(self.root, [conflicting_record])[0]

        # title and refs remain Record-based
        self.assertEqual(row.title, "Record Title")
        self.assertEqual(row.primary_refs, 1)
        self.assertEqual(row.derived_refs, 2)

        # seven policy fields must come from file frontmatter
        self.assertEqual(row.doc_type, "report")
        self.assertEqual(row.status, "deprecated")
        self.assertEqual(row.lifecycle_state, "archived")
        self.assertEqual(row.lifecycle, "audit")
        self.assertEqual(row.owner_task, "TASK-REAL")
        self.assertEqual(row.review_after, "2026-07-01")
        self.assertEqual(row.superseded_by, "docs/reports/replacement.md")

    def test_inline_list_values_are_normalized(self):
        """Inline-list frontmatter values must normalize to empty string, not appear as-is."""
        CASES = [
            {
                "name": "status_empty_list",
                "field": "status",
                "inline_value": "[]",
                "extra_fields": (
                    "doc_type: report\n"
                    "lifecycle_state: archived\n"
                    "lifecycle: audit\n"
                    "owner_task: TASK-1\n"
                ),
                "expect_row_field": "status",
                "expect_row_value": "",
                "expect_finding": "missing_status",
                "expect_group": "archived",
            },
            {
                "name": "status_active_list",
                "field": "status",
                "inline_value": "[active]",
                "extra_fields": (
                    "doc_type: report\n"
                    "lifecycle_state: archived\n"
                    "lifecycle: audit\n"
                    "owner_task: TASK-1\n"
                ),
                "expect_row_field": "status",
                "expect_row_value": "",
                "expect_finding": "missing_status",
                "expect_group": "archived",
            },
            {
                "name": "lifecycle_state_empty_list",
                "field": "lifecycle_state",
                "inline_value": "[]",
                "extra_fields": (
                    "doc_type: report\n"
                    "status: deprecated\n"
                    "lifecycle: audit\n"
                    "owner_task: TASK-1\n"
                ),
                "expect_row_field": "lifecycle_state",
                "expect_row_value": "",
                "expect_finding": "missing_lifecycle_state",
                "expect_group": "unclassified",
            },
            {
                "name": "lifecycle_state_archived_list",
                "field": "lifecycle_state",
                "inline_value": "[archived]",
                "extra_fields": (
                    "doc_type: report\n"
                    "status: deprecated\n"
                    "lifecycle: audit\n"
                    "owner_task: TASK-1\n"
                ),
                "expect_row_field": "lifecycle_state",
                "expect_row_value": "",
                "expect_finding": "missing_lifecycle_state",
                "expect_group": "unclassified",
            },
            {
                "name": "owner_task_list",
                "field": "owner_task",
                "inline_value": "[TASK-1]",
                "extra_fields": (
                    "doc_type: report\n"
                    "status: deprecated\n"
                    "lifecycle_state: archived\n"
                    "lifecycle: audit\n"
                ),
                "expect_row_field": "owner_task",
                "expect_row_value": "",
                "expect_finding": "missing_owner_task",
                "expect_group": "archived",
            },
        ]

        for case in CASES:
            with self.subTest(name=case["name"]):
                fname = f"{case['name']}.md"
                content = (
                    "---\n"
                    + case["extra_fields"]
                    + f"{case['field']}: {case['inline_value']}\n"
                    + "---\n"
                )
                self._write_report(fname, content)
                path = self.reports_dir / fname

                # prove the validator parser returns a list for the inline value
                fm = _load_frontmatter(path)
                self.assertIsInstance(
                    fm.get(case["field"]),
                    list,
                    msg=f"{case['field']}: {case['inline_value']!r} must parse as list",
                )

                config = self._make_config()
                records = collect_reports(config)
                record = next(r for r in records if r.path.endswith(fname))
                row = collect_lifecycle_rows(self.root, [record])[0]

                # policy field must be normalized to empty string
                actual_value = getattr(row, case["expect_row_field"])
                self.assertEqual(
                    actual_value,
                    case["expect_row_value"],
                    msg=(
                        f"{case['name']}: {case['expect_row_field']} expected "
                        f"{case['expect_row_value']!r}, got {actual_value!r}"
                    ),
                )

                # expected finding must be present
                self.assertIn(
                    case["expect_finding"],
                    row.findings,
                    msg=f"{case['name']}: expected finding {case['expect_finding']!r}",
                )

                # grouping must match validator interpretation
                groups = group_rows([row])
                self.assertIn(
                    case["expect_group"],
                    groups,
                    msg=f"{case['name']}: expected group {case['expect_group']!r}",
                )
                self.assertTrue(
                    any(r.path == row.path for r in groups[case["expect_group"]]),
                    msg=f"{case['name']}: row not in group {case['expect_group']!r}",
                )

                # summary counts lifecycle_state empty as missing
                if case["field"] == "lifecycle_state":
                    summary = build_summary([row])
                    self.assertEqual(
                        summary["reports_missing_lifecycle_state"],
                        1,
                        msg=f"{case['name']}: inline list must count as missing lifecycle_state",
                    )
                    self.assertEqual(
                        summary["reports_with_lifecycle_state"],
                        0,
                        msg=f"{case['name']}: inline list must not count as present lifecycle_state",
                    )

                # clean up report for next subTest
                path.unlink()

    def test_rendering_with_status_inline_list(self):
        """Rendered markdown must not show [active] as a policy value; finding must appear."""
        self._write_report(
            "status_list.md",
            "---\n"
            "doc_type: report\n"
            "status: [active]\n"
            "lifecycle_state: archived\n"
            "lifecycle: audit\n"
            "owner_task: TASK-1\n"
            "---\n",
        )
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        # inline list string must not appear as a policy value in any table cell
        self.assertNotIn("[active]", content)

        # finding must be reported because the value normalizes to empty
        self.assertIn("missing_status", content)

    def test_rendering_with_lifecycle_state_inline_list(self):
        """[archived] lifecycle_state must not appear, row goes to unclassified, not archived."""
        self._write_report(
            "ls_list.md",
            "---\n"
            "doc_type: report\n"
            "status: deprecated\n"
            "lifecycle_state: [archived]\n"
            "lifecycle: audit\n"
            "owner_task: TASK-1\n"
            "---\n",
        )
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        # inline list string must not appear as a policy value
        self.assertNotIn("[archived]", content)

        # finding must be reported
        self.assertIn("missing_lifecycle_state", content)

        # row must be in Unclassified, not Archived
        unclassified_section = content.split("## Unclassified Reports", 1)
        self.assertEqual(len(unclassified_section), 2, "Unclassified Reports section missing")
        self.assertIn("docs/reports/ls_list.md", unclassified_section[1].split("## ")[0])

        archived_section = content.split("## Archived Reports", 1)
        self.assertEqual(len(archived_section), 2, "Archived Reports section missing")
        self.assertNotIn("docs/reports/ls_list.md", archived_section[1].split("## ")[0])

        # summary: lifecycle_state counts as missing
        self.assertIn("| reports_missing_lifecycle_state | 1 |", content)
        self.assertIn("| reports_with_lifecycle_state | 0 |", content)

if __name__ == "__main__":
    unittest.main()
