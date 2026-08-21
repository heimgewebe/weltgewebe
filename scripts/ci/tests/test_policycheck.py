from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
POLICYCHECK = REPO_ROOT / "tools" / "py" / "policycheck.py"
VALID_SLO = """version: 3
contract_kind: objectives_only
performance_contract: policies/performance.v1.json
services:
  web:
    availability_target_pct: 99.9
    performance_measurement_ref: measurements.web_runtime
  api:
    availability_target_pct: 99.95
    performance_measurement_ref: measurements.api_runtime
"""
VALID_PERFORMANCE = '{"measurements":{"web_runtime":{},"api_runtime":{}}}\n'


class PolicycheckTests(unittest.TestCase):
    def _run(
        self,
        *,
        policy: str,
        defaults: str,
        slo: str = VALID_SLO,
        performance: str = VALID_PERFORMANCE,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "policies").mkdir()
            (root / "configs").mkdir()
            (root / "policies" / "retention.yml").write_text(policy, encoding="utf-8")
            (root / "policies" / "slo.yaml").write_text(slo, encoding="utf-8")
            (root / "policies" / "performance.v1.json").write_text(
                performance, encoding="utf-8"
            )
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


    def test_rejects_operational_slo_alert_controls(self) -> None:
        slo = VALID_SLO + "error_budgets:\n  window_days: 30\n  warn_at_pct: 25\n"
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults="max_guest_owned_nodes: 1000\n",
            slo=slo,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("objectives-only with exact root keys", result.stdout)
        self.assertIn("error_budgets", result.stdout)

    def test_rejects_operational_slo_service_threshold(self) -> None:
        slo = VALID_SLO.replace(
            "    performance_measurement_ref: measurements.web_runtime\n",
            "    performance_measurement_ref: measurements.web_runtime\n"
            "    alert_threshold_pct_over_budget: 5\n",
            1,
        )
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults="max_guest_owned_nodes: 1000\n",
            slo=slo,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("services.web must expose objectives only", result.stdout)
        self.assertIn("alert_threshold_pct_over_budget", result.stdout)

    def test_rejects_slo_reference_to_missing_performance_measurement(self) -> None:
        slo = VALID_SLO.replace(
            "measurements.web_runtime", "measurements.missing_runtime", 1
        )
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults="max_guest_owned_nodes: 1000\n",
            slo=slo,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("points to missing measurement", result.stdout)

    def test_rejects_invalid_slo_availability_percentage(self) -> None:
        slo = VALID_SLO.replace("availability_target_pct: 99.9", "availability_target_pct: 0", 1)
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults="max_guest_owned_nodes: 1000\n",
            slo=slo,
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must be a percentage greater than 0", result.stdout)

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

    def test_rejects_forget_pipeline_even_without_deadlines(self) -> None:
        result = self._run(
            policy=(
                "data_lifecycle:\n"
                "  anonymize_opt_in_default: true\n"
                "forget_pipeline: []\n"
            ),
            defaults="max_guest_owned_nodes: 1000\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must not publish forget_pipeline", result.stdout)

    def test_rejects_nested_deadline_days_anywhere_in_retention_policy(self) -> None:
        result = self._run(
            policy=(
                "data_lifecycle:\n"
                "  anonymize_opt_in_default: true\n"
                "unsupported_future_contract:\n"
                "  actions:\n"
                "    - deadline_days: 84\n"
            ),
            defaults="max_guest_owned_nodes: 1000\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must not publish unsupported deadline_days", result.stdout)
        self.assertIn("unsupported_future_contract.actions[0].deadline_days", result.stdout)

    def test_rejects_nested_deadline_days_in_app_defaults(self) -> None:
        result = self._run(
            policy="data_lifecycle:\n  anonymize_opt_in_default: true\n",
            defaults=(
                "max_guest_owned_nodes: 1000\n"
                "future_retention:\n"
                "  deadline_days: 28\n"
            ),
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("must not publish unsupported deadline_days", result.stdout)

    def test_rejects_non_mapping_policy_root(self) -> None:
        result = self._run(
            policy="- data_lifecycle\n",
            defaults="max_guest_owned_nodes: 1000\n",
        )

        self.assertEqual(result.returncode, 1)
        self.assertIn("root must be a mapping", result.stdout)


if __name__ == "__main__":
    unittest.main()
