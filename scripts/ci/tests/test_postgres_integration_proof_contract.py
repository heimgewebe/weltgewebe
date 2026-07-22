from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import yaml

REPO = Path(__file__).resolve().parents[3]
CONTRACT = REPO / "scripts/ci/postgres-proof-contract.json"
RUNNER = REPO / "scripts/ci/run-postgres-integration-proofs.sh"
RUST_SUPPORT = REPO / "apps/api/tests/support/postgres_proof.rs"
CI = REPO / ".github/workflows/ci.yml"

TARGETS = {
    "db_auto_provision_write_path",
    "db_domain_account_write_path",
    "db_domain_backfill",
    "db_domain_edge_write_path",
    "db_domain_node_write_path",
    "db_governance",
    "db_multi_instance_foundation",
    "db_domain_read_path",
    "db_domain_schema_migrations",
    "db_passkey_fk_readiness",
    "db_passkey_schema_preflight",
    "db_passkey_store_persistence",
    "db_session_store_persistence",
    "db_webauthn_user_id_backfill_audit",
    "db_semantic_search_foundation",
    "db_semantic_search_projection_worker",
    "sqlx_postgres_direct_session_crud",
}


def test_disposable_database_contract_is_single_source_for_runner_and_rust_tests() -> None:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert contract["schema_version"] == 1
    assert contract["disposable_database_name_segments"] == ["test", "proof", "ci"]
    assert contract["pgbouncer_port"] == 6432
    runner = RUNNER.read_text(encoding="utf-8")
    rust = RUST_SUPPORT.read_text(encoding="utf-8")
    assert "postgres-proof-contract.json" in runner
    assert "postgres-proof-contract.json" in rust
    for target in TARGETS:
        source = (REPO / "apps/api/tests" / f"{target}.rs").read_text(encoding="utf-8")
        assert "mod support;" in source


def test_runner_preflights_postgres_and_jetstream_before_the_first_target() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    preflight = runner.index("preflight_postgres\nprovision_jetstream_if_requested")
    loop = runner.index('for target in "${targets[@]}"; do')
    assert preflight < loop
    assert "info.get('jetstream') is not True" in runner
    assert 'trap cleanup EXIT INT TERM' in runner
    assert 'docker rm --force "$owned_nats_container"' in runner
    assert 'docker exec "$POSTGRES_RESET_CONTAINER" pg_isready' in runner
    assert 'docker exec "$POSTGRES_RESET_CONTAINER" psql' in runner


def test_ci_delegates_jetstream_lifecycle_to_runner() -> None:
    workflow = yaml.safe_load(CI.read_text(encoding="utf-8"))
    job = workflow["jobs"]["postgres-proofs"]
    assert job["env"]["POSTGRES_PROOF_PROVISION_NATS"] == "1"
    rendered = json.dumps(job, sort_keys=True)
    assert "weltgewebe-ci-nats" not in rendered
    assert "run-postgres-integration-proofs.sh" in rendered


def test_runner_rejects_incidental_disposable_name_substrings() -> None:
    env = os.environ.copy()
    for database in ("social", "official", "citizen"):
        url = f"postgres://postgres:postgres@127.0.0.1:5432/{database}"
        env.update(
            DATABASE_URL=url,
            PG_DIRECT_URL=url,
            T005_DATABASE_URL=url,
        )
        completed = subprocess.run(
            [str(RUNNER)],
            cwd=REPO,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        assert completed.returncode != 0
        assert "refusing non-disposable database" in completed.stderr


def test_runner_accepts_delimited_disposable_name_segment_before_preflight() -> None:
    runner = RUNNER.read_text(encoding="utf-8")
    assert "database_segments={segment for segment in database.replace('-', '_').replace('.', '_').split('_') if segment}" in runner
    assert "segment in database_segments for segment in segments" in runner
    assert "weltgewebe_t002_test".split("_")[-1] == "test"
