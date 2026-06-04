import json
import shutil
import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.validate_doc_freshness_registry as validator


class TestValidateDocFreshnessRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="freshness-registry-test-"))

    def tearDown(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    # --- fixtures -----------------------------------------------------------

    def _touch(self, rel_path: str, content: str = "fixture\n") -> str:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return rel_path

    def _write_claims(self, claim_ids=("CLAIM-AGENT-SAFE-001", "CLAIM-AGENT-SAFE-002", "CLAIM-AGENT-SAFE-003")) -> None:
        claims = {
            "version": 1,
            "claims": [
                {
                    "id": cid,
                    "status": "established",
                    "subject": cid.replace("CLAIM-", ""),
                    "statement": "fixture",
                    "evidence": [{"path": "docs/claims/README.md", "kind": "documentation"}],
                    "validation": ["echo ok"],
                    "updated": "2026-06-01",
                }
                for cid in claim_ids
            ],
        }
        path = self.root / "docs" / "claims" / "registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(claims, indent=2) + "\n", encoding="utf-8")

    def _evidence_for(self, n: int) -> list[dict]:
        impl = self._touch(f"scripts/agent/impl_00{n}.py")
        test = self._touch(f"scripts/agent/tests/test_00{n}.py")
        return [
            {"path": impl, "kind": "implementation"},
            {"path": test, "kind": "test"},
        ]

    def _valid_entry(self, n: int) -> dict:
        return {
            "id": f"freshness.claim.agent_safe_00{n}",
            "claim_ref": f"CLAIM-AGENT-SAFE-00{n}",
            "subject": {"kind": "claim", "ref": f"CLAIM-AGENT-SAFE-00{n}"},
            "evidence": self._evidence_for(n),
            "freshness": {"review_policy": "manual", "max_age_days": 90, "last_reviewed": None},
            "status": "active",
        }

    def _entries(self) -> list[dict]:
        return [self._valid_entry(1), self._valid_entry(2), self._valid_entry(3)]

    def _write_registry(self, entries: list, version: object = 1) -> None:
        payload = {"version": version, "entries": entries}
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

    def test_valid_registry_with_exactly_three_known_claims_passes(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertEqual(output["findings_count"], 0)
        self.assertEqual(output["entries_count"], 3)

    # --- negative cases -----------------------------------------------------

    def test_duplicate_entry_id_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[1]["id"] = entries[0]["id"]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "DUPLICATE_ID"))

    def test_missing_one_of_three_claims_fails(self):
        self._write_claims()
        entries = self._entries()[:2]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "WRONG_ENTRY_COUNT"))

    def test_extra_fourth_claim_fails(self):
        self._write_claims()
        entries = self._entries()
        entries.append(self._valid_entry(1))
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "WRONG_ENTRY_COUNT"))

    def test_unknown_claim_ref_fails(self):
        # Claim registry is missing CLAIM-AGENT-SAFE-003 although it is in scope.
        self._write_claims(claim_ids=("CLAIM-AGENT-SAFE-001", "CLAIM-AGENT-SAFE-002"))
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "CLAIM_REF_UNKNOWN"))

    def test_null_claim_ref_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["claim_ref"] = None
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "CLAIM_REF_NULL"))

    def test_subject_kind_other_than_claim_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["subject"]["kind"] = "document"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "SUBJECT_KIND_INVALID"))

    def test_subject_ref_different_from_claim_ref_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["subject"]["ref"] = "CLAIM-AGENT-SAFE-002"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "SUBJECT_REF_MISMATCH"))

    def test_absolute_evidence_path_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"] = [{"path": "/etc/hosts", "kind": "documentation"}]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_PATH_ABSOLUTE"))

    def test_parent_traversal_evidence_path_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"] = [{"path": "../outside.md", "kind": "documentation"}]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_PATH_TRAVERSAL"))

    def test_missing_evidence_path_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"] = [{"path": "scripts/agent/does_not_exist.py", "kind": "implementation"}]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_PATH_MISSING"))

    def test_empty_evidence_list_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"] = []
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_EMPTY"))

    def test_invalid_evidence_kind_fails(self):
        self._write_claims()
        entries = self._entries()
        existing = self._touch("docs/security/agent-write-scope-baseline.md")
        entries[0]["evidence"] = [{"path": existing, "kind": "screenshot"}]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_KIND_INVALID"))

    def test_invalid_review_policy_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["freshness"]["review_policy"] = "auto"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "REVIEW_POLICY_INVALID"))

    def test_invalid_max_age_days_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["freshness"]["max_age_days"] = 0
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "MAX_AGE_DAYS_INVALID"))

    def test_non_null_last_reviewed_fails_for_this_slice(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["freshness"]["last_reviewed"] = "2026-06-04"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "LAST_REVIEWED_NOT_NULL"))

    def test_invalid_last_reviewed_format_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["freshness"]["last_reviewed"] = "2026/06/04"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "LAST_REVIEWED_INVALID"))

    # --- slice-scope guards (status / version) ------------------------------

    def test_invalid_version_fails(self):
        self._write_claims()
        self._write_registry(self._entries(), version=2)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_VERSION"))

    def test_invalid_entry_id_pattern_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["id"] = "freshness.claim.agent_safe_009"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "INVALID_ID"))

    def test_status_not_active_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["status"] = "draft"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "STATUS_NOT_ACTIVE"))

    def test_missing_registry_file_fails(self):
        self._write_claims()
        output, exit_code = validator.run_validation(
            "docs/doc-freshness-registry.yml",
            "docs/claims/registry.yml",
            repo_root=self.root,
        )
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "REGISTRY_LOAD_ERROR"))


if __name__ == "__main__":
    unittest.main()
