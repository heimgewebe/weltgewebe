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
        self._touch("contracts/agent/task.schema.json", "{}\n")
        self._touch("scripts/agent/handoff_validator.py")
        self._touch("scripts/agent/non_ideal_guard.py")
        self._touch("scripts/agent/dry_run_runner.py")

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
        self.assertRegex(report, r"\| claim_evidence_spine \| (pass|partial|open|fail) \|")


if __name__ == "__main__":
    unittest.main()
