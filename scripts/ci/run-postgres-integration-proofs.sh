#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
CONTRACT_FILE="${SCRIPT_DIR}/postgres-proof-contract.json"

: "${DATABASE_URL:?DATABASE_URL must point at a direct disposable PostgreSQL database}"
export PG_DIRECT_URL="${PG_DIRECT_URL:-$DATABASE_URL}"
export T005_DATABASE_URL="${T005_DATABASE_URL:-$PG_DIRECT_URL}"
export AUTH_PG_003_FIXTURE_MUTATION=1

owned_nats_container=""
cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ -n "$owned_nats_container" ]]; then
    docker rm --force "$owned_nats_container" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

contract_value() {
  local key="$1"
  python3 - "$CONTRACT_FILE" "$key" <<'PY'
import json, sys
contract=json.load(open(sys.argv[1], encoding='utf-8'))
if contract.get('schema_version') != 1:
    raise SystemExit('unsupported postgres proof contract schema')
value=contract.get(sys.argv[2])
if value is None:
    raise SystemExit(f'missing postgres proof contract key: {sys.argv[2]}')
if isinstance(value, (list, dict)):
    print(json.dumps(value, separators=(',', ':')))
else:
    print(value)
PY
}

validate_database_url() {
  local url="$1"
  python3 - "$CONTRACT_FILE" "$url" <<'PY'
import json, sys
from urllib.parse import unquote, urlsplit
contract=json.load(open(sys.argv[1], encoding='utf-8'))
if contract.get('schema_version') != 1:
    raise SystemExit('unsupported postgres proof contract schema')
markers=contract.get('disposable_database_name_markers') or []
if not markers:
    raise SystemExit('postgres proof contract has no disposable database markers')
url=urlsplit(sys.argv[2])
if url.scheme not in {'postgres','postgresql'}:
    raise SystemExit(f'unsupported PostgreSQL URL scheme: {url.scheme!r}')
if not url.hostname:
    raise SystemExit('PostgreSQL URL must contain a host')
port=url.port or 5432
if port == int(contract['pgbouncer_port']):
    raise SystemExit('PostgreSQL integration proofs require direct PostgreSQL, not PgBouncer')
database=unquote(url.path.lstrip('/'))
if not database or not any(marker in database for marker in markers):
    raise SystemExit(
        f'refusing non-disposable database {database!r}; expected a name containing one of {markers!r}'
    )
print(database)
PY
}

DATABASE_NAME="$(validate_database_url "$DATABASE_URL")"
PG_DIRECT_DATABASE_NAME="$(validate_database_url "$PG_DIRECT_URL")"
T005_DATABASE_NAME="$(validate_database_url "$T005_DATABASE_URL")"
if [[ "$DATABASE_NAME" == "$PG_DIRECT_DATABASE_NAME" && "$DATABASE_NAME" == "$T005_DATABASE_NAME" ]]; then
  :
else
  echo "PostgreSQL proof URLs must target the same disposable database name: DATABASE_URL=${DATABASE_NAME}, PG_DIRECT_URL=${PG_DIRECT_DATABASE_NAME}, T005_DATABASE_URL=${T005_DATABASE_NAME}" >&2
  exit 1
fi

