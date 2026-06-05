import json
import shutil
import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.generate_claim_evidence_map as gen


class TestGenerateClaimEvidenceMap(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="claim-evidence-map-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # --- fixtures -----------------------------------------------------------

    def _touch(self, rel_path: str) -> str:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")
        return rel_path

    def _entry(self, n: int, status: str = "partial", last_verified: str = "2026-06-05") -> dict:
        return {
            "id": f"claim-agent-safe-00{n}",
            "doc": "docs/claims/registry.yml",
            "locator": f"claims[id=CLAIM-AGENT-SAFE-00{n}]",
            "claim": f"Statement for claim {n}.",
            "status": status,
            "owner": "docs-mechanik",
            "last_verified": last_verified,
            "evidence": [
                {"kind": "file", "target": f"scripts/agent/impl_00{n}.py"},
                {"kind": "test", "target": f"scripts/agent/tests/test_00{n}.py"},
            ],
        }

    def _write_registry(self, entries: list) -> None:
        payload = {
            "kind": "lenskit.doc_freshness_registry",
            "version": "1.0",
            "entries": entries,
        }
        path = self.root / gen.REGISTRY_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _read_md(self) -> str:
        return (self.root / gen.MARKDOWN_REL).read_text(encoding="utf-8")

    # --- markdown shape ----------------------------------------------------

    def test_generates_markdown_with_frontmatter(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        md = self._read_md()
        self.assertTrue(md.startswith("---\n"))
        self.assertIn("id: docs.generated.claim-evidence-map", md)
        self.assertIn("| id | doc | locator | status | owner | last_verified | evidence |", md)

    def test_generated_markdown_contains_do_not_edit_banner(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        self.assertIn("Generated automatically. Do not edit.", self._read_md())

    def test_markdown_shows_entry_fields(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        md = self._read_md()
        self.assertIn("claim-agent-safe-001", md)
        self.assertIn("docs/claims/registry.yml", md)
        self.assertIn("claims[id=CLAIM-AGENT-SAFE-001]", md)
        self.assertIn("partial", md)
        self.assertIn("docs-mechanik", md)
        self.assertIn("2026-06-05", md)

    def test_evidence_column_shows_item_count(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        self.assertIn("| 2 items |", self._read_md())

    def test_entries_are_deterministic(self):
        # Registry order reversed; output must be sorted by id.
        self._write_registry([self._entry(3), self._entry(1), self._entry(2)])
        gen.generate(self.root)
        md = self._read_md()
        pos1 = md.index("claim-agent-safe-001")
        pos2 = md.index("claim-agent-safe-002")
        pos3 = md.index("claim-agent-safe-003")
        self.assertLess(pos1, pos2)
        self.assertLess(pos2, pos3)

    def test_generate_is_idempotent(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        first = self._read_md()
        gen.generate(self.root)
        self.assertEqual(first, self._read_md())

    def test_no_artifacts_claim_evidence_map_json_is_generated(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        json_path = self.root / "artifacts" / "docmeta" / "claim_evidence_map.json"
        self.assertFalse(json_path.exists(), "claim_evidence_map.json must not be generated")

    def test_no_date_today_dependent_computation_in_output(self):
        # The markdown must not contain freshness_status (current/stale/unknown)
        # derived from wall-clock time. It must contain last_verified instead.
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        md = self._read_md()
        self.assertNotIn("current", md)
        self.assertNotIn("stale", md)
        self.assertNotIn("unknown", md)
        self.assertIn("2026-06-05", md)

    # --- --check drift -----------------------------------------------------

    def test_check_passes_when_markdown_matches(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        self.assertEqual(gen.check(self.root), [])

    def test_check_fails_on_markdown_drift(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        md_path = self.root / gen.MARKDOWN_REL
        md_path.write_text(md_path.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        drift = gen.check(self.root)
        self.assertIn(gen.MARKDOWN_REL, drift)

    def test_check_does_not_include_json_artifact(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root)
        drift = gen.check(self.root)
        # Drift list must not mention any JSON path
        for path in drift:
            self.assertFalse(path.endswith(".json"), f"Unexpected JSON path in drift: {path}")

    # --- generator refuses invalid bridge registry -------------------------

    def test_generator_refuses_invalid_bridge_registry(self):
        # Write old-form registry (invalid for new validator)
        old_payload = {"version": 1, "entries": []}
        path = self.root / gen.REGISTRY_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(old_payload) + "\n", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            gen._validate_freshness_registry_or_raise(self.root)
        self.assertIn("Freshness registry validation failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
