#!/usr/bin/env bash
set -euo pipefail

ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)}"
fail=0

require_file() {
  local path="$1"
  if [[ ! -f "$ROOT/$path" ]]; then
    printf 'DOMAIN-MULTI-INSTANCE-GUARD: missing required file: %s\n' "$path" >&2
    fail=1
  fi
}

require_literal() {
  local path="$1" literal="$2" category="$3"
  require_file "$path"
  [[ -f "$ROOT/$path" ]] || return
  if ! grep -qF -- "$literal" "$ROOT/$path"; then
    printf 'DOMAIN-MULTI-INSTANCE-GUARD: %s missing in %s: %s\n' \
      "$category" "$path" "$literal" >&2
    fail=1
  fi
}

MIGRATION='apps/api/migrations/20260716000001_multi_instance_foundation.up.sql'
EPHEMERAL='apps/api/src/auth/ephemeral_db.rs'
ROUTES='apps/api/src/routes/auth.rs'
DOMAIN_DB='apps/api/src/domain_db.rs'
STATE='apps/api/src/state.rs'
MIDDLEWARE='apps/api/src/middleware/domain_projection.rs'
OUTBOX='apps/api/src/outbox.rs'
LIB='apps/api/src/lib.rs'
PROOF='apps/api/tests/db_multi_instance_foundation.rs'
CI='.github/workflows/ci.yml'
PROOF_RUNNER='scripts/ci/run-postgres-integration-proofs.sh'

for table in auth_ephemeral_state auth_rate_limit_counters domain_outbox \
  domain_event_consumptions domain_projection_state; do
  require_literal "$MIGRATION" "CREATE TABLE $table" 'shared-state schema'
done
for trigger in domain_nodes_outbox domain_edges_outbox domain_accounts_outbox; do
  require_literal "$MIGRATION" "CREATE TRIGGER $trigger" 'transactional trigger'
done
require_literal "$MIGRATION" 'UPDATE domain_projection_state' 'projection generation'
require_literal "$MIGRATION" 'ON CONFLICT (singleton) DO NOTHING' 'idempotent projection-state initialization'
require_literal "$MIGRATION" "INSERT INTO domain_outbox" 'transactional outbox'

for symbol in replace_context get_or_insert_context consume_bound insert_with_capacity \
  spawn_cleanup_loop; do
  require_literal "$EPHEMERAL" "${symbol}" 'shared auth backend'
done
for call in create_shared peek_shared consume_shared get_shared \
  consume_if_matches_shared; do
  require_literal "$ROUTES" ".${call}" 'shared auth route'
done
require_literal "$ROUTES" 'check_shared' 'shared rate limit route'
require_literal "$ROUTES" 'AUTH_BACKEND_UNAVAILABLE' 'JSON shared-backend error contract'

require_literal "$DOMAIN_DB" 'load_stable_domain_projection_from_postgres' 'stable projection load'
require_literal "$DOMAIN_DB" 'domain_projection_version' 'projection generation read'
require_literal "$STATE" 'refresh_domain_projection_if_stale' 'projection refresh'
require_literal "$STATE" 'domain_projection_gate' 'atomic projection swap'
require_literal "$MIDDLEWARE" 'refresh_domain_projection_if_stale' 'per-request projection check'
require_literal "$MIDDLEWARE" 'domain_projection_gate.read().await' 'request projection fence'

require_literal "$OUTBOX" 'FOR UPDATE SKIP LOCKED' 'multi-relay claim'
require_literal "$OUTBOX" 'ORDER BY available_at ASC, id ASC' 'pending-index claim order'
require_literal "$OUTBOX" 'Nats-Msg-Id' 'JetStream publisher deduplication'
require_literal "$OUTBOX" 'quarantined_at' 'poison-event quarantine'
require_literal "$OUTBOX" 'requeue_quarantined' 'controlled quarantine recovery'
require_literal "$OUTBOX" 'record_consumed_once' 'consumer idempotency ledger'
require_literal "$OUTBOX" 'ack_policy: consumer::AckPolicy::Explicit' 'explicit consumer acknowledgement'
require_literal "$LIB" 'outbox::start(pool, client)' 'runtime outbox startup'
require_literal "$LIB" 'ensure_current_domain_projection' 'runtime projection middleware'

for marker in 'let state_a =' 'let state_b =' 'let state_c =' \
  'outbox::start(pool.clone(), nats_a.clone())' \
  'outbox::start(pool.clone(), nats_b.clone())' \
  'refresh_domain_projection_if_stale' \
  'consume_shared(&restart_token)' \
  'logout-all challenge is visible on second instance' \
  'record_consumed_once'; do
  require_literal "$PROOF" "$marker" 'two-instance/restart proof'
done

require_literal "$CI" 'weltgewebe_t002_test' 'isolated CI database'
require_literal "$CI" 'NATS_URL: nats://127.0.0.1:4222' 'JetStream CI endpoint'
require_literal "$CI" 'nats@sha256:b83efabe3e7def1e0a4a31ec6e078999bb17c80363f881df35edc70fcb6bb927' 'pinned JetStream CI image'
require_literal "$CI" 'Run PostgreSQL and multi-instance proof suite' 'multi-instance CI job'
require_literal "$PROOF_RUNNER" 'db_multi_instance_foundation' 'multi-instance proof runner'

if [[ -e "$ROOT/scripts/guard/domain-single-instance-guard.sh" ]]; then
  printf 'DOMAIN-MULTI-INSTANCE-GUARD: obsolete single-instance guard still exists\n' >&2
  fail=1
fi

if (( fail != 0 )); then
  printf 'DOMAIN-MULTI-INSTANCE-GUARD: contract violated.\n' >&2
  exit 1
fi
printf 'DOMAIN-MULTI-INSTANCE-GUARD: shared state, coherent projections, outbox and proof present.\n'
