from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.agent import validate_handoff as validator
from scripts.docmeta.docmeta import REPO_ROOT


class TestValidateHandoff(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(REPO_ROOT)
        self.task_path = self.repo_root / "tests/fixtures/agent/handoff-task.json"
        self.handoff_path = self.repo_root / "tests/fixtures/agent/handoff-valid.json"
        self.task = json.loads(self.task_path.read_text(encoding="utf-8"))
        self.handoff = json.loads(self.handoff_path.read_text(encoding="utf-8"))
        self.task_bytes = self.task_path.read_bytes()

    def _validate(self, handoff: dict) -> list[dict[str, str]]:
        return validator.validate_handoff(self.task, handoff, task_bytes=self.task_bytes)

    def _codes(self, findings: list[dict[str, str]]) -> list[str]:
        return [finding["code"] for finding in findings]

    def _run_cli(self, handoff_name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                "-m",
                "scripts.agent.validate_handoff",
                "--task-file",
                "tests/fixtures/agent/handoff-task.json",
                "--handoff-file",
                f"tests/fixtures/agent/{handoff_name}",
            ],
            cwd=self.repo_root,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_valid_fixture_passes(self):
        self.assertEqual(self._validate(self.handoff), [])

    def test_valid_cli_exits_zero(self):
        proc = self._run_cli("handoff-valid.json")
        payload = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(payload["status"], "valid")
        self.assertEqual(payload["findings_count"], 0)

    def test_invalid_digest_is_rejected(self):
        proc = self._run_cli("handoff-invalid-digest.json")
        payload = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("TASK_DIGEST_MISMATCH", self._codes(payload["findings"]))

    def test_path_escape_is_rejected(self):
        proc = self._run_cli("handoff-invalid-path.json")
        payload = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("PATH_OUT_OF_REPO", self._codes(payload["findings"]))

    def test_ready_for_review_with_gap_is_rejected(self):
        proc = self._run_cli("handoff-invalid-outcome.json")
        payload = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("CONTRADICTORY_OUTCOME", self._codes(payload["findings"]))

    def test_task_id_mismatch_is_rejected(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["task_id"] = "AGENT-SAFE-003"
        self.assertIn("TASK_ID_MISMATCH", self._codes(self._validate(handoff)))

    def test_undeclared_claim_is_rejected(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["claims_addressed"] = ["CLAIM-DOES-NOT-EXIST-999"]
        self.assertIn("CLAIM_NOT_DECLARED", self._codes(self._validate(handoff)))

    def test_deletion_without_permission_is_rejected(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["deleted_paths"] = ["scripts/agent/obsolete.py"]
        self.assertIn("DELETE_WITHOUT_PERMISSION", self._codes(self._validate(handoff)))

    def test_expected_evidence_must_be_accounted_for(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["evidence_produced"] = ["contracts/agent/handoff.schema.json"]
        self.assertIn(
            "EXPECTED_EVIDENCE_UNACCOUNTED",
            self._codes(self._validate(handoff)),
        )

    def test_required_validation_result_must_exist(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["validation_results"] = []
        self.assertIn("VALIDATION_RESULT_MISSING", self._codes(self._validate(handoff)))

    def test_blocked_requires_blocker(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["outcome"] = "blocked"
        self.assertIn("CONTRADICTORY_OUTCOME", self._codes(self._validate(handoff)))

    def test_incomplete_requires_gap(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["outcome"] = "incomplete"
        self.assertIn("CONTRADICTORY_OUTCOME", self._codes(self._validate(handoff)))

    def test_findings_are_deterministic(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["task_id"] = "AGENT-SAFE-003"
        handoff["changed_paths"] = ["../outside.txt"]
        first = self._validate(handoff)
        second = self._validate(handoff)
        self.assertEqual(first, second)
        keys = [(item["code"], item.get("field", ""), item["message"]) for item in first]
        self.assertEqual(keys, sorted(keys))

    def test_missing_handoff_file_exits_two(self):
        proc = self._run_cli("does-not-exist.json")
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stderr)
        self.assertEqual(payload["code"], "HANDOFF_FILE_NOT_FOUND")

    def test_absolute_input_path_exits_two(self):
        proc = subprocess.run(
            [
                "python3",
                "-m",
                "scripts.agent.validate_handoff",
                "--task-file",
                str(self.task_path.resolve()),
                "--handoff-file",
                "tests/fixtures/agent/handoff-valid.json",
            ],
            cwd=self.repo_root,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stderr)["code"], "PATH_OUT_OF_REPO")

    def test_handoff_fixture_digest_matches_task_bytes(self):
        expected = hashlib.sha256(self.task_bytes).hexdigest()
        self.assertEqual(self.handoff["task_contract_sha256"], expected)

    def test_schema_and_validator_required_fields_match(self):
        schema = json.loads(
            (self.repo_root / "contracts/agent/handoff.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(schema["required"]), validator.HANDOFF_REQUIRED_FIELDS)
        self.assertEqual(set(schema["properties"]), validator.HANDOFF_ALLOWED_FIELDS)
        self.assertFalse(schema["additionalProperties"])

    def test_schema_and_validator_enums_match(self):
        schema = json.loads(
            (self.repo_root / "contracts/agent/handoff.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            set(schema["properties"]["outcome"]["enum"]),
            validator.HANDOFF_OUTCOMES,
        )
        validation_statuses = set(
            schema["properties"]["validation_results"]["items"]["properties"][
                "status"
            ]["enum"]
        )
        self.assertEqual(validation_statuses, validator.VALIDATION_STATUSES)

    def test_malformed_json_exits_two(self):
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            dir=self.repo_root,
            delete=False,
            encoding="utf-8",
        ) as temp_file:
            temp_file.write("{broken")
            temp_path = Path(temp_file.name)
        try:
            proc = subprocess.run(
                [
                    "python3",
                    "-m",
                    "scripts.agent.validate_handoff",
                    "--task-file",
                    "tests/fixtures/agent/handoff-task.json",
                    "--handoff-file",
                    str(temp_path.relative_to(self.repo_root)),
                ],
                cwd=self.repo_root,
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stderr)["code"], "HANDOFF_JSON_INVALID")
        finally:
            temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
