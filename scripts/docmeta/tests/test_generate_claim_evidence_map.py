import json
import shutil
import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.generate_claim_evidence_map as gen


class TestGenerateClaimEvidenceMap(unittest.TestCase):
    EVIDENCE_SPEC = {
        1: [
            ("scripts/agent/impl_001.py", "implementation", "file"),
            ("scripts/agent/tests/test_001.py", "test", "test"),
        ],
        2: [
            ("scripts/docmeta/impl_002.py", "implementation", "file"),
            ("scripts/docmeta/tests/test_002.py", "test", "test"),
        ],
        3: [
            ("docs/claims/readme_003.md", "documentation", "file"),
            ("scripts/docmeta/tests/test_003.py", "test", "test"),
        ],
    }

    CLAIM_STATEMENTS = {
        1: "Statement for claim 1.",
        2: "Statement for claim 2.",
        3: "Statement for claim 3.",
    }

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="claim-evidence-map-test-"))
        self.bridge_evidence: dict[int, list[dict]] = {}
        self.claim_evidence: dict[int, list[dict]] = {}

        for n, triples in self.EVIDENCE_SPEC.items():
            bridge_items = []
            claim_items = []
            for path, claim_kind, lenskit_kind in triples:
                self._touch(path)
                bridge_items.append({"kind": lenskit_kind, "target": path})
                claim_items.append({"path": path, "kind": claim_kind})
            self.bridge_evidence[n] = bridge_items
            self.claim_evidence[n] = claim_items

        self._write_claims()

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # --- fixtures -----------------------------------------------------------

    def _touch(self, rel_path: str, content: str = "fixture\n") -> str:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return rel_path

    def _write_claims(self) -> None:
        claims = []
        for n in (1, 2, 3):
            claims.append(
                {
                    "id": f"CLAIM-AGENT-SAFE-00{n}",
                    "status": "established",
                    "subject": f"AGENT-SAFE-00{n}",
                    "statement": self.CLAIM_STATEMENTS[n],
                    "evidence": self.claim_evidence[n],
                    "validation": ["echo ok"],
                    "updated": "2026-06-01",
                }
            )

        payload = {"version": 1, "claims": claims}
        path = self.root / "docs" / "claims" / "registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _entry(self, n: int) -> dict:
        return {
            "id": f"claim-agent-safe-00{n}",
            "doc": "docs/claims/registry.yml",
            "locator": f"claims[id=CLAIM-AGENT-SAFE-00{n}]",
            "claim": self.CLAIM_STATEMENTS[n],
            "status": "partial",
            "owner": "docs-mechanik",
            "last_verified": "2026-06-05",
            "evidence": [dict(item) for item in self.bridge_evidence[n]],
        }

    def _entries(self) -> list[dict]:
        return [self._entry(1), self._entry(2), self._entry(3)]

    def _write_registry(self, entries: list[dict] | None = None) -> None:
        payload = {
            "kind": "lenskit.doc_freshness_registry",
            "version": "1.0",
            "entries": entries if entries is not None else self._entries(),
        }
        path = self.root / gen.REGISTRY_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _write_invalid_old_registry(self) -> None:
        payload = {"version": 1, "entries": []}
        path = self.root / gen.REGISTRY_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload) + "\n", encoding="utf-8")

    def _read_md(self) -> str:
        return (self.root / gen.MARKDOWN_REL).read_text(encoding="utf-8")

    # --- markdown shape -----------------------------------------------------

    def test_generates_markdown_with_frontmatter(self):
        self._write_registry()
        gen.generate(self.root)
        md = self._read_md()
        self.assertTrue(md.startswith("---\n"))
        self.assertIn("id: docs.generated.claim-evidence-map", md)
        self.assertIn("| id | doc | locator | status | owner | last_verified | evidence |", md)

    def test_generated_markdown_contains_do_not_edit_banner(self):
        self._write_registry()
        gen.generate(self.root)
        self.assertIn("Generated automatically. Do not edit.", self._read_md())

    def test_markdown_shows_entry_fields(self):
        self._write_registry()
        gen.generate(self.root)
        md = self._read_md()
        self.assertIn("claim-agent-safe-001", md)
        self.assertIn("docs/claims/registry.yml", md)
        self.assertIn("claims[id=CLAIM-AGENT-SAFE-001]", md)
        self.assertIn("partial", md)
        self.assertIn("docs-mechanik", md)
        self.assertIn("2026-06-05", md)

    def test_evidence_column_shows_item_count(self):
        self._write_registry()
        gen.generate(self.root)
        self.assertIn("| 2 items |", self._read_md())

    def test_entries_are_deterministic(self):
        self._write_registry([self._entry(3), self._entry(1), self._entry(2)])
        gen.generate(self.root)
        md = self._read_md()
        pos1 = md.index("claim-agent-safe-001")
        pos2 = md.index("claim-agent-safe-002")
        pos3 = md.index("claim-agent-safe-003")
        self.assertLess(pos1, pos2)
        self.assertLess(pos2, pos3)

    def test_generate_is_idempotent(self):
        self._write_registry()
        gen.generate(self.root)
        first = self._read_md()
        gen.generate(self.root)
        self.assertEqual(first, self._read_md())

    def test_no_artifacts_claim_evidence_map_json_is_generated(self):
        self._write_registry()
        gen.generate(self.root)
        json_path = self.root / "artifacts" / "docmeta" / "claim_evidence_map.json"
        self.assertFalse(json_path.exists(), "claim_evidence_map.json must not be generated")

    def test_no_date_today_dependent_computation_in_output(self):
        self._write_registry()
        gen.generate(self.root)
        md = self._read_md()
        self.assertNotIn("freshness_status", md)
        self.assertNotIn("current", md)
        self.assertNotIn("stale", md)
        self.assertNotIn("unknown", md)
        self.assertIn("2026-06-05", md)

    # --- --check drift ------------------------------------------------------

    def test_check_passes_when_markdown_matches(self):
        self._write_registry()
        gen.generate(self.root)
        self.assertEqual(gen.check(self.root), [])

    def test_check_fails_on_markdown_drift(self):
        self._write_registry()
        gen.generate(self.root)
        md_path = self.root / gen.MARKDOWN_REL
        md_path.write_text(md_path.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        drift = gen.check(self.root)
        self.assertIn(gen.MARKDOWN_REL, drift)

    def test_check_does_not_include_json_artifact(self):
        self._write_registry()
        gen.generate(self.root)
        drift = gen.check(self.root)
        for path in drift:
            self.assertFalse(path.endswith(".json"), f"Unexpected JSON path in drift: {path}")

    # --- invalid registry guards -------------------------------------------

    def test_validation_guard_rejects_invalid_registry_shape(self):
        self._write_invalid_old_registry()
        with self.assertRaises(ValueError) as ctx:
            gen._validate_freshness_registry_or_raise(self.root)
        self.assertIn("Freshness registry validation failed", str(ctx.exception))

    def test_generate_rejects_invalid_bridge_registry(self):
        self._write_invalid_old_registry()

        with self.assertRaises(ValueError) as ctx:
            gen.generate(self.root)

        self.assertIn("Freshness registry validation failed", str(ctx.exception))
        self.assertFalse((self.root / gen.MARKDOWN_REL).exists())

    def test_check_rejects_invalid_bridge_registry(self):
        self._write_invalid_old_registry()

        with self.assertRaises(ValueError) as ctx:
            gen.check(self.root)

        self.assertIn("Freshness registry validation failed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
