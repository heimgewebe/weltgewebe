from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
COMPOSE = REPO / "infra" / "compose" / "compose.prod.yml"
DOCKERFILE = REPO / "apps" / "api" / "Dockerfile"
DEPLOY = REPO / "scripts" / "weltgewebe-up"
ACTIVATE = REPO / "scripts" / "ops" / "activate-production-search-vps.sh"
WORKER = REPO / "scripts" / "ops" / "search-worker-loop.sh"
BACKFILL = REPO / "apps" / "api" / "src" / "bin" / "search-backfill.rs"
MIGRATION = (
    REPO
    / "apps"
    / "api"
    / "migrations"
    / "20260724000002_semantic_search_projection_privacy_boundary.up.sql"
)


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
    assert "configured_preflight_services" in deploy
    assert "WELTGEWEBE_SEARCH_MIN_DISK_BYTES" in deploy
    assert "WELTGEWEBE_SEARCH_MIN_MEMORY_BYTES" in deploy
    assert "WELTGEWEBE_SEARCH_MIN_CPU_COUNT" in deploy
    assert deploy.index("configured_preflight_services") < deploy.index("# 4. Build Decision")


def test_activation_is_commit_locked_identity_bound_and_gate_first() -> None:
    script = ACTIVATE.read_text(encoding="utf-8")
    assert "flock -n 9" in script
    assert "requested commit is no longer current origin/main" in script
    assert "sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907" in script
    assert "search-gen-2e8358273aa6d41e6a59025985a99738614aba725b8f369b3a54f390f8752e5c" in script
    assert "weltgewebe_search_generation_activation_ready" in script
    gate = script.index("weltgewebe_search_generation_activation_ready")
    activate = script.index("weltgewebe_activate_search_generation")
    assert gate < activate
    assert "search_activation=verified" in script
    assert "search worker stopped or was replaced after activation" in script
    assert "active generation has no public semantic probe candidate" in script
    assert "(.items | length > 0)" in script
    assert 'worker_cid="$("${compose[@]}" ps -q search-worker)"' in script
    assert "WELTGEWEBE_SEARCH_MIN_CPU_COUNT" in script
    assert "getconf _NPROCESSORS_ONLN" in script
    assert "SemantAH" in script


def test_persistent_worker_waits_for_exact_model_and_runs_bounded_batches() -> None:
    compose = COMPOSE.read_text(encoding="utf-8")
    worker = WORKER.read_text(encoding="utf-8")
    assert "  search-worker:" in compose
    assert "network_mode: service:api" in compose.split("  search-worker:", 1)[1].split("\n  db:", 1)[0]
    assert "search-gen-2e8358273aa6d41e6a59025985a99738614aba725b8f369b3a54f390f8752e5c" in compose
    assert "sha256:df5bd2e3c74cd8d069d21dc038f1b359fcdc9458fce1c99bd43c9eb1518ff907" in compose
    assert "provider_ready" in worker
    assert "waiting_for_pinned_model" in worker
    assert 'GEWEBE_SEED_REAL: "false"' in compose
    assert 'GEWEBE_SEED_DEMO: "false"' in compose
    assert "/app/search-backfill" in worker
    assert 'sleep "$INTERVAL_SECONDS"' in worker


def test_backfill_session_is_generation_bound_before_leased_processing() -> None:
    backfill = BACKFILL.read_text(encoding="utf-8")
    assert "generation_bound_pool" in backfill
    assert "set_config('weltgewebe.search_generation_id'" in backfill
    assert "SET search_path TO pg_temp, public" in backfill
    assert "CREATE TEMP VIEW search_projection_jobs" in backfill
    assert "FROM public.search_projection_jobs" in backfill
    assert "ensure_generation_identity(&control_pool, &generation)" in backfill
    assert "document_revision=$7" in backfill
    assert "normalization_revision=$8" in backfill
    assert "ranking_revision=$9" in backfill
    assert backfill.index("start_generation(generation.clone())") < backfill.index(
        'format!("backfill:{}:{}"'
    )


def test_projection_privacy_contract_is_generation_bound() -> None:
    worker = (REPO / "apps" / "api" / "src" / "search" / "worker.rs").read_text(encoding="utf-8")
    repository = (REPO / "apps" / "api" / "src" / "search" / "repository.rs").read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    revision = "node-document-v4-canonical-visibility"
    assert revision in worker
    assert revision in migration
    assert "ADD COLUMN search_visibility TEXT NOT NULL DEFAULT 'public'" in migration
    assert "OLD.search_visibility IS NOT DISTINCT FROM NEW.search_visibility" in migration
    assert "OLD.payload -> 'created_by_account_id'" in migration
    assert "LEFT JOIN domain_nodes" in migration
    assert "spec.validate()?" in worker
    assert "search generation id does not match its derived identity" in worker
    assert "n.search_visibility" in worker
    assert "ARRAY['owner']::TEXT[],'unavailable',NULL" in worker
    assert "p.visibility_scopes = ARRAY['owner']::TEXT[]" in repository
    assert "p.embedding IS NULL" in repository
    assert "p.visibility_scopes = ARRAY['owner']::TEXT[]" in migration
    assert "p.embedding IS NULL" in migration
    assert "n.search_visibility = 'public'" in repository
    assert "n.search_visibility = 'private'" in repository
    assert "n.payload ->> 'search_visibility'" not in repository


def test_visibility_cutover_is_trigger_quiet_and_excludes_legacy_documents() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    disable = migration.index("DISABLE TRIGGER search_track_domain_nodes")
    rewrite = migration.index("UPDATE domain_nodes")
    enable = migration.index("ENABLE TRIGGER search_track_domain_nodes")
    assert disable < rewrite < enable
    assert "CREATE OR REPLACE FUNCTION weltgewebe_search_enqueue_node" in migration
    assert "document_revision = 'node-document-v4-canonical-visibility'" in migration


def test_privacy_contract_is_wired_into_make_ci_validate() -> None:
    makefile = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "python3 -m pytest -q scripts/ci/tests/test_semantic_search_production_activation.py" in makefile
