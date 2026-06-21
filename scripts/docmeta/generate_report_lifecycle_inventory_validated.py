#!/usr/bin/env python3
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import parse_frontmatter
from scripts.docmeta import generate_report_lifecycle_inventory as _core
from scripts.docmeta.report_lifecycle_requirements import missing_required_report_fields

InventoryConfig = _core.InventoryConfig
RelationEntry = _core.RelationEntry
CORE_LIFECYCLE_FIELDS = _core.CORE_LIFECYCLE_FIELDS
SUPERSESSION_REQUIRED_LIFECYCLE_STATES = _core.SUPERSESSION_REQUIRED_LIFECYCLE_STATES
REPO_ROOT = _core.REPO_ROOT
REPORTS_DIR = _core.REPORTS_DIR
OUTPUT_PATH = _core.OUTPUT_PATH
PRIMARY_REFERENCE_SEARCH_PATHS = _core.PRIMARY_REFERENCE_SEARCH_PATHS
DERIVED_REFERENCE_SEARCH_PATHS = _core.DERIVED_REFERENCE_SEARCH_PATHS

_as_rel = _core._as_rel
_cell = _core._cell
_compile_path_reference_pattern = _core._compile_path_reference_pattern
_parse_frontmatter = _core._parse_frontmatter


@dataclass(frozen=True)
class ReportRecord:
    path: str
    has_frontmatter: bool
    doc_id: str
    title: str
    doc_type: str
    status: str
    lifecycle_state: str
    lifecycle: str
    owner_task: str
    review_after: str
    superseded_by: str
    relations_count: int
    relation_types: tuple[str, ...]
    relation_targets: tuple[str, ...]
    primary_referenced_by_paths: tuple[str, ...]
    derived_referenced_by_paths: tuple[str, ...]
    absent_core_lifecycle_fields: tuple[str, ...]
    validator_required_missing_fields: tuple[str, ...]
    missing_supersession_target: bool
    frontmatter_parse_warning: str

    @property
    def referenced_by_paths(self) -> tuple[str, ...]:
        return self.primary_referenced_by_paths

    @property
    def referenced_by_count(self) -> int:
        return len(self.primary_referenced_by_paths)


def default_inventory_config() -> InventoryConfig:
    return _core.default_inventory_config()


def collect_reports(config: InventoryConfig | None = None) -> list[ReportRecord]:
    inventory_config = config or default_inventory_config()
    core_records = _core.collect_reports(inventory_config)
    records: list[ReportRecord] = []
    for record in core_records:
        path = inventory_config.repo_root / record.path
        validator_frontmatter = parse_frontmatter(str(path)) or {}
        records.append(
            ReportRecord(
                path=record.path,
                has_frontmatter=record.has_frontmatter,
                doc_id=record.doc_id,
                title=record.title,
                doc_type=record.doc_type,
                status=record.status,
                lifecycle_state=record.lifecycle_state,
                lifecycle=record.lifecycle,
                owner_task=record.owner_task,
                review_after=record.review_after,
                superseded_by=record.superseded_by,
                relations_count=record.relations_count,
                relation_types=record.relation_types,
                relation_targets=record.relation_targets,
                primary_referenced_by_paths=record.primary_referenced_by_paths,
                derived_referenced_by_paths=record.derived_referenced_by_paths,
                absent_core_lifecycle_fields=record.absent_core_lifecycle_fields,
                validator_required_missing_fields=missing_required_report_fields(
                    validator_frontmatter
                ),
                missing_supersession_target=record.missing_supersession_target,
                frontmatter_parse_warning=record.frontmatter_parse_warning,
            )
        )
    return records


def build_summary(records: list[ReportRecord]) -> list[tuple[str, int]]:
    summary = _core.build_summary(records)
    insertion_index = next(
        index
        for index, (metric, _) in enumerate(summary)
        if metric == "files_missing_review_after"
    ) + 1
    validator_metrics = [
        (
            "reports_with_validator_required_missing_fields",
            sum(
                1
                for record in records
                if record.doc_type.strip().lower() == "report"
                and record.validator_required_missing_fields
            ),
        ),
        (
            "reports_without_validator_required_missing_fields",
            sum(
                1
                for record in records
                if record.doc_type.strip().lower() == "report"
                and not record.validator_required_missing_fields
            ),
        ),
        (
            "validator_required_missing_fields_total",
            sum(
                len(record.validator_required_missing_fields)
                for record in records
                if record.doc_type.strip().lower() == "report"
            ),
        ),
    ]
    return summary[:insertion_index] + validator_metrics + summary[insertion_index:]


