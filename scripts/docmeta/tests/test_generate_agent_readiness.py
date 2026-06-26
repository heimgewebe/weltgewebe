import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.generate_agent_readiness as gen


class TestGenerateAgentReadiness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _touch(self, rel_path: str, content: str = "fixture\n") -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _copy_handoff_capability(self) -> None:
        source_root = Path(gen.REPO_ROOT).resolve()
        handoff_path = source_root / "tests/fixtures/agent/handoff-valid.json"
        handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        evidence = handoff.get("evidence_produced")

        if not isinstance(evidence, list) or any(
            not isinstance(item, str) or not item for item in evidence
        ):
            raise AssertionError(
                "handoff-valid.json must declare evidence_produced strings"
            )

        registry_path = source_root / "docs/claims/registry.yml"
        registry_raw = registry_path.read_text(encoding="utf-8")
        if not registry_raw.startswith("---\n"):
            raise AssertionError("claim registry must use JSON-compatible YAML")
        registry = json.loads(registry_raw[4:])
        registry_evidence = [
            item["path"]
            for claim in registry.get("claims", [])
            if isinstance(claim, dict)
            for item in claim.get("evidence", [])
            if isinstance(item, dict)
            and isinstance(item.get("path"), str)
            and item["path"]
        ]

        required_paths = list(
            dict.fromkeys(
                [
                    *gen.HANDOFF_REQUIRED_FILES,
                    *evidence,
                    *registry_evidence,
                ]
            )
        )

        for rel_path in required_paths:
            source = (source_root / rel_path).resolve()
            try:
                source.relative_to(source_root)
            except ValueError as exc:
                raise AssertionError(
                    f"fixture dependency escapes repository root: {rel_path}"
                ) from exc

            if not source.is_file():
                raise AssertionError(
                    f"fixture dependency is missing or not a file: {rel_path}"
                )

            target = self.root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def _copy_dry_run_capability(self) -> None:
        source_root = Path(gen.REPO_ROOT).resolve()
        for rel_path in gen.DRY_RUN_REQUIRED_FILES:
            source = (source_root / rel_path).resolve()
            try:
                source.relative_to(source_root)
            except ValueError as exc:
                raise AssertionError(
                    f"dry-run fixture dependency escapes repository root: {rel_path}"
                ) from exc
            if not source.is_file():
                raise AssertionError(
                    f"dry-run fixture dependency is missing or not a file: {rel_path}"
                )
            target = self.root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def _copy_run_evidence_capability(self) -> None:
        source_root = Path(gen.REPO_ROOT).resolve()
        for rel_path in gen.RUN_EVIDENCE_REQUIRED_FILES:
            source = (source_root / rel_path).resolve()
            try:
                source.relative_to(source_root)
            except ValueError as exc:
                raise AssertionError(
                    f"run-evidence fixture dependency escapes repository root: {rel_path}"
                ) from exc
            if not source.is_file():
                raise AssertionError(
                    f"run-evidence fixture dependency is missing or not a file: {rel_path}"
                )
            target = self.root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def _init_git_repo(self) -> None:
        subprocess_kwargs = {
            "cwd": self.root,
            "check": True,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        subprocess.run(["git", "init"], **subprocess_kwargs)
        subprocess.run(
            ["git", "config", "user.email", "test@example.invalid"],
            **subprocess_kwargs,
        )
        subprocess.run(["git", "config", "user.name", "Test User"], **subprocess_kwargs)
        subprocess.run(["git", "add", "."], **subprocess_kwargs)
        subprocess.run(["git", "commit", "-m", "initial"], **subprocess_kwargs)

    def _status_map(self, results: list[gen.CapabilityResult]) -> dict[str, str]:
        return {result.id: result.status for result in results}

    def test_minimal_preflight_is_partial_not_pass(self):
        self._touch("AGENTS.md")
        self._touch("agent-policy.yaml")
        self._touch("scripts/agent/check_agent_preflight.py")
        self._touch("scripts/agent/tests/test_check_agent_preflight.py")
        self._touch(".github/workflows/agent-safety-preflight.yml")
        self._touch("docs/security/agent-write-scope-baseline.md")

        out_file = gen.generate(self.root)
        report = out_file.read_text(encoding="utf-8")
        results = gen.evaluate_capabilities(self.root)
        status = self._status_map(results)
        overall, reason, _hard_missing = gen.determine_overall_status(results)

        self.assertEqual(status["agent_policy"], "pass")
        self.assertEqual(status["safety_preflight"], "pass")
        self.assertEqual(status["claim_evidence_spine"], "open")
        self.assertEqual(status["agent_contracts"], "open")
        self.assertEqual(overall, "partial")
        self.assertIn("Hard capabilities are still missing", reason)
        self.assertNotIn("- **Overall:** pass", report)

    def test_all_missing_does_not_return_pass(self):
        out_file = gen.generate(self.root)
        report = out_file.read_text(encoding="utf-8")
        results = gen.evaluate_capabilities(self.root)
        overall, _reason, _hard_missing = gen.determine_overall_status(results)

        self.assertIn(overall, {"open", "partial"})
        self.assertNotEqual(overall, "pass")
        self.assertIn("claim_evidence_spine", report)
        self.assertIn("agent_contracts", report)
        self.assertIn("dry_run_runner", report)

    def test_all_hard_capabilities_present_yields_pass(self):
        self._touch("AGENTS.md")
        self._touch("agent-policy.yaml")
        self._touch("scripts/agent/check_agent_preflight.py")
        self._touch("scripts/agent/tests/test_check_agent_preflight.py")
        self._touch(".github/workflows/agent-safety-preflight.yml")
        self._touch("docs/security/agent-write-scope-baseline.md")
        self._touch("docs/claims/registry.yml")
        self._touch("scripts/docmeta/validate_claim_registry.py")
        self._copy_handoff_capability()
        self._copy_dry_run_capability()
        self._copy_run_evidence_capability()
        self._touch("scripts/agent/tests/test_check_non_ideal_task.py")
        self._init_git_repo()

        gen.generate(self.root)
        results = gen.evaluate_capabilities(self.root)
        status = self._status_map(results)
        overall, _reason, _hard_missing = gen.determine_overall_status(results)

        hard_non_pass = [
            result.id for result in results if result.hard and result.status != "pass"
        ]
        self.assertEqual(overall, "pass")
        self.assertEqual(hard_non_pass, [])
        self.assertEqual(status["claim_evidence_spine"], "pass")
        self.assertEqual(status["agent_contracts"], "pass")
        self.assertEqual(status["handoff_validation"], "pass")
        self.assertEqual(status["non_ideal_guard"], "pass")
        self.assertEqual(status["dry_run_runner"], "pass")
        self.assertEqual(status["run_evidence_lite"], "pass")

    def test_generated_markdown_contains_matrix_sections_and_status_values(self):
        self._touch("AGENTS.md")
        self._touch("agent-policy.yaml")
        self._touch("scripts/agent/check_agent_preflight.py")
        self._touch("scripts/agent/tests/test_check_agent_preflight.py")
        self._touch(".github/workflows/agent-safety-preflight.yml")
        self._touch("docs/security/agent-write-scope-baseline.md")
        self._touch("contracts/agent/README.md")

        out_file = gen.generate(self.root)
        report = out_file.read_text(encoding="utf-8")

        self.assertIn("## Capability Matrix", report)
        self.assertIn("## Residual Gaps", report)
        self.assertIn("## Interpretation Rule", report)
        self.assertRegex(report, r"\| agent_policy \| (pass|partial|open|fail) \|")
        self.assertRegex(report, r"\| safety_preflight \| (pass|partial|open|fail) \|")
        self.assertRegex(
            report, r"\| claim_evidence_spine \| (pass|partial|open|fail) \|"
        )
        self.assertRegex(report, r"\| run_evidence_lite \| (pass|partial|open|fail) \|")

    def test_handoff_single_artifact_is_partial_not_pass(self):
        self._touch("contracts/agent/handoff.schema.json", "{}\n")

        results = gen.evaluate_capabilities(self.root)
        status = self._status_map(results)
        handoff = next(
            result for result in results if result.id == "handoff_validation"
        )

        self.assertEqual(status["handoff_validation"], "partial")
        self.assertIn("scripts/agent/validate_handoff.py", handoff.missing)
        self.assertIn("scripts/agent/tests/test_validate_handoff.py", handoff.missing)
        self.assertIn("tests/fixtures/agent/handoff-valid.json", handoff.missing)

    def test_handoff_complete_placeholder_set_fails_functional_smoke(self):
        for rel_path in gen.HANDOFF_REQUIRED_FILES:
            self._touch(
                rel_path, "{}\n" if rel_path.endswith(".json") else "# placeholder\n"
            )

        result = next(
            item
            for item in gen.evaluate_capabilities(self.root)
            if item.id == "handoff_validation"
        )

        self.assertEqual(result.status, "fail")
        self.assertIn("functional handoff smoke", result.missing)

    def test_handoff_missing_claim_in_real_registry_fails_smoke(self):
        self._copy_handoff_capability()

        task = json.loads(
            (self.root / "tests/fixtures/agent/handoff-task.json").read_text(
                encoding="utf-8"
            )
        )
        claim_id = task["claims"][0]
        registry_path = self.root / "docs/claims/registry.yml"
        raw = registry_path.read_text(encoding="utf-8")
        self.assertTrue(raw.startswith("---\n"))
        registry = json.loads(raw[4:])
        registry["claims"] = [
            claim for claim in registry["claims"] if claim.get("id") != claim_id
        ]
        registry_path.write_text(
            "---\n" + json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = next(
            item
            for item in gen.evaluate_capabilities(self.root)
            if item.id == "handoff_validation"
        )
        self.assertEqual(result.status, "fail")
        self.assertIn("functional handoff smoke", result.missing)

    def test_handoff_named_file_alone_cannot_create_false_green(self):
        self._touch("scripts/agent/handoff_placeholder.py")

        results = gen.evaluate_capabilities(self.root)
        status = self._status_map(results)

        self.assertEqual(status["handoff_validation"], "open")

    def test_dry_run_named_placeholder_cannot_create_false_green(self):
        self._touch("scripts/agent/dry_run_runner.py", '"""Placeholder."""\n')

        results = gen.evaluate_capabilities(self.root)
        status = self._status_map(results)

        self.assertNotEqual(status["dry_run_runner"], "pass")

    def test_run_evidence_complete_placeholder_set_fails_functional_smoke(self):
        for rel_path in gen.RUN_EVIDENCE_REQUIRED_FILES:
            if rel_path.endswith(".json"):
                content = "{}\n"
            elif rel_path.endswith(".md"):
                content = "---\nid: placeholder\ntitle: Placeholder\ndoc_type: reference\nstatus: active\n---\n"
            else:
                content = "# placeholder\n"
            self._touch(rel_path, content)

        result = next(
            item
            for item in gen.evaluate_capabilities(self.root)
            if item.id == "run_evidence_lite"
        )

        self.assertEqual(result.status, "fail")
        self.assertIn("functional run-evidence smoke", result.missing)

    def test_agent_policy_directory_artifact_fails_overall(self):
        (self.root / "AGENTS.md").mkdir(parents=True, exist_ok=True)
        self._touch("agent-policy.yaml")

        out_file = gen.generate(self.root)
        report = out_file.read_text(encoding="utf-8")
        results = gen.evaluate_capabilities(self.root)
        status = self._status_map(results)
        overall, reason, _hard_gaps = gen.determine_overall_status(results)

        self.assertEqual(status["agent_policy"], "fail")
        self.assertEqual(overall, "fail")
        self.assertIn("agent_policy", reason)
        self.assertIn("- **Overall:** fail", report)

    def test_claim_registry_directory_artifact_is_hard_fail_and_gap(self):
        self._touch("AGENTS.md")
        self._touch("agent-policy.yaml")
        (self.root / "docs" / "claims" / "registry.yml").mkdir(
            parents=True, exist_ok=True
        )

        out_file = gen.generate(self.root)
        report = out_file.read_text(encoding="utf-8")
        results = gen.evaluate_capabilities(self.root)
        status = self._status_map(results)
        overall, reason, hard_gaps = gen.determine_overall_status(results)

        self.assertEqual(status["claim_evidence_spine"], "fail")
        self.assertEqual(overall, "fail")
        self.assertIn("claim_evidence_spine", reason)
        self.assertIn("claim_evidence_spine", hard_gaps)
        self.assertIn("- Hard capability missing: claim_evidence_spine", report)


if __name__ == "__main__":
    unittest.main()
