import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.docmeta import audit_webauthn_user_id_backfill_runtime as audit  # noqa: E402


def test_hash_account_id_is_stable_and_redacted() -> None:
    first = audit.hash_account_id("account-a")
    second = audit.hash_account_id("account-a")

    assert first == second
    assert first.startswith("account:sha256:")
    assert "account-a" not in first
    assert len(first.rsplit(":", 1)[-1]) == 12


def test_schema_probe_sql_is_read_only_and_avoids_runtime_table_references() -> None:
    sql = audit.build_schema_probe_sql()
    lowered = sql.lower()

    assert "begin transaction read only" in lowered
    assert "rollback" in lowered
    assert "to_regclass('public.domain_accounts')" in lowered
    assert "to_regclass('public.passkey_credentials')" in lowered
    assert " from passkey_credentials" not in lowered
    for forbidden in [" insert ", " update ", " delete ", " drop ", " alter ", " create "]:
        assert forbidden not in lowered


def test_build_audit_sql_is_read_only_and_contains_no_mutation_statements() -> None:
    sql = audit.build_audit_sql(5)
    lowered = sql.lower()

    assert "begin transaction read only" in lowered
    assert "rollback" in lowered
    assert "domain_accounts" in lowered
    assert "passkey_credentials" in lowered
    assert "row_number() over" in lowered
    for forbidden in [" insert ", " update ", " delete ", " drop ", " alter ", " create "]:
        assert forbidden not in lowered


def test_build_audit_sql_rejects_negative_sample_limit() -> None:
    try:
        audit.build_audit_sql(-1)
    except ValueError as exc:
        assert "sample_limit" in str(exc)
    else:  # pragma: no cover - easier failure message than pytest.raises import.
        raise AssertionError("negative sample limit must fail")


def test_classify_missing_schema_blocks_backfill_audit() -> None:
    findings = audit.classify_backfill_readiness({}, schema_ready_for_audit=False)

    assert findings == {
        "schema_ready_for_audit": False,
        "has_backfill_scope": None,
        "has_cutover_blockers": True,
        "not_null_count_ready": False,
        "next_step": "fix_runtime_schema_before_backfill_audit",
    }


def test_classify_blockers_before_backfill() -> None:
    findings = audit.classify_backfill_readiness(
        {
            "accounts_missing_auth_user_id": 3,
            "credential_accounts_missing_auth_user_id": 1,
            "credential_accounts_without_domain_account": 0,
            "credential_accounts_with_multiple_auth_user_ids": 0,
            "credential_accounts_with_account_credential_uuid_mismatch": 0,
            "credential_derived_backfill_candidate_accounts": 1,
            "generated_uuid_candidate_accounts": 2,
        },
        schema_ready_for_audit=True,
    )

    assert findings["schema_ready_for_audit"] is True
    assert findings["has_backfill_scope"] is True
    assert findings["has_cutover_blockers"] is True
    assert findings["not_null_count_ready"] is False
    assert findings["next_step"] == "review_identity_blockers_before_backfill"
    assert findings["credential_derived_backfill_candidate_accounts"] == 1
    assert findings["generated_uuid_candidate_accounts"] == 2


def test_classify_backfill_scope_without_blockers_prepares_proof() -> None:
    findings = audit.classify_backfill_readiness(
        {
            "accounts_missing_auth_user_id": 2,
            "credential_accounts_missing_auth_user_id": 0,
            "credential_accounts_without_domain_account": 0,
            "credential_accounts_with_multiple_auth_user_ids": 0,
            "credential_accounts_with_account_credential_uuid_mismatch": 0,
            "credential_derived_backfill_candidate_accounts": 0,
            "generated_uuid_candidate_accounts": 2,
        },
        schema_ready_for_audit=True,
    )

    assert findings["has_backfill_scope"] is True
    assert findings["has_cutover_blockers"] is False
    assert findings["not_null_count_ready"] is False
    assert findings["next_step"] == "prepare_idempotent_backfill_proof"


def test_classify_zero_missing_zero_blockers_is_count_ready_for_review() -> None:
    findings = audit.classify_backfill_readiness(
        {
            "accounts_missing_auth_user_id": 0,
            "credential_accounts_missing_auth_user_id": 0,
            "credential_accounts_without_domain_account": 0,
            "credential_accounts_with_multiple_auth_user_ids": 0,
            "credential_accounts_with_account_credential_uuid_mismatch": 0,
            "credential_derived_backfill_candidate_accounts": 0,
            "generated_uuid_candidate_accounts": 0,
        },
        schema_ready_for_audit=True,
    )

    assert findings["has_backfill_scope"] is False
    assert findings["has_cutover_blockers"] is False
    assert findings["not_null_count_ready"] is True
    assert findings["next_step"] == "counts_ready_for_not_null_review"


