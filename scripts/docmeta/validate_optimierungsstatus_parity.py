#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.docmeta.docmeta import REPO_ROOT

ROOT = Path(REPO_ROOT)
MARKDOWN_PATH = ROOT / "docs" / "reports" / "optimierungsstatus.md"
JSON_PATH = ROOT / "docs" / "reports" / "optimierungsstatus.json"

FIELD_MAP = (
    ("id", "id"),
    ("bereich", "area"),
    ("maßnahme", "title"),
    ("status", "status"),
    ("befund_evidenzgrad", "evidence_status"),
    ("risiko", "risk"),
    ("aufwand", "effort"),
    ("priorität", "priority"),
    ("zuletzt_geprüft", "updated_at"),
)

VALUE_TRANSLATIONS = {
    "hoch": "high",
    "mittel": "medium",
    "niedrig": "low",
}


@dataclass(frozen=True)
class Finding:
    code: str
    message: str


def _cell(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.startswith("`") and text.endswith("`") and len(text) >= 2:
        text = text[1:-1]
    return text.replace("`", "").strip()


def _normalized(value: object) -> str:
    text = _cell(value)
    return VALUE_TRANSLATIONS.get(text, text)


def parse_markdown_matrix(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] = []
    in_matrix = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "## Matrix":
            in_matrix = True
            continue
        if in_matrix and line.startswith("## "):
            break
        if not in_matrix or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and all(set(cell) <= set("-: ") for cell in cells):
            continue
        if not headers:
            headers = cells
            continue
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def load_json_items(path: Path) -> list[dict[str, object]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError("optimierungsstatus.json field 'items' must be a list")
    return [item for item in items if isinstance(item, dict)]


def validate(markdown_path: Path = MARKDOWN_PATH, json_path: Path = JSON_PATH) -> list[Finding]:
    findings: list[Finding] = []
    markdown_rows = parse_markdown_matrix(markdown_path)
    json_items = load_json_items(json_path)

    markdown_ids = [_normalized(row.get("id")) for row in markdown_rows]
    json_ids = [_normalized(item.get("id")) for item in json_items]
    if markdown_ids != json_ids:
        findings.append(Finding(
            "id_order_mismatch",
            f"Markdown IDs {markdown_ids!r} do not match JSON IDs {json_ids!r}",
        ))

    json_by_id = {_normalized(item.get("id")): item for item in json_items}
    for row in markdown_rows:
        row_id = _normalized(row.get("id"))
        item = json_by_id.get(row_id)
        if item is None:
            findings.append(Finding("missing_json_item", f"{row_id} is missing in JSON"))
            continue
        for markdown_field, json_field in FIELD_MAP:
            markdown_value = _normalized(row.get(markdown_field))
            json_value = _normalized(item.get(json_field))
            if markdown_value != json_value:
                findings.append(Finding(
                    "field_mismatch",
                    f"{row_id}: {markdown_field}/{json_field} mismatch: {markdown_value!r} != {json_value!r}",
                ))

    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate optimierungsstatus Markdown/JSON parity.")
    parser.add_argument("--markdown", type=Path, default=MARKDOWN_PATH)
    parser.add_argument("--json", type=Path, default=JSON_PATH)
    args = parser.parse_args(argv)

    findings = validate(args.markdown, args.json)
    if findings:
        for finding in findings:
            print(f"{finding.code}: {finding.message}", file=sys.stderr)
        return 1
    print("Optimierungsstatus Markdown/JSON parity passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
