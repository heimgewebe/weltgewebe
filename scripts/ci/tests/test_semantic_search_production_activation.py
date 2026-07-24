from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"
DOCKERFILE = REPO / "apps" / "api" / "Dockerfile"
DEPLOY = REPO / "scripts" / "weltgewebe-up"
ACTIVATE = REPO / "scripts" / "ops" / "activate-production-search-vps.sh"
WORKER = REPO / "scripts" / "ops" / "search-worker-loop.sh"


def test_ollama_is_digest_pinned_and_loopback_only() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "ollama/ollama:0.12.6@sha256:352e045b937ac29d3d9550c22fb85525f60a89e064df34c26579bee5a93b3a16" in compose
    assert "network_mode: service:api" in compose
    assert "OLLAMA_HOST: 127.0.0.1:11434" in compose
    ollama_block = compose.split("  ollama:", 1)[1].split("\n  db:", 1)[0]
    assert "ports:" not in ollama_block
    assert "ollama_models:/root/.ollama" in ollama_block
    assert "WELTGEWEBE_SEARCH_OLLAMA_URL: ${WELTGEWEBE_SEARCH_OLLAMA_URL:-http://127.0.0.1:11434/}" in compose


def test_api_image_contains_bounded_backfill_binary() -> None:
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    assert "--bin weltgewebe-api --bin search-backfill" in dockerfile
    assert "target/release/search-backfill /app/search-backfill" in dockerfile


def test_scoped_deploy_treats_api_and_ollama_as_one_unit() -> None:
    deploy = DEPLOY.read_text(encoding="utf-8")
    assert "SCOPED_TARGET_SERVICES=(api)" in deploy
    assert "SCOPED_TARGET_SERVICES+=(ollama)" in deploy
    assert "SCOPED_TARGET_SERVICES+=(search-worker)" in deploy
    assert 'SCOPED_INITIAL_CMD+=("${SCOPED_TARGET_SERVICES[@]}")' in deploy
    assert '"allowed_recreated_services": targets' in deploy
    assert "PROTECTED_SERVICES=(db nats caddy)" in deploy


def test_activation_is_commit_locked_identity_bound_and_gate_first() -> None:
    script = ACTIVATE.read_text(encoding="utf-8")
    assert "flock -n 9" in script
    assert "requested commit is no longer current origin/main" in script
    assert "sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907" in script
    assert "search-gen-bfa894157d53e406d232141f785084d5f33f41e6aee5dc6cbd4ef4b93794c13f" in script
    assert "weltgewebe_search_generation_activation_ready" in script
    gate = script.index("weltgewebe_search_generation_activation_ready")
    activate = script.index("weltgewebe_activate_search_generation")
    assert gate < activate
    assert "search_activation=verified" in script
    assert "search worker stopped after activation" in script
    assert "SemantAH" in script


def test_persistent_worker_waits_for_exact_model_and_runs_bounded_batches() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    assert "  search-worker:" in compose
    assert "network_mode: service:api" in compose.split("  search-worker:", 1)[1].split("\n  db:", 1)[0]
    assert "search-gen-bfa894157d53e406d232141f785084d5f33f41e6aee5dc6cbd4ef4b93794c13f" in compose
    assert "sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907" in compose
    assert "provider_ready" in worker
    assert "waiting_for_pinned_model" in worker
    assert 'GEWEBE_SEED_REAL: "false"' in compose
    assert 'GEWEBE_SEED_DEMO: "false"' in compose
    assert "/app/search-backfill" in worker
    assert 'sleep "$INTERVAL_SECONDS"' in worker
