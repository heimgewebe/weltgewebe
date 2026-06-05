import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

import scripts.docmeta.generate_claim_evidence_map as gen


class TestComputeFreshnessStatus(unittest.TestCase):
    def test_null_last_reviewed_yields_unknown(self):
        self.assertEqual(gen.compute_freshness_status(None, 90, today=date(2026, 6, 4)), "unknown")

    def test_old_last_reviewed_yields_stale(self):
        self.assertEqual(gen.compute_freshness_status("2026-01-01", 30, today=date(2026, 6, 4)), "stale")

    def test_fresh_last_reviewed_yields_current(self):
        self.assertEqual(gen.compute_freshness_status("2026-06-01", 90, today=date(2026, 6, 4)), "current")

    def test_boundary_age_equal_max_age_is_current(self):
        self.assertEqual(gen.compute_freshness_status("2026-05-05", 30, today=date(2026, 6, 4)), "current")

    def test_max_age_days_null_with_reviewed_date_yields_current(self):
        self.assertEqual(gen.compute_freshness_status("2000-01-01", None, today=date(2026, 6, 4)), "current")


class TestGenerateClaimEvidenceMap(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="claim-evidence-map-test-"))
        self.today = date(2026, 6, 4)

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # --- fixtures -----------------------------------------------------------

    def _entry(self, n: int, last_reviewed=None, max_age_days=90) -> dict:
        return {
            "id": f"freshness.claim.agent_safe_00{n}",
            "claim_ref": f"CLAIM-AGENT-SAFE-00{n}",
            "subject": {"kind": "claim", "ref": f"CLAIM-AGENT-SAFE-00{n}"},
            "evidence": [
                {"path": f"scripts/agent/impl_00{n}.py", "kind": "implementation"},
                {"path": f"scripts/agent/tests/test_00{n}.py", "kind": "test"},
            ],
            "freshness": {
                "review_policy": "manual",
                "max_age_days": max_age_days,
                "last_reviewed": last_reviewed,
            },
            "status": "active",
        }

    def _write_registry(self, entries: list) -> None:
        payload = {"version": 1, "entries": entries}
        path = self.root / gen.REGISTRY_REL
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _read_md(self) -> str:
        return (self.root / gen.MARKDOWN_REL).read_text(encoding="utf-8")

    def _read_json(self) -> dict:
        return json.loads((self.root / gen.JSON_REL).read_text(encoding="utf-8"))

    # --- markdown / json shape ---------------------------------------------

    def test_generates_markdown_with_frontmatter(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        md = self._read_md()
        self.assertTrue(md.startswith("---\n"))
        self.assertIn("id: docs.generated.claim-evidence-map", md)
        self.assertIn("| id | claim_ref | subject | evidence | freshness | status |", md)

    def test_generated_markdown_contains_do_not_edit_banner(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        self.assertIn("Generated automatically. Do not edit.", self._read_md())

    def test_generates_json_artifact(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        data = self._read_json()
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["source"], gen.REGISTRY_REL)
        self.assertEqual(data["generated_by"], gen.GENERATOR_REL)
        self.assertEqual(len(data["entries"]), 1)
        entry = data["entries"][0]
        self.assertEqual(entry["evidence_paths"], ["scripts/agent/impl_001.py", "scripts/agent/tests/test_001.py"])
        self.assertEqual(entry["evidence_kinds"], ["implementation", "test"])

    def test_generated_json_preserves_generated_report_kind(self):
        entry = self._entry(2)
        entry["evidence"] = [
            {"path": "scripts/docmeta/generate_agent_readiness.py", "kind": "implementation"},
            {"path": "scripts/docmeta/tests/test_generate_agent_readiness.py", "kind": "test"},
            {"path": "docs/_generated/agent-readiness.md", "kind": "generated-report"},
        ]
        self._write_registry([entry])
        gen.generate(self.root, today=self.today)
        kinds = self._read_json()["entries"][0]["evidence_kinds"]
        self.assertIn("generated-report", kinds)

    def test_generated_json_preserves_registry_kind(self):
        entry = self._entry(3)
        entry["evidence"] = [
            {"path": "docs/claims/registry.yml", "kind": "registry"},
            {"path": "docs/claims/README.md", "kind": "documentation"},
        ]
        self._write_registry([entry])
        gen.generate(self.root, today=self.today)
        kinds = self._read_json()["entries"][0]["evidence_kinds"]
        self.assertIn("registry", kinds)

    def test_entries_are_deterministic(self):
        # Registry order is reversed; output must be sorted by id.
        self._write_registry([self._entry(3), self._entry(1), self._entry(2)])
        gen.generate(self.root, today=self.today)
        ids = [e["id"] for e in self._read_json()["entries"]]
        self.assertEqual(
            ids,
            [
                "freshness.claim.agent_safe_001",
                "freshness.claim.agent_safe_002",
                "freshness.claim.agent_safe_003",
            ],
        )
        first = self._read_md()
        gen.generate(self.root, today=self.today)
        self.assertEqual(first, self._read_md())

    def test_evidence_column_shows_path_count(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        self.assertIn("| 2 paths |", self._read_md())

    # --- --check drift ------------------------------------------------------

    def test_check_passes_when_files_match(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        self.assertEqual(gen.check(self.root, today=self.today), [])

    def test_check_fails_when_markdown_drifts(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        md_path = self.root / gen.MARKDOWN_REL
        md_path.write_text(md_path.read_text(encoding="utf-8") + "\ndrift\n", encoding="utf-8")
        drift = gen.check(self.root, today=self.today)
        self.assertIn(gen.MARKDOWN_REL, drift)

    def test_check_fails_when_json_drifts(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        json_path = self.root / gen.JSON_REL
        json_path.write_text("{}\n", encoding="utf-8")
        drift = gen.check(self.root, today=self.today)
        self.assertIn(gen.JSON_REL, drift)

    def test_check_helper_returns_empty_list_when_files_match(self):
        self._write_registry([self._entry(1)])
        gen.generate(self.root, today=self.today)
        # No drift in the temp root, but main() targets REPO_ROOT; assert the
        # in-memory check helper drives the exit decision deterministically.
        self.assertEqual(gen.check(self.root, today=self.today), [])

    def test_validation_guard_rejects_invalid_registry_shape(self):
        self._write_registry([self._entry(1)])
        with self.assertRaises(ValueError) as ctx:
            gen._validate_freshness_registry_or_raise(self.root)
        self.assertIn("Freshness registry validation failed", str(ctx.exception))


    # --- freshness status surfaces in the output ---------------------------

    def test_null_last_reviewed_yields_unknown_in_output(self):
        self._write_registry([self._entry(1, last_reviewed=None)])
        gen.generate(self.root, today=self.today)
        entry = self._read_json()["entries"][0]
        self.assertEqual(entry["freshness"]["freshness_status"], "unknown")
        self.assertIn("| unknown |", self._read_md())

    def test_old_last_reviewed_yields_stale_in_output(self):
        self._write_registry([self._entry(1, last_reviewed="2026-01-01", max_age_days=30)])
        gen.generate(self.root, today=self.today)
        entry = self._read_json()["entries"][0]
        self.assertEqual(entry["freshness"]["freshness_status"], "stale")

    def test_fresh_last_reviewed_yields_current_in_output(self):
        self._write_registry([self._entry(1, last_reviewed="2026-06-01", max_age_days=90)])
        gen.generate(self.root, today=self.today)
        entry = self._read_json()["entries"][0]
        self.assertEqual(entry["freshness"]["freshness_status"], "current")

    def test_max_age_days_null_with_reviewed_date_yields_current_in_output(self):
        self._write_registry([self._entry(1, last_reviewed="2000-01-01", max_age_days=None)])
        gen.generate(self.root, today=self.today)
        entry = self._read_json()["entries"][0]
        self.assertEqual(entry["freshness"]["freshness_status"], "current")


if __name__ == "__main__":
    unittest.main()
