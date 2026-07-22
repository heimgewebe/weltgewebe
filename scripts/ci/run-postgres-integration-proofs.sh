#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must point at a disposable PostgreSQL database}"
export PG_DIRECT_URL="${PG_DIRECT_URL:-$DATABASE_URL}"
export T005_DATABASE_URL="${T005_DATABASE_URL:-$PG_DIRECT_URL}"
export AUTH_PG_003_FIXTURE_MUTATION=1

load_t003_connection() {
  local -a values=()
  mapfile -d '' -t values < <(
    python3 - "$PG_DIRECT_URL" << 'PY'
import sys
from urllib.parse import unquote, urlsplit

url = urlsplit(sys.argv[1])
if url.scheme not in {'postgres', 'postgresql'}:
    raise SystemExit(f'unsupported PostgreSQL URL scheme: {url.scheme!r}')
if not url.hostname:
    raise SystemExit('PostgreSQL URL must contain a host')
port = url.port or 5432
if port == 6432:
    raise SystemExit('T003 proof requires direct PostgreSQL, not PgBouncer')
values = (
    url.hostname,
    str(port),
    unquote(url.username or ''),
    unquote(url.password or ''),
    unquote(url.path.lstrip('/')),
)
if not values[2] or not values[4]:
    raise SystemExit('PostgreSQL URL must contain a user and database')
for value in values:
    sys.stdout.write(value)
    sys.stdout.write('\0')
PY
  )
  if ((${#values[@]} != 5)); then
    echo 'failed to derive direct T003 PostgreSQL connection parameters' >&2
    exit 1
  fi
  export T003_PG_HOST="${values[0]}"
  export T003_PG_PORT="${values[1]}"
  export T003_PG_USER="${values[2]}"
  export T003_PG_PASSWORD="${values[3]}"
  export T003_PG_DATABASE="${values[4]}"
}

load_t003_connection

database_name() {
  python3 - "$DATABASE_URL" << 'PY'
import sys
from urllib.parse import urlsplit
name=urlsplit(sys.argv[1]).path.lstrip('/')
if not name or not any(marker in name for marker in ('test', 'proof', 'ci')):
    raise SystemExit(f"refusing to reset non-disposable database: {name!r}")
print(name)
PY
}

reset_database() {
  local database
  database="$(database_name)"
  if [[ -n "${POSTGRES_RESET_CONTAINER:-}" ]]; then
    docker exec "$POSTGRES_RESET_CONTAINER" dropdb -U postgres --if-exists --force "$database" > /dev/null
    docker exec "$POSTGRES_RESET_CONTAINER" createdb -U postgres "$database"
    return
  fi
  python3 - "$DATABASE_URL" << 'PY'
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
url = urlsplit(sys.argv[1])
database = url.path.lstrip('/')
admin = urlunsplit((url.scheme, url.netloc, '/postgres', url.query, url.fragment))
env = dict(os.environ)
subprocess.run(['psql', admin, '-X', '--no-psqlrc', '-v', 'ON_ERROR_STOP=1', '-c',
                f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE);'], check=True, env=env)
subprocess.run(['psql', admin, '-X', '--no-psqlrc', '-v', 'ON_ERROR_STOP=1', '-c',
                f'CREATE DATABASE "{database}";'], check=True, env=env)
PY
}

for target in \
  db_auto_provision_write_path \
  db_domain_account_write_path \
  db_domain_backfill \
  db_domain_edge_write_path \
  db_domain_node_write_path \
  db_governance \
  db_multi_instance_foundation \
  db_domain_read_path \
  db_domain_schema_migrations \
  db_passkey_fk_readiness \
  db_passkey_schema_preflight \
  db_passkey_store_persistence \
  db_session_store_persistence \
  db_webauthn_user_id_backfill_audit \
  db_semantic_search_foundation \
  db_semantic_search_projection_worker \
  sqlx_postgres_direct_session_crud; do
  printf '=== PostgreSQL proof: %s ===\n' "$target"
  reset_database
  cargo test --locked -p weltgewebe-api --test "$target" -- --include-ignored --test-threads=1
done
