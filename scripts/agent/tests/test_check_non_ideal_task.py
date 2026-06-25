from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.agent import check_non_ideal_task as guard
from scripts.docmeta.docmeta import REPO_ROOT


class TestCheckNonIdealTask(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(REPO_ROOT)
        self.registry = "docs/claims/registry.yml"

    def _fixture(self, name: str) -> str:
        return f"tests/fixtures/agent/{name}"

    def _run_cli(self, task_file: str, mode: str = "report-only") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                "-m",
                "scripts.agent.check_non_ideal_task",
                "--task-file",
                task_file,
                "--claim-registry",
                self.registry,
                "--mode",
                mode,
            ],
            cwd=self.repo_root,
            check=False,
            text=True,
            capture_output=True,
        )

    def _parse_stdout(self, proc: subprocess.CompletedProcess[str]) -> dict:
        return json.loads(proc.stdout)

    def test_valid_doc_drift_task_passes(self):
        proc = self._run_cli(self._fixture("valid-doc-drift-task.json"))
        payload = self._parse_stdout(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["findings_count"], 0)

    def test_valid_roadmap_claim_task_passes(self):
        proc = self._run_cli(self._fixture("valid-roadmap-claim-task.json"))
        payload = self._parse_stdout(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["findings_count"], 0)

    def test_valid_generated_refresh_task_passes(self):
        proc = self._run_cli(self._fixture("valid-generated-refresh-task.json"))
        payload = self._parse_stdout(proc)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["findings_count"], 0)

    def test_docs_generated_allowed_with_generated_refresh_and_generator(self):
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            dir=self.repo_root,
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(
                json.dumps(
                    {
                        "task_id": "AGENT-SAFE-004",
                        "goal": "Generated refresh with generated output path",
                        "task_type": "generated_refresh",
                        "allowed_paths": ["docs/_generated/"],
                        "forbidden_paths": [],
                        "claims": ["CLAIM-AGENT-SAFE-002"],
                        "expected_evidence": ["docs/_generated/agent-readiness.md"],
                        "validation_commands": ["python3 scripts/docmeta/generate_agent_readiness.py"],
                        "delete_allowed": False,
                    }
                )
            )
            temp_path = Path(temp_file.name)

        try:
            rel_path = str(temp_path.relative_to(self.repo_root))
            proc = self._run_cli(rel_path)
            payload = self._parse_stdout(proc)
            self.assertEqual(proc.returncode, 0)
            codes = [item["code"] for item in payload["findings"]]
            self.assertNotIn("FORBIDDEN_PATH", codes)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_docs_generated_backup_not_treated_as_generated_special_case(self):
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            dir=self.repo_root,
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(
                json.dumps(
                    {
                        "task_id": "AGENT-SAFE-004",
                        "goal": "Backup directory is not generated special path",
                        "task_type": "doc_change",
                        "allowed_paths": ["docs/_generated_backup/"],
                        "forbidden_paths": [],
                        "claims": ["CLAIM-AGENT-SAFE-003"],
                        "expected_evidence": ["docs/tasks/board.md"],
                        "validation_commands": ["python3 -m scripts.docmeta.validate_claim_registry"],
                        "delete_allowed": False,
                    }
                )
            )
            temp_path = Path(temp_file.name)

        try:
            rel_path = str(temp_path.relative_to(self.repo_root))
            proc = self._run_cli(rel_path)
            payload = self._parse_stdout(proc)
            self.assertEqual(proc.returncode, 0)
            codes = [item["code"] for item in payload["findings"]]
            self.assertNotIn("FORBIDDEN_PATH", codes)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_missing_scope_emits_code(self):
        proc = self._run_cli(self._fixture("invalid-missing-scope.json"))
        payload = self._parse_stdout(proc)
        codes = [item["code"] for item in payload["findings"]]
        self.assertIn("NO_ALLOWED_PATHS", codes)

    def test_missing_validation_emits_code(self):
        proc = self._run_cli(self._fixture("invalid-missing-validation.json"))
        payload = self._parse_stdout(proc)
        codes = [item["code"] for item in payload["findings"]]
        self.assertIn("NO_VALIDATION_COMMAND", codes)

    def test_missing_evidence_emits_code(self):
        proc = self._run_cli(self._fixture("invalid-missing-evidence.json"))
        payload = self._parse_stdout(proc)
        codes = [item["code"] for item in payload["findings"]]
        self.assertIn("NO_EXPECTED_EVIDENCE", codes)

    def test_unknown_claim_emits_code(self):
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            dir=self.repo_root,
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(
                json.dumps(
                    {
                        "task_id": "AGENT-SAFE-004",
                        "goal": "Unknown claim fixture",
                        "task_type": "governance",
                        "allowed_paths": ["docs/"],
                        "forbidden_paths": [],
                        "claims": ["CLAIM-DOES-NOT-EXIST-999"],
                        "expected_evidence": ["docs/tasks/board.md"],
                        "validation_commands": ["python3 -m scripts.docmeta.validate_claim_registry"],
                        "delete_allowed": False,
                    }
                )
            )
            temp_path = Path(temp_file.name)

        try:
            rel_path = temp_path.relative_to(self.repo_root)
            proc = self._run_cli(str(rel_path))
            payload = self._parse_stdout(proc)
            codes = [item["code"] for item in payload["findings"]]
            self.assertIn("CLAIM_WITHOUT_REGISTRY_ENTRY", codes)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_forbidden_overlap_emits_code(self):
        proc = self._run_cli(self._fixture("invalid-forbidden-path.json"))
        payload = self._parse_stdout(proc)
        codes = [item["code"] for item in payload["findings"]]
        self.assertIn("FORBIDDEN_PATH", codes)

    def test_scope_too_broad_emits_code(self):
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            dir=self.repo_root,
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write(
                json.dumps(
                    {
                        "task_id": "AGENT-SAFE-004",
                        "goal": "Scope must not be broad",
                        "task_type": "governance",
                        "allowed_paths": ["."],
                        "forbidden_paths": [],
                        "claims": ["CLAIM-AGENT-SAFE-003"],
                        "expected_evidence": ["docs/tasks/board.md"],
                        "validation_commands": ["python3 -m scripts.docmeta.validate_claim_registry"],
                        "delete_allowed": False,
                    }
                )
            )
            temp_path = Path(temp_file.name)

        try:
            rel_path = str(temp_path.relative_to(self.repo_root))
            proc = self._run_cli(rel_path)
            payload = self._parse_stdout(proc)
            codes = [item["code"] for item in payload["findings"]]
            self.assertIn("SCOPE_TOO_BROAD", codes)
        finally:
            temp_path.unlink(missing_ok=True)

    def test_whitespace_only_contract_strings_are_rejected(self):
        baseline = json.loads(
            (self.repo_root / self._fixture("valid-doc-drift-task.json")).read_text(
                encoding="utf-8"
            )
        )
        cases = (
            ("goal", "   "),
            ("allowed_paths", ["   "]),
            ("forbidden_paths", ["   "]),
            ("claims", ["   "]),
            ("expected_evidence", ["   "]),
            ("validation_commands", ["   "]),
        )

        for field, value in cases:
            task = dict(baseline)
            task[field] = value
            findings = guard.run_non_ideal_guard(task, {})
            with self.subTest(field=field):
                self.assertTrue(
                    any(
                        finding["code"] == "TASK_SCHEMA_INVALID"
                        and finding.get("field", "").startswith(field)
                        for finding in findings
                    ),
                    findings,
                )

    def test_done_status_emits_code(self):
        proc = self._run_cli(self._fixture("invalid-status-done-by-agent.json"))
        payload = self._parse_stdout(proc)
        codes = [item["code"] for item in payload["findings"]]
        self.assertIn("STATUS_DONE_BY_AGENT", codes)

    def test_missing_task_file_exit_2(self):
        proc = self._run_cli("tests/fixtures/agent/does-not-exist.json")
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stderr)
        self.assertEqual(payload["code"], "TASK_FILE_NOT_FOUND")

    def test_warn_mode_exits_1_on_findings(self):
        proc = self._run_cli(self._fixture("invalid-missing-validation.json"), mode="warn")
        self.assertEqual(proc.returncode, 1)

    def test_report_only_exits_0_on_findings(self):
        proc = self._run_cli(self._fixture("invalid-missing-validation.json"), mode="report-only")
        self.assertEqual(proc.returncode, 0)

    def test_output_is_json_parseable(self):
        proc = self._run_cli(self._fixture("valid-doc-drift-task.json"))
        parsed = json.loads(proc.stdout)
        self.assertIn("findings_count", parsed)
        self.assertIn("findings", parsed)

    def test_claim_registry_invalid_returns_exit_2(self):
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".yml",
            dir=self.repo_root,
            delete=False,
            encoding="utf-8",
        ) as bad_registry:
            bad_registry.write("{broken-json")
            bad_registry_path = Path(bad_registry.name)

        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            dir=self.repo_root,
            delete=False,
            encoding="utf-8",
        ) as task:
            task.write(
                json.dumps(
                    {
                        "task_id": "AGENT-SAFE-004",
                        "goal": "Registry parse failure test",
                        "task_type": "governance",
                        "allowed_paths": ["docs/"],
                        "forbidden_paths": [],
                        "claims": ["CLAIM-AGENT-SAFE-003"],
                        "expected_evidence": ["docs/tasks/board.md"],
                        "validation_commands": ["python3 -m scripts.docmeta.validate_claim_registry"],
                        "delete_allowed": False,
                    }
                )
            )
            task_path = Path(task.name)

        try:
            rel_task = str(task_path.relative_to(self.repo_root))
            rel_registry = str(bad_registry_path.relative_to(self.repo_root))
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.agent.check_non_ideal_task",
                    "--task-file",
                    rel_task,
                    "--claim-registry",
                    rel_registry,
                    "--mode",
                    "report-only",
                ],
                cwd=self.repo_root,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 2)
            parsed = json.loads(proc.stderr)
            self.assertEqual(parsed["code"], "CLAIM_REGISTRY_INVALID")
        finally:
            task_path.unlink(missing_ok=True)
            bad_registry_path.unlink(missing_ok=True)

    def test_absolute_task_path_rejected_with_exit_2(self):
        absolute_task = str((self.repo_root / self._fixture("valid-doc-drift-task.json")).resolve())
        proc = self._run_cli(absolute_task)
        self.assertEqual(proc.returncode, 2)
        parsed = json.loads(proc.stderr)
        self.assertEqual(parsed["code"], "PATH_OUT_OF_REPO")

    def test_parent_traversal_task_path_rejected_with_exit_2(self):
        proc = self._run_cli("../outside.json")
        self.assertEqual(proc.returncode, 2)
        parsed = json.loads(proc.stderr)
        self.assertEqual(parsed["code"], "PATH_OUT_OF_REPO")

    def test_guard_contract_required_fields_match_schema(self):
        schema_path = self.repo_root / "contracts/agent/task.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        required = set(schema.get("required", []))

        self.assertEqual(required, guard.TASK_REQUIRED_FIELDS)

    def test_guard_task_types_match_schema_enum(self):
        schema_path = self.repo_root / "contracts/agent/task.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        task_type_enum = set(schema.get("properties", {}).get("task_type", {}).get("enum", []))

        self.assertEqual(task_type_enum, guard.TASK_TYPES)

    def test_schema_disallows_additional_properties_and_matches_guard_fields(self):
        schema_path = self.repo_root / "contracts/agent/task.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertFalse(schema.get("additionalProperties", True))
        schema_fields = set(schema.get("properties", {}).keys())
        self.assertEqual(schema_fields, guard.TASK_ALLOWED_FIELDS)


if __name__ == "__main__":
    unittest.main()
