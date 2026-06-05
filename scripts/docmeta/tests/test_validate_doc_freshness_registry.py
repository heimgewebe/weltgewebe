import json
import shutil
import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.validate_doc_freshness_registry as validator


class TestValidateDocFreshnessRegistry(unittest.TestCase):
    # Canonical claim evidence, mirrored by both fixtures so the cross-check
    # passes in the valid baseline. It exercises every claim-registry kind,
    # including ``generated-report`` and ``registry``.
    EVIDENCE_SPEC = {
        1: [
            ("scripts/agent/impl_001.py", "implementation"),
            ("scripts/agent/tests/test_001.py", "test"),
            (".github/workflows/wf_001.yml", "ci"),
            ("docs/security/doc_001.md", "documentation"),
        ],
        2: [
            ("scripts/docmeta/impl_002.py", "implementation"),
            ("scripts/docmeta/tests/test_002.py", "test"),
            ("docs/_generated/report_002.md", "generated-report"),
        ],
        3: [
            ("docs/claims/reg_003.yml", "registry"),
            ("docs/claims/readme_003.md", "documentation"),
            ("scripts/docmeta/impl_003.py", "implementation"),
            ("scripts/docmeta/tests/test_003.py", "test"),
        ],
    }

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="freshness-registry-test-"))
        self.evidence: dict[int, list[dict]] = {}
        for n, pairs in self.EVIDENCE_SPEC.items():
            items = []
            for path, kind in pairs:
                self._touch(path)
                items.append({"path": path, "kind": kind})
            self.evidence[n] = items

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
    ) -> None:
        ev_map = evidence if evidence is not None else self.evidence
        claims = []
        for cid in claim_ids:
            n = int(cid.split("-")[-1])
            claims.append(
                {
                    "id": cid,
                    "status": "established",
                    "subject": cid.replace("CLAIM-", ""),
                    "statement": "fixture",
                    "evidence": ev_map[n],
                    "validation": ["echo ok"],
                    "updated": "2026-06-01",
                }
            )
        payload = {"version": 1, "claims": claims}
        path = self.root / "docs" / "claims" / "registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _copy_evidence(self, n: int) -> list[dict]:
        return [dict(item) for item in self.evidence[n]]

    def _valid_entry(self, n: int, evidence: list | None = None) -> dict:
        ev = evidence if evidence is not None else self._copy_evidence(n)
        return {
            "id": f"freshness.claim.agent_safe_00{n}",
            "claim_ref": f"CLAIM-AGENT-SAFE-00{n}",
            "subject": {"kind": "claim", "ref": f"CLAIM-AGENT-SAFE-00{n}"},
            "evidence": ev,
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

    # --- structural / slice-scope guards ------------------------------------

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
        existing = self._touch("docs/security/some-existing.md")
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
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "REGISTRY_LOAD_ERROR"))

    # --- claim cross-check (path, kind) -------------------------------------

    def test_same_path_but_different_kind_fails(self):
        self._write_claims()
        entries = self._entries()
        # impl_001.py is declared as "implementation" on the claim; relabel it.
        entries[0]["evidence"][0]["kind"] = "test"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))
        self.assertTrue(self._has(output, "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY"))

    def test_extra_existing_evidence_path_not_in_claim_registry_fails(self):
        self._write_claims()
        entries = self._entries()
        extra = self._touch("docs/extra-evidence.md")
        entries[0]["evidence"].append({"path": extra, "kind": "documentation"})
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))
        # The extra path exists, so this is not a path-existence problem.
        self.assertFalse(self._has(output, "EVIDENCE_PATH_MISSING"))

    def test_missing_claim_evidence_pair_in_freshness_registry_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["evidence"].pop()
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY"))

    def test_generated_report_kind_accepted_when_present_in_claim_registry(self):
        # Claim 2 declares docs/_generated/report_002.md as generated-report.
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertFalse(self._has(output, "EVIDENCE_KIND_INVALID"))
        self.assertIn(
            ("docs/_generated/report_002.md", "generated-report"),
            {(p, k) for p, k in self.EVIDENCE_SPEC[2]},
        )

    def test_registry_kind_accepted_when_present_in_claim_registry(self):
        # Claim 3 declares docs/claims/reg_003.yml as registry.
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertFalse(self._has(output, "EVIDENCE_KIND_INVALID"))
        self.assertIn(
            ("docs/claims/reg_003.yml", "registry"),
            {(p, k) for p, k in self.EVIDENCE_SPEC[3]},
        )

    def test_entry_id_must_match_claim_ref_suffix(self):
        self._write_claims()
        entries = self._entries()
        # entry id 001 paired with claim_ref 002 — coupling violated
        entries[0]["id"] = "freshness.claim.agent_safe_001"
        entries[0]["claim_ref"] = "CLAIM-AGENT-SAFE-002"
        entries[0]["subject"]["ref"] = "CLAIM-AGENT-SAFE-002"
        entries[0]["evidence"] = self._copy_evidence(2)
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "ENTRY_ID_CLAIM_REF_MISMATCH"))

    def test_guard_contract_report_kinds_rejected_in_this_slice(self):
        # Even a faithfully mirrored pair is rejected when its kind is outside
        # the slice taxonomy: the cross-check is clean but the kind is invalid.
        for kind in ("guard", "contract", "report"):
            with self.subTest(kind=kind):
                mirror_path = self._touch(f"scripts/docmeta/mirror_{kind}.sh")
                mirror = [{"path": mirror_path, "kind": kind}]
                ev_map = {1: mirror, 2: self.evidence[2], 3: self.evidence[3]}
                self._write_claims(evidence=ev_map)
                entries = self._entries()
                entries[0]["evidence"] = [dict(item) for item in mirror]
                self._write_registry(entries)
                output, exit_code = self._run()
                self.assertEqual(exit_code, 1)
                self.assertTrue(self._has(output, "EVIDENCE_KIND_INVALID"))
                self.assertFalse(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))
                self.assertFalse(self._has(output, "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY"))


if __name__ == "__main__":
    unittest.main()
