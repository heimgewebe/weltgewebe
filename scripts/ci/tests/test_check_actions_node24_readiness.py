import os
import tempfile
import unittest
import subprocess

SCRIPT_PATH = os.path.abspath("scripts/ci/check_actions_node24_readiness.py")

class TestCheckActionsNode24Readiness(unittest.TestCase):
    def test_positive_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            wf_dir = os.path.join(td, ".github", "workflows")
            os.makedirs(wf_dir)

            with open(os.path.join(wf_dir, "good.yml"), "w") as f:
                f.write("""
name: Good Workflow
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
""")

            result = subprocess.run(["python3", SCRIPT_PATH], cwd=td, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"Expected success but failed. Output: {result.stdout}\nErr: {result.stderr}")
            self.assertIn("All good!", result.stdout)

    def test_negative_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            wf_dir = os.path.join(td, ".github", "workflows")
            os.makedirs(wf_dir)

            with open(os.path.join(wf_dir, "bad.yml"), "w") as f:
                f.write("""
name: Bad Workflow
jobs:
  build:
    steps:
      - uses: actions/checkout@v4
""")

            result = subprocess.run(["python3", SCRIPT_PATH], cwd=td, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, f"Expected failure but succeeded.")
            self.assertIn("Found issues:", result.stdout)
            self.assertIn("Missing FORCE_JAVASCRIPT_ACTIONS_TO_NODE24", result.stdout)

    def test_reusable_workflow_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            wf_dir = os.path.join(td, ".github", "workflows")
            os.makedirs(wf_dir)

            with open(os.path.join(wf_dir, "reusable_call.yml"), "w") as f:
                f.write("""
name: Reusable Call Workflow
jobs:
  metrics:
    uses: owner/repo/.github/workflows/reusable.yml@v1
""")

            result = subprocess.run(["python3", SCRIPT_PATH], cwd=td, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, f"Expected success but failed. Output: {result.stdout}\nErr: {result.stderr}")
            self.assertIn("Reusable workflow calls detected; caller env does not prove called workflow Node-24 readiness:", result.stdout)
            self.assertIn(".github/workflows/reusable_call.yml metrics -> owner/repo/.github/workflows/reusable.yml@v1", result.stdout)
            self.assertIn("All good!", result.stdout)

    def test_action_uses_without_at_does_not_crash(self):
        with tempfile.TemporaryDirectory() as td:
            wf_dir = os.path.join(td, ".github", "workflows")
            os.makedirs(wf_dir)

            with open(os.path.join(wf_dir, "no_at.yml"), "w") as f:
                f.write("""
name: No At Workflow
env:
  FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"
jobs:
  build:
    steps:
      - uses: actions/checkout
""")

            result = subprocess.run(
                ["python3", SCRIPT_PATH],
                cwd=td,
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Expected success but failed. Output: {result.stdout}\nErr: {result.stderr}",
            )
            self.assertIn("All good!", result.stdout)

if __name__ == '__main__':
    unittest.main()
