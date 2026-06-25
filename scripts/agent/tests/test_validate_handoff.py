from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def _cli(
        self,
        handoff_name: str,
        *,
        task_file: str = "tests/fixtures/agent/handoff-task.json",
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                "-m",
                "scripts.agent.validate_handoff",
                "--task-file",
                task_file,
                "--handoff-file",
                f"tests/fixtures/agent/{handoff_name}",
            ],
            cwd=self.root,
            check=False,
            text=True,
            capture_output=True,
        )

    def _fixture(self, name: str) -> dict:
        return load_json_strict(self.root / "tests/fixtures/agent" / name)

    def _temporary_repo(self) -> Path:
        root = Path(tempfile.mkdtemp())
        for rel in (
            "contracts/agent/task.schema.json",
            "contracts/agent/handoff.schema.json",
            "tests/fixtures/agent/handoff-task.json",
            "tests/fixtures/agent/handoff-valid.json",
            "docs/claims/registry.yml",
        ):
            source = self.root / rel
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        registry_raw = (root / "docs/claims/registry.yml").read_text(
            encoding="utf-8"
        )
        registry = json.loads(registry_raw[4:])
        for claim in registry.get("claims", []):
            for evidence in claim.get("evidence", []):
                rel = evidence.get("path")
                if not isinstance(rel, str) or not rel:
                    continue
                source = self.root / rel
                if not source.is_file():
                    continue
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        return root

    def _main_in_repo(self, root: Path) -> tuple[int, dict]:
        stderr = io.StringIO()
        with mock.patch.object(validator, "REPO_ROOT", root):
            with contextlib.redirect_stderr(stderr):
                rc = validator.main(
                    [
                        "--task-file",
                        "tests/fixtures/agent/handoff-task.json",
                        "--handoff-file",
                        "tests/fixtures/agent/handoff-valid.json",
                    ]
                )
        return rc, json.loads(stderr.getvalue())

    def test_valid_fixture_and_cli_pass(self):
        self.assertEqual(self._validate(self.handoff), [])
        proc = self._cli("handoff-valid.json")
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "valid")
        self.assertEqual(payload["findings"], [])

    def test_invalid_fixtures_have_exact_findings(self):
        cases = {
            "handoff-invalid-digest.json": ["TASK_DIGEST_MISMATCH"],
            "handoff-invalid-path.json": ["PATH_OUT_OF_REPO"],
            "handoff-invalid-outcome.json": ["CONTRADICTORY_OUTCOME"],
        }
        for fixture, expected_codes in cases.items():
            with self.subTest(fixture=fixture):
                proc = self._cli(fixture)
                self.assertEqual(proc.returncode, 1)
                payload = json.loads(proc.stdout)
                self.assertEqual(self._codes(payload["findings"]), expected_codes)

    def test_invalid_fixtures_are_single_mutations_of_valid_fixture(self):
        cases = {
            "handoff-invalid-digest.json": {"task_contract_sha256"},
            "handoff-invalid-path.json": {"changed_paths"},
            "handoff-invalid-outcome.json": {"outcome"},
        }
        baseline_keys = set(self.handoff)
        for fixture, expected_fields in cases.items():
            candidate = self._fixture(fixture)
            changed = {
                key
                for key in baseline_keys | set(candidate)
                if candidate.get(key) != self.handoff.get(key)
            }
            with self.subTest(fixture=fixture):
                self.assertEqual(changed, expected_fields)

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

    def test_unexpected_missing_evidence_is_rejected(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["outcome"] = "incomplete"
        handoff["missing_evidence"] = ["scripts/agent/not-required.py"]
        self.assertEqual(
            self._codes(self._validate(handoff)),
            ["UNEXPECTED_MISSING_EVIDENCE"],
        )

    def test_expected_missing_evidence_can_justify_incomplete(self):
        expected = self.task["expected_evidence"][0]
        handoff = copy.deepcopy(self.handoff)
        handoff["outcome"] = "incomplete"
        handoff["evidence_produced"].remove(expected)
        handoff["missing_evidence"] = [expected]
        self.assertEqual(self._validate(handoff), [])

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
        codes = self._codes(self._validate(handoff))
        self.assertIn("VALIDATION_RESULT_MISSING", codes)
        self.assertIn("CONTRADICTORY_OUTCOME", codes)

        for status in ("failed", "not_run"):
            handoff = copy.deepcopy(self.handoff)
            handoff["validation_results"][0]["status"] = status
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

    def test_incomplete_accepts_explicit_failed_or_not_run_result(self):
        for status in ("failed", "not_run"):
            handoff = copy.deepcopy(self.handoff)
            handoff["outcome"] = "incomplete"
            handoff["validation_results"][0]["status"] = status
            with self.subTest(status=status):
                self.assertEqual(self._validate(handoff), [])

    def test_incomplete_missing_result_is_invalid_without_outcome_noise(self):
        handoff = copy.deepcopy(self.handoff)
        handoff["outcome"] = "incomplete"
        handoff["validation_results"].pop()
        self.assertEqual(
            self._codes(self._validate(handoff)),
            ["VALIDATION_RESULT_MISSING"],
        )

    def test_incomplete_unaddressed_claim_is_invalid_without_outcome_noise(self):
        task = copy.deepcopy(self.task)
        task["claims"].append("CLAIM-AGENT-SAFE-001")
        handoff = copy.deepcopy(self.handoff)
        handoff["outcome"] = "incomplete"
        self.assertEqual(
            self._codes(self._validate(handoff, task=task, bind_digest=True)),
            ["CLAIM_NOT_ADDRESSED"],
        )

    def test_residual_gap_is_allowed_for_review_or_incomplete(self):
        for outcome in ("ready_for_review", "incomplete"):
            handoff = copy.deepcopy(self.handoff)
            handoff["outcome"] = outcome
            handoff["residual_gaps"] = [
                "independent run attestation is outside this slice"
            ]
            with self.subTest(outcome=outcome):
                self.assertEqual(self._validate(handoff), [])
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

    def test_non_standard_json_constants_exit_two_for_task_and_handoff(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", dir=self.root, delete=False
            ) as handle:
                handle.write(f'{{"value":{constant}}}\n')
                path = Path(handle.name)
            rel = str(path.relative_to(self.root))
            try:
                cases = (
                    (
                        [
                            "python3",
                            "-m",
                            "scripts.agent.validate_handoff",
                            "--task-file",
                            rel,
                            "--handoff-file",
                            "tests/fixtures/agent/handoff-valid.json",
                        ],
                        "TASK_JSON_INVALID",
                    ),
                    (
                        [
                            "python3",
                            "-m",
                            "scripts.agent.validate_handoff",
                            "--task-file",
                            "tests/fixtures/agent/handoff-task.json",
                            "--handoff-file",
                            rel,
                        ],
                        "HANDOFF_JSON_INVALID",
                    ),
                )
                for argv, expected in cases:
                    with self.subTest(constant=constant, code=expected):
                        proc = subprocess.run(
                            argv,
                            cwd=self.root,
                            check=False,
                            text=True,
                            capture_output=True,
                        )
                        self.assertEqual(proc.returncode, 2)
                        self.assertEqual(json.loads(proc.stderr)["code"], expected)
            finally:
                path.unlink(missing_ok=True)

    def test_contract_schema_errors_have_stable_codes(self):
        cases = (
            ("{broken", "CONTRACT_SCHEMA_INVALID"),
            ('{"type":"object","type":"array"}', "CONTRACT_SCHEMA_INVALID"),
            ('{"type":"object","format":"uuid"}', "CONTRACT_SCHEMA_UNSUPPORTED"),
        )
        for schema_raw, expected_code in cases:
            root = self._temporary_repo()
            try:
                (root / "contracts/agent/task.schema.json").write_text(
                    schema_raw,
                    encoding="utf-8",
                )
                rc, payload = self._main_in_repo(root)
                with self.subTest(expected_code=expected_code):
                    self.assertEqual(rc, 2)
                    self.assertEqual(payload["code"], expected_code)
            finally:
                shutil.rmtree(root)


if __name__ == "__main__":
    unittest.main()
