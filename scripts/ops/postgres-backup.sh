#!/usr/bin/env bash
set -euo pipefail

umask 077

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || fail "required command not found: $1"; }
sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | awk '{print $1}'
  else fail "required command not found: sha256sum or shasum"; fi
}

POSTGRES_CONTAINER="${POSTGRES_CONTAINER:-}"

psql_db() {
  if [[ -n "$POSTGRES_CONTAINER" ]]; then
    docker exec "$POSTGRES_CONTAINER" sh -c \
      'exec psql -X --no-psqlrc -v ON_ERROR_STOP=1 -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-postgres}" "$@"' sh "$@"
  elif [[ -n "${DATABASE_URL:-}" ]]; then
    psql -X --no-psqlrc -v ON_ERROR_STOP=1 "$DATABASE_URL" "$@"
  else
    psql -X --no-psqlrc -v ON_ERROR_STOP=1 "$@"
  fi
}

pg_dump_db() {
  if [[ -n "$POSTGRES_CONTAINER" ]]; then
    docker exec "$POSTGRES_CONTAINER" sh -c \
      'exec pg_dump --format=plain --no-owner --no-privileges -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-postgres}"'
  elif [[ -n "${DATABASE_URL:-}" ]]; then
    pg_dump --format=plain --no-owner --no-privileges --dbname="$DATABASE_URL"
  else
    pg_dump --format=plain --no-owner --no-privileges
  fi
}

check_connection_config() {
  if [[ -n "$POSTGRES_CONTAINER" ]]; then
    require_cmd docker
    docker inspect "$POSTGRES_CONTAINER" >/dev/null 2>&1 || fail "PostgreSQL container not found: $POSTGRES_CONTAINER"
    return
  fi
  require_cmd psql
  require_cmd pg_dump
  if [[ -z "${DATABASE_URL:-}" && ( -z "${PGHOST:-}" || -z "${PGDATABASE:-}" || -z "${PGUSER:-}" ) ]]; then
    fail "set POSTGRES_CONTAINER, DATABASE_URL, or PGHOST/PGDATABASE/PGUSER"
  fi
}

check_required_tables() {
  local missing
  missing="$(psql_db -Atc "
with required(name) as (values
 ('domain_accounts'),('domain_nodes'),('domain_edges'),('sessions'),
 ('passkey_credentials'),('_sqlx_migrations')
), missing as (
 select required.name from required
 left join information_schema.tables t
   on t.table_schema='public' and t.table_name=required.name
 where t.table_name is null
)
select coalesce(string_agg(name, ',' order by name), '') from missing;
" | tr -d '[:space:]')"
  [[ -z "$missing" ]] || fail "database is missing required Weltgewebe tables: $missing"
}

require_cmd gzip
require_cmd awk
require_cmd wc
require_cmd find
check_connection_config

BACKUP_DIR="${BACKUP_DIR:-/var/backups/weltgewebe/postgres}"
BACKUP_PREFIX="${BACKUP_PREFIX:-weltgewebe-postgres}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
PGCONNECT_TIMEOUT="${PGCONNECT_TIMEOUT:-10}"
export PGCONNECT_TIMEOUT
case "$BACKUP_RETENTION_DAYS" in ''|*[!0-9]*) fail "BACKUP_RETENTION_DAYS must be a non-negative integer";; esac

install -d -m 0700 "$BACKUP_DIR"
[[ -w "$BACKUP_DIR" ]] || fail "backup directory is not writable: $BACKUP_DIR"
[[ "$(psql_db -Atc 'select 1' | tr -d '[:space:]')" == "1" ]] || fail "PostgreSQL health check failed"
check_required_tables

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
label="${BACKUP_LABEL:-$timestamp}"
case "$label" in ''|*[!A-Za-z0-9._-]*) fail "BACKUP_LABEL contains unsupported characters";; esac
base="${BACKUP_PREFIX}-${label}"
dump_file="${BACKUP_DIR}/${base}.sql.gz"
manifest_file="${BACKUP_DIR}/${base}.sha256.manifest"
[[ ! -e "$dump_file" && ! -e "$manifest_file" ]] || fail "backup target already exists for label: $label"

work_dir="$(mktemp -d "${BACKUP_DIR}/.tmp.${BACKUP_PREFIX}.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT
tmp_dump="${work_dir}/${base}.sql.gz"
tmp_manifest="${work_dir}/${base}.sha256.manifest"

pg_dump_db | gzip -c >"$tmp_dump" || fail "pg_dump or gzip failed"
chmod 600 "$tmp_dump"
gzip -t "$tmp_dump" || fail "gzip integrity test failed"
sha256="$(sha256_file "$tmp_dump")"
bytes="$(wc -c <"$tmp_dump" | tr -d '[:space:]')"
created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
git_commit="${GIT_COMMIT_SHA:-}"
if [[ -z "$git_commit" && -n "${GIT_REPO_DIR:-}" ]]; then
  git_commit="$(git -c safe.directory="$GIT_REPO_DIR" -C "$GIT_REPO_DIR" rev-parse HEAD 2>/dev/null || true)"
fi
{
  printf 'contract=weltgewebe-postgres-backup-v1\n'
  printf 'created_at=%s\nfile=%s.sql.gz\nsha256=%s\nbytes=%s\n' "$created_at" "$base" "$sha256" "$bytes"
  [[ -z "$git_commit" ]] || printf 'git_commit=%s\n' "$git_commit"
  printf 'tables=domain_accounts,domain_nodes,domain_edges,sessions,passkey_credentials,_sqlx_migrations\n'
} >"$tmp_manifest"
chmod 600 "$tmp_manifest"

# Same-filesystem renames: readers see only complete files. Manifest is promoted last.
mv "$tmp_dump" "$dump_file"
mv "$tmp_manifest" "$manifest_file"

if (( BACKUP_RETENTION_DAYS > 0 )); then
  find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "${BACKUP_PREFIX}-*.sql.gz" -o -name "${BACKUP_PREFIX}-*.sha256.manifest" \) \
    -mtime +"$BACKUP_RETENTION_DAYS" -delete
fi
printf 'PostgreSQL backup written: %s\nManifest written: %s\n' "$dump_file" "$manifest_file"
