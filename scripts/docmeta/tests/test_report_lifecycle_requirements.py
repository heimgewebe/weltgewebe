#!/usr/bin/env python3
from __future__ import annotations

import datetime
from pathlib import Path
import tempfile
import textwrap
import unittest

import scripts.docmeta.generate_report_lifecycle_inventory_validated as inventory
from scripts.docmeta.validate_report_lifecycle import (
    _load_frontmatter,
    _validate_report,
)

from scripts.docmeta.report_lifecycle_requirements import (
    missing_required_report_field_rules,
    missing_required_report_fields,
    required_report_field_rules,
    string_value,
)


class TestReportLifecycleRequirements(unittest.TestCase):
    def test_non_report_has_no_requirements(self) -> None:
        frontmatter = {"doc_type": "reference", "status": "active"}
        self.assertEqual(required_report_field_rules(frontmatter), ())
        self.assertEqual(missing_required_report_fields(frontmatter), ())

    def test_report_without_status_or_state(self) -> None:
        self.assertEqual(
            missing_required_report_fields({"doc_type": "report"}),
            ("lifecycle_state", "status"),
        )

    def test_active_report_without_state(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {"doc_type": "report", "status": "active"}
            ),
            ("lifecycle_state", "lifecycle", "review_after"),
        )

    def test_draft_without_state(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {"doc_type": "report", "status": "draft"}
            ),
            ("lifecycle_state", "review_after"),
        )

    def test_known_state_requirements(self) -> None:
        cases = {
            "active": ("lifecycle", "owner_task", "review_after"),
            "deferred": ("lifecycle", "owner_task", "review_after"),
            "superseded": ("lifecycle", "owner_task", "superseded_by"),
            "archived": ("lifecycle", "owner_task"),
        }
        for state, expected in cases.items():
            with self.subTest(state=state):
                self.assertEqual(
                    missing_required_report_fields(
                        {
                            "doc_type": "report",
                            "status": "deprecated",
                            "lifecycle_state": state,
                        }
                    ),
                    expected,
                )

    def test_archived_report_does_not_require_review_after(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {
                    "doc_type": "report",
                    "status": "deprecated",
                    "lifecycle_state": "archived",
                    "lifecycle": "audit",
                    "owner_task": "TASK-1",
                }
            ),
            (),
        )

    def test_unknown_state_adds_no_state_requirements(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {
                    "doc_type": "report",
                    "status": "deprecated",
                    "lifecycle_state": "unknown",
                }
            ),
            (),
        )

    def test_deduplication_preserves_first_message(self) -> None:
        rules = missing_required_report_field_rules(
            {
                "doc_type": "report",
                "status": "active",
                "lifecycle_state": "deferred",
            }
        )
        self.assertEqual(
            tuple((rule.code, rule.field, rule.message) for rule in rules),
            (
                (
                    "missing_lifecycle",
                    "lifecycle",
                    "active reports should define lifecycle",
                ),
                (
                    "missing_review_after",
                    "review_after",
                    "active/draft reports should define review_after",
                ),
                (
                    "missing_owner_task",
                    "owner_task",
                    "deferred reports should define owner_task",
                ),
            ),
        )

    def test_normalization_is_case_insensitive(self) -> None:
        frontmatter = {
            "doc_type": " Report ",
            "status": " Deprecated ",
            "lifecycle_state": " ARCHIVED ",
            "lifecycle": "audit",
            "owner_task": "TASK-1",
        }
        self.assertEqual(missing_required_report_fields(frontmatter), ())

    def test_string_value_matches_validator_behavior(self) -> None:
        self.assertEqual(string_value(None), "")
        self.assertEqual(string_value("  value  "), "value")
        self.assertEqual(string_value([]), "")
        self.assertEqual(string_value(()), "")
        self.assertEqual(string_value(set()), "")
        self.assertEqual(string_value({}), "")
        self.assertEqual(string_value(7), "7")
        self.assertEqual(string_value(datetime.date(2026, 7, 13)), "2026-07-13")


