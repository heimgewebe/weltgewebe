#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import tempfile
import textwrap
import unittest

import scripts.docmeta.generate_report_lifecycle_inventory as presence_inventory
import scripts.docmeta.generate_report_lifecycle_validator_requirements as requirements
from scripts.docmeta.validate_report_lifecycle import (
    _load_frontmatter,
    _validate_report,
)


class TestGenerateReportLifecycleValidatorRequirements(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for rel in (
            "docs/reports",
            "docs/tasks",
            "docs/blueprints",
            "docs/proofs",
            "docs/adr",
            "docs/specs",
            "docs/_generated",
        ):
            (self.root / rel).mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, name: str, frontmatter: str) -> Path:
        path = self.root / "docs" / "reports" / name
        path.write_text(
            f"---\n{textwrap.dedent(frontmatter).strip()}\n---\n",
            encoding="utf-8",
        )
        return path

    def _config(self) -> presence_inventory.InventoryConfig:
        return presence_inventory.InventoryConfig(
            repo_root=self.root,
            reports_dir=self.root / "docs" / "reports",
            output_path=(
                self.root / "docs" / "_generated" / "report-lifecycle-inventory.md"
            ),
            primary_search_paths=(self.root / "docs",),
            derived_search_paths=(self.root / "docs" / "_generated",),
        )

    def test_presence_and_validator_views_are_distinct(self) -> None:
        self._write(
            "archived.md",
            """
            doc_type: report
            status: deprecated
            lifecycle_state: archived
            lifecycle: audit
            owner_task: TASK-1
            """,
        )
        presence = presence_inventory.collect_reports(self._config())[0]
        required = requirements.collect_requirement_records(self._config())[0]
        self.assertIn("review_after", presence.absent_core_lifecycle_fields)
        self.assertEqual(required.missing_fields, ())

    def test_summary_and_rendering(self) -> None:
        self._write("active.md", "doc_type: report\nstatus: active")
        self._write(
            "archived.md",
            """
            doc_type: report
            status: deprecated
            lifecycle_state: archived
            lifecycle: audit
            owner_task: TASK-1
            """,
        )
        records = requirements.collect_requirement_records(self._config())
        summary = dict(requirements.build_summary(records))
        markdown = requirements.render(records)
        self.assertEqual(
            summary["reports_with_validator_required_missing_fields"], 1
        )
        self.assertEqual(
            summary["reports_without_validator_required_missing_fields"], 1
        )
        self.assertEqual(
            summary["validator_required_missing_fields_total"], 3
        )
        self.assertIn("# Report Lifecycle Validator Requirements", markdown)
        self.assertIn("## Reports With Missing Required Fields", markdown)
        self.assertNotIn(
            "| docs/reports/archived.md | review_after |",
            markdown.split("## Reports With Missing Required Fields", 1)[1],
        )

    def test_real_parser_paths_match(self) -> None:
        fixtures = {
            "active.md": "doc_type: report\nstatus: active\nlifecycle_state: active",
            "draft.md": "doc_type: report\nstatus: draft",
            "deferred.md": "doc_type: report\nstatus: deprecated\nlifecycle_state: deferred",
            "superseded.md": "doc_type: report\nstatus: deprecated\nlifecycle_state: superseded",
            "archived.md": "doc_type: report\nstatus: deprecated\nlifecycle_state: archived",
            "unknown.md": "doc_type: report\nstatus: deprecated\nlifecycle_state: unknown",
            "reference.md": "doc_type: reference\nstatus: active",
            "inline-lists.md": (
                "doc_type: report\nstatus: active\nlifecycle_state: active\n"
                "lifecycle: [audit]\nowner_task: TASK-1\n"
                "review_after: [2026-12-01]"
            ),
        }
        for name, frontmatter in fixtures.items():
            self._write(name, frontmatter)

        records = {
            record.path: record
            for record in requirements.collect_requirement_records(
                self._config()
            )
        }
        for name in fixtures:
            with self.subTest(name=name):
                path = self.root / "docs" / "reports" / name
                findings = _validate_report(
                    path, _load_frontmatter(path), self.root
                )
                expected = tuple(
                    finding.field
                    for finding in findings
                    if finding.code.startswith("missing_")
                    and finding.field is not None
                )
                record = records.get(f"docs/reports/{name}")
                actual = record.missing_fields if record is not None else ()
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
