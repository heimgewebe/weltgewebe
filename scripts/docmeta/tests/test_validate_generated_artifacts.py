import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.docmeta import validate_generated_artifacts as validator


class TestValidateGeneratedArtifacts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._write_minimal_repo()

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, rel_path: str, content: str = "fixture\n") -> None:
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _manifest(self) -> dict:
        command_a = ["python3", "-m", "scripts.docmeta.generate_agent_readiness"]
        command_b = ["python3", "-m", "scripts.docmeta.generate_claim_evidence_map"]
        return {
            "schema_version": 1,
            "artifacts": [
                {
                    "path": "docs/_generated/agent-readiness.md",
                    "kind": "generated",
                    "role": "diagnostic",
                    "canonicality": "derived",
                    "generator": command_a,
                    "checks": [command_a + ["--check"]],
                    "sources": ["scripts/agent", "docs/claims/registry.yml"],
                    "commit_required": True,
                    "blocking": True,
                },
                {
                    "path": "docs/_generated/claim-evidence-map.md",
                    "kind": "generated",
                    "role": "diagnostic",
                    "canonicality": "derived",
                    "generator": command_b,
                    "checks": [command_b + ["--check"]],
                    "sources": ["docs/doc-freshness-registry.yml"],
                    "commit_required": True,
                    "blocking": True,
                },
                {
                    "path": "docs/tasks/index.json",
                    "kind": "curated_index",
                    "role": "task_control",
                    "canonicality": "canonical",
                    "checks": [
                        [
                            "python3",
                            "-m",
                            "scripts.docmeta.validate_task_index",
                            "docs/tasks/index.json",
                        ],
                        [
                            "python3",
                            "-m",
                            "scripts.docmeta.generate_task_index",
                            "--check",
                        ],
                    ],
                    "sources": ["docs/tasks/board.md"],
                    "commit_required": True,
                    "blocking": True,
                },
            ],
        }

    def _write_manifest(self, data: dict) -> None:
        self._write(
            validator.MANIFEST_REL,
            "---\n" + json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        )

    def _write_minimal_repo(self) -> None:
        for module in (
            "generate_agent_readiness",
            "generate_claim_evidence_map",
            "validate_task_index",
            "generate_task_index",
        ):
            self._write(f"scripts/docmeta/{module}.py", "# module\n")
        self._write("scripts/agent/.keep")
        self._write("docs/claims/registry.yml")
        self._write("docs/doc-freshness-registry.yml")
        self._write("docs/tasks/board.md")
        self._write("docs/tasks/index.json", "{}\n")
        marker = "Generated automatically. Do not edit.\n"
        self._write("docs/_generated/agent-readiness.md", marker)
        self._write("docs/_generated/claim-evidence-map.md", marker)
        self._write(
            "repo.meta.yaml",
            "generated_artifacts:\n"
            "  - docs/_generated/agent-readiness.md\n"
            "  - docs/_generated/claim-evidence-map.md\n"
            "required_checks: []\n",
        )
        self._write_manifest(self._manifest())

    def _codes(self) -> set[str]:
        return {item["code"] for item in validator.validate_manifest(self.root)}

    def test_valid_manifest_passes(self):
        self.assertEqual(validator.validate_manifest(self.root), [])

    def test_generated_role_must_be_diagnostic(self):
        data = self._manifest()
        data["artifacts"][0]["role"] = "task_control"
        self._write_manifest(data)
        self.assertIn("ARTIFACT_ROLE_INVALID", self._codes())

    def test_curated_index_role_must_be_task_control(self):
        data = self._manifest()
        data["artifacts"][2]["role"] = "diagnostic"
        self._write_manifest(data)
        self.assertIn("ARTIFACT_ROLE_INVALID", self._codes())

    def test_docs_guard_covers_declared_source_roots(self):
        workflow = (
            Path(validator.REPO_ROOT) / ".github/workflows/docs-guard.yml"
        ).read_text(encoding="utf-8")
        for trigger in (
            "contracts/agent/**",
            "scripts/agent/**",
            "tests/fixtures/agent/**",
            "scripts/contracts-agent-check.sh",
            "docs/tasks/schema.json",
            "docs/reference/agent-run-evidence-lite.md",
            "docs/security/agent-write-scope-baseline.md",
        ):
            with self.subTest(trigger=trigger):
                self.assertIn(f"- '{trigger}'", workflow)

    def test_required_artifact_cannot_be_removed_from_manifest(self):
        data = self._manifest()
        data["artifacts"] = data["artifacts"][1:]
        self._write_manifest(data)
        self.assertIn("REQUIRED_ARTIFACT_MISSING", self._codes())

    def test_generated_artifact_requires_marker(self):
        self._write("docs/_generated/agent-readiness.md", "manual edit\n")
        self.assertIn("GENERATED_MARKER_MISSING", self._codes())

    def test_curated_index_must_not_claim_a_generator(self):
        data = self._manifest()
        data["artifacts"][2]["generator"] = [
            "python3",
            "-m",
            "scripts.docmeta.validate_task_index",
        ]
        self._write_manifest(data)
        self.assertIn("CURATED_GENERATOR_FORBIDDEN", self._codes())

    def test_generated_output_cannot_be_its_own_source(self):
        data = self._manifest()
        data["artifacts"][0]["sources"] = [
            "docs/_generated/agent-readiness.md"
        ]
        self._write_manifest(data)
        self.assertIn("GENERATED_SOURCE_INVALID", self._codes())

    def test_generated_scope_must_match_repo_meta(self):
        data = self._manifest()
        data["artifacts"].append(
            {
                "path": "docs/_generated/extra.md",
                "kind": "generated",
                "role": "diagnostic",
                "canonicality": "derived",
                "generator": [
                    "python3",
                    "-m",
                    "scripts.docmeta.generate_agent_readiness",
                ],
                "checks": [
                    [
                        "python3",
                        "-m",
                        "scripts.docmeta.generate_agent_readiness",
                        "--check",
                    ]
                ],
                "sources": ["docs/claims/registry.yml"],
                "commit_required": True,
                "blocking": True,
            }
        )
        self._write("docs/_generated/extra.md", "Generated automatically.\n")
        self._write_manifest(data)
        self.assertIn("REPO_META_GENERATED_DRIFT", self._codes())

    def test_generated_check_cannot_call_writing_generator(self):
        data = self._manifest()
        data["artifacts"][0]["checks"] = [
            ["python3", "-m", "scripts.docmeta.generate_agent_readiness"]
        ]
        self._write_manifest(data)
        self.assertIn("CHECK_COMMAND_MISMATCH", self._codes())

    def test_repository_external_command_is_rejected(self):
        data = self._manifest()
        data["artifacts"][0]["checks"] = [["bash", "-lc", "true"]]
        self._write_manifest(data)
        self.assertIn("COMMAND_NOT_ALLOWED", self._codes())

    def test_reviewed_shell_generator_is_allowed(self):
        self._write("scripts/docmeta/generate-fixture.sh", "#!/usr/bin/env bash\n")
        data = self._manifest()
        data["artifacts"][0]["generator"] = ["bash", "scripts/docmeta/generate-fixture.sh"]
        self._write_manifest(data)
        self.assertNotIn("COMMAND_NOT_ALLOWED", self._codes())

    def test_reviewed_shell_generator_check_argument_is_allowed(self):
        self._write("scripts/docmeta/generate-fixture.sh", "#!/usr/bin/env bash\n")
        data = self._manifest()
        data["artifacts"][0]["generator"] = ["bash", "scripts/docmeta/generate-fixture.sh"]
        data["artifacts"][0]["checks"] = [["bash", "scripts/docmeta/generate-fixture.sh", "--check"]]
        self._write_manifest(data)
        self.assertNotIn("COMMAND_NOT_ALLOWED", self._codes())

    def test_reviewed_shell_generator_extra_argument_is_rejected(self):
        self._write("scripts/docmeta/generate-fixture.sh", "#!/usr/bin/env bash\n")
        data = self._manifest()
        data["artifacts"][0]["generator"] = ["bash", "scripts/docmeta/generate-fixture.sh"]
        data["artifacts"][0]["checks"] = [["bash", "scripts/docmeta/generate-fixture.sh", "--write"]]
        self._write_manifest(data)
        self.assertIn("COMMAND_NOT_ALLOWED", self._codes())

    def test_symlink_parent_source_is_rejected(self):
        source_dir = self.root / "docs" / "claims"
        target_dir = self.root / "real-claims"
        source_dir.rename(target_dir)
        source_dir.symlink_to(target_dir, target_is_directory=True)
        self.assertIn("SOURCE_MISSING", self._codes())

    def test_duplicate_manifest_key_is_rejected(self):
        self._write(
            validator.MANIFEST_REL,
            '---\n{"schema_version":1,"schema_version":1,"artifacts":[]}\n',
        )
        self.assertEqual(self._codes(), {"MANIFEST_JSON_INVALID"})

    def test_check_failure_is_bound_to_artifact(self):
        calls: list[list[str]] = []

        def failing_runner(command, **kwargs):
            calls.append(command)
            self.assertEqual(command[0], sys.executable)
            self.assertEqual(kwargs["env"]["PYTHONNOUSERSITE"], "1")
            self.assertNotIn("PYTHONPATH", kwargs["env"])
            return subprocess.CompletedProcess(
                command,
                1,
                stdout="",
                stderr="synthetic drift",
            )

        findings = validator.validate_manifest(
            self.root,
            run_checks=True,
            runner=failing_runner,
        )
        self.assertEqual(len(calls), 4)
        self.assertEqual(
            {item["code"] for item in findings},
            {"ARTIFACT_CHECK_FAILED"},
        )
        self.assertTrue(all("synthetic drift" in item["detail"] for item in findings))


if __name__ == "__main__":
    unittest.main()
