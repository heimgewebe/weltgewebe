import unittest
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"


def _api_healthcheck_command() -> str:
    payload = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    test = payload["services"]["api"]["healthcheck"]["test"]
    if test[0] != "CMD-SHELL" or len(test) != 2:
        raise AssertionError("API healthcheck must be one CMD-SHELL command")
    return test[1]


class ComposeReadinessContractTests(unittest.TestCase):
    def test_production_api_healthcheck_requires_readiness(self) -> None:
        command = _api_healthcheck_command()
        self.assertEqual(command.count("/health/ready"), 1)
        self.assertNotIn("/health/live", command)
        self.assertNotIn("||", command)

    def test_production_api_healthcheck_preserves_failure_status(self) -> None:
        command = _api_healthcheck_command().strip()
        self.assertTrue(command.startswith("wget -qO-"))
        self.assertTrue(command.endswith(">/dev/null 2>&1"))


if __name__ == "__main__":
    unittest.main()
