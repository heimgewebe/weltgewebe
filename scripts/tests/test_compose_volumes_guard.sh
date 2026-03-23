#!/usr/bin/env bash
set -euo pipefail

# Test: scripts/guard-compose-no-relative-volumes.sh
# Verifies that the compose volume guard correctly detects
# relative host volume paths and enforces the prod allowlist.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
GUARD_SCRIPT="$REPO_ROOT/scripts/guard-compose-no-relative-volumes.sh"

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

# Case 1: No relative volumes — should pass
cat > "$TEMP_DIR/compose-clean.yml" <<'YAML'
services:
  api:
    image: api:latest
    volumes:
      - db_data:/var/lib/postgresql/data
      - /opt/weltgewebe/policies:/app/policies:ro
YAML

if bash "$GUARD_SCRIPT" "$TEMP_DIR/compose-clean.yml" >/dev/null 2>&1; then
  report 0 "No relative volumes passes"
else
  report 1 "No relative volumes should pass"
fi

# Case 2: Relative volume in non-prod file — should fail
cat > "$TEMP_DIR/compose-bad.yml" <<'YAML'
services:
  api:
    image: api:latest
    volumes:
      - ./data:/app/data
YAML

if bash "$GUARD_SCRIPT" "$TEMP_DIR/compose-bad.yml" >/dev/null 2>&1; then
  report 1 "Relative volume in non-prod should fail"
else
  report 0 "Relative volume in non-prod correctly rejected"
fi

# Case 3: Parent-relative volume — should fail
cat > "$TEMP_DIR/compose-parent.yml" <<'YAML'
services:
  web:
    image: web:latest
    volumes:
      - ../config/app.conf:/etc/app/app.conf:ro
YAML

if bash "$GUARD_SCRIPT" "$TEMP_DIR/compose-parent.yml" >/dev/null 2>&1; then
  report 1 "Parent-relative volume should fail"
else
  report 0 "Parent-relative volume correctly rejected"
fi

# Case 4: Allowed Caddy mounts in compose.prod.yml — should pass
cat > "$TEMP_DIR/compose.prod.yml" <<'YAML'
services:
  caddy:
    image: caddy:latest
    volumes:
      - ../caddy/Caddyfile.prod:/etc/caddy/Caddyfile:ro
      - ../caddy/heimserver:/etc/caddy/heimserver:ro
YAML

if bash "$GUARD_SCRIPT" "$TEMP_DIR/compose.prod.yml" >/dev/null 2>&1; then
  report 0 "Allowed Caddy mounts in compose.prod.yml pass"
else
  report 1 "Allowed Caddy mounts in compose.prod.yml should pass"
fi

# Case 5: Non-allowed relative volume in compose.prod.yml — should fail
cat > "$TEMP_DIR/compose.prod.yml" <<'YAML'
services:
  caddy:
    image: caddy:latest
    volumes:
      - ../caddy/Caddyfile.prod:/etc/caddy/Caddyfile:ro
      - ./secrets:/app/secrets
YAML

if bash "$GUARD_SCRIPT" "$TEMP_DIR/compose.prod.yml" >/dev/null 2>&1; then
  report 1 "Non-allowed relative volume in compose.prod.yml should fail"
else
  report 0 "Non-allowed relative volume in compose.prod.yml correctly rejected"
fi

# Case 6: Missing compose file — should exit 2
if bash "$GUARD_SCRIPT" "$TEMP_DIR/nonexistent.yml" >/dev/null 2>&1; then
  report 1 "Missing compose file should fail"
else
  report 0 "Missing compose file correctly detected"
fi

# Case 7: Named volumes only — should pass
cat > "$TEMP_DIR/compose-named.yml" <<'YAML'
services:
  db:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
YAML

if bash "$GUARD_SCRIPT" "$TEMP_DIR/compose-named.yml" >/dev/null 2>&1; then
  report 0 "Named volumes pass"
else
  report 1 "Named volumes should pass"
fi

# Case 8: Caddy mounts without :ro — should also pass
cat > "$TEMP_DIR/compose.prod.yml" <<'YAML'
services:
  caddy:
    image: caddy:latest
    volumes:
      - ../caddy/Caddyfile.prod:/etc/caddy/Caddyfile
      - ../caddy/heimserver:/etc/caddy/heimserver
YAML

if bash "$GUARD_SCRIPT" "$TEMP_DIR/compose.prod.yml" >/dev/null 2>&1; then
  report 0 "Caddy mounts without :ro pass (optional suffix)"
else
  report 1 "Caddy mounts without :ro should pass"
fi

echo ""
echo "test_compose_volumes_guard: $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
