#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import parse_frontmatter
from scripts.docmeta.generate_report_lifecycle_inventory import (
    InventoryConfig,
    collect_reports as collect_inventory_records,
    default_inventory_config,
)
from scripts.docmeta.report_lifecycle_requirements import (
    missing_required_report_fields,
    string_value,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_PATH = (
    REPO_ROOT
    / "docs"
    / "_generated"
    / "report-lifecycle-validator-requirements.md"
)

HEADER = """\
---
id: docs.generated.report-lifecycle-validator-requirements
title: Report Lifecycle Validator Requirements
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generierte Sicht auf fehlende Felder nach den aktuell implementierten Report-Lifecycle-Validatorregeln.
---
# Report Lifecycle Validator Requirements

Generated automatically. Do not edit manually.

This artifact reports fields missing under the currently implemented
report-lifecycle validator rules. It is distinct from the presence-only
inventory in `docs/_generated/report-lifecycle-inventory.md`.

The shared requirements are not the complete normative lifecycle policy and
do not replace future enum, date, owner, or relation checks.
"""


@dataclass(frozen=True)
class ValidatorRequirementRecord:
    path: str
    status: str
    lifecycle_state: str
    missing_fields: tuple[str, ...]


def collect_requirement_records(
    config: InventoryConfig | None = None,
) -> list[ValidatorRequirementRecord]:
    inventory_config = config or default_inventory_config()
    records: list[ValidatorRequirementRecord] = []
    for inventory_record in collect_inventory_records(inventory_config):
        path = inventory_config.repo_root / inventory_record.path
        frontmatter = parse_frontmatter(str(path)) or {}
        if string_value(frontmatter.get("doc_type")).lower() != "report":
            continue
        records.append(
            ValidatorRequirementRecord(
                path=inventory_record.path,
                status=string_value(frontmatter.get("status")),
                lifecycle_state=string_value(frontmatter.get("lifecycle_state")),
                missing_fields=missing_required_report_fields(frontmatter),
            )
        )
    return sorted(records, key=lambda record: record.path)


def build_summary(
    records: list[ValidatorRequirementRecord],
) -> list[tuple[str, int]]:
    return [
        ("reports_checked", len(records)),
        (
            "reports_with_validator_required_missing_fields",
            sum(1 for record in records if record.missing_fields),
        ),
        (
            "reports_without_validator_required_missing_fields",
            sum(1 for record in records if not record.missing_fields),
        ),
        (
            "validator_required_missing_fields_total",
            sum(len(record.missing_fields) for record in records),
        ),
    ]


def _cell(value: str) -> str:
    return value.replace("|", "&#124;").replace("\n", " ").strip()


def render(records: list[ValidatorRequirementRecord]) -> str:
    lines = [
        HEADER.rstrip(),
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
    ]
    for metric, count in build_summary(records):
        lines.append(f"| {metric} | {count} |")

    lines.extend(
        [
            "",
            "## Reports With Missing Required Fields",
            "",
            "| Path | status | lifecycle_state | Missing required fields |",
            "| --- | --- | --- | --- |",
        ]
    )
    missing_records = [record for record in records if record.missing_fields]
    if missing_records:
        for record in missing_records:
            lines.append(
                "| {path} | {status} | {state} | {missing} |".format(
                    path=record.path,
                    status=_cell(record.status),
                    state=_cell(record.lifecycle_state),
                    missing=_cell(", ".join(record.missing_fields)),
                )
            )
    else:
        lines.append("| _None_ | _None_ | _None_ | _None_ |")

    lines.extend(
        [
            "",
            "## Complete Reports",
            "",
            "Reports without missing validator-required fields: "
            f"{sum(1 for record in records if not record.missing_fields)}.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def generate(
    config: InventoryConfig | None = None,
    output_path: Path | None = None,
) -> Path:
    target = output_path or OUTPUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render(collect_requirement_records(config)), encoding="utf-8")
    return target


def main() -> None:
    output_path = generate()
    print(f"Generated {output_path.relative_to(REPO_ROOT).as_posix()}")


if __name__ == "__main__":
    main()
