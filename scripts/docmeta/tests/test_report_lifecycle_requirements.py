#!/usr/bin/env python3
from __future__ import annotations

import datetime
import unittest

from scripts.docmeta.report_lifecycle_requirements import (
    missing_required_report_field_rules,
    missing_required_report_fields,
    required_report_field_rules,
    string_value,
)


class TestReportLifecycleRequirements(unittest.TestCase):
    def test_non_report_has_no_requirements(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {"doc_type": "reference", "status": "active"}
            ),
            (),
        )

    def test_base_and_status_rules(self) -> None:
        cases = [
            ({"doc_type": "report"}, ("lifecycle_state", "status")),
            (
                {"doc_type": "report", "status": "active"},
                ("lifecycle_state", "lifecycle", "review_after"),
            ),
            (
                {"doc_type": "report", "status": "draft"},
                ("lifecycle_state", "review_after"),
            ),
        ]
        for frontmatter, expected in cases:
            with self.subTest(frontmatter=frontmatter):
                self.assertEqual(
                    missing_required_report_fields(frontmatter), expected
                )

    def test_lifecycle_state_rules(self) -> None:
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

    def test_deduplication_preserves_first_rule(self) -> None:
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

    def test_required_rule_precedence_and_messages_are_frozen(self) -> None:
        """Freeze ordered applicable rule definitions before presence filtering.

        When status- and lifecycle_state-derived rules share a finding code,
        the first occurrence wins. This test covers internal compatibility
        ordering. Emitted findings are covered by the validator parity test.
        """

        def rules(frontmatter: dict[str, object]) -> tuple[tuple[str, str, str], ...]:
            return tuple(
                (rule.code, rule.field, rule.message)
                for rule in required_report_field_rules(frontmatter)
            )

        # status=active wins the lifecycle/review_after message over archived.
        self.assertEqual(
            rules(
                {"doc_type": "report", "status": "active", "lifecycle_state": "archived"}
            ),
            (
                ("missing_lifecycle_state", "lifecycle_state", "report documents should define lifecycle_state"),
                ("missing_status", "status", "report documents should define status"),
                ("missing_lifecycle", "lifecycle", "active reports should define lifecycle"),
                ("missing_review_after", "review_after", "active/draft reports should define review_after"),
                ("missing_owner_task", "owner_task", "archived reports should define owner_task"),
            ),
        )
        # superseded contributes superseded_by; status=active still wins lifecycle.
        self.assertEqual(
            rules(
                {"doc_type": "report", "status": "active", "lifecycle_state": "superseded"}
            ),
            (
                ("missing_lifecycle_state", "lifecycle_state", "report documents should define lifecycle_state"),
                ("missing_status", "status", "report documents should define status"),
                ("missing_lifecycle", "lifecycle", "active reports should define lifecycle"),
                ("missing_review_after", "review_after", "active/draft reports should define review_after"),
                ("missing_owner_task", "owner_task", "superseded reports should define owner_task"),
                ("missing_superseded_by", "superseded_by", "superseded reports should define superseded_by"),
            ),
        )
        # status=draft wins review_after message; deferred contributes lifecycle/owner_task.
        self.assertEqual(
            rules(
                {"doc_type": "report", "status": "draft", "lifecycle_state": "deferred"}
            ),
            (
                ("missing_lifecycle_state", "lifecycle_state", "report documents should define lifecycle_state"),
                ("missing_status", "status", "report documents should define status"),
                ("missing_review_after", "review_after", "active/draft reports should define review_after"),
                ("missing_lifecycle", "lifecycle", "deferred reports should define lifecycle"),
                ("missing_owner_task", "owner_task", "deferred reports should define owner_task"),
            ),
        )

    def test_normalization_matches_validator_behavior(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {
                    "doc_type": " Report ",
                    "status": " Deprecated ",
                    "lifecycle_state": " ARCHIVED ",
                    "lifecycle": "audit",
                    "owner_task": "TASK-1",
                }
            ),
            (),
        )
        self.assertEqual(string_value(None), "")
        self.assertEqual(string_value([]), "")
        self.assertEqual(string_value({}), "")
        self.assertEqual(string_value(7), "7")
        self.assertEqual(
            string_value(datetime.date(2026, 7, 13)), "2026-07-13"
        )


if __name__ == "__main__":
    unittest.main()
