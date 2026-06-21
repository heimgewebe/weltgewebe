#!/usr/bin/env python3
from __future__ import annotations

import datetime
import itertools
import unittest
from pathlib import Path

from scripts.docmeta.validate_report_lifecycle import _validate_report


FindingTuple = tuple[str, str | None, str, str]


def legacy_string_value(value: object) -> str:
    """Frozen normalization from the pre-refactor validator."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return ""
    return str(value).strip()


def legacy_expected_findings(
    frontmatter: dict[str, object],
) -> tuple[FindingTuple, ...]:
    """Frozen compatibility oracle from PR base 0fcd01a52156df250fe21660d7675547338b990c.

    This is test evidence, not a second production policy source. Changing it
    requires an explicit behavior-change decision.
    """
    doc_type = legacy_string_value(frontmatter.get("doc_type")).lower()
    if doc_type != "report":
        return ()

    status = legacy_string_value(frontmatter.get("status")).lower()
    lifecycle_state = legacy_string_value(frontmatter.get("lifecycle_state")).lower()
    lifecycle = legacy_string_value(frontmatter.get("lifecycle"))
    owner_task = legacy_string_value(frontmatter.get("owner_task"))
    review_after = legacy_string_value(frontmatter.get("review_after"))
    superseded_by = legacy_string_value(frontmatter.get("superseded_by"))

    findings: list[FindingTuple] = []
    added_codes: set[str] = set()

    def add_finding(code: str, field: str, message: str) -> None:
        if code in added_codes:
            return
        findings.append((code, field, message, "warn"))
        added_codes.add(code)

    if not lifecycle_state:
        add_finding(
            "missing_lifecycle_state",
            "lifecycle_state",
            "report documents should define lifecycle_state",
        )
    if not status:
        add_finding(
            "missing_status",
            "status",
            "report documents should define status",
        )
    if status == "active" and not lifecycle:
        add_finding(
            "missing_lifecycle",
            "lifecycle",
            "active reports should define lifecycle",
        )
    if status in {"active", "draft"} and not review_after:
        add_finding(
            "missing_review_after",
            "review_after",
            "active/draft reports should define review_after",
        )

    if lifecycle_state == "active":
        if not lifecycle:
            add_finding(
                "missing_lifecycle",
                "lifecycle",
                "active reports should define lifecycle",
            )
        if not owner_task:
            add_finding(
                "missing_owner_task",
                "owner_task",
                "active reports should define owner_task",
            )
        if not review_after:
            add_finding(
                "missing_review_after",
                "review_after",
                "active/draft reports should define review_after",
            )
    elif lifecycle_state == "deferred":
        if not lifecycle:
            add_finding(
                "missing_lifecycle",
                "lifecycle",
                "deferred reports should define lifecycle",
            )
        if not owner_task:
            add_finding(
                "missing_owner_task",
                "owner_task",
                "deferred reports should define owner_task",
            )
        if not review_after:
            add_finding(
                "missing_review_after",
                "review_after",
                "deferred reports should define review_after",
            )
    elif lifecycle_state == "superseded":
        if not lifecycle:
            add_finding(
                "missing_lifecycle",
                "lifecycle",
                "superseded reports should define lifecycle",
            )
        if not owner_task:
            add_finding(
                "missing_owner_task",
                "owner_task",
                "superseded reports should define owner_task",
            )
        if not superseded_by:
            add_finding(
                "missing_superseded_by",
                "superseded_by",
                "superseded reports should define superseded_by",
            )
    elif lifecycle_state == "archived":
        if not lifecycle:
            add_finding(
                "missing_lifecycle",
                "lifecycle",
                "archived reports should define lifecycle",
            )
        if not owner_task:
            add_finding(
                "missing_owner_task",
                "owner_task",
                "archived reports should define owner_task",
            )

    return tuple(findings)


class TestReportLifecycleValidatorParity(unittest.TestCase):
    ROOT = Path("/repo")
    PATH = ROOT / "docs" / "reports" / "sample.md"

    def assert_matches_legacy(self, frontmatter: dict[str, object]) -> None:
        findings = _validate_report(self.PATH, frontmatter, self.ROOT)
        actual = tuple(
            (finding.code, finding.field, finding.message, finding.severity)
            for finding in findings
        )
        self.assertEqual(
            actual,
            legacy_expected_findings(frontmatter),
            msg=f"frontmatter={frontmatter!r}",
        )
        self.assertEqual(
            len({finding.code for finding in findings}),
            len(findings),
            msg=f"duplicate finding code for frontmatter={frontmatter!r}",
        )
        self.assertTrue(
            all(finding.path == "docs/reports/sample.md" for finding in findings),
            msg=f"unexpected path for frontmatter={frontmatter!r}",
        )

    def test_semantic_decision_matrix_matches_legacy_validator(self) -> None:
        doc_types = ("report", "reference")
        statuses = ("", "active", "draft", "deprecated")
        lifecycle_states = (
            "",
            "active",
            "deferred",
            "superseded",
            "archived",
            "unknown",
        )
        fields = ("lifecycle", "owner_task", "review_after", "superseded_by")
        case_count = 0

        for doc_type, status, lifecycle_state, presence in itertools.product(
            doc_types,
            statuses,
            lifecycle_states,
            itertools.product((False, True), repeat=len(fields)),
        ):
            frontmatter: dict[str, object] = {
                "doc_type": doc_type,
                "status": status,
                "lifecycle_state": lifecycle_state,
            }
            frontmatter.update(
                {
                    field: "value" if present else ""
                    for field, present in zip(fields, presence, strict=True)
                }
            )
            self.assert_matches_legacy(frontmatter)
            case_count += 1

        self.assertEqual(case_count, 768)

    def test_empty_value_normalization_matches_legacy_validator(self) -> None:
        empty_values = (None, "", "   ", [], (), set(), {})
        keys = (
            "doc_type",
            "status",
            "lifecycle_state",
            "lifecycle",
            "owner_task",
            "review_after",
            "superseded_by",
        )
        base: dict[str, object] = {
            "doc_type": "report",
            "status": "active",
            "lifecycle_state": "superseded",
            "lifecycle": "value",
            "owner_task": "value",
            "review_after": "value",
            "superseded_by": "value",
        }

        for key, empty_value in itertools.product(keys, empty_values):
            frontmatter = dict(base)
            frontmatter[key] = empty_value
            with self.subTest(key=key, value=empty_value):
                self.assert_matches_legacy(frontmatter)

    def test_non_string_scalar_normalization_matches_legacy_validator(self) -> None:
        scalar_values = (7, False, datetime.date(2026, 7, 13))
        keys = (
            "doc_type",
            "status",
            "lifecycle_state",
            "lifecycle",
            "owner_task",
            "review_after",
            "superseded_by",
        )
        base: dict[str, object] = {
            "doc_type": "report",
            "status": "active",
            "lifecycle_state": "superseded",
            "lifecycle": "value",
            "owner_task": "value",
            "review_after": "value",
            "superseded_by": "value",
        }

        for key, scalar_value in itertools.product(keys, scalar_values):
            frontmatter = dict(base)
            frontmatter[key] = scalar_value
            with self.subTest(key=key, value=scalar_value):
                self.assert_matches_legacy(frontmatter)

    def test_case_and_whitespace_normalization_matches_legacy_validator(self) -> None:
        cases = (
            {
                "doc_type": " Report ",
                "status": " ACTIVE ",
                "lifecycle_state": " Deferred ",
            },
            {
                "doc_type": " REPORT ",
                "status": " Draft ",
                "lifecycle_state": " ARCHIVED ",
            },
            {
                "doc_type": " Reference ",
                "status": " ACTIVE ",
                "lifecycle_state": " SUPERSEDED ",
            },
        )
        for frontmatter in cases:
            with self.subTest(frontmatter=frontmatter):
                self.assert_matches_legacy(frontmatter)


if __name__ == "__main__":
    unittest.main()
