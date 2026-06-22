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
    render_markdown,
)
from scripts.docmeta.generate_report_lifecycle_inventory import collect_reports, InventoryConfig
from scripts.docmeta.validate_report_lifecycle import _load_frontmatter


def _section(content: str, heading: str) -> str:
    marker = f"## {heading}"
    lines = content.splitlines()

    matches = [index for index, line in enumerate(lines) if line == marker]
    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one {marker!r} section, found {len(matches)}."
        )

    start = matches[0] + 1
    end = next(
        (
            index
            for index in range(start, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return "\n".join(lines[start:end])


def _table_cells(row: str) -> list[str]:
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def _row_for_path(section: str, path: str) -> str:
    matches = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = _table_cells(line)
        if cells and cells[0] == path:
            matches.append(line)

    if len(matches) != 1:
        raise AssertionError(
            f"Expected exactly one row for {path!r}, found {len(matches)}."
        )
    return matches[0]


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

        section = _section(content, "Active Reports")
        _row_for_path(section, "docs/reports/mixed.md")

    def test_active_report_group(self):
        self._write_report("active1.md", "---\ndoc_type: report\nlifecycle_state: active\nstatus: active\nlifecycle: production\nowner_task: T123\nreview_after: 2026-01-01\n---")

        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Active Reports")
        row = _row_for_path(section, "docs/reports/active1.md")
        cells = _table_cells(row)
        self.assertEqual(cells[0], "docs/reports/active1.md")
        self.assertEqual(cells[1], "active") # status

        with self.assertRaises(AssertionError):
            _row_for_path(_section(content, "Unclassified Reports"), "docs/reports/active1.md")

    def test_unclassified_report_group(self):
        self._write_report("unclass.md", "---\ndoc_type: report\nstatus: draft\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Unclassified Reports")
        _row_for_path(section, "docs/reports/unclass.md")

        findings_section = _section(content, "Reports With Findings")
        row = _row_for_path(findings_section, "docs/reports/unclass.md")
        cells = _table_cells(row)
        self.assertIn("missing_lifecycle_state", cells[3])

    def test_non_report_section(self):
        self._write_report("status.md", "---\ndoc_type: status-matrix\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Non-Report Files Under docs/reports")
        row = _row_for_path(section, "docs/reports/status.md")
        cells = _table_cells(row)
        self.assertEqual(cells[1], "status-matrix")

        unclassified = _section(content, "Unclassified Reports")
        self.assertIn("| _None_ |", unclassified)

    def test_superseded_report_with_missing_superseded_by(self):
        self._write_report("super.md", "---\ndoc_type: report\nstatus: archived\nlifecycle_state: superseded\nlifecycle: eol\nowner_task: T123\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Superseded Reports")
        _row_for_path(section, "docs/reports/super.md")

        findings_section = _section(content, "Reports With Findings")
        row = _row_for_path(findings_section, "docs/reports/super.md")
        cells = _table_cells(row)
        self.assertIn("missing_superseded_by", cells[3])

    def test_deferred_and_archived_groups(self):
        self._write_report("def.md", "---\ndoc_type: report\nstatus: draft\nlifecycle_state: deferred\nlifecycle: backlog\nowner_task: T1\nreview_after: 2026-01-01\n---")
        self._write_report("arch.md", "---\ndoc_type: report\nstatus: archived\nlifecycle_state: archived\nlifecycle: eol\nowner_task: T2\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        deferred_section = _section(content, "Deferred Reports")
        _row_for_path(deferred_section, "docs/reports/def.md")

        archived_section = _section(content, "Archived Reports")
        arch_row = _row_for_path(archived_section, "docs/reports/arch.md")
        cells = _table_cells(arch_row)
        self.assertEqual(cells[1], "archived")

        with self.assertRaises(AssertionError):
            _row_for_path(_section(content, "Superseded Reports"), "docs/reports/arch.md")

    def test_markdown_cells_escape_pipes(self):
        self._write_report("pipes.md", "---\ndoc_type: report\nlifecycle_state: active\nstatus: active\nlifecycle: production\nowner_task: \"Team | Task\"\nreview_after: 2026-01-01\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Active Reports")
        row = _row_for_path(section, "docs/reports/pipes.md")
        cells = _table_cells(row)
        self.assertEqual(cells[3], "Team &#124; Task")

    def test_output_is_deterministically_sorted(self):
        self._write_report("b.md", "---\ndoc_type: report\nlifecycle_state: active\n---")
        self._write_report("a.md", "---\ndoc_type: report\nlifecycle_state: active\n---")
        self._write_report("c.md", "---\ndoc_type: report\nlifecycle_state: active\n---")

        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Active Reports")

        paths = []
        for line in section.splitlines():
            if line.startswith("| docs/reports/"):
                paths.append(_table_cells(line)[0])

        self.assertEqual(
            paths,
            [
                "docs/reports/a.md",
                "docs/reports/b.md",
                "docs/reports/c.md",
            ],
        )

    def test_missing_currently_enforced_fields_section(self):
        self._write_report("unclass.md", "---\ndoc_type: report\nstatus: active\n---")
        self._write_report("reference.md", "---\ndoc_type: reference\nstatus: active\n---")
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Reports With Missing Currently-Enforced Fields")

        row = _row_for_path(section, "docs/reports/unclass.md")
        cells = _table_cells(row)
        self.assertIn("lifecycle_state, lifecycle, review_after", cells[3])

        self.assertIn("field presence only", section)
        self.assertNotIn("Complete Reports", section)

        with self.assertRaises(AssertionError):
            _row_for_path(section, "docs/reports/reference.md")

    def test_classified_report_absent_from_missing_fields_section(self):
        self._write_report(
            "arch.md",
            "---\ndoc_type: report\nstatus: deprecated\nlifecycle_state: archived\n"
            "lifecycle: audit\nowner_task: T1\n---",
        )
        generate(self.root, self.output_path)
        content = self.output_path.read_text(encoding="utf-8")

        section = _section(content, "Reports With Missing Currently-Enforced Fields")
        self.assertIn("| _None_ |", section)
        with self.assertRaises(AssertionError):
            _row_for_path(section, "docs/reports/arch.md")

    def test_no_real_repo_mutation_when_output_is_temp(self):
        default_output = self.root / "docs" / "_generated" / "report-lifecycle.md"
        default_output.parent.mkdir(parents=True, exist_ok=True)

        original_content = "sentinel"
        default_output.write_text(original_content, encoding="utf-8")

        self._write_report("fake.md", "---\ndoc_type: report\n---")
        generate(self.root, self.output_path)

        self.assertTrue(self.output_path.exists())
        self.assertEqual(default_output.read_text(encoding="utf-8"), original_content)

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

        self.assertEqual(row.path, "docs/reports/real.md")
        self.assertEqual(row.title, "Record Title")
        self.assertEqual(row.primary_refs, 1)
        self.assertEqual(row.derived_refs, 2)

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
                "name": "doc_type_list",
                "field": "doc_type",
                "inline_value": "[report]",
                "extra_fields": (
                    "status: deprecated\n"
                    "lifecycle_state: archived\n"
                    "lifecycle: audit\n"
                    "owner_task: TASK-1\n"
                ),
                "expect_row_field": "doc_type",
                "expect_row_value": "",
                "expect_finding": None,
                "expect_group": "non_report",
            },
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
                "name": "lifecycle_list",
                "field": "lifecycle",
                "inline_value": "[audit]",
                "extra_fields": (
                    "doc_type: report\n"
                    "status: active\n"
                    "lifecycle_state: active\n"
                    "owner_task: TASK-1\n"
                    "review_after: 2026-07-01\n"
                ),
                "expect_row_field": "lifecycle",
                "expect_row_value": "",
                "expect_finding": "missing_lifecycle",
                "expect_group": "active",
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
            {
                "name": "review_after_list",
                "field": "review_after",
                "inline_value": "[2026-07-01]",
                "extra_fields": (
                    "doc_type: report\n"
                    "status: active\n"
                    "lifecycle_state: active\n"
                    "lifecycle: audit\n"
                    "owner_task: TASK-1\n"
                ),
                "expect_row_field": "review_after",
                "expect_row_value": "",
                "expect_finding": "missing_review_after",
                "expect_group": "active",
            },
            {
                "name": "superseded_by_list",
                "field": "superseded_by",
                "inline_value": "[docs/reports/replacement.md]",
                "extra_fields": (
                    "doc_type: report\n"
                    "status: deprecated\n"
                    "lifecycle_state: superseded\n"
                    "lifecycle: audit\n"
                    "owner_task: TASK-1\n"
                ),
                "expect_row_field": "superseded_by",
                "expect_row_value": "",
                "expect_finding": "missing_superseded_by",
                "expect_group": "superseded",
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

                actual_value = getattr(row, case["expect_row_field"])
                self.assertEqual(
                    actual_value,
                    case["expect_row_value"],
                    msg=(
                        f"{case['name']}: {case['expect_row_field']} expected "
                        f"{case['expect_row_value']!r}, got {actual_value!r}"
                    ),
                )

                if case["expect_finding"] is None:
                    self.assertEqual(
                        list(row.findings),
                        [],
                        msg=f"{case['name']}: non-report must not receive report findings",
                    )
                else:
                    self.assertEqual(list(row.findings), [case["expect_finding"]])

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

                if case["field"] == "doc_type":
                    summary = build_summary([row])
                    self.assertEqual(summary["reports_checked"], 0)
                    self.assertEqual(summary["reports_ignored_non_report"], 1)
                elif case["field"] == "lifecycle_state":
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

        section = _section(content, "Archived Reports")
        row = _row_for_path(section, "docs/reports/status_list.md")
        cells = _table_cells(row)
        self.assertEqual(cells[1], "") # status cell

        findings_section = _section(content, "Reports With Findings")
        findings_row = _row_for_path(findings_section, "docs/reports/status_list.md")
        f_cells = _table_cells(findings_row)
        self.assertIn("missing_status", f_cells[3]) # findings cell

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

        unclassified_section = _section(content, "Unclassified Reports")
        row = _row_for_path(unclassified_section, "docs/reports/ls_list.md")
        cells = _table_cells(row)
        self.assertEqual(cells[1], "deprecated") # status cell

        archived_section = _section(content, "Archived Reports")
        self.assertIn("| _None_ |", archived_section)

        findings_section = _section(content, "Reports With Findings")
        f_row = _row_for_path(findings_section, "docs/reports/ls_list.md")
        f_cells = _table_cells(f_row)
        self.assertEqual(f_cells[1], "")
        self.assertEqual(f_cells[2], "deprecated")
        self.assertIn("missing_lifecycle_state", f_cells[3]) # findings cell

        self.assertIn("| reports_missing_lifecycle_state | 1 |", content)
        self.assertIn("| reports_with_lifecycle_state | 0 |", content)

    def test_other_lifecycle_state_groups_to_other_and_renders_in_summary(self):
        self._write_report("exp.md", "---\ndoc_type: report\nstatus: active\nlifecycle_state: experimental\nlifecycle: audit\nowner_task: T1\nreview_after: 2026-01-01\n---")

        config = self._make_config()
        records = collect_reports(config)
        rows = collect_lifecycle_rows(self.root, records)
        groups = group_rows(rows)

        self.assertIn("other", groups)
        self.assertEqual(len(groups["other"]), 1)
        self.assertEqual(groups["other"][0].path, "docs/reports/exp.md")

        summary = build_summary(rows)
        content = render_markdown(rows, summary)

        self.assertIn("| other | 1 |", content)


if __name__ == "__main__":
    unittest.main()
