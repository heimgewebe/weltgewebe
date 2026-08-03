#!/usr/bin/env python3
from __future__ import annotations

import datetime
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.docmeta.report_lifecycle_requirements import (
    build_truth_contract,
    missing_required_report_field_rules,
    missing_required_report_fields,
    report_truth_migration_state,
    required_report_field_rules,
    source_revision_metadata,
    string_value,
    validate_truth_contract,
)


class TestReportLifecycleRequirements(unittest.TestCase):
    def test_non_report_has_no_requirements(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {"doc_type": "reference", "status": "active"}
            ),
            (),
        )

    def test_base_and_status_rules(self) -> None:
        cases = [
            ({"doc_type": "report"}, ("lifecycle_state", "status")),
            (
                {"doc_type": "report", "status": "active"},
                ("lifecycle_state", "lifecycle", "review_after"),
            ),
            (
                {"doc_type": "report", "status": "draft"},
                ("lifecycle_state", "review_after"),
            ),
        ]
        for frontmatter, expected in cases:
            with self.subTest(frontmatter=frontmatter):
                self.assertEqual(
                    missing_required_report_fields(frontmatter), expected
                )

    def test_lifecycle_state_rules(self) -> None:
        cases = {
            "active": ("lifecycle", "owner_task", "review_after"),
            "deferred": ("lifecycle", "owner_task", "review_after"),
            "superseded": ("lifecycle", "owner_task", "superseded_by"),
            "archived": ("lifecycle", "owner_task"),
        }
        for state, expected in cases.items():
            with self.subTest(state=state):
                self.assertEqual(
                    missing_required_report_fields(
                        {
                            "doc_type": "report",
                            "status": "deprecated",
                            "lifecycle_state": state,
                        }
                    ),
                    expected,
                )

    def test_archived_report_does_not_require_review_after(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {
                    "doc_type": "report",
                    "status": "deprecated",
                    "lifecycle_state": "archived",
                    "lifecycle": "audit",
                    "owner_task": "TASK-1",
                }
            ),
            (),
        )

    def test_unknown_state_adds_no_state_requirements(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {
                    "doc_type": "report",
                    "status": "deprecated",
                    "lifecycle_state": "unknown",
                }
            ),
            (),
        )

    def test_deduplication_preserves_first_rule(self) -> None:
        rules = missing_required_report_field_rules(
            {
                "doc_type": "report",
                "status": "active",
                "lifecycle_state": "deferred",
            }
        )
        self.assertEqual(
            tuple((rule.code, rule.field, rule.message) for rule in rules),
            (
                (
                    "missing_lifecycle",
                    "lifecycle",
                    "active reports should define lifecycle",
                ),
                (
                    "missing_review_after",
                    "review_after",
                    "active/draft reports should define review_after",
                ),
                (
                    "missing_owner_task",
                    "owner_task",
                    "deferred reports should define owner_task",
                ),
            ),
        )

    def test_required_rule_precedence_and_messages_are_frozen(self) -> None:
        """Freeze ordered applicable rule definitions before presence filtering.

        When status- and lifecycle_state-derived rules share a finding code,
        the first occurrence wins. This test covers internal compatibility
        ordering. Emitted findings are covered by the validator parity test.
        """

        def rules(frontmatter: dict[str, object]) -> tuple[tuple[str, str, str], ...]:
            return tuple(
                (rule.code, rule.field, rule.message)
                for rule in required_report_field_rules(frontmatter)
            )

        # status=active wins the lifecycle/review_after message over archived.
        self.assertEqual(
            rules(
                {"doc_type": "report", "status": "active", "lifecycle_state": "archived"}
            ),
            (
                (
                    "missing_lifecycle_state",
                    "lifecycle_state",
                    "report documents should define lifecycle_state",
                ),
                (
                    "missing_status",
                    "status",
                    "report documents should define status",
                ),
                (
                    "missing_lifecycle",
                    "lifecycle",
                    "active reports should define lifecycle",
                ),
                (
                    "missing_review_after",
                    "review_after",
                    "active/draft reports should define review_after",
                ),
                (
                    "missing_owner_task",
                    "owner_task",
                    "archived reports should define owner_task",
                ),
            ),
        )
        # superseded contributes superseded_by; status=active still wins lifecycle.
        self.assertEqual(
            rules(
                {"doc_type": "report", "status": "active", "lifecycle_state": "superseded"}
            ),
            (
                (
                    "missing_lifecycle_state",
                    "lifecycle_state",
                    "report documents should define lifecycle_state",
                ),
                (
                    "missing_status",
                    "status",
                    "report documents should define status",
                ),
                (
                    "missing_lifecycle",
                    "lifecycle",
                    "active reports should define lifecycle",
                ),
                (
                    "missing_review_after",
                    "review_after",
                    "active/draft reports should define review_after",
                ),
                (
                    "missing_owner_task",
                    "owner_task",
                    "superseded reports should define owner_task",
                ),
                (
                    "missing_superseded_by",
                    "superseded_by",
                    "superseded reports should define superseded_by",
                ),
            ),
        )
        # status=draft wins review_after message; deferred contributes lifecycle/owner_task.
        self.assertEqual(
            rules(
                {"doc_type": "report", "status": "draft", "lifecycle_state": "deferred"}
            ),
            (
                (
                    "missing_lifecycle_state",
                    "lifecycle_state",
                    "report documents should define lifecycle_state",
                ),
                (
                    "missing_status",
                    "status",
                    "report documents should define status",
                ),
                (
                    "missing_review_after",
                    "review_after",
                    "active/draft reports should define review_after",
                ),
                (
                    "missing_lifecycle",
                    "lifecycle",
                    "deferred reports should define lifecycle",
                ),
                (
                    "missing_owner_task",
                    "owner_task",
                    "deferred reports should define owner_task",
                ),
            ),
        )

    def test_normalization_matches_validator_behavior(self) -> None:
        self.assertEqual(
            missing_required_report_fields(
                {
                    "doc_type": " Report ",
                    "status": " Deprecated ",
                    "lifecycle_state": " ARCHIVED ",
                    "lifecycle": "audit",
                    "owner_task": "TASK-1",
                }
            ),
            (),
        )
        self.assertEqual(string_value(None), "")
        self.assertEqual(string_value([]), "")
        self.assertEqual(string_value({}), "")
        self.assertEqual(string_value(7), "7")
        self.assertEqual(
            string_value(datetime.date(2026, 7, 13)), "2026-07-13"
        )


