import json
import os
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
        # Every test runs against a temp repo, so the scope policy must live
        # there too. The default policy mirrors the real conservative scope.
        self._write_policy()

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
        claim_ids=(
            "CLAIM-AGENT-SAFE-001",
            "CLAIM-AGENT-SAFE-002",
            "CLAIM-AGENT-SAFE-003",
        ),
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
        path.write_text(
            "---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

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
        path.write_text(
            "---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    # --- scope policy fixtures ---------------------------------------------

    def _policy_path(self) -> Path:
        return self.root / "scripts" / "docmeta" / "freshness_scope_policy.yml"

    def _default_policy_families(self) -> list[dict]:
        return [
            {
                "id": "agent-safe",
                "claim_id_prefix": "CLAIM-AGENT-SAFE-",
                "entry_id_prefix": "claim-agent-safe-",
                "registry_doc": "docs/claims/registry.yml",
                "mirror_mode": "exact",
                "require_live_check": True,
                "status": "active",
            }
        ]

    def _write_policy(
        self,
        families: list[dict] | None = None,
        kind: str = "weltgewebe.docmeta.freshness_scope_policy",
        version: str = "1.0",
    ) -> None:
        families = self._default_policy_families() if families is None else families
        lines = [f"kind: {kind}", f'version: "{version}"', "", "families:"]
        for fam in families:
            first = True
            for key, value in fam.items():
                if isinstance(value, bool):
                    rendered = "true" if value else "false"
                else:
                    rendered = str(value)
                prefix = "  - " if first else "    "
                lines.append(f"{prefix}{key}: {rendered}")
                first = False
        self._write_policy_text("\n".join(lines) + "\n")

    def _write_policy_text(self, text: str) -> None:
        path = self._policy_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def _remove_policy(self) -> None:
        path = self._policy_path()
        if path.exists():
            path.unlink()

    # --- arbitrary claim/entry pairs ---------------------------------------

    def _write_claims_list(self, claims: list[dict]) -> None:
        payload = {"version": 1, "claims": claims}
        path = self.root / "docs" / "claims" / "registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n" + json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

    def _write_claims_list_at(self, rel_path: str, claims: list[dict]) -> None:
        payload = {"version": 1, "claims": claims}
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n" + json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    def _pair(
        self,
        claim_id: str,
        entry_id: str,
        statement: str | None = None,
        evidence: list[tuple[str, str, str]] | None = None,
    ) -> tuple[dict, dict]:
        """Build a mirrored (claim, entry) pair and touch its evidence files.

        evidence is a list of (path, weltgewebe_kind, lenskit_kind). The default
        carries a documentation file plus a test, so require_live_check passes.
        """
        if statement is None:
            statement = f"Statement for {claim_id}."
        if evidence is None:
            evidence = [
                (f"docs/pair/{entry_id}.md", "documentation", "file"),
                (f"scripts/pair/test_{entry_id}.py", "test", "test"),
            ]
        claim_items = []
        bridge_items = []
        for path, wg_kind, lenskit_kind in evidence:
            self._touch(path)
            claim_items.append({"path": path, "kind": wg_kind})
            bridge_items.append({"kind": lenskit_kind, "target": path})
        claim = {
            "id": claim_id,
            "status": "established",
            "subject": claim_id.replace("CLAIM-", ""),
            "statement": statement,
            "evidence": claim_items,
            "validation": ["echo ok"],
            "updated": "2026-06-01",
        }
        entry = {
            "id": entry_id,
            "doc": "docs/claims/registry.yml",
            "locator": f"claims[id={claim_id}]",
            "claim": statement,
            "status": "partial",
            "owner": "docs-mechanik",
            "last_verified": "2026-06-05",
            "evidence": bridge_items,
        }
        return claim, entry

    def _run(self):
        return validator.run_validation(
            "docs/doc-freshness-registry.yml",
            "docs/claims/registry.yml",
            repo_root=self.root,
        )

    def _has(self, output, code: str) -> bool:
        return any(f["code"] == code for f in output["findings"])

    def _messages(self, output, code: str) -> list[str]:
        return [f["message"] for f in output["findings"] if f["code"] == code]

    # --- positive case ------------------------------------------------------

    def test_valid_lenskit_bridge_registry_passes(self):
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertEqual(output["findings_count"], 0)
        self.assertEqual(output["entries_count"], 3)

    def test_block_yaml_registry_passes_without_pyyaml(self):
        self._write_claims()
        path = self.root / "docs" / "doc-freshness-registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            """---
kind: lenskit.doc_freshness_registry
version: "1.0"
entries:
  - id: claim-agent-safe-001
    doc: docs/claims/registry.yml
    locator: claims[id=CLAIM-AGENT-SAFE-001]
    claim: >-
      Statement for claim 1.
    status: partial
    owner: docs-mechanik
    last_verified: "2026-06-05"
    evidence:
      - kind: file
        target: scripts/agent/impl_001.py
      - kind: test
        target: scripts/agent/tests/test_001.py
      - kind: file
        target: .github/workflows/wf_001.yml
      - kind: file
        target: docs/security/doc_001.md

  - id: claim-agent-safe-002
    doc: docs/claims/registry.yml
    locator: claims[id=CLAIM-AGENT-SAFE-002]
    claim: >-
      Statement for claim 2.
    status: partial
    owner: docs-mechanik
    last_verified: "2026-06-05"
    evidence:
      - kind: file
        target: scripts/docmeta/impl_002.py
      - kind: test
        target: scripts/docmeta/tests/test_002.py
      - kind: file
        target: docs/_generated/report_002.md

  - id: claim-agent-safe-003
    doc: docs/claims/registry.yml
    locator: claims[id=CLAIM-AGENT-SAFE-003]
    claim: >-
      Statement for claim 3.
    status: partial
    owner: docs-mechanik
    last_verified: "2026-06-05"
    evidence:
      - kind: file
        target: docs/claims/reg_003.yml
      - kind: file
        target: docs/claims/readme_003.md
      - kind: file
        target: scripts/docmeta/impl_003.py
      - kind: test
        target: scripts/docmeta/tests/test_003.py
""",
            encoding="utf-8",
        )

        original_yaml = validator.yaml
        try:
            validator.yaml = None
            output, exit_code = self._run()
        finally:
            validator.yaml = original_yaml

        self.assertEqual(exit_code, 0, output["findings"])
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
            "evidence": [
                {"path": "scripts/agent/impl_001.py", "kind": "implementation"}
            ],
            "freshness": {
                "review_policy": "manual",
                "max_age_days": 90,
                "last_reviewed": None,
            },
            "status": "active",
        }
        payload = {"version": 1, "entries": [old_entry]}
        path = self.root / "docs" / "doc-freshness-registry.yml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + json.dumps(payload) + "\n", encoding="utf-8")
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        # Must fail on kind and version at minimum
        self.assertTrue(
            self._has(output, "INVALID_KIND") or self._has(output, "INVALID_VERSION")
        )

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

    def test_entry_id_for_unknown_claim_fails(self):
        # Replaces the old static VALID_ENTRY_IDS membership check: an entry id
        # inside the active family prefix but without a backing claim now fails
        # as an unknown claim, derived from claim-registry + policy.
        self._write_claims()
        entries = self._entries()
        entries[0]["id"] = "claim-agent-safe-009"
        entries[0]["locator"] = "claims[id=CLAIM-AGENT-SAFE-009]"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "CLAIM_ID_UNKNOWN"))

    def test_duplicate_entry_id_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[1]["id"] = entries[0]["id"]
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "DUPLICATE_ID"))

    # --- exact mirror (count is now derived from claims + policy) ----------

    def test_missing_one_of_three_entries_fails(self):
        # An in-scope claim without a mirror entry is detected by the
        # exact-mirror reverse check, not a static count.
        self._write_claims()
        self._write_registry(self._entries()[:2])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_ENTRY_MISSING_FOR_CLAIM"))

    def test_extra_fourth_entry_fails(self):
        # A duplicate extra entry now fails on the duplicate id rather than a
        # static count limit.
        self._write_claims()
        entries = self._entries()
        entries.append(self._valid_entry(1))
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "DUPLICATE_ID"))

    # --- status checks -----------------------------------------------------

    def test_status_active_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["status"] = "active"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            self._has(output, "INVALID_STATUS")
            or self._has(output, "STATUS_NOT_PARTIAL")
        )

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

    def test_nonexistent_last_verified_calendar_date_fails(self):
        self._write_claims()
        entries = self._entries()
        entries[0]["last_verified"] = "2026-99-99"
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

    def test_directory_target_fails_for_file_like_evidence_kind(self):
        directory_rel = "docs/evidence-directory"
        (self.root / directory_rel).mkdir(parents=True, exist_ok=True)

        claim_evidence = {
            1: [{"path": directory_rel, "kind": "documentation"}],
            2: self.claim_evidence[2],
            3: self.claim_evidence[3],
        }
        self._write_claims(evidence=claim_evidence)

        entries = self._entries()
        entries[0]["evidence"] = [{"kind": "file", "target": directory_rel}]
        self._write_registry(entries)

        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_TARGET_MISSING"))
        self.assertFalse(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))

    def test_symlink_target_outside_repo_fails(self):
        if not hasattr(os, "symlink"):
            self.skipTest("os.symlink is not available")

        outside_dir = Path(tempfile.mkdtemp(prefix="freshness-outside-"))
        self.addCleanup(lambda: shutil.rmtree(outside_dir, ignore_errors=True))
        outside_file = outside_dir / "outside.md"
        outside_file.write_text("outside\n", encoding="utf-8")

        link_rel = "docs/outside-link.md"
        link_path = self.root / link_rel
        link_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            os.symlink(outside_file, link_path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation not supported: {exc}")

        claim_evidence = {
            1: [{"path": link_rel, "kind": "documentation"}],
            2: self.claim_evidence[2],
            3: self.claim_evidence[3],
        }
        self._write_claims(evidence=claim_evidence)

        entries = self._entries()
        entries[0]["evidence"] = [{"kind": "file", "target": link_rel}]
        self._write_registry(entries)

        output, exit_code = self._run()

        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_TARGET_TRAVERSAL"))
        self.assertFalse(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))
        self.assertFalse(self._has(output, "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY"))

    def test_symlink_loop_target_fails_as_missing(self):
        if not hasattr(os, "symlink"):
            self.skipTest("os.symlink is not available")

        link_rel = "docs/self-loop.md"
        link_path = self.root / link_rel
        link_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            os.symlink(link_path, link_path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation not supported: {exc}")

        claim_evidence = {
            1: [{"path": link_rel, "kind": "documentation"}],
            2: self.claim_evidence[2],
            3: self.claim_evidence[3],
        }
        self._write_claims(evidence=claim_evidence)

        entries = self._entries()
        entries[0]["evidence"] = [{"kind": "file", "target": link_rel}]
        self._write_registry(entries)

        output, exit_code = self._run()

        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "EVIDENCE_TARGET_MISSING"))
        self.assertFalse(self._has(output, "EVIDENCE_TARGET_TRAVERSAL"))
        self.assertFalse(self._has(output, "EVIDENCE_NOT_IN_CLAIM_REGISTRY"))
        self.assertFalse(self._has(output, "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY"))

    def test_symlink_target_inside_repo_passes(self):
        if not hasattr(os, "symlink"):
            self.skipTest("os.symlink is not available")

        real_rel = "docs/real-evidence.md"
        link_rel = "docs/internal-link.md"
        real_path = self.root / real_rel
        link_path = self.root / link_rel

        real_path.parent.mkdir(parents=True, exist_ok=True)
        real_path.write_text("inside\n", encoding="utf-8")

        try:
            os.symlink(real_path, link_path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlink creation not supported: {exc}")

        claim_evidence = {
            1: [{"path": link_rel, "kind": "documentation"}],
            2: self.claim_evidence[2],
            3: self.claim_evidence[3],
        }
        self._write_claims(evidence=claim_evidence)

        entries = self._entries()
        entries[0]["evidence"] = [{"kind": "file", "target": link_rel}]
        self._write_registry(entries)

        output, exit_code = self._run()

        self.assertEqual(exit_code, 0, output["findings"])

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
        generated_report_triples = [
            t for t in self.EVIDENCE_SPEC[2] if t[1] == "generated-report"
        ]
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

    def test_missing_claim_registry_skips_claim_dependent_checks(self):
        self._write_registry([self._valid_entry(1)])
        # Do not write claims registry so it fails to load

        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "CLAIM_REGISTRY_LOAD_ERROR"))

        for code in (
            "CLAIM_ID_UNKNOWN",
            "CLAIM_STATEMENT_MISMATCH",
            "EVIDENCE_NOT_IN_CLAIM_REGISTRY",
            "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY",
            "EVIDENCE_KIND_MAPPING_INVALID",
        ):
            self.assertFalse(self._has(output, code), code)

    def test_duplicate_claim_id_is_detected_when_claim_registry_missing(self):
        entries = self._entries()
        entries[1]["id"] = entries[0]["id"]
        entries[1]["locator"] = entries[0]["locator"]
        entries[1]["claim"] = entries[0]["claim"]

        self._write_registry(entries)
        # Do not write docs/claims/registry.yml

        output, exit_code = self._run()

        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "CLAIM_REGISTRY_LOAD_ERROR"))
        self.assertTrue(self._has(output, "DUPLICATE_CLAIM_ID"))
        self.assertFalse(self._has(output, "CLAIM_ID_UNKNOWN"))

    # --- scope policy: derived scope, mirror, out-of-scope, live-check ------

    def test_real_agent_safe_slice_passes_under_policy(self):
        # A: the current conservative slice (three CLAIM-AGENT-SAFE-* mirrors)
        # plus the default policy validates clean.
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertEqual(output["findings_count"], 0)
        self.assertEqual(output["entries_count"], 3)

    def test_policy_allows_additional_same_family_claim(self):
        # B: scope is derived from claim-registry + policy, not a static 3-id
        # list. A fourth CLAIM-AGENT-SAFE-* claim with a mirrored entry passes.
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        c2, e2 = self._pair("CLAIM-AGENT-SAFE-002", "claim-agent-safe-002")
        c3, e3 = self._pair("CLAIM-AGENT-SAFE-003", "claim-agent-safe-003")
        c4, e4 = self._pair("CLAIM-AGENT-SAFE-004", "claim-agent-safe-004")
        self._write_claims_list([c1, c2, c3, c4])
        self._write_registry([e1, e2, e3, e4])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertEqual(output["findings_count"], 0)
        self.assertEqual(output["entries_count"], 4)

    def test_missing_mirror_entry_for_additional_claim_fails(self):
        # C: an in-scope claim (here a fourth one) without a mirror entry is a
        # finding, proving the expectation is derived, not capped at three.
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        c2, e2 = self._pair("CLAIM-AGENT-SAFE-002", "claim-agent-safe-002")
        c3, e3 = self._pair("CLAIM-AGENT-SAFE-003", "claim-agent-safe-003")
        c4, _e4 = self._pair("CLAIM-AGENT-SAFE-004", "claim-agent-safe-004")
        self._write_claims_list([c1, c2, c3, c4])
        self._write_registry([e1, e2, e3])  # entry for claim 004 missing
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_ENTRY_MISSING_FOR_CLAIM"))

    def test_out_of_scope_entry_fails(self):
        # D: a freshness entry for a claim family with no active policy family
        # is rejected as out of scope.
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        c2, e2 = self._pair("CLAIM-AGENT-SAFE-002", "claim-agent-safe-002")
        c3, e3 = self._pair("CLAIM-AGENT-SAFE-003", "claim-agent-safe-003")
        self._write_claims_list([c1, c2, c3])
        extra = self._touch("docs/deploy/evidence.md")
        out_of_scope_entry = {
            "id": "claim-deploy-001",
            "doc": "docs/claims/registry.yml",
            "locator": "claims[id=CLAIM-DEPLOY-001]",
            "claim": "Out of scope claim.",
            "status": "partial",
            "owner": "docs-mechanik",
            "last_verified": "2026-06-05",
            "evidence": [{"kind": "file", "target": extra}],
        }
        self._write_registry([e1, e2, e3, out_of_scope_entry])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_ENTRY_OUT_OF_SCOPE"))

    def test_policy_second_active_family_in_scope_passes(self):
        # E: a second active family added only in the temp policy is honoured;
        # the real repo keeps only agent-safe active.
        families = self._default_policy_families() + [
            {
                "id": "docmeta-test",
                "claim_id_prefix": "CLAIM-DOCMETA-TEST-",
                "entry_id_prefix": "claim-docmeta-test-",
                "registry_doc": "docs/claims/registry.yml",
                "mirror_mode": "exact",
                "require_live_check": True,
                "status": "active",
            }
        ]
        self._write_policy(families=families)
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        c2, e2 = self._pair("CLAIM-AGENT-SAFE-002", "claim-agent-safe-002")
        c3, e3 = self._pair("CLAIM-AGENT-SAFE-003", "claim-agent-safe-003")
        c_dm, e_dm = self._pair("CLAIM-DOCMETA-TEST-001", "claim-docmeta-test-001")
        self._write_claims_list([c1, c2, c3, c_dm])
        self._write_registry([e1, e2, e3, e_dm])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertEqual(output["findings_count"], 0)

    def test_inactive_family_does_not_bring_claims_into_scope(self):
        # An inactive family is syntactically valid but ignored: its claim must
        # not be expected, and an entry for it is out of scope.
        families = self._default_policy_families() + [
            {
                "id": "docmeta-test",
                "claim_id_prefix": "CLAIM-DOCMETA-TEST-",
                "entry_id_prefix": "claim-docmeta-test-",
                "registry_doc": "docs/claims/registry.yml",
                "mirror_mode": "exact",
                "require_live_check": True,
                "status": "inactive",
            }
        ]
        self._write_policy(families=families)
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        c2, e2 = self._pair("CLAIM-AGENT-SAFE-002", "claim-agent-safe-002")
        c3, e3 = self._pair("CLAIM-AGENT-SAFE-003", "claim-agent-safe-003")
        # An inactive-family claim exists but is not mirrored: must stay green.
        c_dm, _e_dm = self._pair("CLAIM-DOCMETA-TEST-001", "claim-docmeta-test-001")
        self._write_claims_list([c1, c2, c3, c_dm])
        self._write_registry([e1, e2, e3])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertFalse(self._has(output, "FRESHNESS_ENTRY_MISSING_FOR_CLAIM"))

    def test_missing_policy_file_fails(self):
        # F: an absent policy is a hard stop, never a silent fallback.
        self._remove_policy()
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_policy_missing_families_fails(self):
        # F: a policy without a families list is structurally invalid.
        self._write_policy_text(
            "kind: weltgewebe.docmeta.freshness_scope_policy\nversion: \"1.0\"\n"
        )
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_policy_unknown_mirror_mode_fails(self):
        # F: only mirror_mode 'exact' is allowed in this slice.
        families = self._default_policy_families()
        families[0]["mirror_mode"] = "loose"
        self._write_policy(families=families)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_policy_duplicate_family_id_fails(self):
        # F: duplicate family ids are rejected.
        families = self._default_policy_families() + self._default_policy_families()
        self._write_policy(families=families)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_require_live_check_missing_fails(self):
        # G: require_live_check demands at least one file/test/proof evidence.
        # An entry whose only evidence is a non-live 'text' kind violates it.
        # (The mirror mismatch findings that accompany this are expected, since
        # no claim evidence kind maps to a non-live kind.)
        c1, e1 = self._pair(
            "CLAIM-AGENT-SAFE-001",
            "claim-agent-safe-001",
            evidence=[("docs/pair/doc-only.md", "documentation", "file")],
        )
        target = e1["evidence"][0]["target"]
        e1["evidence"] = [{"kind": "text", "target": target}]
        self._write_claims_list([c1])
        self._write_registry([e1])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            self._has(output, "FRESHNESS_ENTRY_REQUIRES_LIVE_CHECK_MISSING")
        )

    def test_policy_duplicate_family_key_fails(self):
        # A duplicate key within a family block is rejected as a parse error
        # and surfaces as FRESHNESS_SCOPE_POLICY_INVALID.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
            "    status: inactive\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))
        # The error locates the duplicate at its source line (status at line 12).
        messages = self._messages(output, "FRESHNESS_SCOPE_POLICY_INVALID")
        self.assertTrue(any("at line 12" in m for m in messages), messages)

    def test_policy_duplicate_top_level_key_fails(self):
        # A duplicate key at the top level of the policy is rejected and
        # surfaces as FRESHNESS_SCOPE_POLICY_INVALID.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))
        # The error locates the duplicate at its source line (kind at line 2).
        messages = self._messages(output, "FRESHNESS_SCOPE_POLICY_INVALID")
        self.assertTrue(any("at line 2" in m for m in messages), messages)

    def test_policy_registry_doc_must_match_claims_path(self):
        # An active family whose registry_doc does not match the claims path
        # passed to run_validation is rejected as FRESHNESS_SCOPE_POLICY_INVALID.
        families = [
            {
                "id": "agent-safe",
                "claim_id_prefix": "CLAIM-AGENT-SAFE-",
                "entry_id_prefix": "claim-agent-safe-",
                "registry_doc": "docs/claims/other-registry.yml",
                "mirror_mode": "exact",
                "require_live_check": True,
                "status": "active",
            }
        ]
        self._write_policy(families=families)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_in_scope_entry_doc_must_match_family_registry_doc(self):
        # The 'doc' field is checked against family.registry_doc, not a
        # hardcoded constant. An in-scope entry with the wrong doc fails.
        self._write_claims()
        entries = self._entries()
        entries[0]["doc"] = "docs/claims/other-registry.yml"
        self._write_registry(entries)
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "DOC_MISMATCH"))

    def test_policy_duplicate_registry_doc_key_fails(self):
        # A: a family with two registry_doc keys is a parse-level duplicate and
        # surfaces as FRESHNESS_SCOPE_POLICY_INVALID (never silently last-wins).
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    registry_doc: docs/claims/other-registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_policy_duplicate_claim_id_prefix_key_fails(self):
        # B: a family with two claim_id_prefix keys is a parse-level duplicate.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    claim_id_prefix: CLAIM-OTHER-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_policy_duplicate_inline_family_id_key_fails(self):
        # C: the inline '- id: ...' assignment must not escape duplicate
        # protection; a second 'id:' field below it is still rejected.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    id: other\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))
        # The inline '- id:' plus a later 'id:' is located at its source line 6.
        messages = self._messages(output, "FRESHNESS_SCOPE_POLICY_INVALID")
        self.assertTrue(any("at line 6" in m for m in messages), messages)

    def test_policy_registry_doc_can_match_custom_claims_path(self):
        # D: registry_doc is validated against the actual --claims path, not a
        # hardcoded default. A custom claims path with a matching family passes.
        custom_claims = "docs/claims/custom-registry.yml"
        families = self._default_policy_families()
        families[0]["registry_doc"] = custom_claims
        self._write_policy(families=families)

        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        # In-scope entries mirror family.registry_doc, so the doc must follow.
        e1["doc"] = custom_claims
        self._write_claims_list_at(custom_claims, [c1])
        self._write_registry([e1])

        output, exit_code = validator.run_validation(
            "docs/doc-freshness-registry.yml",
            claims=custom_claims,
            repo_root=self.root,
        )
        self.assertEqual(exit_code, 0, output["findings"])

    def test_out_of_scope_entry_emits_no_doc_mismatch(self):
        # E: an out-of-scope entry is reported as FRESHNESS_ENTRY_OUT_OF_SCOPE
        # and not additionally flagged with a global-default DOC_MISMATCH, even
        # when its doc field differs. Out-of-scope and doc semantics stay apart.
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        c2, e2 = self._pair("CLAIM-AGENT-SAFE-002", "claim-agent-safe-002")
        c3, e3 = self._pair("CLAIM-AGENT-SAFE-003", "claim-agent-safe-003")
        self._write_claims_list([c1, c2, c3])
        extra = self._touch("docs/deploy/evidence.md")
        out_of_scope_entry = {
            "id": "claim-deploy-001",
            "doc": "docs/deploy/some-other-doc.yml",
            "locator": "claims[id=CLAIM-DEPLOY-001]",
            "claim": "Out of scope claim.",
            "status": "partial",
            "owner": "docs-mechanik",
            "last_verified": "2026-06-05",
            "evidence": [{"kind": "file", "target": extra}],
        }
        self._write_registry([e1, e2, e3, out_of_scope_entry])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_ENTRY_OUT_OF_SCOPE"))
        self.assertFalse(self._has(output, "DOC_MISMATCH"))

    def test_require_live_check_empty_evidence_fails(self):
        # An empty evidence list must not bypass require_live_check: any([]) is
        # False, so the live-check finding still fires. EVIDENCE_EMPTY may also
        # appear, but it must not replace the live-check finding.
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        e1["evidence"] = []
        self._write_claims_list([c1])
        self._write_registry([e1])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(
            self._has(output, "FRESHNESS_ENTRY_REQUIRES_LIVE_CHECK_MISSING")
        )

    def test_require_live_check_accepts_proof_evidence_but_cross_check_still_fires(self):
        # This test pins three independent properties of 'proof' evidence:
        #
        # 1. proof satisfies require_live_check: 'proof' is in
        #    EVIDENCE_KINDS_CHECK_PATH, so FRESHNESS_ENTRY_REQUIRES_LIVE_CHECK_MISSING
        #    must NOT fire.
        # 2. proof is checked against the live filesystem: the proof target
        #    exists, so EVIDENCE_TARGET_MISSING must NOT fire (a missing file
        #    would).
        # 3. proof is NOT a Weltgewebe claim evidence kind (not in
        #    CLAIM_EVIDENCE_KIND_TO_LENSKIT). _pair() gives c1 two claim evidence
        #    items (documentation->file, test->test). Replacing e1's bridge
        #    evidence with a single proof item makes the bridge evidence set and
        #    the mapped claim evidence set disjoint, so the cross-check fires
        #    EVIDENCE_NOT_IN_CLAIM_REGISTRY (the proof item) and, twice,
        #    EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY (each unmirrored claim item).
        #
        # The exact-set assertion below stops this test from passing on unrelated
        # findings. No other codes are expected: the claim/entry are mirrored 1:1
        # and in scope, the proof target exists, and the live-check is satisfied.
        proof_path = self._touch("docs/proofs/live-proof.md")
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        e1["evidence"] = [{"kind": "proof", "target": proof_path}]
        self._write_claims_list([c1])
        self._write_registry([e1])
        output, exit_code = self._run()

        codes = {finding["code"] for finding in output["findings"]}

        # (1) require_live_check satisfied and (2) live filesystem check passed:
        self.assertNotIn("FRESHNESS_ENTRY_REQUIRES_LIVE_CHECK_MISSING", codes)
        self.assertNotIn("EVIDENCE_TARGET_MISSING", codes)

        # (3) proof is not a claim-evidence mapping kind: the cross-check fires.
        self.assertIn("EVIDENCE_NOT_IN_CLAIM_REGISTRY", codes)
        self.assertIn("EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY", codes)

        # Exactly these cross-check codes, nothing else.
        self.assertEqual(
            codes,
            {
                "EVIDENCE_NOT_IN_CLAIM_REGISTRY",
                "EVIDENCE_MISSING_FROM_FRESHNESS_REGISTRY",
            },
            output["findings"],
        )
        # The cross-check failures keep the run red.
        self.assertEqual(exit_code, 1)

    def test_policy_unknown_top_level_key_fails(self):
        # An unknown key at the top level of the policy is rejected as a parse
        # error and surfaces as FRESHNESS_SCOPE_POLICY_INVALID. The message
        # names the offending key so the author can locate the typo.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "extra_key: not_allowed\n"
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))
        messages = self._messages(output, "FRESHNESS_SCOPE_POLICY_INVALID")
        self.assertTrue(any("extra_key" in m for m in messages), messages)

    def test_policy_unknown_family_key_fails(self):
        # A typo in a family key ('require_live_chek') is rejected as an
        # unknown key. Without this guard the typo would be silently accepted
        # while require_live_check defaulted to False, bypassing the live-check
        # requirement. The message names the unknown key.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_chek: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))
        messages = self._messages(output, "FRESHNESS_SCOPE_POLICY_INVALID")
        self.assertTrue(
            any("require_live_chek" in m for m in messages), messages
        )

    def test_active_policy_family_missing_require_live_check_fails(self):
        # An active family that does not set require_live_check at all is
        # invalid. Silently defaulting to False would be a dangerous surprise;
        # every active family must declare its intent explicitly.
        families = [
            {
                "id": "agent-safe",
                "claim_id_prefix": "CLAIM-AGENT-SAFE-",
                "entry_id_prefix": "claim-agent-safe-",
                "registry_doc": "docs/claims/registry.yml",
                "mirror_mode": "exact",
                # require_live_check intentionally absent
                "status": "active",
            }
        ]
        self._write_policy(families=families)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))
        messages = self._messages(output, "FRESHNESS_SCOPE_POLICY_INVALID")
        self.assertTrue(
            any("require_live_check" in m for m in messages), messages
        )

    def test_policy_require_live_check_must_be_boolean(self):
        # require_live_check must be a YAML boolean (true/false). The coerce
        # helper converts 'true'/'false' but 'yes' stays a string and fails
        # the explicit isinstance(_, bool) check.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-safe-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: yes\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))
        messages = self._messages(output, "FRESHNESS_SCOPE_POLICY_INVALID")
        self.assertTrue(
            any("must be a boolean" in m for m in messages), messages
        )

    def test_policy_overlapping_claim_prefixes_fail(self):
        # 'CLAIM-AGENT-SAFE-' starts with 'CLAIM-AGENT-', making family
        # assignment ambiguous by startswith. Both active families are valid
        # individually, but their claim_id_prefixes are prefix-related, so the
        # policy is rejected.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: agent\n"
            "    claim_id_prefix: CLAIM-AGENT-\n"
            "    entry_id_prefix: claim-agent-001-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
            "  - id: agent-safe\n"
            "    claim_id_prefix: CLAIM-AGENT-SAFE-\n"
            "    entry_id_prefix: claim-agent-002-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_policy_overlapping_entry_prefixes_fail(self):
        # 'claim-other-' starts with 'claim-', making entry family lookup
        # ambiguous even though the claim prefixes ('CLAIM-FOO-' / 'CLAIM-BAR-')
        # are disjoint. The entry prefix overlap is caught independently.
        text = (
            "kind: weltgewebe.docmeta.freshness_scope_policy\n"
            'version: "1.0"\n'
            "\n"
            "families:\n"
            "  - id: foo\n"
            "    claim_id_prefix: CLAIM-FOO-\n"
            "    entry_id_prefix: claim-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
            "  - id: bar\n"
            "    claim_id_prefix: CLAIM-BAR-\n"
            "    entry_id_prefix: claim-other-\n"
            "    registry_doc: docs/claims/registry.yml\n"
            "    mirror_mode: exact\n"
            "    require_live_check: true\n"
            "    status: active\n"
        )
        self._write_policy_text(text)
        self._write_claims()
        self._write_registry(self._entries())
        output, exit_code = self._run()
        self.assertEqual(exit_code, 1)
        self.assertTrue(self._has(output, "FRESHNESS_SCOPE_POLICY_INVALID"))

    def test_claim_with_unknown_family_prefix_is_not_expected(self):
        # A claim whose prefix matches no active family is not expected to carry
        # a freshness entry: the reverse-mirror check skips it. With all
        # agent-safe entries present and complete, the run stays green.
        c1, e1 = self._pair("CLAIM-AGENT-SAFE-001", "claim-agent-safe-001")
        c2, e2 = self._pair("CLAIM-AGENT-SAFE-002", "claim-agent-safe-002")
        c3, e3 = self._pair("CLAIM-AGENT-SAFE-003", "claim-agent-safe-003")
        c_deploy, _ = self._pair("CLAIM-DEPLOY-001", "claim-deploy-001")
        self._write_claims_list([c1, c2, c3, c_deploy])
        self._write_registry([e1, e2, e3])
        output, exit_code = self._run()
        self.assertEqual(exit_code, 0, output["findings"])
        self.assertFalse(self._has(output, "FRESHNESS_ENTRY_MISSING_FOR_CLAIM"))


if __name__ == "__main__":
    unittest.main()
