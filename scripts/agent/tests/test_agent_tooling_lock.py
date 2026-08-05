"""Tests for the hash-bound Python dependency contract used by agent tooling."""

from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.agent.validate_agent_tooling_lock import (
    EXPECTED_ARTIFACT_COUNT,
    EXPECTED_ARTIFACT_SET_SHA256,
    EXPECTED_DEPENDENCY,
    validate_tooling_lock,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


class TestAgentToolingLock(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        target = self.root / "tools" / "py"
        target.mkdir(parents=True)
        shutil.copy2(REPO_ROOT / "tools/py/pyproject.toml", target / "pyproject.toml")
        shutil.copy2(REPO_ROOT / "tools/py/uv.lock", target / "uv.lock")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _replace_lock_once(self, old: str, new: str) -> None:
        path = self.root / "tools/py/uv.lock"
        raw = path.read_text(encoding="utf-8")
        self.assertEqual(raw.count(old), 1)
        path.write_text(raw.replace(old, new, 1), encoding="utf-8")

    def test_repository_lock_contract_is_valid(self) -> None:
        self.assertEqual(validate_tooling_lock(REPO_ROOT), [])

    def test_wrong_artifact_hash_is_rejected(self) -> None:
        lock = (self.root / "tools/py/uv.lock").read_text(encoding="utf-8")
        match = re.search(r"sha256:[0-9a-f]{64}", lock)
        self.assertIsNotNone(match)
        self._replace_lock_once(match.group(0), "sha256:" + "0" * 64)
        findings = validate_tooling_lock(self.root)
        self.assertTrue(
            any(item["code"] == "AGENT_TOOLING_LOCK_ARTIFACT_SET" for item in findings)
        )

    def test_missing_artifact_hash_is_rejected(self) -> None:
        path = self.root / "tools/py/uv.lock"
        raw = path.read_text(encoding="utf-8")
        mutated, count = re.subn(
            r', hash = "sha256:[0-9a-f]{64}"',
            "",
            raw,
            count=1,
        )
        self.assertEqual(count, 1)
        path.write_text(mutated, encoding="utf-8")
        findings = validate_tooling_lock(self.root)
        self.assertTrue(
            any(item["code"] == "AGENT_TOOLING_LOCK_ARTIFACT" for item in findings)
        )

    def test_unreviewed_distribution_is_rejected(self) -> None:
        marker = "wheels = [\n"
        fake = (
            '    { url = "https://files.pythonhosted.org/packages/00/fake.whl", '
            'hash = "sha256:' + "1" * 64 + '", size = 1 },\n'
        )
        self._replace_lock_once(marker, marker + fake)
        findings = validate_tooling_lock(self.root)
        self.assertTrue(
            any(item["code"] == "AGENT_TOOLING_LOCK_ARTIFACT_SET" for item in findings)
        )

    def test_pyproject_version_drift_is_rejected(self) -> None:
        path = self.root / "tools/py/pyproject.toml"
        raw = path.read_text(encoding="utf-8")
        self.assertIn(EXPECTED_DEPENDENCY, raw)
        path.write_text(raw.replace(EXPECTED_DEPENDENCY, "PyYAML==6.0.3"), encoding="utf-8")
        findings = validate_tooling_lock(self.root)
        self.assertTrue(
            any(item["code"] == "AGENT_TOOLING_DEPENDENCY_PIN" for item in findings)
        )

    def test_workflow_and_justfile_use_the_locked_project(self) -> None:
        workflow = (REPO_ROOT / ".github/workflows/agent-safety-preflight.yml").read_text(
            encoding="utf-8"
        )
        justfile = (REPO_ROOT / "Justfile").read_text(encoding="utf-8")
        makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

        self.assertNotRegex(workflow, r"pip install .*PyYAML|pip install .*pyyaml")
        self.assertIn("uv sync --project tools/py --locked", workflow)
        self.assertIn(
            "uv run --project tools/py --locked python -m scripts.agent.validate_agent_tooling_lock",
            workflow,
        )
        self.assertIn(
            "uv run --project tools/py --locked python -m scripts.agent.validate_agent_tooling_lock",
            justfile,
        )
        self.assertIn(
            "uv run --project tools/py --locked python -m scripts.agent.validate_repo_agent_contract",
            justfile,
        )
        # Full make validate path must share the same uv-locked agent semantics.
        self.assertIn("UV_RUN := uv run --project $(UV_PROJECT) --locked", makefile)
        self.assertIn("require-uv-tooling", makefile)
        self.assertIn("agent-contract-check", makefile)
        self.assertIn(
            "$(UV_RUN) python -m scripts.agent.validate_agent_tooling_lock",
            makefile,
        )
        self.assertIn(
            "$(UV_RUN) python -m scripts.agent.validate_repo_agent_contract",
            makefile,
        )
        self.assertIn(
            "$(UV_RUN) python -m unittest discover scripts/agent/tests/",
            makefile,
        )
        self.assertNotRegex(
            makefile,
            r"(?m)^validate-tests:.*\n(?:\t.*\n)*?\tpython3 -m unittest discover scripts/agent/tests/",
        )

    def test_reviewed_artifact_contract_is_explicit(self) -> None:
        self.assertEqual(EXPECTED_ARTIFACT_COUNT, 28)
        self.assertRegex(EXPECTED_ARTIFACT_SET_SHA256, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
