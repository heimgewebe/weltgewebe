#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "docs" / "reports"
OUTPUT_PATH = REPO_ROOT / "docs" / "_generated" / "report-lifecycle-inventory.md"
REFERENCE_SEARCH_PATHS = [
    REPO_ROOT / "docs" / "tasks",
    REPO_ROOT / "docs" / "blueprints",
    REPO_ROOT / "docs" / "reports",
    REPO_ROOT / "docs" / "proofs",
    REPO_ROOT / "docs" / "roadmap.md",
    REPO_ROOT / "docs" / "_generated",
]
LIFECYCLE_FIELDS = ("lifecycle", "owner_task", "review_after", "superseded_by")

HEADER = """\
---
id: docs.generated.report-lifecycle-inventory
title: Report Lifecycle Inventory
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generiertes Inventar der Report-Lifecycle-Metadaten.
---
# Report Lifecycle Inventory

Generated automatically. Do not edit manually.
This inventory is descriptive only. Missing lifecycle fields are expected at this stage and are not policy violations.
Reference counts are based on heuristic text matches against selected documentation paths.
"""


@dataclass(frozen=True)
class RelationEntry:
    relation_type: str
    target: str


@dataclass(frozen=True)
class ReportRecord:
    path: str
    has_frontmatter: bool
    doc_id: str
    title: str
    doc_type: str
    status: str
    lifecycle: str
    owner_task: str
    review_after: str
    superseded_by: str
    relations_count: int
    relation_types: tuple[str, ...]
    relation_targets: tuple[str, ...]
    referenced_by_paths: tuple[str, ...]
    missing_lifecycle_fields: tuple[str, ...]
    frontmatter_parse_warning: str

    @property
    def referenced_by_count(self) -> int:
        return len(self.referenced_by_paths)


def _as_rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _split_frontmatter(content: str) -> tuple[bool, list[str], str]:
    if not content.startswith("---"):
        return False, [], ""

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return False, [], ""

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break

    if closing_index is None:
        return True, lines[1:], "frontmatter start found without closing delimiter"

    return True, lines[1:closing_index], ""


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_frontmatter(content: str) -> tuple[bool, dict[str, object], str]:
    has_frontmatter, fm_lines, split_warning = _split_frontmatter(content)
    if not has_frontmatter:
        return False, {}, "frontmatter missing"

    data: dict[str, object] = {}
    relations: list[RelationEntry] = []
    warning_parts: list[str] = []
    if split_warning:
        warning_parts.append(split_warning)

    index = 0
    while index < len(fm_lines):
        raw_line = fm_lines[index]
        stripped = raw_line.strip()
        index += 1

        if not stripped or stripped.startswith("#"):
            continue

        if raw_line[:1] in {" ", "\t"}:
            warning_parts.append(f"unexpected indented line: {stripped}")
            continue

        if ":" not in raw_line:
            warning_parts.append(f"unparseable frontmatter line: {stripped}")
            continue

        key, raw_value = raw_line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()

        if key == "relations":
            if value == "[]":
                data[key] = []
                continue
            if value:
                warning_parts.append("relations must use block list syntax for this inventory")
                data[key] = []
                continue

            relation_warning, parsed_relations, next_index = _parse_relations_block(fm_lines, index)
            if relation_warning:
                warning_parts.append(relation_warning)
            relations = parsed_relations
            data[key] = [
                {"type": relation.relation_type, "target": relation.target}
                for relation in relations
            ]
            index = next_index
            continue

        if value in {">", "|"}:
            folded_value, next_index = _parse_multiline_scalar_block(fm_lines, index)
            data[key] = folded_value
            index = next_index
            continue

        if value == "":
            block_value, next_index = _parse_generic_block_value(fm_lines, index)
            data[key] = block_value
            index = next_index
            continue

        data[key] = _strip_quotes(value)

    if relations:
        data["relations"] = [
            {"type": relation.relation_type, "target": relation.target}
            for relation in relations
        ]

    warning = "; ".join(dict.fromkeys(part for part in warning_parts if part))
    return True, data, warning


