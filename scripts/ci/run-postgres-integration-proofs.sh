#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL must point at a disposable PostgreSQL database}"
export PG_DIRECT_URL="${PG_DIRECT_URL:-$DATABASE_URL}"
export AUTH_PG_003_FIXTURE_MUTATION=1

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
  sqlx_postgres_direct_session_crud; do
  printf '=== PostgreSQL proof: %s ===\n' "$target"
  reset_database
  cargo test --locked -p weltgewebe-api --test "$target" -- --include-ignored --test-threads=1
done
