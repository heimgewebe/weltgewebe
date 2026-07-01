#!/usr/bin/env python3
"""Read-only runtime audit for AUTH-PG-003 webauthn_user_id backfill readiness.

The audit classifies live PostgreSQL state before any future
`domain_accounts.webauthn_user_id` backfill or NOT NULL decision. It performs no
writes, emits only redacted account identifiers, and treats missing runtime
schema as an audit blocker rather than as an empty result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

MAX_PSQL_STDERR_LOG_BYTES = 500
AUDIT_NAME = "webauthn_user_id_backfill_runtime"


def hash_account_id(account_id: str) -> str:
    digest = hashlib.sha256(account_id.encode("utf-8")).hexdigest()[:12]
    return f"account:sha256:{digest}"


def postgres_env_from_database_url(database_url: str) -> dict[str, str]:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL must use scheme postgres or postgresql")

    env = os.environ.copy()
    for key in list(env):
        if key == "DATABASE_URL" or key.startswith("PG"):
            env.pop(key, None)

    if parsed.hostname:
        env["PGHOST"] = parsed.hostname
    if parsed.port:
        env["PGPORT"] = str(parsed.port)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    if parsed.path and parsed.path != "/":
        env["PGDATABASE"] = unquote(parsed.path.lstrip("/"))

    query = parse_qs(parsed.query, keep_blank_values=False)
    query_env_map = {
        "sslmode": "PGSSLMODE",
        "connect_timeout": "PGCONNECT_TIMEOUT",
        "application_name": "PGAPPNAME",
        "sslrootcert": "PGSSLROOTCERT",
        "sslcert": "PGSSLCERT",
        "sslkey": "PGSSLKEY",
    }
    for key, env_key in query_env_map.items():
        values = query.get(key)
        if values:
            env[env_key] = values[-1]

    env["PGAPPNAME"] = env.get("PGAPPNAME", "weltgewebe-auth-pg-003-runtime-audit")
    return env


def sanitize_psql_stderr(stderr: str, database_url: str | None) -> str:
    text = stderr or ""
    if database_url:
        text = text.replace(database_url, "<redacted>")
        parsed = urlparse(database_url)
        for value in [
            parsed.hostname,
            parsed.username,
            parsed.password,
            parsed.path.lstrip("/") if parsed.path else None,
        ]:
            if value:
                text = text.replace(value, "<redacted>")
    text = re.sub(r"postgres(?:ql)?://\S+", "postgresql://<redacted>", text)
    text = re.sub(r"(?i)(password=)[^ \n\t]+", r"\1<redacted>", text)
    text = re.sub(r"(?i)(PGPASSWORD=)[^ \n\t]+", r"\1<redacted>", text)
    return text[:MAX_PSQL_STDERR_LOG_BYTES]


def build_schema_probe_sql() -> str:
    return """
BEGIN TRANSACTION READ ONLY;
SELECT json_build_object(
    'schema_version', 1,
    'audit', 'webauthn_user_id_backfill_runtime_schema_probe',
    'tables', json_build_object(
        'domain_accounts_exists', to_regclass('public.domain_accounts') IS NOT NULL,
        'passkey_credentials_exists', to_regclass('public.passkey_credentials') IS NOT NULL
    )
)::text;
ROLLBACK;
"""


def build_audit_sql(sample_limit: int) -> str:
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

    return f"""