def _parse_relations_block(lines: list[str], start_index: int) -> tuple[str, list[RelationEntry], int]:
    relations: list[RelationEntry] = []
    warning_parts: list[str] = []
    index = start_index
    current: dict[str, str] | None = None

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()

        if not stripped or stripped.startswith("#"):
            index += 1
            continue

        if not raw_line[:1] in {" ", "\t"}:
            break

        if stripped.startswith("- "):
            if current is not None:
                relations.append(
                    RelationEntry(
                        relation_type=current.get("type", ""),
                        target=current.get("target", ""),
                    )
                )
            current = {}
            item = stripped[2:].strip()
            if item:
                if ":" not in item:
                    warning_parts.append(f"unparseable relations entry: {item}")
                else:
                    sub_key, sub_value = item.split(":", 1)
                    current[sub_key.strip()] = _strip_quotes(sub_value.strip())
            index += 1
            continue

        if current is None:
            warning_parts.append(f"relation continuation without list item: {stripped}")
            index += 1
            continue

        if ":" not in stripped:
            warning_parts.append(f"unparseable relation line: {stripped}")
            index += 1
            continue

        sub_key, sub_value = stripped.split(":", 1)
        current[sub_key.strip()] = _strip_quotes(sub_value.strip())
        index += 1

    if current is not None:
        relations.append(
            RelationEntry(
                relation_type=current.get("type", ""),
                target=current.get("target", ""),
            )
        )

    warning = "; ".join(dict.fromkeys(part for part in warning_parts if part))
    return warning, relations, index


def _parse_multiline_scalar_block(lines: list[str], start_index: int) -> tuple[str, int]:
    values: list[str] = []
    index = start_index

    while index < len(lines):
        raw_line = lines[index]
        if raw_line.strip() and not raw_line[:1] in {" ", "\t"}:
            break
        if raw_line.strip():
            values.append(raw_line.strip())
        index += 1

    return " ".join(values).strip(), index


def _parse_generic_block_value(lines: list[str], start_index: int) -> tuple[object, int]:
    values: list[str] = []
    index = start_index

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped:
            index += 1
            continue
        if not raw_line[:1] in {" ", "\t"}:
            break
        if stripped.startswith("- "):
            values.append(_strip_quotes(stripped[2:].strip()))
        else:
            values.append(stripped)
        index += 1

    if values:
        return values, index
    return "", index


def collect_reports(reports_dir: Path = REPORTS_DIR) -> list[ReportRecord]:
    reports = []
    report_paths = sorted(path for path in reports_dir.glob("*.md") if path.is_file())
    reference_index = _build_reference_index(report_paths)

    for path in report_paths:
        content = _read_text(path)
        has_frontmatter, frontmatter, warning = _parse_frontmatter(content)
        relations = _extract_relations(frontmatter.get("relations", []))
        rel_path = _as_rel(path)
        reports.append(
            ReportRecord(
                path=rel_path,
                has_frontmatter=has_frontmatter,
                doc_id=_string_value(frontmatter.get("id")),
                title=_string_value(frontmatter.get("title")),
                doc_type=_string_value(frontmatter.get("doc_type")),
                status=_string_value(frontmatter.get("status")),
                lifecycle=_string_value(frontmatter.get("lifecycle")),
                owner_task=_string_value(frontmatter.get("owner_task")),
                review_after=_string_value(frontmatter.get("review_after")),
                superseded_by=_string_value(frontmatter.get("superseded_by")),
                relations_count=len(relations),
                relation_types=tuple(relation.relation_type for relation in relations if relation.relation_type),
                relation_targets=tuple(relation.target for relation in relations if relation.target),
                referenced_by_paths=tuple(reference_index.get(rel_path, [])),
                missing_lifecycle_fields=tuple(
                    field for field in LIFECYCLE_FIELDS if not _string_value(frontmatter.get(field))
                ),
                frontmatter_parse_warning=warning,
            )
        )

    return reports


def _extract_relations(raw_relations: object) -> list[RelationEntry]:
    relations: list[RelationEntry] = []
    if not isinstance(raw_relations, list):
        return relations

    for entry in raw_relations:
        if not isinstance(entry, dict):
            continue
        relations.append(
            RelationEntry(
                relation_type=_string_value(entry.get("type")),
                target=_string_value(entry.get("target")),
            )
        )
    return relations


def _string_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def _build_reference_index(report_paths: list[Path]) -> dict[str, list[str]]:
    search_files = _iter_reference_files()
    reference_index: dict[str, set[str]] = {_as_rel(path): set() for path in report_paths}

    for search_file in search_files:
        search_rel = _as_rel(search_file)
        if search_file == OUTPUT_PATH:
            continue
        content = _read_text(search_file)
        for report_path in report_paths:
            report_rel = _as_rel(report_path)
            if search_rel == report_rel:
                continue
            if report_rel in content:
                reference_index.setdefault(report_rel, set()).add(search_rel)

    return {
        report_rel: sorted(paths)
        for report_rel, paths in sorted(reference_index.items())
    }


