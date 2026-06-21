#!/usr/bin/env python3
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class RequiredFieldRule:
    field: str
    code: str
    message: str


BASE_REPORT_RULES = (
    RequiredFieldRule(
        field="lifecycle_state",
        code="missing_lifecycle_state",
        message="report documents should define lifecycle_state",
    ),
    RequiredFieldRule(
        field="status",
        code="missing_status",
        message="report documents should define status",
    ),
)

STATUS_RULES = {
    "active": (
        RequiredFieldRule(
            field="lifecycle",
            code="missing_lifecycle",
            message="active reports should define lifecycle",
        ),
        RequiredFieldRule(
            field="review_after",
            code="missing_review_after",
            message="active/draft reports should define review_after",
        ),
    ),
    "draft": (
        RequiredFieldRule(
            field="review_after",
            code="missing_review_after",
            message="active/draft reports should define review_after",
        ),
    ),
}

LIFECYCLE_STATE_RULES = {
    "active": (
        RequiredFieldRule(
            field="lifecycle",
            code="missing_lifecycle",
            message="active reports should define lifecycle",
        ),
        RequiredFieldRule(
            field="owner_task",
            code="missing_owner_task",
            message="active reports should define owner_task",
        ),
        RequiredFieldRule(
            field="review_after",
            code="missing_review_after",
            message="active/draft reports should define review_after",
        ),
    ),
    "deferred": (
        RequiredFieldRule(
            field="lifecycle",
            code="missing_lifecycle",
            message="deferred reports should define lifecycle",
        ),
        RequiredFieldRule(
            field="owner_task",
            code="missing_owner_task",
            message="deferred reports should define owner_task",
        ),
        RequiredFieldRule(
            field="review_after",
            code="missing_review_after",
            message="deferred reports should define review_after",
        ),
    ),
    "superseded": (
        RequiredFieldRule(
            field="lifecycle",
            code="missing_lifecycle",
            message="superseded reports should define lifecycle",
        ),
        RequiredFieldRule(
            field="owner_task",
            code="missing_owner_task",
            message="superseded reports should define owner_task",
        ),
        RequiredFieldRule(
            field="superseded_by",
            code="missing_superseded_by",
            message="superseded reports should define superseded_by",
        ),
    ),
    "archived": (
        RequiredFieldRule(
            field="lifecycle",
            code="missing_lifecycle",
            message="archived reports should define lifecycle",
        ),
        RequiredFieldRule(
            field="owner_task",
            code="missing_owner_task",
            message="archived reports should define owner_task",
        ),
    ),
}


def string_value(value: object) -> str:
    """Normalize scalar values exactly like the lifecycle validator.

    This module mirrors the validator's currently implemented field-presence
    requirements. It is not the complete normative lifecycle policy and does
    not validate enums, dates, owners, or relation consistency.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return ""
    return str(value).strip()


def required_report_field_rules(
    frontmatter: Mapping[str, object],
) -> tuple[RequiredFieldRule, ...]:
    doc_type = string_value(frontmatter.get("doc_type")).lower()
    if doc_type != "report":
        return ()

    status = string_value(frontmatter.get("status")).lower()
    lifecycle_state = string_value(frontmatter.get("lifecycle_state")).lower()

    candidates = (
        *BASE_REPORT_RULES,
        *STATUS_RULES.get(status, ()),
        *LIFECYCLE_STATE_RULES.get(lifecycle_state, ()),
    )

    rules: list[RequiredFieldRule] = []
    seen_codes: set[str] = set()
    for rule in candidates:
        if rule.code in seen_codes:
            continue
        rules.append(rule)
        seen_codes.add(rule.code)
    return tuple(rules)


def missing_required_report_field_rules(
    frontmatter: Mapping[str, object],
) -> tuple[RequiredFieldRule, ...]:
    return tuple(
        rule
        for rule in required_report_field_rules(frontmatter)
        if not string_value(frontmatter.get(rule.field))
    )


def missing_required_report_fields(
    frontmatter: Mapping[str, object],
) -> tuple[str, ...]:
    return tuple(
        rule.field
        for rule in missing_required_report_field_rules(frontmatter)
    )
