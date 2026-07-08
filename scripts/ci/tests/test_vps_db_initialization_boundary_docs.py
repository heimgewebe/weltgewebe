from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
BOUNDARY = REPO_ROOT / "docs" / "deploy" / "vps-db-initialization-boundary.md"
SMOKE_RUNBOOK = REPO_ROOT / "docs" / "deploy" / "vps-migration-safe-runtime-smoke.md"


def test_db_initialization_boundary_defines_hard_stop_for_empty_db_shape() -> None:
    text = BOUNDARY.read_text(encoding="utf-8")

    for expected in [
        "history_table=absent",
        "user_relation_count=0",
        "base_table_count=0",
        "reason=app_schema_empty_or_migration_history_absent",
        "A normal API startup or compose retry must not be used",
        "outside the no-migration boundary of #1348",
    ]:
        assert expected in text


def test_db_initialization_boundary_lists_required_evidence_and_non_actions() -> None:
    text = BOUNDARY.read_text(encoding="utf-8")

    for expected in [
        "DB-history preflight JSON payload",
        "whether migration SQL was applied",
        "post-state DB-history preflight JSON payload",
        "failed or duplicate migration-history rows",
        "explicit non-actions for DNS, HTTPS, mail, SMTP, credentials, and cutover",
        "It does not complete #1348 and it does not approve DB mutation by itself.",
    ]:
        assert expected in text


def test_migration_safe_runtime_runbook_links_to_db_initialization_boundary() -> None:
    smoke = SMOKE_RUNBOOK.read_text(encoding="utf-8")

    assert "vps-db-initialization-boundary.md" in smoke
    assert "DB initialization or repair" in smoke
    assert "must not be treated as part" in smoke
    assert "of the no-migration #1348 smoke" in smoke
