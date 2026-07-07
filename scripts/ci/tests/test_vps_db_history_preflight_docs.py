from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNBOOK = REPO_ROOT / "docs" / "deploy" / "vps-migration-safe-runtime-smoke.md"
HELPER = REPO_ROOT / "scripts" / "ops" / "check_vps_db_migration_history_shape.py"


def test_runtime_runbook_requires_db_history_preflight_before_retry() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")

    assert "## DB migration-history preflight" in text
    assert "check_vps_db_migration_history_shape.py --json" in text
    assert "A `blocked` result is a hard stop for #1348 runtime work." in text
    assert "Do not retry the API in normal `run` mode" in text
    assert "genuinely DB-free route smoke that does not claim API/database readiness" in text


def test_runtime_runbook_db_history_preflight_boundary_matches_helper() -> None:
    runbook = RUNBOOK.read_text(encoding="utf-8")
    helper = HELPER.read_text(encoding="utf-8")

    for expected in [
        "helper_started_api",
        "helper_applied_migrations",
        "helper_read_env_file",
        "helper_printed_confidential_values",
        "migration_history_table_absent",
        "app_schema_empty_or_migration_history_absent",
        "app_schema_empty",
        "migration_history_empty",
        "failed_migration_history_rows",
        "duplicate_migration_versions",
    ]:
        assert expected in helper

    for expected in [
        "does not start the API",
        "does not apply migrations",
        "does not read runtime env files",
        "does not print confidential values",
        "when `public._sqlx_migrations` is absent",
        "when migration history is empty",
        "when failed history rows exist",
        "when duplicate",
        "migration versions exist",
    ]:
        assert expected in runbook
