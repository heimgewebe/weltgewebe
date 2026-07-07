#!/usr/bin/env python3
"""Check PostgreSQL migration-history shape before a VPS API smoke.

The helper reads only PostgreSQL catalog shape through an already-running database
container. It does not start the API and it does not apply migrations.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Sequence

DEFAULT_CONTAINER = "weltgewebe-db-1"

CATALOG_QUERY = r"""
psql -v ON_ERROR_STOP=1 -qAt -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
SELECT 'history_table=' || CASE
  WHEN to_regclass('public._sqlx_migrations') IS NULL THEN 'absent'
  ELSE 'present'
END;
SELECT 'user_relation_count=' || count(*)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND NOT (n.nspname = 'public' AND c.relname = '_sqlx_migrations')
  AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f');
SELECT 'base_table_count=' || count(*)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
  AND n.nspname NOT LIKE 'pg_toast%'
  AND NOT (n.nspname = 'public' AND c.relname = '_sqlx_migrations')
  AND c.relkind IN ('r', 'p');
SQL
""".strip()

HISTORY_QUERY = r"""
psql -v ON_ERROR_STOP=1 -qAt -U "$POSTGRES_USER" -d "$POSTGRES_DB" <<'SQL'
SELECT 'history_row_count=' || count(*) FROM public._sqlx_migrations;
SELECT 'failed_history_count=' || count(*) FROM public._sqlx_migrations WHERE success IS NOT TRUE;
SELECT 'duplicate_version_count=' || count(*)
FROM (
  SELECT version
  FROM public._sqlx_migrations
  GROUP BY version
  HAVING count(*) > 1
) duplicates;
SQL
""".strip()


@dataclass(frozen=True)
class ProbeResult:
    status: str
    container: str
    history_table: str
    user_relation_count: int | None
    base_table_count: int | None
    history_row_count: int | None
    failed_history_count: int | None
    duplicate_version_count: int | None
    reason: str | None = None
    command_error: str | None = None

    def payload(self) -> dict[str, object]:
        data: dict[str, object] = {
            "status": self.status,
            "container": self.container,
            "history_table": self.history_table,
            "user_relation_count": self.user_relation_count,
            "base_table_count": self.base_table_count,
            "history_row_count": self.history_row_count,
            "failed_history_count": self.failed_history_count,
            "duplicate_version_count": self.duplicate_version_count,
            "helper_started_api": False,
            "helper_applied_migrations": False,
            "helper_read_env_file": False,
            "helper_printed_confidential_values": False,
        }
        if self.reason:
            data["reason"] = self.reason
        if self.command_error:
            data["command_error"] = self.command_error
        return data


def _run_docker_psql(docker_bin: str, container: str, script: str) -> str:
    proc = subprocess.run(
        [docker_bin, "exec", container, "sh", "-lc", script],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"docker exec exited with {proc.returncode}"
        raise RuntimeError(detail)
    return proc.stdout


def _parse_key_values(output: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            raise RuntimeError(f"unexpected probe output line: {line!r}")
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _optional_int(values: dict[str, str], key: str) -> int | None:
    value = values.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"probe output {key!r} must be an integer, got {value!r}") from exc


def probe(docker_bin: str, container: str) -> ProbeResult:
    try:
        catalog = _parse_key_values(_run_docker_psql(docker_bin, container, CATALOG_QUERY))
    except Exception as exc:
        return ProbeResult(
            status="error",
            container=container,
            history_table="unknown",
            user_relation_count=None,
            base_table_count=None,
            history_row_count=None,
            failed_history_count=None,
            duplicate_version_count=None,
            reason="catalog_probe_failed",
            command_error=str(exc),
        )

    history_table = catalog.get("history_table", "unknown")
    try:
        user_relation_count = _optional_int(catalog, "user_relation_count")
        base_table_count = _optional_int(catalog, "base_table_count")
    except Exception as exc:
        return ProbeResult(
            status="error",
            container=container,
            history_table=history_table,
            user_relation_count=None,
            base_table_count=None,
            history_row_count=None,
            failed_history_count=None,
            duplicate_version_count=None,
            reason="catalog_probe_failed",
            command_error=str(exc),
        )

    if history_table != "present":
        reason = "migration_history_table_absent"
        if user_relation_count == 0 or base_table_count == 0:
            reason = "app_schema_empty_or_migration_history_absent"
        return ProbeResult(
            status="blocked",
            container=container,
            history_table=history_table,
            user_relation_count=user_relation_count,
            base_table_count=base_table_count,
            history_row_count=None,
            failed_history_count=None,
            duplicate_version_count=None,
            reason=reason,
        )

    try:
        history = _parse_key_values(_run_docker_psql(docker_bin, container, HISTORY_QUERY))
    except Exception as exc:
        return ProbeResult(
            status="error",
            container=container,
            history_table=history_table,
            user_relation_count=user_relation_count,
            base_table_count=base_table_count,
            history_row_count=None,
            failed_history_count=None,
            duplicate_version_count=None,
            reason="history_probe_failed",
            command_error=str(exc),
        )

    try:
        history_row_count = _optional_int(history, "history_row_count")
        failed_history_count = _optional_int(history, "failed_history_count")
        duplicate_version_count = _optional_int(history, "duplicate_version_count")
    except Exception as exc:
        return ProbeResult(
            status="error",
            container=container,
            history_table=history_table,
            user_relation_count=user_relation_count,
            base_table_count=base_table_count,
            history_row_count=None,
            failed_history_count=None,
            duplicate_version_count=None,
            reason="history_probe_failed",
            command_error=str(exc),
        )

    if user_relation_count == 0 or base_table_count == 0:
        status = "blocked"
        reason = "app_schema_empty"
    elif history_row_count == 0:
        status = "blocked"
        reason = "migration_history_empty"
    elif (failed_history_count or 0) > 0:
        status = "blocked"
        reason = "failed_migration_history_rows"
    elif (duplicate_version_count or 0) > 0:
        status = "blocked"
        reason = "duplicate_migration_versions"
    else:
        status = "pass"
        reason = None

    return ProbeResult(
        status=status,
        container=container,
        history_table=history_table,
        user_relation_count=user_relation_count,
        base_table_count=base_table_count,
        history_row_count=history_row_count,
        failed_history_count=failed_history_count,
        duplicate_version_count=duplicate_version_count,
        reason=reason,
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check VPS DB migration-history shape.")
    parser.add_argument("--container", default=DEFAULT_CONTAINER)
    parser.add_argument("--docker-bin", default="docker")
    parser.add_argument("--json", action="store_true", help="print only JSON output")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = probe(args.docker_bin, args.container)
    payload = result.payload()
    if args.json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