class TestLifecycleValidatorAndInventoryIntegration(unittest.TestCase):
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

    def _config(self) -> inventory.InventoryConfig:
        return inventory.InventoryConfig(
            repo_root=self.root,
            reports_dir=self.root / "docs" / "reports",
            output_path=(
                self.root / "docs" / "_generated" / "report-lifecycle-inventory.md"
            ),
            primary_search_paths=(self.root / "docs",),
            derived_search_paths=(self.root / "docs" / "_generated",),
        )

    def test_validator_regressions_for_archived_draft_and_overlap(self) -> None:
        path = self.root / "docs" / "reports" / "example.md"
        archived = _validate_report(
            path,
            {
                "doc_type": "report",
                "status": "deprecated",
                "lifecycle_state": "archived",
                "lifecycle": "audit",
                "owner_task": "TASK-1",
            },
            self.root,
        )
        self.assertEqual(archived, [])

        archived_missing = _validate_report(
            path,
            {
                "doc_type": "report",
                "status": "deprecated",
                "lifecycle_state": "archived",
            },
            self.root,
        )
        self.assertEqual(
            [(finding.code, finding.field) for finding in archived_missing],
            [
                ("missing_lifecycle", "lifecycle"),
                ("missing_owner_task", "owner_task"),
            ],
        )

        draft = _validate_report(
            path,
            {
                "doc_type": "report",
                "status": "draft",
                "lifecycle_state": "unknown",
            },
            self.root,
        )
        self.assertEqual(
            [(finding.code, finding.field) for finding in draft],
            [("missing_review_after", "review_after")],
        )

        overlap = _validate_report(
            path,
            {
                "doc_type": "report",
                "status": "active",
                "lifecycle_state": "deferred",
            },
            self.root,
        )
        self.assertEqual(
            [(finding.code, finding.field, finding.message) for finding in overlap],
            [
                (
                    "missing_lifecycle",
                    "lifecycle",
                    "active reports should define lifecycle",
                ),
                (
                    "missing_review_after",
                    "review_after",
                    "active/draft reports should define review_after",
                ),
                (
                    "missing_owner_task",
                    "owner_task",
                    "deferred reports should define owner_task",
                ),
            ],
        )

    def test_presence_and_validator_requirements_are_distinct(self) -> None:
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
        self._write(
            "active.md",
            """
            doc_type: report
            status: active
            lifecycle_state: active
            lifecycle: audit
            owner_task: TASK-1
            """,
        )
        self._write(
            "draft.md",
            """
            doc_type: report
            status: draft
            lifecycle_state: unknown
            """,
        )
        records = {
            record.path: record
            for record in inventory.collect_reports(self._config())
        }

        archived = records["docs/reports/archived.md"]
        self.assertIn("review_after", archived.absent_core_lifecycle_fields)
        self.assertEqual(archived.validator_required_missing_fields, ())

        active = records["docs/reports/active.md"]
        self.assertIn("review_after", active.absent_core_lifecycle_fields)
        self.assertIn("review_after", active.validator_required_missing_fields)

        draft = records["docs/reports/draft.md"]
        self.assertIn("review_after", draft.validator_required_missing_fields)

    def test_supersession_and_non_report_behavior_stays_distinct(self) -> None:
        self._write(
            "with-target.md",
            """
            doc_type: report
            status: deprecated
            lifecycle_state: superseded
            lifecycle: audit
            owner_task: TASK-1
            superseded_by: docs/reports/new.md
            """,
        )
        self._write(
            "without-target.md",
            """
            doc_type: report
            status: deprecated
            lifecycle_state: superseded
            lifecycle: audit
            owner_task: TASK-1
            """,
        )
        self._write(
            "reference.md",
            """
            doc_type: reference
            status: active
            """,
        )
        records = {
            record.path: record
            for record in inventory.collect_reports(self._config())
        }

        with_target = records["docs/reports/with-target.md"]
        self.assertIn("review_after", with_target.absent_core_lifecycle_fields)
        self.assertNotIn("review_after", with_target.validator_required_missing_fields)
        self.assertFalse(with_target.missing_supersession_target)

        without_target = records["docs/reports/without-target.md"]
        self.assertIn(
            "superseded_by",
            without_target.validator_required_missing_fields,
        )
        self.assertTrue(without_target.missing_supersession_target)

        reference = records["docs/reports/reference.md"]
        self.assertEqual(reference.validator_required_missing_fields, ())

    def test_validator_required_summary_and_rendering(self) -> None:
        self._write(
            "active.md",
            """
            doc_type: report
            status: active
            """,
        )
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
        records = inventory.collect_reports(self._config())
        summary = dict(inventory.build_summary(records))
        markdown = inventory.render_inventory(records)

        self.assertEqual(
            summary["reports_with_validator_required_missing_fields"],
            1,
        )
        self.assertEqual(
            summary["reports_without_validator_required_missing_fields"],
            1,
        )
        self.assertEqual(summary["validator_required_missing_fields_total"], 3)
        self.assertIn(
            "## Absent Tracked Lifecycle Fields — Presence Only",
            markdown,
        )
        self.assertIn("## Validator-Required Missing Fields", markdown)
        self.assertIn("validator-required missing fields", markdown)
        validator_section = markdown.split(
            "## Validator-Required Missing Fields",
            1,
        )[1]
        self.assertNotIn(
            "| docs/reports/archived.md | review_after |",
            validator_section,
        )

    def test_real_parser_paths_produce_matching_missing_fields(self) -> None:
        fixtures = {
            "active.md": """
                doc_type: report
                status: active
                lifecycle_state: active
            """,
            "draft.md": """
                doc_type: report
                status: draft
            """,
            "deferred.md": """
                doc_type: report
                status: deprecated
                lifecycle_state: deferred
            """,
            "superseded.md": """
                doc_type: report
                status: deprecated
                lifecycle_state: superseded
            """,
            "archived.md": """
                doc_type: report
                status: deprecated
                lifecycle_state: archived
            """,
            "missing-state.md": """
                doc_type: report
                status: active
            """,
            "unknown.md": """
                doc_type: report
                status: deprecated
                lifecycle_state: unknown
            """,
            "reference.md": """
                doc_type: reference
                status: active
            """,
            "inline-lists.md": """
                doc_type: report
                status: active
                lifecycle_state: active
                lifecycle: [audit]
                owner_task: TASK-1
                review_after: [2026-12-01]
            """,
        }
        for name, frontmatter in fixtures.items():
            self._write(name, frontmatter)

        records = {
            record.path: record
            for record in inventory.collect_reports(self._config())
        }
        for name in fixtures:
            with self.subTest(name=name):
                path = self.root / "docs" / "reports" / name
                findings = _validate_report(
                    path,
                    _load_frontmatter(path),
                    self.root,
                )
                expected = tuple(
                    finding.field
                    for finding in findings
                    if finding.code.startswith("missing_")
                    and finding.field is not None
                )
                self.assertEqual(
                    records[
                        f"docs/reports/{name}"
                    ].validator_required_missing_fields,
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
