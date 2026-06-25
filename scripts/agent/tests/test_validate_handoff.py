from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.agent import validate_handoff as validator
from scripts.agent.json_contract import load_json_strict
from scripts.docmeta.docmeta import REPO_ROOT


class TestValidateHandoff(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(REPO_ROOT)
        self.task_path = self.root / "tests/fixtures/agent/handoff-task.json"
        self.handoff_path = self.root / "tests/fixtures/agent/handoff-valid.json"
        self.task = load_json_strict(self.task_path)
        self.handoff = load_json_strict(self.handoff_path)
        self.registry = json.loads(
            (self.root / "docs/claims/registry.yml").read_text(encoding="utf-8")[4:]
        )

    @staticmethod
    def _task_bytes(task: dict) -> bytes:
        return (json.dumps(task, ensure_ascii=False, indent=2) + "\n").encode()

    def _validate(
        self,
        handoff: dict,
        *,
        task: dict | None = None,
        bind_digest: bool = False,
    ) -> list[dict[str, str]]:
        task_data = copy.deepcopy(task if task is not None else self.task)
        handoff_data = copy.deepcopy(handoff)
        task_bytes = self._task_bytes(task_data)
        if bind_digest:
            handoff_data["task_contract_sha256"] = hashlib.sha256(task_bytes).hexdigest()
        return validator.validate_handoff(
            task_data,
            handoff_data,
            task_bytes=task_bytes,
            repo_root=self.root,
            claim_registry=self.registry,
        )

    @staticmethod
    def _codes(findings: list[dict[str, str]]) -> list[str]:
        return [item["code"] for item in findings]

    def _cli(self, handoff_name: str) -> subprocess.CompletedProcess[str]:
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
            cwd=self.root,
            check=False,
            text=True,
            capture_output=True,
        )

    def test_valid_fixture_and_cli_pass(self):
        self.assertEqual(self._validate(self.handoff), [])
        proc = self._cli("handoff-valid.json")
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(json.loads(proc.stdout)["status"], "valid")

    def test_invalid_fixtures_fail_as_expected(self):
        cases = {
            "handoff-invalid-digest.json": "TASK_DIGEST_MISMATCH",
            "handoff-invalid-path.json": "PATH_OUT_OF_REPO",
        }
        for fixture, code in cases.items():
            with self.subTest(fixture=fixture):
                proc = self._cli(fixture)
                self.assertEqual(proc.returncode, 1)
                self.assertIn(code, self._codes(json.loads(proc.stdout)["findings"]))

    def test_canonical_task_schema_rejects_false_greens(self):
        mutations = (
            lambda task: task.pop("goal"),
            lambda task: task.pop("task_type"),
            lambda task: task.__setitem__("invented", True),
            lambda task: task.__setitem__("expected_evidence", []),
            lambda task: task.__setitem__("validation_commands", []),
        )
        for mutate in mutations:
            task = copy.deepcopy(self.task)
            mutate(task)
            with self.subTest(task=task):
                self.assertIn(
                    "TASK_SCHEMA_INVALID",
                    self._codes(self._validate(self.handoff, task=task, bind_digest=True)),
                )

    def test_task_id_and_claim_binding(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["task_id"] = "AGENT-SAFE-003"
        self.assertIn("TASK_ID_MISMATCH", self._codes(self._validate(handoff)))

        task = copy.deepcopy(self.task)
        task["claims"].append("CLAIM-AGENT-SAFE-001")
        self.assertIn(
            "CLAIM_NOT_ADDRESSED",
            self._codes(self._validate(self.handoff, task=task, bind_digest=True)),
        )

        handoff = copy.deepcopy(self.handoff)
        handoff["claims_addressed"] = ["CLAIM-AGENT-SAFE-001"]
        self.assertIn("CLAIM_NOT_DECLARED", self._codes(self._validate(handoff)))

    def test_scope_and_deletion_rules(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["deleted_paths"] = ["scripts/agent/obsolete.py"]
        self.assertIn("DELETE_WITHOUT_PERMISSION", self._codes(self._validate(handoff)))

        task = copy.deepcopy(self.task)
        task["delete_allowed"] = True
        handoff["changed_paths"] = ["scripts/agent/validate_handoff.py"]
        handoff["deleted_paths"] = [r"scripts\agent\validate_handoff.py"]
        self.assertIn(
            "PATH_STATE_CONTRADICTION",
            self._codes(self._validate(handoff, task=task, bind_digest=True)),
        )

        task["allowed_paths"] = ["scripts/agent/validate_handoff.py"]
        handoff["changed_paths"] = ["scripts/agent/validate_handoff.py/child"]
        handoff["deleted_paths"] = []
        self.assertIn(
            "PATH_OUT_OF_SCOPE",
            self._codes(self._validate(handoff, task=task, bind_digest=True)),
        )

    def test_evidence_must_be_accounted_and_exist(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["evidence_produced"] = ["contracts/agent/handoff.schema.json"]
        self.assertIn(
            "EXPECTED_EVIDENCE_UNACCOUNTED", self._codes(self._validate(handoff))
        )

        task = copy.deepcopy(self.task)
        task["expected_evidence"].append("scripts/agent/does-not-exist.py")
        handoff = copy.deepcopy(self.handoff)
        handoff["evidence_produced"].append("scripts/agent/does-not-exist.py")
        self.assertIn(
            "EVIDENCE_NOT_FOUND",
            self._codes(self._validate(handoff, task=task, bind_digest=True)),
        )

        handoff = copy.deepcopy(self.handoff)
        handoff["missing_evidence"] = [r"contracts\agent\handoff.schema.json"]
        self.assertIn(
            "EVIDENCE_STATE_CONTRADICTION", self._codes(self._validate(handoff))
        )

    def test_evidence_symlink_cannot_escape_repo(self):
        outside = Path(tempfile.mkstemp()[1])
        link = self.root / "tests/fixtures/agent/outside-evidence-link.tmp"
        try:
            link.symlink_to(outside)
            rel = str(link.relative_to(self.root))
            task = copy.deepcopy(self.task)
            task["expected_evidence"].append(rel)
            handoff = copy.deepcopy(self.handoff)
            handoff["evidence_produced"].append(rel)
            self.assertIn(
                "EVIDENCE_NOT_FOUND",
                self._codes(self._validate(handoff, task=task, bind_digest=True)),
            )
        finally:
            link.unlink(missing_ok=True)
            outside.unlink(missing_ok=True)

    def test_validation_results_control_outcome(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["validation_results"] = []
        self.assertIn("VALIDATION_RESULT_MISSING", self._codes(self._validate(handoff)))

        for status in ("failed", "not_run"):
            handoff = copy.deepcopy(self.handoff)
            handoff["validation_results"].append(
                {"command": f"extra-{status}", "status": status}
            )
            with self.subTest(status=status):
                self.assertIn(
                    "CONTRADICTORY_OUTCOME", self._codes(self._validate(handoff))
                )

        handoff = copy.deepcopy(self.handoff)
        duplicate = copy.deepcopy(handoff["validation_results"][0])
        duplicate["status"] = "failed"
        handoff["validation_results"].append(duplicate)
        self.assertIn(
            "VALIDATION_RESULT_DUPLICATE", self._codes(self._validate(handoff))
        )

    def test_residual_gap_is_allowed_for_review(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["residual_gaps"] = ["independent run attestation is outside this slice"]
        self.assertNotIn("CONTRADICTORY_OUTCOME", self._codes(self._validate(handoff)))
        proc = self._cli("handoff-valid-residual-gap.json")
        self.assertEqual(proc.returncode, 0)

    def test_missing_field_has_one_schema_finding(self):
        handoff = copy.deepcopy(self.handoff)
        handoff.pop("changed_paths")
        matches = [
            item
            for item in self._validate(handoff)
            if item["code"] == "HANDOFF_SCHEMA_INVALID"
            and item.get("field") == "changed_paths"
        ]
        self.assertEqual(len(matches), 1)

    def test_findings_are_deterministic(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["task_id"] = "AGENT-SAFE-003"
        handoff["changed_paths"] = ["../outside.txt"]
        first = self._validate(handoff)
        self.assertEqual(first, self._validate(handoff))
        keys = [(item["code"], item.get("field", ""), item["message"]) for item in first]
        self.assertEqual(keys, sorted(keys))

    def test_digest_fixture_matches_task_bytes(self):
        self.assertEqual(
            self.handoff["task_contract_sha256"],
            hashlib.sha256(self.task_path.read_bytes()).hexdigest(),
        )

    def test_duplicate_key_and_malformed_json_exit_two(self):
        variants = (
            ("{broken", "HANDOFF_JSON_INVALID"),
            (
                self.handoff_path.read_text().replace(
                    '"outcome": "ready_for_review",',
                    '"outcome": "blocked",\n  "outcome": "ready_for_review",',
                ),
                "DUPLICATE_JSON_KEY",
            ),
        )
        for raw, code in variants:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", dir=self.root, delete=False
            ) as handle:
                handle.write(raw)
                path = Path(handle.name)
            try:
                proc = subprocess.run(
                    [
                        "python3",
                        "-m",
                        "scripts.agent.validate_handoff",
                        "--task-file",
                        "tests/fixtures/agent/handoff-task.json",
                        "--handoff-file",
                        str(path.relative_to(self.root)),
                    ],
                    cwd=self.root,
                    check=False,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(json.loads(proc.stderr)["code"], code)
            finally:
                path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