load_t003_connection() {
  local -a values=()
  mapfile -d '' -t values < <(
    python3 - "$PG_DIRECT_URL" <<'PY'
import sys
from urllib.parse import unquote, urlsplit
url=urlsplit(sys.argv[1])
values=(
    url.hostname or '',
    str(url.port or 5432),
    unquote(url.username or ''),
    unquote(url.password or ''),
    unquote(url.path.lstrip('/')),
)
if not values[0] or not values[2] or not values[4]:
    raise SystemExit('PostgreSQL URL must contain host, user and database')
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

postgres_admin_url() {
  python3 - "$PG_DIRECT_URL" <<'PY'
import sys
from urllib.parse import urlsplit, urlunsplit
url=urlsplit(sys.argv[1])
print(urlunsplit((url.scheme, url.netloc, '/postgres', url.query, url.fragment)))
PY
}

preflight_postgres() {
  local admin
  admin="$(postgres_admin_url)"
  if [[ -n "${POSTGRES_RESET_CONTAINER:-}" ]]; then
    command -v docker >/dev/null 2>&1 || {
      echo 'PostgreSQL proof container preflight requires docker' >&2
      return 1
    }
    if ! docker exec "$POSTGRES_RESET_CONTAINER" pg_isready -U postgres -d postgres >/dev/null 2>&1; then
      echo "PostgreSQL proof preflight container is not ready: ${POSTGRES_RESET_CONTAINER}" >&2
      return 1
    fi
    if ! docker exec "$POSTGRES_RESET_CONTAINER" psql -U postgres -d postgres -X --no-psqlrc -v ON_ERROR_STOP=1 -Atqc 'SELECT 1' >/dev/null; then
      echo "PostgreSQL proof preflight container query failed: ${POSTGRES_RESET_CONTAINER}" >&2
      return 1
    fi
    echo "PostgreSQL proof preflight: isolated container ready; disposable database=${DATABASE_NAME}"
    return 0
  fi
  if ! command -v psql >/dev/null 2>&1; then
    echo 'PostgreSQL proof preflight requires psql before the first test' >&2
    return 1
  fi
  if ! psql "$admin" -X --no-psqlrc -v ON_ERROR_STOP=1 -Atqc 'SELECT 1' >/dev/null; then
    echo 'PostgreSQL proof preflight could not reach the direct PostgreSQL admin database' >&2
    return 1
  fi
  echo "PostgreSQL proof preflight: direct server ready; disposable database=${DATABASE_NAME}"
}

check_jetstream_once() {
  python3 - "$NATS_URL" <<'PY'
import json, socket, sys
from urllib.parse import urlsplit
url=urlsplit(sys.argv[1])
if url.scheme != 'nats' or not url.hostname:
    raise SystemExit('NATS_URL must be a plain nats:// URL for the integration proof')
with socket.create_connection((url.hostname, url.port or 4222), timeout=2.0) as sock:
    sock.settimeout(2.0)
    data=b''
    while b'\r\n' not in data and len(data) < 65536:
        chunk=sock.recv(4096)
        if not chunk:
            break
        data += chunk
line=data.split(b'\r\n',1)[0]
if not line.startswith(b'INFO '):
    raise SystemExit(f'NATS readiness expected INFO line, got {line[:80]!r}')
info=json.loads(line[5:].decode('utf-8'))
if info.get('jetstream') is not True:
    raise SystemExit('NATS server is reachable but JetStream is not enabled')
print('JetStream proof preflight: semantic INFO jetstream=true')
PY
}

wait_for_jetstream() {
  for _ in {1..30}; do
    if check_jetstream_once; then
      return 0
    fi
    sleep 1
  done
  echo "JetStream proof preflight failed for ${NATS_URL}" >&2
  if [[ -n "$owned_nats_container" ]]; then
    docker logs "$owned_nats_container" >&2 || true
  fi
  return 1
}

provision_jetstream_if_requested() {
  if [[ "${POSTGRES_PROOF_PROVISION_NATS:-0}" != "1" ]]; then
    : "${NATS_URL:?NATS_URL is required unless POSTGRES_PROOF_PROVISION_NATS=1}"
    wait_for_jetstream
    return
  fi
  command -v docker >/dev/null 2>&1 || {
    echo 'JetStream proof provisioning requires docker' >&2
    return 1
  }
  local image binding port suffix
  image="$(contract_value jetstream_image)"
  suffix="${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-0}-$$"
  owned_nats_container="weltgewebe-ci-nats-${suffix}"
  docker run --detach --rm \
    --name "$owned_nats_container" \
    --publish 127.0.0.1::4222 \
    "$image" -js >/dev/null
  binding="$(docker port "$owned_nats_container" 4222/tcp | head -n1)"
  port="${binding##*:}"
  if [[ ! "$port" =~ ^[0-9]+$ ]]; then
    echo "could not resolve dynamically published JetStream port from ${binding}" >&2
    return 1
  fi
  export NATS_URL="nats://127.0.0.1:${port}"
  wait_for_jetstream
}

reset_database() {
  local admin
  admin="$(postgres_admin_url)"
  if [[ -n "${POSTGRES_RESET_CONTAINER:-}" ]]; then
    docker exec "$POSTGRES_RESET_CONTAINER" dropdb -U postgres --if-exists --force "$DATABASE_NAME" >/dev/null
    docker exec "$POSTGRES_RESET_CONTAINER" createdb -U postgres "$DATABASE_NAME"
    return
  fi
  psql "$admin" -X --no-psqlrc -v ON_ERROR_STOP=1 -c \
    "DROP DATABASE IF EXISTS \"${DATABASE_NAME}\" WITH (FORCE);" >/dev/null
  psql "$admin" -X --no-psqlrc -v ON_ERROR_STOP=1 -c \
    "CREATE DATABASE \"${DATABASE_NAME}\";" >/dev/null
}

preflight_postgres
provision_jetstream_if_requested

if [[ "${POSTGRES_PROOF_PREFLIGHT_ONLY:-0}" == "1" ]]; then
  echo 'PostgreSQL integration proof preflight-only mode: PASS'
  exit 0
fi

targets=(
  db_auto_provision_write_path
  db_domain_account_write_path
  db_domain_backfill
  db_domain_edge_write_path
  db_domain_node_write_path
  db_governance
  db_multi_instance_foundation
  db_domain_read_path
  db_domain_schema_migrations
  db_passkey_fk_readiness
  db_passkey_schema_preflight
  db_passkey_store_persistence
  db_session_store_persistence
  db_webauthn_user_id_backfill_audit
  db_semantic_search_foundation
  db_semantic_search_projection_worker
  sqlx_postgres_direct_session_crud
)

if [[ -n "${POSTGRES_PROOF_TARGETS:-}" ]]; then
  read -r -a targets <<<"$POSTGRES_PROOF_TARGETS"
fi

for target in "${targets[@]}"; do
  printf '=== PostgreSQL proof: %s ===\n' "$target"
  reset_database
  cargo test --locked -p weltgewebe-api --test "$target" -- --include-ignored --test-threads=1
done
