#!/usr/bin/env bash
set -euo pipefail

# Test: scripts/guard/domain-single-instance-guard.sh
# Verifies that the DOMAIN-PG-002 single-instance guard detects the obvious
# API scale-out drift (compose replicas, --scale api, multi-upstream Caddy)
# while NOT producing false positives for non-api scaling or single instances.
#
# Tests call the REAL guard script via REPO_ROOT override — no shadow
# reimplementation of guard logic.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
GUARD_SCRIPT="$REPO_ROOT/scripts/guard/domain-single-instance-guard.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

PASS=0
FAIL=0

report() {
  if [ "$1" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "PASS: $2"
  else
    FAIL=$((FAIL + 1))
    echo "FAIL: $2"
  fi
}

run_guard() {
  # $1 = fixture root. Returns the guard's exit status.
  REPO_ROOT="$1" bash "$GUARD_SCRIPT" >/dev/null 2>&1
}

# Case 1: Clean minimal stack (single api service, single api upstream) — pass.
mkdir -p "$TEMP_DIR/clean/infra/compose" "$TEMP_DIR/clean/infra/caddy"
cat > "$TEMP_DIR/clean/infra/compose/compose.core.yml" <<'YAML'
services:
  api:
    image: weltgewebe-api:latest
  db:
    image: postgres:16
YAML
cat > "$TEMP_DIR/clean/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
}
CADDY
if run_guard "$TEMP_DIR/clean"; then
  report 0 "Clean single-instance stack passes"
else
  report 1 "Clean single-instance stack should pass"
fi

# Case 2: api service with replicas: 2 — fail.
mkdir -p "$TEMP_DIR/api_replicas/infra/compose"
cat > "$TEMP_DIR/api_replicas/infra/compose/compose.yml" <<'YAML'
services:
  api:
    image: weltgewebe-api:latest
    replicas: 2
YAML
if run_guard "$TEMP_DIR/api_replicas"; then
  report 1 "api replicas: 2 should fail"
else
  report 0 "api replicas: 2 correctly detected"
fi

# Case 3: api service with deploy.replicas: 3 — fail.
mkdir -p "$TEMP_DIR/api_deploy_replicas/infra/compose"
cat > "$TEMP_DIR/api_deploy_replicas/infra/compose/compose.yml" <<'YAML'
services:
  api:
    image: weltgewebe-api:latest
    deploy:
      replicas: 3
YAML
if run_guard "$TEMP_DIR/api_deploy_replicas"; then
  report 1 "api deploy.replicas: 3 should fail"
else
  report 0 "api deploy.replicas: 3 correctly detected"
fi

# Case 4: replicas: 2 on a NON-api service (db) — must NOT false-positive.
mkdir -p "$TEMP_DIR/db_replicas/infra/compose"
cat > "$TEMP_DIR/db_replicas/infra/compose/compose.yml" <<'YAML'
services:
  api:
    image: weltgewebe-api:latest
  db:
    image: postgres:16
    deploy:
      replicas: 2
YAML
if run_guard "$TEMP_DIR/db_replicas"; then
  report 0 "Non-api (db) replicas does not false-positive"
else
  report 1 "Non-api (db) replicas must not be flagged"
fi

# Case 5: api replicas: 1 — single instance is allowed, must pass.
mkdir -p "$TEMP_DIR/api_replicas_1/infra/compose"
cat > "$TEMP_DIR/api_replicas_1/infra/compose/compose.yml" <<'YAML'
services:
  api:
    image: weltgewebe-api:latest
    deploy:
      replicas: 1
YAML
if run_guard "$TEMP_DIR/api_replicas_1"; then
  report 0 "api replicas: 1 (single instance) passes"
else
  report 1 "api replicas: 1 should pass"
fi

# Case 6: docker compose --scale api=2 in a script — fail.
mkdir -p "$TEMP_DIR/scale_api/scripts"
cat > "$TEMP_DIR/scale_api/scripts/deploy.sh" <<'SH'
#!/usr/bin/env bash
docker compose -f infra/compose/compose.prod.yml up -d --scale api=2
SH
if run_guard "$TEMP_DIR/scale_api"; then
  report 1 "--scale api=2 should fail"
else
  report 0 "--scale api=2 correctly detected"
fi

# Case 7: --scale caddy=0 — must NOT false-positive (existing legitimate usage).
mkdir -p "$TEMP_DIR/scale_caddy/scripts"
cat > "$TEMP_DIR/scale_caddy/scripts/up.sh" <<'SH'
#!/usr/bin/env bash
docker compose up -d --build --scale caddy=0
SH
if run_guard "$TEMP_DIR/scale_caddy"; then
  report 0 "--scale caddy=0 does not false-positive"
else
  report 1 "--scale caddy=0 must not be flagged"
fi

# Case 8: --scale api=1 — single instance is allowed, must pass.
mkdir -p "$TEMP_DIR/scale_api_1/scripts"
cat > "$TEMP_DIR/scale_api_1/scripts/up.sh" <<'SH'
#!/usr/bin/env bash
docker compose up -d --scale api=1
SH
if run_guard "$TEMP_DIR/scale_api_1"; then
  report 0 "--scale api=1 (single instance) passes"
else
  report 1 "--scale api=1 should pass"
fi

# Case 9: Caddy reverse_proxy with multiple api upstreams — fail.
mkdir -p "$TEMP_DIR/caddy_multi/infra/caddy"
cat > "$TEMP_DIR/caddy_multi/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080 api-2:8080
  }
}
CADDY
if run_guard "$TEMP_DIR/caddy_multi"; then
  report 1 "Multiple api upstreams should fail"
else
  report 0 "Multiple api upstreams correctly detected"
fi

# Case 10: Caddy single api upstream + path-matched web upstream — must pass.
mkdir -p "$TEMP_DIR/caddy_single/infra/caddy"
cat > "$TEMP_DIR/caddy_single/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
}
CADDY
if run_guard "$TEMP_DIR/caddy_single"; then
  report 0 "Single api upstream + web upstream passes"
else
  report 1 "Single api upstream + web upstream should pass"
fi

# Case 11: The real repository must currently satisfy the boundary (drift guard).
if run_guard "$REPO_ROOT"; then
  report 0 "Real repository satisfies the single-instance boundary"
else
  report 1 "Real repository must satisfy the single-instance boundary"
fi

echo ""
echo "test_domain_single_instance_guard: $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
