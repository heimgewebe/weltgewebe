#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from scripts.docmeta.validate_optimierungsstatus_parity import validate


HEADER = """# Optimierungsstatus

## Matrix

| id | bereich | maßnahme | status | befund_evidenzgrad | risiko | aufwand | priorität | nachweis | test | restlücke | zuletzt_geprüft |
|---|---|---|---|---|---|---|---|---|---|---|---|
"""


def row(
    task_id: str = "OPT-API-001",
    area: str = "API",
    title: str = "Titel",
    status: str = "done",
    evidence_status: str = "code+test",
    risk: str = "hoch",
    effort: str = "mittel",
    priority: str = "niedrig",
    updated_at: str = "2026-06-29",
) -> str:
    return (
        f"| {task_id} | {area} | {title} | {status} | {evidence_status} | "
        f"{risk} | {effort} | {priority} | n | t | r | {updated_at} |\n"
    )


def json_doc(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": "OPT-API-001",
        "area": "API",
        "title": "Titel",
        "status": "done",
        "evidence_status": "code+test",
        "risk": "high",
        "effort": "medium",
        "priority": "low",
        "updated_at": "2026-06-29",
    }
    item.update(overrides)
    return {"schema_version": "1.0.0", "items": [item]}


class TestValidateOptimierungsstatusParity(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.md = self.root / "optimierungsstatus.md"
        self.js = self.root / "optimierungsstatus.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def write_pair(self, markdown_row: str, json_data: dict[str, object]) -> None:
        self.md.write_text(HEADER + markdown_row, encoding="utf-8")
        self.js.write_text(json.dumps(json_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_matching_markdown_and_json_pass(self) -> None:
        self.write_pair(row(), json_doc())
        self.assertEqual(validate(self.md, self.js), [])

    def test_german_priority_values_match_json_enums(self) -> None:
        self.write_pair(row(risk="hoch", effort="mittel", priority="niedrig"), json_doc())
        self.assertEqual(validate(self.md, self.js), [])

    def test_code_ticks_do_not_create_title_drift(self) -> None:
        self.write_pair(row(title="Limit `/nodes`"), json_doc(title="Limit /nodes"))
        self.assertEqual(validate(self.md, self.js), [])

    def test_id_order_mismatch_is_reported(self) -> None:
        self.write_pair(row(), json_doc(id="OPT-API-002"))
        findings = validate(self.md, self.js)
        self.assertIn("id_order_mismatch", [finding.code for finding in findings])
        self.assertIn("missing_json_item", [finding.code for finding in findings])

    def test_field_mismatch_is_reported(self) -> None:
        self.write_pair(row(status="partial"), json_doc(status="done"))
        findings = validate(self.md, self.js)
        self.assertEqual([finding.code for finding in findings], ["field_mismatch"])
        self.assertIn("status/status mismatch", findings[0].message)


if __name__ == "__main__":
    unittest.main()
