"""Regression tests for the one-Garnrolle ontology cutover."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class GarnrolleOntologyContractTests(unittest.TestCase):
    def test_account_contract_has_one_identity_and_explicit_map_state(self) -> None:
        schema = json.loads((ROOT / "contracts/domain/account.schema.json").read_text())
        self.assertEqual(schema["properties"]["type"], {"const": "garnrolle"})
        self.assertEqual(
            schema["properties"]["map_state"]["enum"],
            ["not_on_map", "exact", "radius"],
        )
        self.assertNotIn("mode", schema["properties"])
        self.assertIn("map_state", schema["required"])

    def test_new_data_producers_do_not_emit_legacy_identity_fields(self) -> None:
        paths = (
            "scripts/dev/generate-demo-data.sh",
            "scripts/dev/gewebe-demo-server.mjs",
            "scripts/dev/bootstrap-first-account.sh",
            "apps/web/src/lib/demo/demoData.ts",
            "apps/web/tests/map-url-state.spec.ts",
            "contracts/domain/examples/account.example.json",
        )
        forbidden = re.compile(r'(?i)(["\'](?:mode|ron_flag|visibility|suppress_public_pos)["\']\s*:|["\']type["\']\s*:\s*["\']ron["\'])')
        for relative in paths:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIsNone(forbidden.search(text), relative)
            self.assertIn("map_state", text, relative)

    def test_final_migration_removes_legacy_identity_fail_closed(self) -> None:
        up = (ROOT / "apps/api/migrations/20260724000001_remove_ron_legacy.up.sql").read_text()
        self.assertIn("kind IS DISTINCT FROM 'garnrolle'", up)
        self.assertNotIn("mode IS NOT NULL", up)
        self.assertIn("private_payload ? 'ron_flag'", up)
        self.assertIn("private_payload ? 'visibility'", up)
        self.assertIn("private_payload ? 'suppress_public_pos'", up)
        self.assertIn("RAISE EXCEPTION", up)
        self.assertIn("DROP COLUMN mode", up)
        down = (ROOT / "apps/api/migrations/20260724000001_remove_ron_legacy.down.sql").read_text()
        self.assertEqual(down.strip(), "ALTER TABLE domain_accounts ADD COLUMN mode TEXT;")

    def test_runtime_rejects_removed_identity_fields(self) -> None:
        production = "\n".join(
            (ROOT / path)
            .read_text(encoding="utf-8")
            .split("#[cfg(test)]", 1)[0]
            for path in ("apps/api/src/routes/accounts.rs", "apps/api/src/domain_db.rs")
        )
        self.assertNotIn("legacy_not_on_map", production)
        self.assertNotIn("legacy_mode", production)
        self.assertNotIn('kind == "ron"', production)
        self.assertNotIn("legacy_visibility", production)
        self.assertIn('"mode", "ron_flag", "visibility", "suppress_public_pos"', production)
        self.assertIn("rejecting removed account field", production)

    def test_public_api_type_no_longer_contains_account_mode(self) -> None:
        source = (ROOT / "apps/api/src/routes/accounts.rs").read_text()
        self.assertNotIn("pub enum AccountMode", source)
        self.assertIn("pub enum GarnrolleMapState", source)
        self.assertIn("pub map_state: GarnrolleMapState", source)
        self.assertNotRegex(source, r"pub\s+mode:\s+AccountMode")

    def test_canonical_docs_describe_completed_identity_removal(self) -> None:
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "README.md",
                "architecture/overview.md",
                "architecture/security.md",
                "docs/datenmodell.md",
                "docs/domain/vocabulary.md",
            )
        )
        self.assertIn("not_on_map", combined)
        self.assertNotIn("Rollbackbrücke", combined)
        self.assertNotIn("Legacy-RoN wird", combined)
        self.assertIn("entfernt", combined)


if __name__ == "__main__":
    unittest.main()
