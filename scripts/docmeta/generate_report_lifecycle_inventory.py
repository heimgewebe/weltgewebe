#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "docs" / "reports"
OUTPUT_PATH = REPO_ROOT / "docs" / "_generated" / "report-lifecycle-inventory.md"
PRIMARY_REFERENCE_SEARCH_PATHS = (
    REPO_ROOT / "docs",
)
DERIVED_REFERENCE_SEARCH_PATHS = (
    REPO_ROOT / "docs" / "_generated",
)
CORE_LIFECYCLE_FIELDS = (
    "lifecycle",
    "owner_task",
    "review_after",
    "lifecycle_state",
)
SUPERSESSION_REQUIRED_LIFECYCLE_STATES = {"superseded"}

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
This inventory is descriptive only. Absent core lifecycle metadata is expected at this stage and is not a policy judgement.
Primary references are exact path matches in canonical documentation surfaces. Derived generated references are reported separately.
"""


@dataclass(frozen=True)
class InventoryConfig:
    repo_root: Path
    reports_dir: Path
    output_path: Path
    primary_search_paths: tuple[Path, ...]
    derived_search_paths: tuple[Path, ...]


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
    missing_supersession_target: bool
    frontmatter_parse_warning: str

    @property
    def referenced_by_paths(self) -> tuple[str, ...]:
        return self.primary_referenced_by_paths

    @property
    def referenced_by_count(self) -> int:
        # Primary references only; derived/generated references are reported separately.
        return len(self.primary_referenced_by_paths)


def default_inventory_config() -> InventoryConfig:
    return InventoryConfig(
        repo_root=REPO_ROOT,
        reports_dir=REPORTS_DIR,
        output_path=OUTPUT_PATH,
        primary_search_paths=PRIMARY_REFERENCE_SEARCH_PATHS,
        derived_search_paths=DERIVED_REFERENCE_SEARCH_PATHS,
    )


def _as_rel(path: Path, repo_root: Path) -> str:
    return str(path.relative_to(repo_root)).replace("\\", "/")


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

        if raw_line[:1] not in {" ", "\t"}:
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
        if raw_line.strip() and raw_line[:1] not in {" ", "\t"}:
            break
        if raw_line[:1] in {" ", "\t"}:
            values.append(raw_line.strip())
        index += 1

    joined = " ".join(part for part in values if part)
    return joined.strip(), index


def _parse_generic_block_value(lines: list[str], start_index: int) -> tuple[object, int]:
    values: list[str] = []
    index = start_index

    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        if not stripped:
            index += 1
            continue
        if raw_line[:1] not in {" ", "\t"}:
            break
        if stripped.startswith("- "):
            values.append(_strip_quotes(stripped[2:].strip()))
        else:
            values.append(stripped)
        index += 1

    if values:
        return values, index
    return "", index


def _string_value(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


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


def _compile_path_reference_pattern(report_rel: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?<![A-Za-z0-9_./-]){re.escape(report_rel)}(?![A-Za-z0-9_/-]|\.[A-Za-z0-9_])"
    )


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _iter_reference_files(
    search_paths: tuple[Path, ...],
    exclude_paths: tuple[Path, ...] = (),
) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for path in search_paths:
        if not path.exists():
            continue
        if path.is_file():
            if path not in seen and not any(
                _is_relative_to(path, excluded_path) for excluded_path in exclude_paths
            ):
                files.append(path)
                seen.add(path)
            continue
        for file_path in sorted(candidate for candidate in path.rglob("*.md") if candidate.is_file()):
            if file_path not in seen and not any(
                _is_relative_to(file_path, excluded_path) for excluded_path in exclude_paths
            ):
                files.append(file_path)
                seen.add(file_path)
    return files


def _build_reference_index(
    report_paths: list[Path],
    search_files: list[Path],
    repo_root: Path,
    skip_file: Path | None = None,
) -> dict[str, tuple[str, ...]]:
    reference_index: defaultdict[str, set[str]] = defaultdict(set)
    report_rels = [_as_rel(path, repo_root) for path in report_paths]
    patterns = {
        report_rel: _compile_path_reference_pattern(report_rel)
        for report_rel in report_rels
    }

    for search_file in search_files:
        if skip_file is not None and search_file == skip_file:
            continue
        search_rel = _as_rel(search_file, repo_root)
        content = _read_text(search_file)
        for report_rel in report_rels:
            if search_rel == report_rel:
                continue
            if report_rel in content and patterns[report_rel].search(content):
                reference_index[report_rel].add(search_rel)

    return {
        report_rel: tuple(sorted(reference_index.get(report_rel, set())))
        for report_rel in sorted(report_rels)
    }


def collect_reports(config: InventoryConfig | None = None) -> list[ReportRecord]:
    inventory_config = config or default_inventory_config()
    report_paths = sorted(
        path for path in inventory_config.reports_dir.glob("*.md") if path.is_file()
    )
    primary_reference_index = _build_reference_index(
        report_paths=report_paths,
        search_files=_iter_reference_files(
            inventory_config.primary_search_paths,
            exclude_paths=inventory_config.derived_search_paths,
        ),
        repo_root=inventory_config.repo_root,
    )
    derived_reference_index = _build_reference_index(
        report_paths=report_paths,
        search_files=_iter_reference_files(inventory_config.derived_search_paths),
        repo_root=inventory_config.repo_root,
        skip_file=inventory_config.output_path,
    )

    records: list[ReportRecord] = []
    for path in report_paths:
        content = _read_text(path)
        has_frontmatter, frontmatter, warning = _parse_frontmatter(content)
        relations = _extract_relations(frontmatter.get("relations", []))
        rel_path = _as_rel(path, inventory_config.repo_root)
        relation_types = tuple(
            sorted({relation.relation_type for relation in relations if relation.relation_type})
        )
        relation_targets = tuple(
            sorted({relation.target for relation in relations if relation.target})
        )
        status = _string_value(frontmatter.get("status"))
        lifecycle_state = _string_value(frontmatter.get("lifecycle_state"))
        normalized_lifecycle_state = lifecycle_state.lower()
        superseded_by = _string_value(frontmatter.get("superseded_by"))
        records.append(
            ReportRecord(
                path=rel_path,
                has_frontmatter=has_frontmatter,
                doc_id=_string_value(frontmatter.get("id")),
                title=_string_value(frontmatter.get("title")),
                doc_type=_string_value(frontmatter.get("doc_type")),
                status=status,
                lifecycle_state=lifecycle_state,
                lifecycle=_string_value(frontmatter.get("lifecycle")),
                owner_task=_string_value(frontmatter.get("owner_task")),
                review_after=_string_value(frontmatter.get("review_after")),
                superseded_by=superseded_by,
                relations_count=len(relations),
                relation_types=relation_types,
                relation_targets=relation_targets,
                primary_referenced_by_paths=primary_reference_index.get(rel_path, ()),
                derived_referenced_by_paths=derived_reference_index.get(rel_path, ()),
                absent_core_lifecycle_fields=tuple(
                    field for field in CORE_LIFECYCLE_FIELDS if not _string_value(frontmatter.get(field))
                ),
                missing_supersession_target=(
                    normalized_lifecycle_state in SUPERSESSION_REQUIRED_LIFECYCLE_STATES
                    and not superseded_by
                ),
                frontmatter_parse_warning=warning,
            )
        )

    return records


def build_summary(records: list[ReportRecord]) -> list[tuple[str, int]]:
    return [
        ("files_total", len(records)),
        ("files_with_frontmatter", sum(1 for record in records if record.has_frontmatter)),
        ("files_without_frontmatter", sum(1 for record in records if not record.has_frontmatter)),
        ("files_with_status", sum(1 for record in records if record.status)),
        ("files_missing_status", sum(1 for record in records if not record.status)),
        ("files_with_lifecycle_state", sum(1 for record in records if record.lifecycle_state)),
        ("files_missing_lifecycle_state", sum(1 for record in records if not record.lifecycle_state)),
        ("files_with_lifecycle", sum(1 for record in records if record.lifecycle)),
        ("files_missing_lifecycle", sum(1 for record in records if not record.lifecycle)),
        ("files_with_owner_task", sum(1 for record in records if record.owner_task)),
        ("files_missing_owner_task", sum(1 for record in records if not record.owner_task)),
        ("files_with_review_after", sum(1 for record in records if record.review_after)),
        ("files_missing_review_after", sum(1 for record in records if not record.review_after)),
        ("files_primary_referenced", sum(1 for record in records if record.referenced_by_count > 0)),
        ("files_primary_unreferenced", sum(1 for record in records if record.referenced_by_count == 0)),
        ("files_with_derived_references", sum(1 for record in records if record.derived_referenced_by_paths)),
        ("files_with_relations", sum(1 for record in records if record.relations_count > 0)),
        (
            "files_with_missing_supersession_target",
            sum(1 for record in records if record.missing_supersession_target),
        ),
    ]


def build_doc_type_distribution(records: list[ReportRecord]) -> list[tuple[str, int]]:
    counts = Counter(record.doc_type or "<missing>" for record in records)
    return sorted(counts.items())


def render_inventory(records: list[ReportRecord]) -> str:
    sections = [HEADER.rstrip(), "", "## Summary", "", "| Metric | Count |", "| --- | ---: |"]
    for metric, count in build_summary(records):
        sections.append(f"| {metric} | {count} |")

    sections.extend(
        [
            "",
            "## Doc Type Distribution",
            "",
            "| doc_type | Count |",
            "| --- | ---: |",
        ]
    )
    for doc_type, count in build_doc_type_distribution(records):
        sections.append(f"| {_cell(doc_type)} | {count} |")

    sections.extend(
        [
            "",
            "## Reports",
            "",
            "| Path | doc_type | status | lifecycle_state | lifecycle | owner_task | review_after | superseded_by | primary refs | derived refs | relations | absent core lifecycle fields | supersession target diagnostic |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for record in records:
        sections.append(
            "| {path} | {doc_type} | {status} | {lifecycle_state} | {lifecycle} | {owner_task} | {review_after} | "
            "{superseded_by} | {primary_refs} | {derived_refs} | {relations} | {absent} | {supersession_target_diagnostic} |".format(
                path=record.path,
                doc_type=_cell(record.doc_type),
                status=_cell(record.status),
                lifecycle_state=_cell(record.lifecycle_state),
                lifecycle=_cell(record.lifecycle),
                owner_task=_cell(record.owner_task),
                review_after=_cell(record.review_after),
                superseded_by=_cell(record.superseded_by),
                primary_refs=record.referenced_by_count,
                derived_refs=len(record.derived_referenced_by_paths),
                relations=record.relations_count,
                absent=_cell(", ".join(record.absent_core_lifecycle_fields)),
                supersession_target_diagnostic="missing superseded_by target" if record.missing_supersession_target else "",
            )
        )

    sections.extend(
        [
            "",
            "## Absent Core Lifecycle Metadata",
            "",
            "| Path | Absent fields |",
            "| --- | --- |",
        ]
    )
    absent_records = [record for record in records if record.absent_core_lifecycle_fields]
    if absent_records:
        for record in absent_records:
            sections.append(
                f"| {record.path} | {_cell(', '.join(record.absent_core_lifecycle_fields))} |"
            )
    else:
        sections.append("| _None_ | _None_ |")

    sections.extend(["", "## Relations", ""])
    relation_records = [record for record in records if record.relations_count > 0]
    if relation_records:
        sections.extend(
            [
                "| Path | Count | Types | Targets |",
                "| --- | ---: | --- | --- |",
            ]
        )
        for record in relation_records:
            sections.append(
                "| {path} | {count} | {types} | {targets} |".format(
                    path=record.path,
                    count=record.relations_count,
                    types=_cell(", ".join(record.relation_types)),
                    targets=_cell(", ".join(record.relation_targets)),
                )
            )
    else:
        sections.append("_None_")

    sections.extend(["", "## Primary Referenced Reports", ""])
    primary_referenced_records = [record for record in records if record.primary_referenced_by_paths]
    if primary_referenced_records:
        for record in primary_referenced_records:
            sections.append(f"- `{record.path}`")
            for ref_path in record.primary_referenced_by_paths:
                sections.append(f"  - `{ref_path}`")
            sections.append("")
    else:
        sections.append("None.")
        sections.append("")

    sections.extend(["## Derived Referenced Reports", ""])
    derived_referenced_records = [record for record in records if record.derived_referenced_by_paths]
    if derived_referenced_records:
        for record in derived_referenced_records:
            sections.append(f"- `{record.path}`")
            for ref_path in record.derived_referenced_by_paths:
                sections.append(f"  - `{ref_path}`")
            sections.append("")
    else:
        sections.append("None.")
        sections.append("")

    sections.extend(["## Primary Unreferenced Reports", ""])
    primary_unreferenced_records = [record for record in records if not record.primary_referenced_by_paths]
    if primary_unreferenced_records:
        for record in primary_unreferenced_records:
            sections.append(f"- `{record.path}`")
        sections.append("")
    else:
        sections.append("_None_")
        sections.append("")

    supersession_gap_records = [record for record in records if record.missing_supersession_target]
    sections.extend(["## Supersession Target Diagnostics", ""])
    if supersession_gap_records:
        sections.extend(
            [
                "| Path | lifecycle_state | Diagnostic |",
                "| --- | --- | --- |",
            ]
        )
        for record in supersession_gap_records:
            sections.append(f"| {record.path} | {_cell(record.lifecycle_state)} | missing superseded_by target |")
    else:
        sections.append("None.")
    sections.append("")

    sections.extend(["## Parse Warnings", ""])
    warning_records = [record for record in records if record.frontmatter_parse_warning]
    if warning_records:
        sections.extend(["| Path | Warning |", "| --- | --- |"])
        for record in warning_records:
            sections.append(f"| {record.path} | {_cell(record.frontmatter_parse_warning)} |")
    else:
        sections.append("None.")
        sections.append("")

    return "\n".join(sections).rstrip() + "\n"


def _cell(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.replace("|", "&#124;")).strip()


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
