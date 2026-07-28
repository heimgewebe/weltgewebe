from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"


def _api_healthcheck_command() -> str:
    payload = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    test = payload["services"]["api"]["healthcheck"]["test"]
    assert test[0] == "CMD-SHELL"
    assert len(test) == 2
    return test[1]


def test_production_api_healthcheck_requires_readiness() -> None:
    command = _api_healthcheck_command()
    assert command.count("/health/ready") == 1
    assert "/health/live" not in command
    assert "||" not in command


def test_production_api_healthcheck_preserves_failure_status() -> None:
    command = _api_healthcheck_command().strip()
    assert command.startswith("wget -qO-")
    assert command.endswith(">/dev/null 2>&1")
