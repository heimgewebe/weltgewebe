#!/usr/bin/env bash
set -euo pipefail
umask 077
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"; }
sha256_file() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"|awk '{print $1}'; else shasum -a 256 "$1"|awk '{print $1}'; fi; }
manifest_value() { awk -F= -v key="$1" '$1==key {print $2; exit}' "$2"; }

RESTORE_POSTGRES_CONTAINER="${RESTORE_POSTGRES_CONTAINER:-}"
psql_restore_db() {
  if [[ -n "$RESTORE_POSTGRES_CONTAINER" ]]; then
    docker exec -i "$RESTORE_POSTGRES_CONTAINER" psql -X --no-psqlrc -v ON_ERROR_STOP=1 -U postgres -d weltgewebe_restore_proof "$@"
  else
    psql -X --no-psqlrc -v ON_ERROR_STOP=1 "$RESTORE_DATABASE_URL" "$@"
  fi
}
check_restore_target() {
  if [[ -n "$RESTORE_POSTGRES_CONTAINER" ]]; then
    require_cmd docker
    [[ "$RESTORE_POSTGRES_CONTAINER" == *restore* || "$RESTORE_POSTGRES_CONTAINER" == *proof* ]] || fail "restore container name must identify a restore/proof target"
    return
  fi
  [[ -n "${RESTORE_DATABASE_URL:-}" ]] || fail "RESTORE_DATABASE_URL must point at a disposable database"
  [[ -z "${DATABASE_URL:-}" || "$RESTORE_DATABASE_URL" != "$DATABASE_URL" ]] || fail "RESTORE_DATABASE_URL must not equal DATABASE_URL"
  if [[ "${ALLOW_ANY_RESTORE_DATABASE:-0}" != 1 ]]; then
    case "$RESTORE_DATABASE_URL" in *restore*|*proof*|*tmp*|*test*) ;; *) fail "RESTORE_DATABASE_URL must visibly target a disposable database";; esac
  fi
}
check_required_tables() {
  local missing
  missing="$(psql_restore_db -Atc "
with required(name) as (values ('domain_accounts'),('domain_nodes'),('domain_edges'),('sessions'),('passkey_credentials'),('_sqlx_migrations')),
missing as (select required.name from required left join information_schema.tables t on t.table_schema='public' and t.table_name=required.name where t.table_name is null)
select coalesce(string_agg(name, ',' order by name), '') from missing;
" | tr -d '[:space:]')"
  [[ -z "$missing" ]] || fail "restored database is missing required tables: $missing"
}

require_cmd gzip; require_cmd gunzip; require_cmd awk
[[ -n "${BACKUP_FILE:-}" && -f "$BACKUP_FILE" ]] || fail "BACKUP_FILE must name an existing backup"
check_restore_target
[[ -n "$RESTORE_POSTGRES_CONTAINER" ]] || require_cmd psql
BACKUP_MANIFEST="${BACKUP_MANIFEST:-${BACKUP_FILE%.sql.gz}.sha256.manifest}"
RESTORE_PROOF_DIR="${RESTORE_PROOF_DIR:-/var/backups/weltgewebe/postgres/proofs}"
PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"; export PGCONNECT_TIMEOUT

gzip -t "$BACKUP_FILE" || fail "backup gzip integrity test failed"
[[ -f "$BACKUP_MANIFEST" ]] || fail "backup manifest is required: $BACKUP_MANIFEST"
actual_sha="$(sha256_file "$BACKUP_FILE")"
expected_sha="$(manifest_value sha256 "$BACKUP_MANIFEST")"
[[ -n "$expected_sha" && "$actual_sha" == "$expected_sha" ]] || fail "backup sha256 mismatch"

table_count="$(psql_restore_db -Atc "select count(*) from pg_class c join pg_namespace n on n.oid=c.relnamespace where c.relkind in ('r','p') and n.nspname not in ('pg_catalog','information_schema');" | tr -d '[:space:]')"
case "$table_count" in ''|*[!0-9]*) fail "could not determine restore database table count";; esac
[[ "$table_count" -eq 0 || "${ALLOW_NONEMPTY_RESTORE_DB:-0}" == 1 ]] || fail "restore database is not empty"
gunzip -c "$BACKUP_FILE" | psql_restore_db >/dev/null || fail "restore import failed"
check_required_tables

install -d -m 0700 "$RESTORE_PROOF_DIR"
proof_base="$(basename "$BACKUP_FILE" .sql.gz).restore-proof"
proof_file="${RESTORE_PROOF_FILE:-${RESTORE_PROOF_DIR}/${proof_base}}"
work_dir="$(mktemp -d "${RESTORE_PROOF_DIR}/.tmp.restore-proof.XXXXXX")"; trap 'rm -rf "$work_dir"' EXIT
tmp_proof="$work_dir/$proof_base"
{
  printf 'contract=weltgewebe-postgres-restore-proof-v1\ncreated_at=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf 'backup_file=%s\nbackup_sha256=%s\n' "$(basename "$BACKUP_FILE")" "$actual_sha"
  printf 'tables=domain_accounts,domain_nodes,domain_edges,sessions,passkey_credentials,_sqlx_migrations\nresult=ok\n'
} >"$tmp_proof"
chmod 600 "$tmp_proof"; mv -f "$tmp_proof" "$proof_file"
printf 'PostgreSQL restore proof written: %s\n' "$proof_file"
