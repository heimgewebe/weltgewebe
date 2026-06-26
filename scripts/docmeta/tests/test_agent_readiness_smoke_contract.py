import json
import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.agent import run_task
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

    def _copy_dry_run_smoke_dependencies(self) -> None:
        source_root = Path(gen.REPO_ROOT).resolve()
        for rel_path in (
            *gen.DRY_RUN_REQUIRED_FILES,
            "contracts/agent/task.schema.json",
            "contracts/agent/handoff.schema.json",
            "docs/claims/registry.yml",
        ):
            source = source_root / rel_path
            target = self.root / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())

    def _valid_dry_run_payload(self) -> dict:
        if not (self.root / gen.DRY_RUN_TASK_FILE).is_file():
            self._copy_dry_run_smoke_dependencies()
        task_path = self.root / gen.DRY_RUN_TASK_FILE
        task = json.loads(task_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(task_path.read_bytes()).hexdigest()
        source_revision = "1" * 40
        handoff = run_task._handoff(task, digest, source_revision)
        return {
            "mode": "dry_run",
            "status": "planned",
            "task_file": gen.DRY_RUN_TASK_FILE,
            "task_id": task["task_id"],
            "task_contract_sha256": digest,
            "source_revision": source_revision,
            "stages": [],
            "findings": [],
            "execution_plan": {},
            "evidence_accounting": {},
            "handoff": handoff,
            "repository_unchanged": True,
        }

    def _dry_run_result(
        self,
        completed: subprocess.CompletedProcess[str],
        *,
        before_status: bytes = b"",
        after_status: bytes = b"",
        timeout: bool = False,
    ):
        self._copy_dry_run_smoke_dependencies()
        git_statuses = [before_status, after_status]

        def run_side_effect(args, **kwargs):
            if args[:2] == ["git", "status"]:
                status = git_statuses.pop(0)
                return subprocess.CompletedProcess(
                    args=args, returncode=0, stdout=status, stderr=b""
                )
            if timeout:
                raise subprocess.TimeoutExpired(cmd=args, timeout=20)
            return completed

        with mock.patch.object(gen.subprocess, "run", side_effect=run_side_effect):
            return gen._evaluate_dry_run_runner(self.root)

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

    def test_dry_run_smoke_requires_complete_structured_success(self):
        valid = self._valid_dry_run_payload()
        cases = (
            (0, ""),
            (0, "{broken"),
            (0, json.dumps({**valid, "mode": "write"})),
            (0, json.dumps({**valid, "status": "blocked"})),
            (0, json.dumps({**valid, "findings": [{"code": "X"}]})),
            (0, json.dumps({**valid, "handoff": None})),
            (0, json.dumps({**valid, "repository_unchanged": False})),
            (1, json.dumps(valid)),
        )
        for returncode, stdout in cases:
            with self.subTest(returncode=returncode, stdout=stdout):
                completed = subprocess.CompletedProcess(
                    args=["runner"],
                    returncode=returncode,
                    stdout=stdout,
                    stderr="",
                )
                result = self._dry_run_result(completed)
                self.assertEqual(result.status, "fail")
                self.assertIn("functional dry-run smoke", result.missing)

    def test_dry_run_smoke_rejects_bad_handoff_semantics(self):
        valid = self._valid_dry_run_payload()
        invalid_handoff = dict(valid["handoff"])
        invalid_handoff["task_contract_sha256"] = "0" * 64

        review_handoff = dict(valid["handoff"])
        review_handoff["outcome"] = "ready_for_review"

        passed_validation_handoff = dict(valid["handoff"])
        passed_validation_handoff["validation_results"] = [
            {**item, "status": "passed"}
            for item in passed_validation_handoff["validation_results"]
        ]

        cases = (
            {**valid, "handoff": invalid_handoff},
            {**valid, "handoff": review_handoff},
            {**valid, "handoff": passed_validation_handoff},
        )
        for payload in cases:
            with self.subTest(handoff=payload["handoff"]):
                completed = subprocess.CompletedProcess(
                    args=["runner"],
                    returncode=0,
                    stdout=json.dumps(payload),
                    stderr="",
                )
                result = self._dry_run_result(completed)
                self.assertEqual(result.status, "fail")
                self.assertIn("functional dry-run smoke", result.missing)

    def test_dry_run_smoke_rejects_git_status_change_and_timeout(self):
        valid = self._valid_dry_run_payload()
        completed = subprocess.CompletedProcess(
            args=["runner"],
            returncode=0,
            stdout=json.dumps(valid),
            stderr="",
        )
        changed = self._dry_run_result(
            completed,
            before_status=b"",
            after_status=b"?? new-file\n",
        )
        self.assertEqual(changed.status, "fail")
        self.assertIn("functional dry-run smoke", changed.missing)

        timeout = self._dry_run_result(completed, timeout=True)
        self.assertEqual(timeout.status, "fail")
        self.assertIn("functional dry-run smoke", timeout.missing)

    def test_dry_run_smoke_accepts_functional_runner_payload(self):
        valid = self._valid_dry_run_payload()
        completed = subprocess.CompletedProcess(
            args=["runner"],
            returncode=0,
            stdout=json.dumps(valid),
            stderr="",
        )
        result = self._dry_run_result(completed)
        self.assertEqual(result.status, "pass")
        self.assertEqual(result.missing, [])


if __name__ == "__main__":
    unittest.main()
