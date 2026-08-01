from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[3]


class GitFixtureMaintenanceIsolationTests(unittest.TestCase):
    def test_validate_tests_disables_automatic_git_maintenance(self) -> None:
        result = subprocess.run(
            ["make", "--no-print-directory", "-n", "validate-tests"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        command = next(
            (
                line.strip()
                for line in result.stdout.splitlines()
                if line.strip().endswith(
                    "python3 -m unittest discover scripts/ci/tests/"
                )
            ),
            None,
        )
        self.assertIsNotNone(command, result.stdout)
        assert command is not None

        expected_assignments = (
            "GIT_CONFIG_COUNT=2",
            "GIT_CONFIG_KEY_0=maintenance.auto",
            "GIT_CONFIG_VALUE_0=false",
            "GIT_CONFIG_KEY_1=gc.auto",
            "GIT_CONFIG_VALUE_1=0",
        )
        for assignment in expected_assignments:
            self.assertIn(assignment, command)

        self.assertLess(
            command.index("GIT_CONFIG_COUNT=2"),
            command.index("python3 -m unittest discover scripts/ci/tests/"),
        )


if __name__ == "__main__":
    unittest.main()