def test_redact_audit_removes_raw_account_and_user_ids() -> None:
    raw = {
        "totals": {
            "accounts_total": 5,
            "accounts_missing_auth_user_id": 2,
            "credential_rows_total": 4,
            "credential_account_ids_distinct": 3,
            "credential_accounts_missing_auth_user_id": 1,
            "credential_derived_backfill_candidate_accounts": 1,
            "generated_uuid_candidate_accounts": 1,
            "credential_accounts_without_domain_account": 1,
            "credential_accounts_with_multiple_auth_user_ids": 1,
            "credential_accounts_with_account_credential_uuid_mismatch": 1,
        },
        "samples": [
            {
                "class": "orphan_credential_account",
                "account_id": "real-account-id",
                "credential_count": 2,
                "distinct_credential_webauthn_user_ids": 1,
            }
        ],
    }

    redacted = audit.redact_audit(raw, source_label="heimserver", sample_limit=10)
    serialized = json.dumps(redacted, sort_keys=True)

    assert redacted["audit"] == "webauthn_user_id_backfill_runtime"
    assert redacted["read_only"] is True
    assert redacted["mutation_performed"] is False
    assert redacted["source_label"] == "heimserver"
    assert redacted["samples"] == [
        {
            "class": "orphan_credential_account",
            "account_id_hash": audit.hash_account_id("real-account-id"),
            "credential_count": 2,
            "distinct_credential_webauthn_user_ids": 1,
        }
    ]
    assert redacted["findings"]["next_step"] == "review_identity_blockers_before_backfill"
    assert "real-account-id" not in serialized
    assert "webauthn-user-id" not in serialized


def test_redacted_missing_schema_audit_has_no_counts_but_blocks() -> None:
    result = audit.redacted_missing_schema_audit(
        {
            "tables": {
                "domain_accounts_exists": True,
                "passkey_credentials_exists": False,
            }
        },
        source_label="heimserver",
        sample_limit=5,
    )

    assert result["schema"] == {
        "domain_accounts_exists": True,
        "passkey_credentials_exists": False,
    }
    assert result["totals"] is None
    assert result["samples"] == []
    assert result["findings"]["has_cutover_blockers"] is True
    assert result["findings"]["next_step"] == "fix_runtime_schema_before_backfill_audit"


def test_postgres_env_from_database_url_redacts_ambient_pg(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://ambient:bad@example.invalid/ambient")
    monkeypatch.setenv("PGPASSWORD", "ambient-secret")
    env = audit.postgres_env_from_database_url(
        "postgres://user:secret@db.example.invalid:5432/welt?sslmode=require&connect_timeout=5"
    )

    assert env["PGHOST"] == "db.example.invalid"
    assert env["PGPORT"] == "5432"
    assert env["PGUSER"] == "user"
    assert env["PGPASSWORD"] == "secret"
    assert env["PGDATABASE"] == "welt"
    assert env["PGSSLMODE"] == "require"
    assert env["PGCONNECT_TIMEOUT"] == "5"
    assert env["PGAPPNAME"] == "weltgewebe-auth-pg-003-runtime-audit"
    assert env.get("DATABASE_URL") is None


def test_postgres_env_from_database_url_sets_default_timeout(monkeypatch) -> None:
    monkeypatch.delenv("PGCONNECT_TIMEOUT", raising=False)
    env = audit.postgres_env_from_database_url("postgres://user:secret@db.example.invalid/welt")

    assert env["PGCONNECT_TIMEOUT"] == audit.DEFAULT_PGCONNECT_TIMEOUT_SECONDS


def test_build_audit_sql_rejects_too_large_sample_limit() -> None:
    try:
        audit.build_audit_sql(audit.MAX_SAMPLE_LIMIT + 1)
    except ValueError as exc:
        assert "sample_limit" in str(exc)
    else:  # pragma: no cover - easier failure message than pytest.raises import.
        raise AssertionError("too large sample limit must fail")


def test_parse_args_rejects_too_large_sample_limit() -> None:
    try:
        audit.parse_args(["--sample-limit", str(audit.MAX_SAMPLE_LIMIT + 1)])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover - argparse should exit.
        raise AssertionError("too large CLI sample limit must fail")


def test_sanitize_psql_stderr_redacts_url_parts() -> None:
    url = "postgres://user:secret@db.example.invalid:5432/welt"
    stderr = f"could not connect to {url}; password=secret; PGPASSWORD=secret"

    sanitized = audit.sanitize_psql_stderr(stderr, url)

    assert url not in sanitized
    assert "secret" not in sanitized
    assert "db.example.invalid" not in sanitized
    assert "<redacted>" in sanitized
