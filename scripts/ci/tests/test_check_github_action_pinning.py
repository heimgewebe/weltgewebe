from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "check_github_action_pinning.py"


class CheckGitHubActionPinningTest(unittest.TestCase):
    def run_checker(self, workflow: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            workflows_dir = repo / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)
            (workflows_dir / "audit.yml").write_text(workflow, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

    def test_sha_pinned_action_is_classified(self) -> None:
        result = self.run_checker(
            """
name: pin
on: workflow_dispatch
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@1234567890123456789012345678901234567890
"""
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("kind.github-action=1", result.stdout)
        self.assertIn("policy.pinned-sha=1", result.stdout)

    def test_named_action_ref_is_classified(self) -> None:
        result = self.run_checker(
            """
name: tag
on: workflow_dispatch
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("policy.named-ref=1", result.stdout)

    def test_reusable_default_branch_is_classified(self) -> None:
        result = self.run_checker(
            """
name: reusable
on: workflow_dispatch
jobs:
  call:
    uses: owner/repo/.github/workflows/reusable.yml@main
"""
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("kind.reusable-workflow=1", result.stdout)
        self.assertIn("policy.mutable-default-branch=1", result.stdout)

    def test_local_action_is_not_sha_pinning_scope(self) -> None:
        result = self.run_checker(
            """
name: local
on: workflow_dispatch
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/local
"""
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("kind.local-action=1", result.stdout)
        self.assertIn("policy.local=1", result.stdout)

    def test_inline_comment_is_ignored_for_sha_ref(self) -> None:
        result = self.run_checker(
            """
name: pinned-comment
on: workflow_dispatch
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@1234567890123456789012345678901234567890 # tag: v4
"""
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("policy.pinned-sha=1", result.stdout)


if __name__ == "__main__":
    unittest.main()
