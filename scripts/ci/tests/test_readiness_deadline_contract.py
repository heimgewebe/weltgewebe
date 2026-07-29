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


def _rust_function_body(source: str, signature: str) -> str:
    signature_start = source.find(signature)
    if signature_start < 0:
        raise AssertionError(f"missing Rust function signature {signature!r}")
    opening_brace = source.find("{", signature_start + len(signature))
    if opening_brace < 0:
        raise AssertionError(f"missing opening brace for {signature!r}")

    depth = 0
    for index in range(opening_brace, len(source)):
        token = source[index]
        if token == "{":
            depth += 1
        elif token == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1 : index]

    raise AssertionError(f"missing closing brace for {signature!r}")


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
        live_body = _rust_function_body(source, "async fn live() -> Response")
        self.assertNotIn("run_readiness_checks", live_body)
        self.assertNotIn("check_database", live_body)
        self.assertNotIn("check_nats", live_body)
        self.assertNotIn("check_policy", live_body)


if __name__ == "__main__":
    unittest.main()
