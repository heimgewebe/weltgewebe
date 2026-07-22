from __future__ import annotations

from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_prometheus_config_is_mounted_read_only_and_targets_internal_api() -> None:
    observ = _load_yaml(REPO / "infra/compose/compose.observ.yml")
    prometheus = observ["services"]["prometheus"]
    assert "./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro" in prometheus["volumes"]

    config = _load_yaml(REPO / "infra/compose/monitoring/prometheus.yml")
    targets = config["scrape_configs"][0]["static_configs"][0]["targets"]
    assert targets == ["weltgewebe-api:8080"]
    assert all("host.docker.internal" not in target for target in targets)


def test_api_is_internal_only_and_has_network_alias_for_prometheus() -> None:
    prod = _load_yaml(REPO / "infra/compose/compose.prod.yml")
    api = prod["services"]["api"]
    assert "ports" not in api
    assert "expose" not in api
    aliases = api["networks"]["default"]["aliases"]
    assert "weltgewebe-api" in aliases


def test_observability_overlay_does_not_publish_api_port() -> None:
    observ = _load_yaml(REPO / "infra/compose/compose.observ.yml")
    assert "api" not in observ.get("services", {})


def test_observability_host_ports_are_loopback_bound_by_default() -> None:
    observ = _load_yaml(REPO / "infra/compose/compose.observ.yml")
    expected_ports = {
        "prometheus": "${OBSERVABILITY_BIND:-127.0.0.1}:9090:9090",
        "grafana": "${OBSERVABILITY_BIND:-127.0.0.1}:3001:3000",
        "loki": "${OBSERVABILITY_BIND:-127.0.0.1}:3100:3100",
        "tempo": "${OBSERVABILITY_BIND:-127.0.0.1}:3200:3200",
    }
    for service_name, expected_port in expected_ports.items():
        assert observ["services"][service_name]["ports"] == [expected_port]
