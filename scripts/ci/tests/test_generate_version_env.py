from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "apps" / "web" / "scripts" / "generate-version.js"


class GenerateVersionEnvironmentTests(unittest.TestCase):
    commit = "7b65127e852561997fa6a45b8cb3bfcef38e1eb8"

    def run_generator(self, commit: str) -> tuple[subprocess.CompletedProcess[str], Path]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        env = os.environ.copy()
        env.update(
            {
                "GIT_COMMIT_SHA": commit,
                "SOURCE_DATE_EPOCH": "1784139708",
            }
        )
        result = subprocess.run(
            ["node", str(SCRIPT), "--server"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, root / "build" / "_app" / "version.json"

    def test_explicit_commit_produces_deterministic_identity_without_git(self) -> None:
        result, version_file = self.run_generator(self.commit)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(version_file.read_text(encoding="utf-8"))
        self.assertEqual(payload["commit"], self.commit)
        self.assertEqual(payload["version"], self.commit[:8])
        self.assertEqual(payload["build_id"], f"{self.commit[:8]}-1784139708000")
        self.assertEqual(payload["built_at"], "2026-07-15T18:21:48.000Z")

    def test_invalid_explicit_commit_fails_closed(self) -> None:
        result, version_file = self.run_generator("7b65127e")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("GIT_COMMIT_SHA", result.stderr)
        self.assertFalse(version_file.exists())


if __name__ == "__main__":
    unittest.main()
