from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HISTORICAL = REPO / "apps/api/migrations/20260721000001_semantic_search_projection_worker.up.sql"
HARDENING_UP = REPO / "apps/api/migrations/20260723000001_semantic_search_activation_readiness_hardening.up.sql"
HARDENING_DOWN = REPO / "apps/api/migrations/20260723000001_semantic_search_activation_readiness_hardening.down.sql"
EXPECTED_HISTORICAL_SHA384 = "0e1612268276f4805cfb1ef5dd3e8d688f24fbbdcc1a861a71aa7da1ad5649dbcbcd775551383e4d19c8f9f6c2a94c16"


def test_applied_semantic_search_migration_remains_byte_immutable() -> None:
    assert hashlib.sha384(HISTORICAL.read_bytes()).hexdigest() == EXPECTED_HISTORICAL_SHA384


def test_activation_hardening_lives_only_in_additive_migration() -> None:
    historical = HISTORICAL.read_text(encoding="utf-8")
    up = HARDENING_UP.read_text(encoding="utf-8")
    down = HARDENING_DOWN.read_text(encoding="utf-8")

    assert "weltgewebe_search_generation_activation_ready" not in historical
    assert "search_projection_jobs_generation_state" not in historical

    assert "CREATE OR REPLACE FUNCTION weltgewebe_search_generation_activation_ready" in up
    assert "CREATE INDEX IF NOT EXISTS search_projection_jobs_generation_state" in up
    assert "IF NOT weltgewebe_search_generation_activation_ready(p_generation_id) THEN" in up

    assert "DROP FUNCTION IF EXISTS weltgewebe_search_generation_activation_ready(TEXT)" in down
    assert "DROP INDEX IF EXISTS search_projection_jobs_generation_state" in down
    assert "target.state NOT IN ('building', 'ready', 'active')" in down
