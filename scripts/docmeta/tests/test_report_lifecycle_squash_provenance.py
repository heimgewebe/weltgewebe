#!/usr/bin/env python3
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

from scripts.docmeta.report_lifecycle_requirements import (
    build_truth_contract,
    source_revision_metadata,
    validate_truth_contract,
)

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "docs-guard.yml"
MAIN_PUSH_CONDITION = "github.event_name == 'push' && github.ref == 'refs/heads/main'"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _contract_for_source(root: Path, source: Path) -> dict[str, object]:
    revision, generated_at, fresh = source_revision_metadata(root, [source])
    if not fresh:
        raise AssertionError("test source must be clean and fresh")
    return build_truth_contract(
        status="pass",
        scope="one exact source",
        complete=True,
        fresh=True,
        method="exact",
        checked_items=1,
        total_items=1,
        failures=0,
        source_revision=revision,
        generated_at=generated_at,
        sources=[
            {
                "path": source.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ],
        limitations=["repository-only"],
        does_not_establish=["runtime_health"],
    )


class TestReportLifecycleSquashProvenance(unittest.TestCase):
    def test_source_change_requires_exact_head_regeneration_after_squash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repo"
            root.mkdir()
            _git(root, "init", "-q")
            _git(root, "config", "user.name", "Test")
            _git(root, "config", "user.email", "test@example.invalid")

            source = root / "docs" / "reports" / "source.md"
            source.parent.mkdir(parents=True)
            source.write_text("source v1\n", encoding="utf-8")
            _git(root, "add", "docs/reports/source.md")
            _git(root, "commit", "-q", "-m", "base source")
            _git(root, "branch", "-M", "main")

            _git(root, "switch", "-q", "-c", "feature")
            source.write_text("source v2\n", encoding="utf-8")
            _git(root, "add", "docs/reports/source.md")
            _git(root, "commit", "-q", "-m", "feature source")
            feature_revision = _git(root, "rev-parse", "HEAD")
            feature_contract = _contract_for_source(root, source)
            self.assertEqual(validate_truth_contract(feature_contract, root=root), ())

            _git(root, "switch", "-q", "main")
            _git(root, "merge", "--squash", "feature")
            _git(root, "commit", "-q", "-m", "squash feature")
            squash_revision = _git(root, "rev-parse", "HEAD")
            self.assertNotEqual(feature_revision, squash_revision)
            self.assertNotEqual(
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", feature_revision, "HEAD"],
                    cwd=root,
                    check=False,
                ).returncode,
                0,
            )

            feature_violations = validate_truth_contract(feature_contract, root=root)
            self.assertIn("source_revision_not_ancestor", feature_violations)

            rebound_contract = _contract_for_source(root, source)
            self.assertEqual(rebound_contract["source_revision"], squash_revision)
            self.assertEqual(validate_truth_contract(rebound_contract, root=root), ())

            shallow = Path(temp_dir) / "shallow"
            subprocess.run(
                ["git", "clone", "-q", "--depth=1", root.resolve().as_uri(), str(shallow)],
                check=True,
            )
            self.assertIn(
                "source_history_unavailable",
                validate_truth_contract(rebound_contract, root=shallow),
            )

    def test_docs_guard_rebinds_before_validation_and_publishes_only_after_green(self) -> None:
        workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        jobs = workflow["jobs"]

        blocking = jobs["blocking-doc-validations"]
        blocking_steps = blocking["steps"]
        names = [step.get("name", "") for step in blocking_steps]
        rebind_index = names.index("Rebind report lifecycle provenance for main validation")
        strict_index = names.index("Report lifecycle global strict")
        self.assertLess(rebind_index, strict_index)

        rebind = blocking_steps[rebind_index]
        self.assertEqual(rebind["if"], MAIN_PUSH_CONDITION)
        rebind_run = rebind["run"]
        self.assertIn("scripts.docmeta.generate_report_lifecycle\n", rebind_run)
        self.assertIn("scripts.docmeta.generate_report_lifecycle_inventory", rebind_run)

        reconcile = jobs["reconcile-report-lifecycle-provenance"]
        self.assertEqual(reconcile["if"], MAIN_PUSH_CONDITION)
        self.assertEqual(reconcile["needs"], "blocking-doc-validations")
        self.assertEqual(reconcile["permissions"], {"contents": "write"})

        checkout = reconcile["steps"][0]
        self.assertTrue(checkout["uses"].startswith("actions/checkout@"))
        self.assertEqual(checkout["with"]["fetch-depth"], 0)

        reconcile_steps = {step.get("name", ""): step for step in reconcile["steps"]}
        verify_run = reconcile_steps["Verify regenerated report lifecycle provenance"]["run"]
        self.assertIn("scripts.docmeta.validate_report_lifecycle --mode strict", verify_run)
        self.assertIn("scripts.docmeta.generate_report_lifecycle --check", verify_run)
        self.assertIn("scripts.docmeta.generate_report_lifecycle_inventory --check", verify_run)

        publish_run = reconcile_steps["Publish exact report lifecycle provenance refresh"]["run"]
        self.assertIn("git fetch --no-tags origin main", publish_run)
        self.assertIn('refs/remotes/origin/main)\" != \"${TARGET_SHA}', publish_run)
        self.assertIn("unexpected tracked changes outside report lifecycle outputs", publish_run)
        self.assertIn('git push origin "HEAD:refs/heads/main"', publish_run)
        self.assertNotIn("--force", publish_run)

        diagnostics = jobs["generated-diagnostics"]
        diagnostics_checkout = diagnostics["steps"][0]
        self.assertTrue(diagnostics_checkout["uses"].startswith("actions/checkout@"))
        self.assertEqual(diagnostics_checkout["with"]["fetch-depth"], 0)


if __name__ == "__main__":
    unittest.main()
