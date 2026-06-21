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


# Cross-product matrix inputs. The full product is exhaustively executed, but
# the cases are not all distinct semantic states: the non-report combinations
# (doc_type != "report") all terminate early with no findings. The redundancy
# is intentional and cheap, and documents parity across the entire input
# cross product rather than only the report-typed subset.
DOC_TYPES = ("report", "reference")
STATUSES = ("", "active", "draft", "deprecated")
LIFECYCLE_STATES = (
    "",
    "active",
    "deferred",
    "superseded",
    "archived",
    "unknown",
)
MATRIX_FIELDS = ("lifecycle", "owner_task", "review_after", "superseded_by")
EXPECTED_MATRIX_CASES = 768

# Normalization probe surface. The probe count is frozen so the documented
# number cannot silently drift from the executed test surface.
NORMALIZATION_KEYS = (
    "doc_type",
    "status",
    "lifecycle_state",
    "lifecycle",
    "owner_task",
    "review_after",
    "superseded_by",
)
NORMALIZATION_BASE: dict[str, object] = {
    "doc_type": "report",
    "status": "active",
    "lifecycle_state": "superseded",
    "lifecycle": "value",
    "owner_task": "value",
    "review_after": "value",
    "superseded_by": "value",
}
EMPTY_VALUES = (None, "", "   ", [], (), set(), {})
NON_STRING_SCALARS = (7, False, datetime.date(2026, 7, 13))
CASE_AND_WHITESPACE_CASES = (
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
EXPECTED_NORMALIZATION_CASES = 73


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

    def test_cross_product_matrix_matches_legacy_validator(self) -> None:
        """Exhaustively executed cross product of doc_type, status,
        lifecycle_state, and field presence.

        These are fully executed matrix cases, not 768 distinct semantic
        states: the non-report combinations terminate identically early.
        Verifies the refactored validator matches the frozen legacy oracle on
        finding code, field, message, severity, and order across the whole
        cross product.
        """
        case_count = 0

        for doc_type, status, lifecycle_state, presence in itertools.product(
            DOC_TYPES,
            STATUSES,
            LIFECYCLE_STATES,
            itertools.product((False, True), repeat=len(MATRIX_FIELDS)),
        ):
            frontmatter: dict[str, object] = {
                "doc_type": doc_type,
                "status": status,
                "lifecycle_state": lifecycle_state,
            }
            frontmatter.update(
                {
                    field: "value" if present else ""
                    for field, present in zip(MATRIX_FIELDS, presence, strict=True)
                }
            )
            self.assert_matches_legacy(frontmatter)
            case_count += 1

        self.assertEqual(case_count, EXPECTED_MATRIX_CASES)

    def test_empty_value_normalization_matches_legacy_validator(self) -> None:
        for key, empty_value in itertools.product(
            NORMALIZATION_KEYS, EMPTY_VALUES
        ):
            frontmatter = dict(NORMALIZATION_BASE)
            frontmatter[key] = empty_value
            with self.subTest(key=key, value=empty_value):
                self.assert_matches_legacy(frontmatter)

    def test_non_string_scalar_normalization_matches_legacy_validator(self) -> None:
        for key, scalar_value in itertools.product(
            NORMALIZATION_KEYS, NON_STRING_SCALARS
        ):
            frontmatter = dict(NORMALIZATION_BASE)
            frontmatter[key] = scalar_value
            with self.subTest(key=key, value=scalar_value):
                self.assert_matches_legacy(frontmatter)

    def test_case_and_whitespace_normalization_matches_legacy_validator(self) -> None:
        for frontmatter in CASE_AND_WHITESPACE_CASES:
            with self.subTest(frontmatter=frontmatter):
                self.assert_matches_legacy(frontmatter)

    def test_probe_surface_sizes_are_frozen(self) -> None:
        """Pin the documented case counts to the executed test surface.

        If the matrix or normalization constants change, these literals must be
        updated deliberately, so the PR description cannot silently diverge from
        what the tests actually exercise.
        """
        matrix_cases = (
            len(DOC_TYPES)
            * len(STATUSES)
            * len(LIFECYCLE_STATES)
            * 2 ** len(MATRIX_FIELDS)
        )
        self.assertEqual(matrix_cases, EXPECTED_MATRIX_CASES)
        self.assertEqual(EXPECTED_MATRIX_CASES, 768)

        normalization_cases = (
            len(NORMALIZATION_KEYS) * len(EMPTY_VALUES)
            + len(NORMALIZATION_KEYS) * len(NON_STRING_SCALARS)
            + len(CASE_AND_WHITESPACE_CASES)
        )
        self.assertEqual(normalization_cases, EXPECTED_NORMALIZATION_CASES)
        self.assertEqual(EXPECTED_NORMALIZATION_CASES, 73)


if __name__ == "__main__":
    unittest.main()
