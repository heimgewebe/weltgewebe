#!/usr/bin/env python3
from __future__ import annotations

import datetime
import unittest

from scripts.docmeta.report_lifecycle_requirements import (
    missing_required_report_field_rules,
    missing_required_report_fields,
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


if __name__ == "__main_":
    unittest.main()
