from __future__ import annotations

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.agent import run_task
from scripts.agent.json_contract import load_json_strict
from scripts.agent.validate_handoff import validate_handoff
from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.validate_claim_registry import load_registry


class TestRunTask(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(REPO_ROOT)
        self.source_revision = "1" * 40
        registry, findings, exit_code = load_registry(
            self.root / "docs/claims/registry.yml"
        )
        if exit_code != 0 or registry is None:
            raise AssertionError(f"claim registry must load for tests: {findings}")
        self.registry = registry

    def _fixture(self, name: str) -> str:
        return f"tests/fixtures/agent/{name}"

    def _fixture_path(self, name: str) -> Path:
        return self.root / self._fixture(name)

    def _run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "scripts.agent.run_task", *args],
            cwd=self.root,
            check=False,
            text=True,
            capture_output=True,
        )

    def _write_temp_task(self, data: object) -> str:
        handle = tempfile.NamedTemporaryFile(
            "w",
            suffix=".json",
            dir=self.root,
            delete=False,
            encoding="utf-8",
        )
        with handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return str(path.relative_to(self.root))

    def _write_temp_raw(self, raw: str | bytes) -> str:
        mode = "wb" if isinstance(raw, bytes) else "w"
        kwargs = {} if isinstance(raw, bytes) else {"encoding": "utf-8"}
        handle = tempfile.NamedTemporaryFile(
            mode,
            suffix=".json",
            dir=self.root,
            delete=False,
            **kwargs,
        )
        with handle:
            handle.write(raw)
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return str(path.relative_to(self.root))

    @staticmethod
    def _parse_single_json_document(raw: str) -> object:
        decoder = json.JSONDecoder()
        payload, end = decoder.raw_decode(raw)
        if raw[end:].strip():
            raise AssertionError(f"stdout contains trailing non-JSON data: {raw[end:]}")
        return payload

    def _assert_valid_planned_result(self, result: dict, fixture: str) -> None:
        task_path = self.root / fixture
        task = load_json_strict(task_path)
        digest = hashlib.sha256(task_path.read_bytes()).hexdigest()

        self.assertEqual(result["mode"], "dry_run")
        self.assertEqual(result["status"], "planned")
        self.assertEqual(result["task_file"], fixture)
        self.assertEqual(result["task_id"], task["task_id"])
        self.assertEqual(result["task_contract_sha256"], digest)
        self.assertEqual(result["source_revision"], self.source_revision)
        self.assertEqual(
            [item["name"] for item in result["stages"]], run_task.STAGE_NAMES
        )
        self.assertTrue(all(item["status"] == "passed" for item in result["stages"]))
        self.assertEqual(result["findings"], [])
        self.assertTrue(result["repository_unchanged"])

        plan = result["execution_plan"]
        self.assertEqual(plan["allowed_paths"], task["allowed_paths"])
        self.assertEqual(plan["forbidden_paths"], task["forbidden_paths"])
        self.assertEqual(plan["delete_allowed"], task["delete_allowed"])
        self.assertEqual(plan["planned_changed_paths"], [])
        self.assertEqual(plan["planned_deleted_paths"], [])

        handoff = result["handoff"]
        self.assertEqual(handoff["outcome"], "incomplete")
        self.assertEqual(handoff["changed_paths"], [])
        self.assertEqual(handoff["deleted_paths"], [])
        self.assertEqual(handoff["claims_addressed"], task["claims"])
        self.assertEqual(handoff["evidence_produced"], [])
        self.assertEqual(handoff["missing_evidence"], task["expected_evidence"])
        self.assertEqual(
            handoff["validation_results"],
            [
                {"command": command, "status": "not_run"}
                for command in task["validation_commands"]
            ],
        )
        self.assertEqual(handoff["blockers"], [])

        accounting = result["evidence_accounting"]
        self.assertEqual(accounting["expected_evidence"], task["expected_evidence"])
        self.assertEqual(accounting["evidence_produced"], [])
        self.assertEqual(accounting["missing_evidence"], task["expected_evidence"])

        findings = validate_handoff(
            task,
            handoff,
            task_bytes=task_path.read_bytes(),
            repo_root=self.root,
            claim_registry=self.registry,
        )
        self.assertEqual(findings, [])

    def test_positive_fixtures_plan_without_repository_changes(self):
        fixtures = (
            self._fixture("valid-doc-drift-task.json"),
            self._fixture("valid-roadmap-claim-task.json"),
            self._fixture("valid-generated-refresh-task.json"),
        )
        handoff_ids: set[str] = set()
        for fixture in fixtures:
            with self.subTest(fixture=fixture):
                before = run_task.git_status_bytes(self.root)
                outcome = run_task.run_dry_run(
                    repo_root=self.root,
                    task_file=fixture,
                    source_revision=self.source_revision,
                )
                after = run_task.git_status_bytes(self.root)
                self.assertEqual(before, after)
                self.assertEqual(outcome.exit_code, 0)
                self._assert_valid_planned_result(outcome.result, fixture)
                handoff_ids.add(outcome.result["handoff"]["handoff_id"])

        self.assertEqual(len(handoff_ids), len(fixtures))

    def test_generated_refresh_fixture_does_not_execute_generator_command(self):
        readiness = self.root / "docs/_generated/agent-readiness.md"
        before_bytes = readiness.read_bytes()
        outcome = run_task.run_dry_run(
            repo_root=self.root,
            task_file=self._fixture("valid-generated-refresh-task.json"),
            source_revision=self.source_revision,
        )
        self.assertEqual(outcome.exit_code, 0)
        self.assertEqual(readiness.read_bytes(), before_bytes)
        self.assertTrue(
            all(
                item["status"] == "not_run"
                for item in outcome.result["handoff"]["validation_results"]
            )
        )

    def test_cli_emits_single_json_document(self):
        proc = self._run_cli(
            "--dry-run",
            self._fixture("valid-doc-drift-task.json"),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        payload = self._parse_single_json_document(proc.stdout)
        self.assertIsInstance(payload, dict)
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["status"], "planned")

    def test_output_files_are_deterministic_and_do_not_embed_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            out_a = base / "a"
            out_b = base / "b"
            out_a.mkdir()
            out_b.mkdir()

            for output in (out_a, out_b):
                outcome = run_task.run_dry_run(
                    repo_root=self.root,
                    task_file=self._fixture("valid-doc-drift-task.json"),
                    source_revision=self.source_revision,
                    output_dir=output,
                )
                self.assertEqual(outcome.exit_code, 0)
                self.assertEqual(
                    sorted(path.name for path in output.iterdir()),
                    ["handoff.json", "run-result.json"],
                )

            for name in ("handoff.json", "run-result.json"):
                a_bytes = (out_a / name).read_bytes()
                b_bytes = (out_b / name).read_bytes()
                self.assertEqual(a_bytes, b_bytes)
                self.assertNotIn(str(base).encode(), a_bytes)

    def test_malformed_json_duplicate_keys_constants_and_utf8_fail_exit_two(self):
        cases = (
            ("{broken", "TASK_JSON_INVALID"),
            (
                '{"task_id":"AGENT-SAFE-004","task_id":"AGENT-SAFE-005"}',
                "TASK_JSON_DUPLICATE_KEY",
            ),
            ('{"value":NaN}', "TASK_JSON_INVALID"),
            ('{"value":Infinity}', "TASK_JSON_INVALID"),
            (b"\xff", "TASK_UTF8_INVALID"),
        )
        for raw, expected_code in cases:
            with self.subTest(expected_code=expected_code, raw=raw):
                rel = self._write_temp_raw(raw)
                proc = self._run_cli("--dry-run", rel)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(json.loads(proc.stderr)["code"], expected_code)

    def test_schema_invalid_task_blocks_with_not_run_later_stages(self):
        task = load_json_strict(self._fixture_path("valid-doc-drift-task.json"))
        task.pop("goal")
        rel = self._write_temp_task(task)

        proc = self._run_cli("--dry-run", rel)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr, "")
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["stages"][1]["name"], "validate_task_schema")
        self.assertEqual(payload["stages"][1]["status"], "blocked")
        self.assertTrue(
            all(item["status"] == "not_run" for item in payload["stages"][2:])
        )
        self.assertIn(
            "TASK_SCHEMA_INVALID", {item["code"] for item in payload["findings"]}
        )

    def test_whitespace_only_field_blocks(self):
        task = load_json_strict(self._fixture_path("valid-doc-drift-task.json"))
        task["goal"] = "   "
        rel = self._write_temp_task(task)

        proc = self._run_cli("--dry-run", rel)
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertIn(
            "TASK_SCHEMA_INVALID", {item["code"] for item in payload["findings"]}
        )

    def test_non_ideal_and_unknown_claim_tasks_block(self):
        proc = self._run_cli(
            "--dry-run",
            self._fixture("invalid-forbidden-path.json"),
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn(
            "FORBIDDEN_PATH",
            {item["code"] for item in json.loads(proc.stdout)["findings"]},
        )

        task = load_json_strict(self._fixture_path("valid-roadmap-claim-task.json"))
        task["claims"] = ["CLAIM-DOES-NOT-EXIST-999"]
        rel = self._write_temp_task(task)
        proc = self._run_cli("--dry-run", rel)
        self.assertEqual(proc.returncode, 1)
        self.assertIn(
            "CLAIM_WITHOUT_REGISTRY_ENTRY",
            {item["code"] for item in json.loads(proc.stdout)["findings"]},
        )

    def test_absolute_parent_and_external_symlink_task_paths_fail_exit_two(self):
        absolute = str(self._fixture_path("valid-doc-drift-task.json").resolve())
        cases = (
            (absolute, "TASK_PATH_INVALID"),
            ("../outside.json", "TASK_PATH_INVALID"),
        )
        for task_arg, expected_code in cases:
            with self.subTest(task_arg=task_arg):
                proc = self._run_cli("--dry-run", task_arg)
                self.assertEqual(proc.returncode, 2)
                self.assertEqual(json.loads(proc.stderr)["code"], expected_code)

        outside = Path(tempfile.NamedTemporaryFile(delete=False).name)
        self.addCleanup(outside.unlink, missing_ok=True)
        outside.write_bytes(
            self._fixture_path("valid-doc-drift-task.json").read_bytes()
        )
        link = self.root / "run-task-external-task-link.json"
        link.symlink_to(outside)
        self.addCleanup(link.unlink, missing_ok=True)

        proc = self._run_cli("--dry-run", str(link.relative_to(self.root)))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stderr)["code"], "TASK_PATH_INVALID")

    def test_source_revision_unavailable_is_exit_two(self):
        stderr = io.StringIO()
        stdout = io.StringIO()
        with mock.patch.object(
            run_task,
            "resolve_git_head",
            side_effect=run_task.RunnerError(
                "SOURCE_REVISION_UNAVAILABLE",
                "no git head",
            ),
        ):
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = run_task.main(
                    ["--dry-run", self._fixture("valid-doc-drift-task.json")]
                )
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(
            json.loads(stderr.getvalue())["code"], "SOURCE_REVISION_UNAVAILABLE"
        )

    def test_write_flag_is_invalid(self):
        proc = self._run_cli("--write", self._fixture("valid-doc-drift-task.json"))
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(json.loads(proc.stderr)["code"], "INVALID_ARGUMENTS")

    def test_output_directory_rejections(self):
        in_repo = "tests/fixtures/agent/run-task-output"
        proc = self._run_cli(
            "--dry-run",
            "--output-dir",
            in_repo,
            self._fixture("valid-doc-drift-task.json"),
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(json.loads(proc.stderr)["code"], "OUTPUT_DIR_IN_REPOSITORY")

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = base / "symlink-output"
            actual = base / "actual"
            actual.mkdir()
            target.symlink_to(actual)
            proc = self._run_cli(
                "--dry-run",
                "--output-dir",
                str(target),
                self._fixture("valid-doc-drift-task.json"),
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stderr)["code"], "OUTPUT_DIR_INVALID")

            non_empty = base / "non-empty"
            non_empty.mkdir()
            (non_empty / "existing.txt").write_text("x", encoding="utf-8")
            proc = self._run_cli(
                "--dry-run",
                "--output-dir",
                str(non_empty),
                self._fixture("valid-doc-drift-task.json"),
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stderr)["code"], "OUTPUT_DIR_NOT_EMPTY")

            file_target = base / "target-file"
            file_target.write_text("x", encoding="utf-8")
            proc = self._run_cli(
                "--dry-run",
                "--output-dir",
                str(file_target),
                self._fixture("valid-doc-drift-task.json"),
            )
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(json.loads(proc.stderr)["code"], "OUTPUT_DIR_INVALID")

    def test_repository_drift_is_detected(self):
        statuses = [b"", b" M docs/tasks/board.md\n"]

        def reader(_root: Path) -> bytes:
            return statuses.pop(0)

        with self.assertRaises(run_task.RunnerError) as ctx:
            run_task.run_dry_run(
                repo_root=self.root,
                task_file=self._fixture("valid-doc-drift-task.json"),
                source_revision=self.source_revision,
                repository_status_reader=reader,
            )
        self.assertEqual(ctx.exception.code, "REPO_MUTATED_DURING_DRY_RUN")

    def test_invalid_generated_handoff_is_operational_error(self):
        with mock.patch.object(
            run_task,
            "validate_handoff",
            return_value=[{"code": "TEST", "message": "synthetic failure"}],
        ):
            with self.assertRaises(run_task.RunnerError) as ctx:
                run_task.run_dry_run(
                    repo_root=self.root,
                    task_file=self._fixture("valid-doc-drift-task.json"),
                    source_revision=self.source_revision,
                )
        self.assertEqual(ctx.exception.code, "HANDOFF_VALIDATION_FAILED")

    def test_incomplete_evidence_accounting_is_operational_error(self):
        with mock.patch.object(
            run_task,
            "_evidence_accounting",
            return_value={
                "expected_evidence": ["docs/tasks/board.md"],
                "evidence_produced": [],
                "missing_evidence": [],
            },
        ):
            with self.assertRaises(run_task.RunnerError) as ctx:
                run_task.run_dry_run(
                    repo_root=self.root,
                    task_file=self._fixture("valid-doc-drift-task.json"),
                    source_revision=self.source_revision,
                )
        self.assertEqual(ctx.exception.code, "EVIDENCE_ACCOUNTING_INCOMPLETE")

    def test_incomplete_validation_accounting_is_rejected_by_handoff_validator(self):
        original_handoff = run_task._handoff

        def incomplete_handoff(
            task: dict[str, object], task_digest: str, source_revision: str
        ) -> dict[str, object]:
            handoff = original_handoff(task, task_digest, source_revision)
            handoff["validation_results"] = handoff["validation_results"][:-1]
            return handoff

        with mock.patch.object(run_task, "_handoff", side_effect=incomplete_handoff):
            with self.assertRaises(run_task.RunnerError) as ctx:
                run_task.run_dry_run(
                    repo_root=self.root,
                    task_file=self._fixture("valid-doc-drift-task.json"),
                    source_revision=self.source_revision,
                )
        self.assertEqual(ctx.exception.code, "HANDOFF_VALIDATION_FAILED")


if __name__ == "__main__":
    unittest.main()