BEGIN TRANSACTION READ ONLY;
WITH credential_accounts AS (
    SELECT
        p.account_id,
        COUNT(*)::bigint AS credential_count,
        COUNT(DISTINCT p.webauthn_user_id)::bigint AS distinct_credential_webauthn_user_ids
    FROM passkey_credentials p
    GROUP BY p.account_id
),
credential_accounts_missing_domain_uuid AS (
    SELECT ca.account_id, ca.credential_count, ca.distinct_credential_webauthn_user_ids
    FROM credential_accounts ca
    JOIN domain_accounts a ON a.id = ca.account_id
    WHERE a.webauthn_user_id IS NULL
),
credential_derived_candidates AS (
    SELECT account_id
    FROM credential_accounts_missing_domain_uuid
    WHERE distinct_credential_webauthn_user_ids = 1
),
accounts_missing_without_credentials AS (
    SELECT a.id AS account_id
    FROM domain_accounts a
    LEFT JOIN credential_accounts ca ON ca.account_id = a.id
    WHERE a.webauthn_user_id IS NULL
      AND ca.account_id IS NULL
),
orphan_credential_accounts AS (
    SELECT ca.account_id, ca.credential_count, ca.distinct_credential_webauthn_user_ids
    FROM credential_accounts ca
    LEFT JOIN domain_accounts a ON a.id = ca.account_id
    WHERE a.id IS NULL
),
multi_webauthn_user_id_accounts AS (
    SELECT account_id, credential_count, distinct_credential_webauthn_user_ids
    FROM credential_accounts
    WHERE distinct_credential_webauthn_user_ids > 1
),
credential_account_uuid_mismatches AS (
    SELECT
        p.account_id,
        COUNT(*)::bigint AS credential_count,
        COUNT(DISTINCT p.webauthn_user_id)::bigint AS distinct_credential_webauthn_user_ids
    FROM passkey_credentials p
    JOIN domain_accounts a ON a.id = p.account_id
    WHERE a.webauthn_user_id IS NOT NULL
      AND p.webauthn_user_id <> a.webauthn_user_id
    GROUP BY p.account_id
),
sample_rows AS (
    SELECT class, account_id, credential_count, distinct_credential_webauthn_user_ids
    FROM (
        SELECT
            class,
            account_id,
            credential_count,
            distinct_credential_webauthn_user_ids,
            row_number() OVER (PARTITION BY class ORDER BY credential_count DESC, account_id) AS rn
        FROM (
            SELECT
                'credential_account_missing_auth_user_id' AS class,
                account_id,
                credential_count,
                distinct_credential_webauthn_user_ids
            FROM credential_accounts_missing_domain_uuid
            UNION ALL
            SELECT
                'orphan_credential_account' AS class,
                account_id,
                credential_count,
                distinct_credential_webauthn_user_ids
            FROM orphan_credential_accounts
            UNION ALL
            SELECT
                'multi_credential_uuid_account' AS class,
                account_id,
                credential_count,
                distinct_credential_webauthn_user_ids
            FROM multi_webauthn_user_id_accounts
            UNION ALL
            SELECT
                'account_credential_uuid_mismatch' AS class,
                account_id,
                credential_count,
                distinct_credential_webauthn_user_ids
            FROM credential_account_uuid_mismatches
        ) unioned_samples
    ) ranked_samples
    WHERE rn <= {sample_limit}
),
counts AS (
    SELECT
        (SELECT COUNT(*)::bigint FROM domain_accounts) AS accounts_total,
        (SELECT COUNT(*)::bigint FROM domain_accounts WHERE webauthn_user_id IS NULL) AS accounts_missing_auth_user_id,
        (SELECT COUNT(*)::bigint FROM passkey_credentials) AS credential_rows_total,
        (SELECT COUNT(DISTINCT account_id)::bigint FROM passkey_credentials) AS credential_account_ids_distinct,
        (SELECT COUNT(*)::bigint FROM credential_accounts_missing_domain_uuid) AS credential_accounts_missing_auth_user_id,
        (SELECT COUNT(*)::bigint FROM credential_derived_candidates) AS credential_derived_backfill_candidate_accounts,
        (SELECT COUNT(*)::bigint FROM accounts_missing_without_credentials) AS generated_uuid_candidate_accounts,
        (SELECT COUNT(*)::bigint FROM orphan_credential_accounts) AS credential_accounts_without_domain_account,
        (SELECT COUNT(*)::bigint FROM multi_webauthn_user_id_accounts) AS credential_accounts_with_multiple_auth_user_ids,
        (SELECT COUNT(*)::bigint FROM credential_account_uuid_mismatches) AS credential_accounts_with_account_credential_uuid_mismatch
)
SELECT json_build_object(
    'schema_version', 1,
    'audit', 'webauthn_user_id_backfill_runtime',
    'read_only', true,
    'mutation_performed', false,
    'totals', json_build_object(
        'accounts_total', accounts_total,
        'accounts_missing_auth_user_id', accounts_missing_auth_user_id,
        'credential_rows_total', credential_rows_total,
        'credential_account_ids_distinct', credential_account_ids_distinct,
        'credential_accounts_missing_auth_user_id', credential_accounts_missing_auth_user_id,
        'credential_derived_backfill_candidate_accounts', credential_derived_backfill_candidate_accounts,
        'generated_uuid_candidate_accounts', generated_uuid_candidate_accounts,
        'credential_accounts_without_domain_account', credential_accounts_without_domain_account,
        'credential_accounts_with_multiple_auth_user_ids', credential_accounts_with_multiple_auth_user_ids,
        'credential_accounts_with_account_credential_uuid_mismatch', credential_accounts_with_account_credential_uuid_mismatch
    ),
    'samples', COALESCE(
        (SELECT json_agg(json_build_object(
            'class', class,
            'account_id', account_id,
            'credential_count', credential_count,
            'distinct_credential_webauthn_user_ids', distinct_credential_webauthn_user_ids
        ) ORDER BY class, account_id) FROM sample_rows),
        '[]'::json
    )
)::text
FROM counts;
ROLLBACK;
"""


def run_psql_json(sql: str, postgres_env: dict[str, str], database_url: str) -> dict[str, Any]:
    if shutil.which("psql") is None:
        raise RuntimeError("psql executable not found; install PostgreSQL client tools")

    proc = subprocess.run(
        ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"],
        input=sql,
        env=postgres_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "psql audit query failed: " + sanitize_psql_stderr(proc.stderr, database_url)
        )

    json_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("{")]
    if len(json_lines) != 1:
        raise RuntimeError(f"expected exactly one JSON result line from psql, got {len(json_lines)}")
    return json.loads(json_lines[0])


def classify_backfill_readiness(
    totals: dict[str, Any], *, schema_ready_for_audit: bool
) -> dict[str, Any]:
    if not schema_ready_for_audit:
        return {
            "schema_ready_for_audit": False,
            "has_backfill_scope": None,
            "has_cutover_blockers": True,
            "not_null_count_ready": False,
            "next_step": "fix_runtime_schema_before_backfill_audit",
        }

    accounts_missing = int(totals.get("accounts_missing_auth_user_id", 0))
    blocker_keys = [
        "credential_accounts_missing_auth_user_id",
        "credential_accounts_without_domain_account",
        "credential_accounts_with_multiple_auth_user_ids",
        "credential_accounts_with_account_credential_uuid_mismatch",
    ]
    has_cutover_blockers = any(int(totals.get(key, 0)) > 0 for key in blocker_keys)
    has_backfill_scope = accounts_missing > 0

    if has_cutover_blockers:
        next_step = "review_identity_blockers_before_backfill"
    elif has_backfill_scope:
        next_step = "prepare_idempotent_backfill_proof"
    else:
        next_step = "counts_ready_for_not_null_review"

    return {
        "schema_ready_for_audit": True,
        "has_backfill_scope": has_backfill_scope,
        "has_cutover_blockers": has_cutover_blockers,
        "not_null_count_ready": accounts_missing == 0 and not has_cutover_blockers,
        "credential_derived_backfill_candidate_accounts": int(
            totals.get("credential_derived_backfill_candidate_accounts", 0)
        ),
        "generated_uuid_candidate_accounts": int(totals.get("generated_uuid_candidate_accounts", 0)),
        "next_step": next_step,
    }


def redacted_missing_schema_audit(
    schema_probe: dict[str, Any], *, source_label: str, sample_limit: int
) -> dict[str, Any]:
    tables = schema_probe.get("tables") or {}
    result = {
        "schema_version": 1,
        "audit": AUDIT_NAME,
        "source_label": source_label,
        "read_only": True,
        "mutation_performed": False,
        "sample_limit": sample_limit,
        "schema": {
            "domain_accounts_exists": bool(tables.get("domain_accounts_exists", False)),
            "passkey_credentials_exists": bool(tables.get("passkey_credentials_exists", False)),
        },
        "redaction": redaction_policy(),
        "totals": None,
        "samples": [],
    }
    result["findings"] = classify_backfill_readiness({}, schema_ready_for_audit=False)
    return result


def redaction_policy() -> dict[str, str]:
    return {
        "account_ids": "sha256-prefix-12",
        "credential_ids": "not_emitted",
        "webauthn_user_ids": "not_emitted",
        "credentials": "not_emitted",
    }


def redact_audit(raw: dict[str, Any], *, source_label: str, sample_limit: int) -> dict[str, Any]:
    totals = {key: int(value) for key, value in (raw.get("totals") or {}).items()}
    samples = raw.get("samples") or []
    redacted_samples = [
        {
            "class": str(sample["class"]),
            "account_id_hash": hash_account_id(str(sample["account_id"])),
            "credential_count": int(sample["credential_count"]),
            "distinct_credential_webauthn_user_ids": int(
                sample["distinct_credential_webauthn_user_ids"]
            ),
        }
        for sample in samples
    ]

    return {
        "schema_version": 1,
        "audit": AUDIT_NAME,
        "source_label": source_label,
        "read_only": True,
        "mutation_performed": False,
        "sample_limit": sample_limit,
        "schema": {
            "domain_accounts_exists": True,
            "passkey_credentials_exists": True,
        },
        "redaction": redaction_policy(),
        "totals": totals,
        "samples": redacted_samples,
        "findings": classify_backfill_readiness(totals, schema_ready_for_audit=True),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url-env",
        default="DATABASE_URL",
        help="environment variable containing the PostgreSQL URL (default: DATABASE_URL)",
    )
    parser.add_argument(
        "--source-label",
        default="runtime-postgres",
        help="non-secret label for the audited database/source",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=10,
        help="maximum redacted samples to emit per finding class",
    )
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    database_url = os.environ.get(args.database_url_env)
    if not database_url:
        print(f"ERROR: {args.database_url_env} is not set", file=sys.stderr)
        return 2

    try:
        postgres_env = postgres_env_from_database_url(database_url)
        schema_probe = run_psql_json(build_schema_probe_sql(), postgres_env, database_url)
        tables = schema_probe.get("tables") or {}
        schema_ready = bool(tables.get("domain_accounts_exists")) and bool(
            tables.get("passkey_credentials_exists")
        )
        if schema_ready:
            raw = run_psql_json(build_audit_sql(args.sample_limit), postgres_env, database_url)
            redacted = redact_audit(raw, source_label=args.source_label, sample_limit=args.sample_limit)
        else:
            redacted = redacted_missing_schema_audit(
                schema_probe, source_label=args.source_label, sample_limit=args.sample_limit
            )
    except Exception as exc:  # noqa: BLE001 - CLI must redact and exit cleanly.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    indent = 2 if args.pretty else None
    print(json.dumps(redacted, indent=indent, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
