#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
GUARD="$ROOT/scripts/guard/domain-multi-instance-guard.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

FILES=(
  apps/api/migrations/20260716000001_multi_instance_foundation.up.sql
  apps/api/src/auth/ephemeral_db.rs
  apps/api/src/routes/auth.rs
  apps/api/src/domain_db.rs
  apps/api/src/state.rs
  apps/api/src/middleware/domain_projection.rs
  apps/api/src/outbox.rs
  apps/api/src/lib.rs
  apps/api/tests/db_multi_instance_foundation.rs
  .github/workflows/ci.yml
  scripts/ci/run-postgres-integration-proofs.sh
)

seed() {
  local dest="$1" file
  mkdir -p "$dest"
  for file in "${FILES[@]}"; do
    mkdir -p "$dest/$(dirname -- "$file")"
    cp "$ROOT/$file" "$dest/$file"
  done
}

expect_pass() {
  local name="$1" root="$2" out
  if out="$(REPO_ROOT="$root" bash "$GUARD" 2>&1)"; then
    printf 'PASS: %s\n' "$name"
  else
    printf 'FAIL: %s: %s\n' "$name" "$out" >&2
    exit 1
  fi
}

expect_fail() {
  local name="$1" root="$2" needle="$3" out rc=0
  out="$(REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$?
  if [[ "$rc" -eq 1 ]] && grep -qF -- "$needle" <<<"$out"; then
    printf 'PASS: %s\n' "$name"
  else
    printf 'FAIL: %s (rc=%s, need=%s): %s\n' "$name" "$rc" "$needle" "$out" >&2
    exit 1
  fi
}

expect_pass 'actual repository satisfies multi-instance contract' "$ROOT"

case_root="$TMP/pass"
seed "$case_root"
mkdir -p "$case_root/infra/compose"
printf 'services:\n  api:\n    deploy:\n      replicas: 3\n' > "$case_root/infra/compose/compose.yml"
expect_pass 'replica count is no longer artificially capped' "$case_root"

case_root="$TMP/no-shared-auth"
seed "$case_root"
sed -i 's/consume_bound/consume_removed/g' "$case_root/apps/api/src/auth/ephemeral_db.rs"
expect_fail 'shared auth binding is mandatory' "$case_root" 'shared auth backend'

case_root="$TMP/no-projection-fence"
seed "$case_root"
sed -i 's/domain_projection_gate.read().await/domain_projection_gate.read_removed()/g' \
  "$case_root/apps/api/src/middleware/domain_projection.rs"
expect_fail 'request projection fence is mandatory' "$case_root" 'request projection fence'

case_root="$TMP/no-skip-locked"
seed "$case_root"
sed -i 's/FOR UPDATE SKIP LOCKED/FOR UPDATE/g' "$case_root/apps/api/src/outbox.rs"
expect_fail 'multi-relay claim is mandatory' "$case_root" 'multi-relay claim'

case_root="$TMP/no-restart-proof"
seed "$case_root"
sed -i 's/let state_c =/let restarted_state =/g' \
  "$case_root/apps/api/tests/db_multi_instance_foundation.rs"
expect_fail 'restart proof is mandatory' "$case_root" 'two-instance/restart proof'

case_root="$TMP/no-ci-proof"
seed "$case_root"
sed -i 's/db_multi_instance_foundation/db_multi_instance_removed/g' \
  "$case_root/scripts/ci/run-postgres-integration-proofs.sh"
expect_fail 'multi-instance CI execution is mandatory' "$case_root" 'multi-instance proof runner'

case_root="$TMP/obsolete-guard"
seed "$case_root"
mkdir -p "$case_root/scripts/guard"
: > "$case_root/scripts/guard/domain-single-instance-guard.sh"
expect_fail 'obsolete single-instance guard is rejected' "$case_root" 'obsolete single-instance guard'