class TestAuditReportTruthContract(unittest.TestCase):
    def _contract(self, status: str = "pass", **changes: object) -> dict[str, object]:
        coverage: dict[str, object] = {
            "scope": "all contract sources",
            "complete": True,
            "fresh": True,
            "method": "exact",
            "checked_items": 2,
            "total_items": 2,
            "failures": 0,
        }
        coverage.update(changes)
        return build_truth_contract(
            status=status,
            scope=str(coverage["scope"]),
            complete=bool(coverage["complete"]),
            fresh=bool(coverage["fresh"]),
            method=str(coverage["method"]),
            checked_items=int(coverage["checked_items"]),
            total_items=int(coverage["total_items"]),
            failures=int(coverage["failures"]),
            source_revision="a" * 40,
            generated_at="2026-08-03T00:00:00+00:00",
            sources=[{"path": "docs/reports/a.md", "sha256": "b" * 64}],
            limitations=["repository-only"],
            does_not_establish=["runtime_health"],
        )

    def test_valid_positive_contract_passes(self) -> None:
        self.assertEqual(validate_truth_contract(self._contract()), ())

    def test_positive_status_is_downgraded_for_unsafe_coverage(self) -> None:
        for changes in (
            {"complete": False},
            {"fresh": False},
            {"method": "heuristic"},
            {"failures": 1},
            {"checked_items": 1},
        ):
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, "positive_status"):
                    self._contract(**changes)

    def test_missing_and_unknown_fields_fail_closed(self) -> None:
        contract = self._contract(status="partial")
        contract.pop("sources")
        contract["surprise"] = True
        violations = validate_truth_contract(contract)
        self.assertIn("missing_sources", violations)
        self.assertIn("unknown_surprise", violations)

    def test_false_source_revision_fails_when_revision_blob_differs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=root,
                check=True,
            )
            source = root / "docs" / "reports" / "source.md"
            source.parent.mkdir(parents=True)
            source.write_text("source v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "source v1"], cwd=root, check=True)
            old_revision = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=True
            ).stdout.strip()
            old_timestamp = subprocess.run(
                ["git", "show", "-s", "--format=%cI", old_revision],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            source.write_text("source v2\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "source v2"], cwd=root, check=True)
            contract = build_truth_contract(
                status="partial",
                scope="one source",
                complete=True,
                fresh=True,
                method="exact",
                checked_items=1,
                total_items=1,
                failures=0,
                source_revision=old_revision,
                generated_at=old_timestamp,
                sources=[{
                    "path": "docs/reports/source.md",
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                }],
                limitations=["repository-only"],
                does_not_establish=["runtime-health"],
            )
            self.assertIn(
                "source_revision_digest_mismatch_0",
                validate_truth_contract(contract, root=root),
            )

    def test_migration_classification_is_explicit(self) -> None:
        self.assertEqual(
            report_truth_migration_state({"lifecycle_state": "archived", "status": "active"}),
            "deprecated",
        )
        self.assertEqual(
            report_truth_migration_state({"lifecycle_state": "active", "status": "active"}),
            "not_decision_relevant",
        )


class TestSourceRevisionMetadata(unittest.TestCase):
    def test_revision_tracks_latest_source_commit_not_generator_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=root,
                check=True,
            )
            source = root / "source.md"
            source.write_text("source v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "source.md"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "source"],
                cwd=root,
                check=True,
            )
            source_revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()

            (root / "generator.py").write_text("# generator\n", encoding="utf-8")
            subprocess.run(["git", "add", "generator.py"], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-q", "-m", "generator"],
                cwd=root,
                check=True,
            )

            revision, generated_at, fresh = source_revision_metadata(root, [source])
            self.assertEqual(revision, source_revision)
            self.assertTrue(generated_at)
            self.assertTrue(fresh)

            source.write_text("source v2\n", encoding="utf-8")
            revision, _, fresh = source_revision_metadata(root, [source])
            self.assertEqual(revision, source_revision)
            self.assertFalse(fresh)


    def test_root_validation_materializes_bound_revision_in_shallow_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            source_repo = temp_root / "source-repo"
            source_repo.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=source_repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=source_repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=source_repo,
                check=True,
            )
            source = source_repo / "source.md"
            source.write_text("source v1\n", encoding="utf-8")
            subprocess.run(["git", "add", "source.md"], cwd=source_repo, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "source"], cwd=source_repo, check=True)
            source_revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=source_repo,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            generated_at = subprocess.run(
                ["git", "show", "-s", "--format=%cI", source_revision],
                cwd=source_repo,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            source_digest = hashlib.sha256(source.read_bytes()).hexdigest()

            (source_repo / "generator.py").write_text("# generator\n", encoding="utf-8")
            subprocess.run(["git", "add", "generator.py"], cwd=source_repo, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "generator"], cwd=source_repo, check=True)

            checkout = temp_root / "checkout"
            subprocess.run(
                ["git", "clone", "-q", "--depth=1", source_repo.resolve().as_uri(), str(checkout)],
                check=True,
            )
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "--is-shallow-repository"],
                    cwd=checkout,
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip(),
                "true",
            )
            self.assertNotEqual(
                subprocess.run(
                    ["git", "cat-file", "-e", f"{source_revision}^{{commit}}"],
                    cwd=checkout,
                    capture_output=True,
                    check=False,
                ).returncode,
                0,
            )

            resolved_revision, resolved_generated_at, resolved_fresh = source_revision_metadata(
                checkout, [checkout / "source.md"]
            )
            self.assertEqual(resolved_revision, source_revision)
            self.assertEqual(resolved_generated_at, generated_at)
            self.assertTrue(resolved_fresh)

            contract = build_truth_contract(
                status="pass",
                scope="one exact source",
                complete=True,
                fresh=True,
                method="exact",
                checked_items=1,
                total_items=1,
                failures=0,
                source_revision=source_revision,
                generated_at=generated_at,
                sources=[{"path": "source.md", "sha256": source_digest}],
                limitations=["repository-only"],
                does_not_establish=["runtime_health"],
            )
            self.assertEqual(validate_truth_contract(contract, root=checkout), ())
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "--is-shallow-repository"],
                    cwd=checkout,
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip(),
                "false",
            )


if __name__ == "__main__":
    unittest.main()