def _iter_reference_files() -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for path in REFERENCE_SEARCH_PATHS:
        if not path.exists():
            continue
        if path.is_file():
            if path not in seen:
                files.append(path)
                seen.add(path)
            continue
        for file_path in sorted(candidate for candidate in path.rglob("*.md") if candidate.is_file()):
            if file_path not in seen:
                files.append(file_path)
                seen.add(file_path)
    return files


def build_summary(records: list[ReportRecord]) -> list[tuple[str, int]]:
    return [
        ("reports_total", len(records)),
        ("reports_with_frontmatter", sum(1 for record in records if record.has_frontmatter)),
        ("reports_without_frontmatter", sum(1 for record in records if not record.has_frontmatter)),
        ("reports_with_status", sum(1 for record in records if record.status)),
        ("reports_missing_status", sum(1 for record in records if not record.status)),
        ("reports_with_lifecycle", sum(1 for record in records if record.lifecycle)),
        ("reports_missing_lifecycle", sum(1 for record in records if not record.lifecycle)),
        ("reports_with_owner_task", sum(1 for record in records if record.owner_task)),
        ("reports_missing_owner_task", sum(1 for record in records if not record.owner_task)),
        ("reports_with_review_after", sum(1 for record in records if record.review_after)),
        ("reports_missing_review_after", sum(1 for record in records if not record.review_after)),
        ("reports_referenced", sum(1 for record in records if record.referenced_by_count > 0)),
        ("reports_unreferenced", sum(1 for record in records if record.referenced_by_count == 0)),
    ]


def render_inventory(records: list[ReportRecord]) -> str:
    sections = [HEADER.rstrip(), "", "## Summary", "", "| Metric | Count |", "| --- | ---: |"]
    for metric, count in build_summary(records):
        sections.append(f"| {metric} | {count} |")

    sections.extend(
        [
            "",
            "## Reports",
            "",
            "| Path | doc_type | status | lifecycle | owner_task | review_after | superseded_by | refs | missing |",
            "| --- | --- | --- | --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for record in records:
        sections.append(
            "| {path} | {doc_type} | {status} | {lifecycle} | {owner_task} | {review_after} | "
            "{superseded_by} | {refs} | {missing} |".format(
                path=record.path,
                doc_type=_cell(record.doc_type),
                status=_cell(record.status),
                lifecycle=_cell(record.lifecycle),
                owner_task=_cell(record.owner_task),
                review_after=_cell(record.review_after),
                superseded_by=_cell(record.superseded_by),
                refs=record.referenced_by_count,
                missing=_cell(", ".join(record.missing_lifecycle_fields)),
            )
        )

    sections.extend(["", "## Missing Lifecycle Fields", "", "| Path | Missing fields |", "| --- | --- |"])
    for record in records:
        if record.missing_lifecycle_fields:
            sections.append(f"| {record.path} | {_cell(', '.join(record.missing_lifecycle_fields))} |")

    sections.extend(["", "## Referenced Reports", "", "| Path | Referenced by |", "| --- | --- |"])
    for record in records:
        if record.referenced_by_paths:
            sections.append(f"| {record.path} | {_cell(', '.join(record.referenced_by_paths))} |")

    sections.extend(["", "## Unreferenced Reports", "", "| Path |", "| --- |"])
    for record in records:
        if not record.referenced_by_paths:
            sections.append(f"| {record.path} |")

    sections.extend(["", "## Parse Warnings", "", "| Path | Warning |", "| --- | --- |"])
    warning_records = [record for record in records if record.frontmatter_parse_warning]
    if warning_records:
        for record in warning_records:
            sections.append(f"| {record.path} | {_cell(record.frontmatter_parse_warning)} |")
    else:
        sections.append("| _None_ | _None_ |")

    return "\n".join(sections).rstrip() + "\n"


def _cell(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("|", "\\|")).strip()


def generate(output_path: Path = OUTPUT_PATH, reports_dir: Path = REPORTS_DIR) -> Path:
    records = collect_reports(reports_dir)
    content = render_inventory(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def main() -> None:
    output_path = generate()
    print(f"Generated {_as_rel(output_path)}")


if __name__ == "__main__":
    main()
