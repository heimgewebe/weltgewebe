from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "check_actions_node24_readiness.py"


class CheckActionsNode24ReadinessTest(unittest.TestCase):
    def run_checker(self, workflow: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            workflows_dir = repo / ".github" / "workflows"
            workflows_dir.mkdir(parents=True)
            (workflows_dir / "ok.yml").write_text(workflow, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT)],
                cwd=repo,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

    def test_top_level_env_allows_direct_javascript_action(self) -> None:
        result = self.run_checker(
            """
name: ok
on: workflow_dispatch
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("All good!", result.stdout)

    def test_missing_force_env_fails_direct_javascript_action(self) -> None:
        result = self.run_checker(
            """
name: missing
on: workflow_dispatch
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Missing FORCE_JAVASCRIPT_ACTIONS_TO_NODE24", result.stdout)

    def test_reusable_workflow_call_is_follow_up_only(self) -> None:
        result = self.run_checker(
            """
name: reusable
on: workflow_dispatch
jobs:
  metrics:
    uses: owner/repo/.github/workflows/reusable.yml@abc123
"""
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Reusable workflow calls detected", result.stdout)

    def test_uses_without_ref_does_not_crash(self) -> None:
        result = self.run_checker(
            """
name: no-ref
on: workflow_dispatch
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout
"""
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("ref=no-ref", result.stdout)

    def test_false_force_env_fails_direct_javascript_action(self) -> None:
        result = self.run_checker(
            """
name: false-env
on: workflow_dispatch
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "false"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Missing FORCE_JAVASCRIPT_ACTIONS_TO_NODE24", result.stdout)

    def test_job_level_force_env_does_not_cover_other_jobs(self) -> None:
        result = self.run_checker(
            """
name: job-scope
on: workflow_dispatch
jobs:
  covered:
    runs-on: ubuntu-latest
    env:
      FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
    steps:
      - uses: actions/checkout@v4
  uncovered:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v4
"""
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("uncovered", result.stdout)
        self.assertIn("actions/setup-node@v4", result.stdout)

    def test_job_level_force_env_covers_own_job(self) -> None:
        result = self.run_checker(
            """
name: job-scope-covered
on: workflow_dispatch
jobs:
  covered:
    runs-on: ubuntu-latest
    env:
      FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
    steps:
      - uses: actions/checkout@v4
"""
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("All good!", result.stdout)

    def test_known_third_party_javascript_action_is_checked(self) -> None:
        result = self.run_checker(
            """
name: third-party
on: workflow_dispatch
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: dorny/paths-filter@v3
"""
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("dorny/paths-filter@v3", result.stdout)
        self.assertIn("All good!", result.stdout)

    def test_known_third_party_javascript_action_requires_force_env(self) -> None:
        result = self.run_checker(
            """
name: third-party-missing
on: workflow_dispatch
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: dorny/paths-filter@v3
"""
        )

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("Missing FORCE_JAVASCRIPT_ACTIONS_TO_NODE24", result.stdout)

    def test_known_repo_action_prefix_is_checked(self) -> None:
        result = self.run_checker(
            """
name: repo-known
on: workflow_dispatch
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: anchore/sbom-action@v0
"""
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("anchore/sbom-action@v0", result.stdout)
        self.assertIn("All good!", result.stdout)


if __name__ == "__main__":
    unittest.main()
