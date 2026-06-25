import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import scripts.docmeta.generate_agent_readiness as gen


class TestAgentReadinessSmokeContract(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for rel_path in gen.HANDOFF_REQUIRED_FILES:
            path = self.root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "{}\n" if rel_path.endswith(".json") else "# placeholder\n",
                encoding="utf-8",
            )

    def tearDown(self):
        self._tmp.cleanup()

    def _result(self, completed: subprocess.CompletedProcess[str]):
        with mock.patch.object(gen.subprocess, "run", return_value=completed):
            return next(
                item
                for item in gen.evaluate_capabilities(self.root)
                if item.id == "handoff_validation"
            )

    def test_smoke_requires_complete_structured_success(self):
        valid = {
            "status": "valid",
            "task_file": gen.HANDOFF_TASK_FILE,
            "handoff_file": gen.HANDOFF_VALID_FILE,
            "findings_count": 0,
            "findings": [],
        }
        cases = (
            (0, ""),
            (0, "{broken"),
            (0, json.dumps({**valid, "status": "invalid"})),
            (0, json.dumps({**valid, "findings_count": 1})),
            (0, json.dumps({**valid, "findings": [{}]})),
            (0, json.dumps({**valid, "task_file": "other.json"})),
            (1, json.dumps(valid)),
        )
        for returncode, stdout in cases:
            with self.subTest(returncode=returncode, stdout=stdout):
                completed = subprocess.CompletedProcess(
                    args=["validator"],
                    returncode=returncode,
                    stdout=stdout,
                    stderr="",
                )
                result = self._result(completed)
                self.assertEqual(result.status, "fail")
                self.assertIn("functional handoff smoke", result.missing)

    def test_report_exposes_registry_dependency(self):
        completed = subprocess.CompletedProcess(
            args=["validator"],
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "valid",
                    "task_file": gen.HANDOFF_TASK_FILE,
                    "handoff_file": gen.HANDOFF_VALID_FILE,
                    "findings_count": 0,
                    "findings": [],
                }
            ),
            stderr="",
        )
        result = self._result(completed)
        report = gen.render_report([result], "partial", "test", [])
        self.assertEqual(result.status, "pass")
        self.assertIn("docs/claims/registry.yml", result.evidence)
        self.assertIn("`docs/claims/registry.yml`", report)


if __name__ == "__main__":
    unittest.main()
