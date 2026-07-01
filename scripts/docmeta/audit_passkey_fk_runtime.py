#!/usr/bin/env python3
"""Read-only runtime audit for passkey credential account FK readiness.

The audit answers whether existing `passkey_credentials.account_id` values all
resolve to `domain_accounts.id`. It is intentionally read-only and redacts any
account identifiers before printing JSON.
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

    env["PGAPPNAME"] = env.get("PGAPPNAME", "weltgewebe-passkey-fk-runtime-audit")
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


def build_audit_sql(sample_limit: int) -> str:
    if sample_limit < 0:
        raise ValueError("sample_limit must be non-negative")

    return f"""
BEGIN TRANSACTION READ ONLY;
WITH orphan_accounts AS (
    SELECT pc.account_id, COUNT(*)::bigint AS credential_count
    FROM passkey_credentials pc
    LEFT JOIN domain_accounts da ON da.id = pc.account_id
    WHERE da.id IS NULL
    GROUP BY pc.account_id
),
orphan_samples AS (
    SELECT account_id, credential_count
    FROM orphan_accounts
    ORDER BY credential_count DESC, account_id
    LIMIT {sample_limit}
),
counts AS (
    SELECT
        (SELECT COUNT(*)::bigint FROM passkey_credentials) AS credential_records_total,
        (SELECT COUNT(DISTINCT account_id)::bigint FROM passkey_credentials) AS credential_account_ids_total,
        (SELECT COUNT(*)::bigint FROM domain_accounts) AS domain_accounts_total,
        (SELECT COUNT(*)::bigint
         FROM passkey_credentials pc
         JOIN domain_accounts da ON da.id = pc.account_id) AS credentials_with_account_total,
        (SELECT COUNT(*)::bigint
         FROM passkey_credentials pc
         LEFT JOIN domain_accounts da ON da.id = pc.account_id
         WHERE da.id IS NULL) AS orphan_credentials_total,
        (SELECT COUNT(*)::bigint FROM orphan_accounts) AS orphan_account_ids_total
)
SELECT json_build_object(
    'schema_version', 1,
    'audit', 'passkey_fk_runtime',
    'read_only', true,
    'mutation_performed', false,
    'totals', json_build_object(
        'credential_records_total', credential_records_total,
        'credential_account_ids_total', credential_account_ids_total,
        'domain_accounts_total', domain_accounts_total,
        'credentials_with_account_total', credentials_with_account_total,
        'orphan_credentials_total', orphan_credentials_total,
        'orphan_account_ids_total', orphan_account_ids_total
    ),
    'orphan_samples', COALESCE(
        (SELECT json_agg(json_build_object(
            'account_id', account_id,
            'credential_count', credential_count
        )) FROM orphan_samples),
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


def redact_audit(raw: dict[str, Any], *, source_label: str, sample_limit: int) -> dict[str, Any]:
    totals = raw.get("totals") or {}
    samples = raw.get("orphan_samples") or []
    redacted_samples = [
        {
            "account_id_hash": hash_account_id(str(sample["account_id"])),
            "credential_count": int(sample["credential_count"]),
        }
        for sample in samples
    ]
    orphan_credentials_total = int(totals.get("orphan_credentials_total", 0))
    orphan_account_ids_total = int(totals.get("orphan_account_ids_total", 0))

    return {
        "schema_version": 1,
        "audit": "passkey_fk_runtime",
        "source_label": source_label,
        "read_only": True,
        "mutation_performed": False,
        "redaction": {
            "account_ids": "sha256-prefix-12",
            "credential_ids": "not_emitted",
            "credentials": "not_emitted",
        },
        "sample_limit": sample_limit,
        "totals": {
            "credential_records_total": int(totals.get("credential_records_total", 0)),
            "credential_account_ids_total": int(totals.get("credential_account_ids_total", 0)),
            "domain_accounts_total": int(totals.get("domain_accounts_total", 0)),
            "credentials_with_account_total": int(totals.get("credentials_with_account_total", 0)),
            "orphan_credentials_total": orphan_credentials_total,
            "orphan_account_ids_total": orphan_account_ids_total,
        },
        "orphan_account_samples": redacted_samples,
        "findings": {
            "fk_ready_by_count": orphan_credentials_total == 0 and orphan_account_ids_total == 0,
            "requires_runtime_review": orphan_credentials_total > 0 or orphan_account_ids_total > 0,
        },
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
        help="maximum number of redacted orphan account samples to emit",
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
        raw = run_psql_json(build_audit_sql(args.sample_limit), postgres_env, database_url)
        redacted = redact_audit(raw, source_label=args.source_label, sample_limit=args.sample_limit)
    except Exception as exc:  # noqa: BLE001 - CLI must redact and exit cleanly.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    indent = 2 if args.pretty else None
    print(json.dumps(redacted, indent=indent, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
