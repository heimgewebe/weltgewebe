from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
POLICYCHECK = REPO_ROOT / "tools" / "py" / "policycheck.py"


class PolicycheckTests(unittest.TestCase):
    def _run(self, *, policy: str, defaults: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policies").mkdir()
            (root / "configs").mkdir()
            (root / "policies" / "retention.yml").write_text(policy, encoding="utf-8")
            (root / "configs" / "app.defaults.yml").write_text(defaults, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(POLICYCHECK)],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )

    def test_accepts_current_policy_surface(self) -> None:
        # `anonymize_opt_in_default` is the declared retention policy and must stay
        # legal; only the removed runtime switch `anonymize_opt_in` is rejected.
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults="max_guest_owned_nodes: 1000\n",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("policy ok", result.stdout)

    def test_rejects_delegation_expire_days_in_retention_policy(self) -> None:
        result = self._run(
            policy=(
                "data_lifecycle:\n"
                "  delegation_expire_days: 28\n"
                "  anonymize_opt_in_default: true\n"
            ),
            defaults="max_guest_owned_nodes: 1000\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must not publish delegation_expire_days", result.stdout)

    def test_rejects_delegation_expire_days_in_app_defaults(self) -> None:
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults="max_guest_owned_nodes: 1000\ndelegation_expire_days: 28\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must not publish delegation_expire_days", result.stdout)

    def test_rejects_anonymize_opt_in_in_retention_policy(self) -> None:
        result = self._run(
            policy=(
                "data_lifecycle:\n"
                "  anonymize_opt_in: true\n"
                "  anonymize_opt_in_default: true\n"
            ),
            defaults="max_guest_owned_nodes: 1000\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must not publish anonymize_opt_in", result.stdout)

    def test_rejects_anonymize_opt_in_in_app_defaults(self) -> None:
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults="max_guest_owned_nodes: 1000\nanonymize_opt_in: true\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must not publish anonymize_opt_in", result.stdout)


if __name__ == "__main__":
    unittest.main()
