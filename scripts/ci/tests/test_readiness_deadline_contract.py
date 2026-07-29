import re
import unittest
from pathlib import Path

import yaml


REPO = Path(__file__).resolve().parents[3]
HEALTH_ROUTE = REPO / "apps" / "api" / "src" / "routes" / "health.rs"
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"
KUBERNETES = (
    REPO / "platform" / "apps" / "weltgewebe" / "base" / "api-deployment.yaml"
)


def _rust_timeout_ms(name: str) -> int:
    source = HEALTH_ROUTE.read_text(encoding="utf-8")
    match = re.search(rf"const {name}: u64 = ([0-9_]+);", source)
    if match is None:
        raise AssertionError(f"missing Rust timeout constant {name}")
    return int(match.group(1).replace("_", ""))


def _compose_timeout_ms() -> int:
    payload = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    value = payload["services"]["api"]["healthcheck"]["timeout"]
    match = re.fullmatch(r"([0-9]+)s", value)
    if match is None:
        raise AssertionError(f"unsupported Compose timeout: {value!r}")
    return int(match.group(1)) * 1_000


def _kubernetes_timeout_ms() -> int:
    documents = yaml.safe_load_all(KUBERNETES.read_text(encoding="utf-8"))
    deployment = next(
        document
        for document in documents
        if document and document.get("kind") == "Deployment"
    )
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    return int(container["readinessProbe"]["timeoutSeconds"]) * 1_000


class ReadinessDeadlineContractTests(unittest.TestCase):
    def test_check_budget_is_lower_than_total_budget(self) -> None:
        self.assertLess(
            _rust_timeout_ms("READINESS_CHECK_TIMEOUT_MS"),
            _rust_timeout_ms("READINESS_TOTAL_TIMEOUT_MS"),
        )

    def test_external_probe_timeouts_exceed_internal_total_budget(self) -> None:
        internal_ms = _rust_timeout_ms("READINESS_TOTAL_TIMEOUT_MS")
        self.assertLess(internal_ms, _kubernetes_timeout_ms())
        self.assertLess(internal_ms, _compose_timeout_ms())

    def test_liveness_remains_separate_from_readiness(self) -> None:
        source = HEALTH_ROUTE.read_text(encoding="utf-8")
        live_body = source.split("async fn live()", 1)[1].split(
            "#[derive(Debug, Default, Clone, Copy)]", 1
        )[0]
        self.assertNotIn("run_readiness_checks", live_body)
        self.assertNotIn("check_database", live_body)
        self.assertNotIn("check_nats", live_body)


if __name__ == "__main__":
    unittest.main()