def build_doc_type_distribution(records: list[ReportRecord]) -> list[tuple[str, int]]:
    return _core.build_doc_type_distribution(records)


def _augment_reports_table(markdown: str, records: list[ReportRecord]) -> str:
    missing_by_path = {
        record.path: ", ".join(record.validator_required_missing_fields)
        for record in records
    }
    lines = markdown.splitlines()
    in_reports = False
    for index, line in enumerate(lines):
        if line == "## Reports":
            in_reports = True
            continue
        if in_reports and line.startswith("## "):
            break
        if not in_reports or not line.startswith("|"):
            continue
        if "absent core lifecycle fields" in line:
            lines[index] = line.replace(
                "absent core lifecycle fields | supersession target diagnostic",
                "absent tracked lifecycle fields (presence only) | "
                "validator-required missing fields | supersession target diagnostic",
            )
            continue
        cells = line[2:-2].split(" | ")
        if len(cells) == 13:
            cells.insert(
                12,
                "---" if line.startswith("| ---") else _cell(missing_by_path.get(cells[0], "")),
            )
            lines[index] = "| " + " | ".join(cells) + " |"
    return "\n".join(lines) + "\n"


def render_inventory(records: list[ReportRecord]) -> str:
    markdown = _core.render_inventory(records)
    markdown = markdown.replace(
        "This inventory is descriptive only. Absent core lifecycle metadata "
        "is expected at this stage and is not a policy judgement.\n",
        "This inventory is descriptive only. Presence metrics report whether "
        "tracked keys exist; validator-required metrics follow the currently "
        "implemented report-lifecycle validator rules.\n"
        "The shared requirements are not the complete normative lifecycle "
        "policy and do not replace future enum, date, owner, or relation checks.\n",
    )
    summary_lines = [
        f"| {metric} | {count} |"
        for metric, count in build_summary(records)
        if metric.startswith("reports_")
        or metric == "validator_required_missing_fields_total"
    ]
    marker = next(
        line
        for line in markdown.splitlines()
        if line.startswith("| files_primary_referenced |")
    )
    markdown = markdown.replace(marker, "\n".join(summary_lines + [marker]), 1)
    markdown = _augment_reports_table(markdown, records)
    markdown = markdown.replace(
        "## Absent Core Lifecycle Metadata",
        "## Absent Tracked Lifecycle Fields — Presence Only\n\n"
        "This section reports physical field absence only. It is not a "
        "validator finding.\n"
        "Fields that are optional or not required for the current `status` or "
        "`lifecycle_state` may appear here.",
        1,
    )
    required_lines = [
        "## Validator-Required Missing Fields",
        "",
        "| Path | Missing required fields |",
        "| --- | --- |",
    ]
    missing_records = [
        record for record in records if record.validator_required_missing_fields
    ]
    if missing_records:
        required_lines.extend(
            f"| {record.path} | "
            f"{_cell(', '.join(record.validator_required_missing_fields))} |"
            for record in missing_records
        )
    else:
        required_lines.append("| _None_ | _None_ |")
    markdown = markdown.replace(
        "## Relations\n",
        "\n".join(required_lines) + "\n\n## Relations\n",
        1,
    )
    return markdown


def generate(config: InventoryConfig | None = None) -> Path:
    inventory_config = config or default_inventory_config()
    records = collect_reports(inventory_config)
    content = render_inventory(records)
    inventory_config.output_path.parent.mkdir(parents=True, exist_ok=True)
    inventory_config.output_path.write_text(content, encoding="utf-8")
    return inventory_config.output_path


def main() -> None:
    output_path = generate()
    print(f"Generated {_as_rel(output_path, default_inventory_config().repo_root)}")


if __name__ == "__main__":
    main()
