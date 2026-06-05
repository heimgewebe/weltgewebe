import json
import shutil
import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.validate_doc_freshness_registry as validator


class TestValidateDocFreshnessRegistry(unittest.TestCase):
    # Evidence spec: (path, weltgewebe_kind, lenskit_kind)
    # Used to build both the claim registry and the bridge registry fixtures.
    EVIDENCE_SPEC = {
        1: [
            ("scripts/agent/impl_001.py", "implementation", "file"),
            ("scripts/agent/tests/test_001.py", "test", "test"),
            (".github/workflows/wf_001.yml", "ci", "file"),
            ("docs/security/doc_001.md", "documentation", "file"),
        ],
        2: [
            ("scripts/docmeta/impl_002.py", "implementation", "file"),
            ("scripts/docmeta/tests/test_002.py", "test", "test"),
            ("docs/_generated/report_002.md", "generated-report", "file"),
        ],
        3: [
            ("docs/claims/reg_003.yml", "registry", "file"),
            ("docs/claims/readme_003.md", "documentation", "file"),
            ("scripts/docmeta/impl_003.py", "implementation", "file"),
            ("scripts/docmeta/tests/test_003.py", "test", "test"),
        ],
    }

    CLAIM_STATEMENTS = {
        1: "Statement for claim 1.",
        2: "Statement for claim 2.",
        3: "Statement for claim 3.",
    }

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="freshness-registry-test-"))
        self.bridge_evidence: dict[int, list[dict]] = {}
        self.claim_evidence: dict[int, list[dict]] = {}
        for n, triples in self.EVIDENCE_SPEC.items():
            bridge_items = []
            claim_items = []
            for path, wg_kind, lenskit_kind in triples:
                self._touch(path)
                bridge_items.append({"kind": lenskit_kind, "target": path})
                claim_items.append({"path": path, "kind": wg_kind})
            self.bridge_evidence[n] = bridge_items
            self.claim_evidence[n] = claim_items

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # --- fixtures -----------------------------------------------------------

    def _touch(self, rel_path: str, content: str = "fixture\n") -> str:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return rel_path

    def _write_claims(
        self,
        evidence: dict[int, list[dict]] | None = None,
        claim_ids=("CLAIM-AGENT-SAFE-001", "CLAIM-AGENT-SAFE-002", "CLAIM-AGENT-SAFE-003"),
        statements: dict[str, str] | None = None,
    ) -> None:
        ev_map = evidence if evidence is not None else self.claim_evidence
        stmt_map = statements or {}
        claims = []
        for cid in claim_ids:
            n = int(cid.split("-")[-1])
            stmt = stmt_map.get(cid, self.CLAIM_STATEMENTS[n])
            claims.append(
                {
                    "id": cid,
                    "status": "established",
                    "subject": cid.replace("CLAIM-", ""),
                    "statement": stmt,
                    "evidence": ev_map[n],
                    "validation": ["echo ok"],
                    "updated": "2026-06-01",
                }
            )
        payload = {"version": 1, "claims": claims}
        path = self.root / "docs" / "claims" / "registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _copy_bridge_evidence(self, n: int) -> list[dict]:
        return [dict(item) for item in self.bridge_evidence[n]]

    def _valid_entry(self, n: int, evidence: list | None = None) -> dict:
        ev = evidence if evidence is not None else self._copy_bridge_evidence(n)
        return {
            "id": f"claim-agent-safe-00{n}",
            "doc": "docs/claims/registry.yml",
            "locator": f"claims[id=CLAIM-AGENT-SAFE-00{n}]",
            "claim": self.CLAIM_STATEMENTS[n],
            "status": "partial",
            "owner": "docs-mechanik",
            "last_verified": "2026-06-05",
            "evidence": ev,
        }

    def _entries(self) -> list[dict]:
        return [self._valid_entry(1), self._valid_entry(2), self._valid_entry(3)]

    def _write_registry(
        self,
        entries: list,
        kind: str = "lenskit.doc_freshness_registry",
        version: object = "1.0",
    ) -> None:
        payload: dict = {"kind": kind, "version": version, "entries": entries}
        path = self.root / "docs" / "doc-freshness-registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _run(self):
        return validator.run_validation(
            "docs/doc-freshness-registry.yml",
            "docs/claims/registry.yml",
            repo_root=self.root,
        )

    def _has(self, output, code: str) -> bool:
        return any(f["code"] == code for f in output["findings"])

    # --- positive case ------------------------------------------------------

    def test_valid_lenskit_bridge_registry_passes(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertEqual(output["findings_count"], 0)
        self.assertEqual(output["entries_count"], 3)

    # --- top-level schema checks -------------------------------------------

    def test_missing_top_level_kind_fails(self):
        self._write_claims()
        payload = {"version": "1.0", "entries": self._entries()}
        path = self.root / "docs" / "doc-freshness-registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload) + "\n", encoding="utf-8")
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_KIND"))

    def test_wrong_kind_fails(self):
        self._write_claims()
        self._write_registry(self._entries(), kind="weltgewebe.freshness")
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_KIND"))

    def test_version_integer_fails(self):
        self._write_claims()
        self._write_registry(self._entries(), version=1)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_VERSION"))

    def test_wrong_version_string_fails(self):
        self._write_claims()
        self._write_registry(self._entries(), version="2.0")
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_VERSION"))

    def test_old_custom_form_registry_fails(self):
        # Old Weltgewebe form: version=1 (int), claim_ref, subject, freshness, status=active
        old_entry = {
            "id": "freshness.claim.agent_safe_001",
            "claim_ref": "CLAIM-AGENT-SAFE-001",
            "subject": {"kind": "claim", "ref": "CLAIM-AGENT-SAFE-001"},
            "evidence": [{"path": "scripts/agent/impl_001.py", "kind": "implementation"}],
            "freshness": {"review_policy": "manual", "max_age_days": 90, "last_reviewed": None},
            "status": "active",
        }
        payload = {"version": 1, "entries": [old_entry]}
        path = self.root / "docs" / "doc-freshness-registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload) + "\n", encoding="utf-8")
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        # Must fail on kind and version at minimum
        self.assertTrue(self._has(output, "INVALID_KIND") or self._has(output, "INVALID_VERSION"))

    # --- entry id checks ---------------------------------------------------

    def test_entry_id_with_dots_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["id"] = "freshness.claim.agent_safe_001"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_ID"))

    def test_entry_id_with_underscores_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["id"] = "claim_agent_safe_001"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_ID"))

    def test_entry_id_out_of_valid_set_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["id"] = "claim-agent-safe-009"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_ID"))

    def test_duplicate_entry_id_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[1]["id"] = entries[0]["id"]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "DUPLICATE_ID"))

    # --- entry count -------------------------------------------------------

    def test_missing_one_of_three_entries_fails(self):
        self._write_claims()
        self._write_registry(self._entries()[:2])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "WRONG_ENTRY_COUNT"))

    def test_extra_fourth_entry_fails(self):
        self._write_claims()
        entries = self._entries()
        entries.append(self._valid_entry(1))
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "WRONG_ENTRY_COUNT"))

    # --- status checks -----------------------------------------------------

    def test_status_active_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["status"] = "active"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_STATUS") or self._has(output, "STATUS_NOT_PARTIAL"))

    def test_status_done_fails_for_this_slice(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["status"] = "done"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "STATUS_NOT_PARTIAL"))

    def test_status_partial_passes(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])

    def test_invalid_status_string_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["status"] = "draft"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_STATUS"))

    # --- doc field ---------------------------------------------------------

    def test_missing_doc_fails(self):
        self._write_claims()
        entries = self._entries()
        del entries[0]["doc"]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "DOC_MISMATCH"))

    def test_doc_other_than_claims_registry_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["doc"] = "docs/other.yml"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "DOC_MISMATCH"))

    # --- locator field -----------------------------------------------------

    def test_missing_locator_fails(self):
        self._write_claims()
        entries = self._entries()
        del entries[0]["locator"]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "LOCATOR_MISSING"))

    def test_locator_not_matching_claim_id_fails(self):
        self._write_claims()
        entries = self._entries()
        # entry id implies CLAIM-AGENT-SAFE-001 but locator implies 002
        entries[0]["locator"] = "claims[id=CLAIM-AGENT-SAFE-002]"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "ENTRY_ID_CLAIM_MISMATCH"))

    # --- claim statement ---------------------------------------------------

    def test_claim_statement_mismatch_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["claim"] = "Something completely different."
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "CLAIM_STATEMENT_MISMATCH"))

    # --- owner field -------------------------------------------------------

    def test_missing_owner_fails(self):
        self._write_claims()
        entries = self._entries()
        del entries[0]["owner"]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "OWNER_MISSING"))

    def test_empty_owner_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["owner"] = ""
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "OWNER_MISSING"))

    # --- last_verified field -----------------------------------------------

    def test_invalid_last_verified_format_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["last_verified"] = "2026/06/05"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "LAST_VERIFIED_INVALID"))

    def test_missing_last_verified_fails(self):
        self._write_claims()
        entries = self._entries()
        del entries[0]["last_verified"]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "LAST_VERIFIED_INVALID"))

    def test_null_last_verified_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["last_verified"] = None
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "LAST_VERIFIED_INVALID"))

    def test_valid_last_verified_passes(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])

    # --- evidence target path checks ---------------------------------------

    def test_evidence_target_path_exists_passes(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])

    def test_absolute_target_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"][0]["target"] = "/etc/hosts"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_TARGET_ABSOLUTE"))

    def test_parent_traversal_target_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"][0]["target"] = "../outside.md"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_TARGET_TRAVERSAL"))

    def test_missing_target_file_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"][0]["target"] = "scripts/agent/does_not_exist.py"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_TARGET_MISSING"))

    def test_empty_evidence_list_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"] = []
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_EMPTY"))

    # --- evidence kind checks ----------------------------------------------

    def test_wrong_lenskit_evidence_kind_fails(self):
        self._write_claims()
        entries = self._entries()
        existing = self._touch("docs/security/some-existing.md")
        entries[0]["evidence"] = [{"target": existing, "kind": "screenshot"}]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_KIND_INVALID"))

    def test_old_weltgewebe_kind_implementation_rejected_as_lenskit_kind(self):
        # 'implementation' is not a valid Lenskit evidence kind
        self._write_claims()
        entries = self._entries()
        existing = self._touch("scripts/agent/impl_test.py")
        entries[0]["evidence"] = [{"target": existing, "kind": "implementation"}]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_KIND_INVALID"))

    # --- evidence cross-check: (target, kind) set equality -----------------

    def test_same_target_but_wrong_mapped_kind_fails(self):
        # scripts/agent/impl_001.py maps implementation -> file.
        # Using 'test' instead of 'file' is wrong.
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"][0]["kind"] = "test"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))
        self.assertTrue(self._has(output, "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY"))

    def test_extra_target_not_in_claim_registry_fails(self):
        self._write_claims()
        entries = self._entries()
        extra = self._touch("docs/extra-evidence.md")
        entries[0]["evidence"].append({"target": extra, "kind": "file"})
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))
        self.assertFalse(self._has(output, "EVIDENCE_TARGET_MISSING"))

    def test_missing_target_from_claim_registry_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"].pop()
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY"))

    # --- kind mapping correctness ------------------------------------------

    def test_generated_report_in_claim_registry_maps_to_file(self):
        # Claim 2: docs/_generated/report_002.md as generated-report -> bridge uses 'file'
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        generated_report_triples = [t for t in self.EVIDENCE_SPEC[2] if t[1] == "generated-report"]
        self.assertTrue(generated_report_triples)
        for _path, _wg_kind, lenskit_kind in generated_report_triples:
            self.assertEqual(lenskit_kind, "file")

    def test_registry_in_claim_registry_maps_to_file(self):
        # Claim 3: docs/claims/reg_003.yml as registry -> bridge uses 'file'
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        registry_triples = [t for t in self.EVIDENCE_SPEC[3] if t[1] == "registry"]
        self.assertTrue(registry_triples)
        for _path, _wg_kind, lenskit_kind in registry_triples:
            self.assertEqual(lenskit_kind, "file")

    def test_test_in_claim_registry_maps_to_test(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        test_triples = [t for t in self.EVIDENCE_SPEC[1] if t[1] == "test"]
        self.assertTrue(test_triples)
        for _path, _wg_kind, lenskit_kind in test_triples:
            self.assertEqual(lenskit_kind, "test")

    def test_ci_kind_maps_to_file(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        ci_triples = [t for t in self.EVIDENCE_SPEC[1] if t[1] == "ci"]
        self.assertTrue(ci_triples)
        for _path, _wg_kind, lenskit_kind in ci_triples:
            self.assertEqual(lenskit_kind, "file")

    def test_documentation_kind_maps_to_file(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        doc_triples = [t for t in self.EVIDENCE_SPEC[1] if t[1] == "documentation"]
        self.assertTrue(doc_triples)
        for _path, _wg_kind, lenskit_kind in doc_triples:
            self.assertEqual(lenskit_kind, "file")

    # --- missing registry file ---------------------------------------------

    def test_missing_registry_file_fails(self):
        self._write_claims()
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "REGISTRY_LOAD_ERROR"))


if __name__ == "__main__":
    unittest.main()
