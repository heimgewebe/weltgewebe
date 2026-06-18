#!/usr/bin/env bash
set -euo pipefail

# Test: scripts/guard/domain-single-instance-guard.sh
#
# Verifies that the DOMAIN-PG-002 single-instance guard detects API scale-out
# drift (compose replicas, --scale api, an API upstream plus any additional
# upstream on one Caddy directive line), including quoted,
# zero-padded and non-literal/`$`-expanded values (fail-closed), while NOT
# producing false positives for non-api scaling, single instances, or
# documentation placeholders.
#
# Tests call the REAL guard via REPO_ROOT override — no shadow reimplementation.

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

# --- helpers ------------------------------------------------------------------

make_fixture_root() {
  mktemp -d "$TEMP_DIR/fixture.XXXXXX"
}

# write_file <path> ; content read from stdin
write_file() {
  local path="$1"
  mkdir -p "$(dirname "$path")"
  cat >"$path"
}

expect_pass() {
  # <root> <description>
  if REPO_ROOT="$1" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
    report 0 "$2"
  else
    report 1 "$2 (expected PASS)"
  fi
}

expect_fail() {
  # <root> <description>
  if REPO_ROOT="$1" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
    report 1 "$2 (expected FAIL)"
  else
    report 0 "$2"
  fi
}

# ----------------------------------------------------------------------------
# Negative tests — must FAIL
# ----------------------------------------------------------------------------

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: 2
YAML
expect_fail "$root" "api replicas: 2"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: 3
YAML
expect_fail "$root" "api deploy.replicas: 3"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: '2'
YAML
expect_fail "$root" "api replicas: '2' (single-quoted)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: "2"
YAML
expect_fail "$root" "api replicas: \"2\" (double-quoted)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: 02
YAML
expect_fail "$root" "api replicas: 02 (zero-padded)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: ${API_REPLICAS:-2}
YAML
expect_fail "$root" "api replicas: \${API_REPLICAS:-2} (non-literal, fail-closed)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: "${API_REPLICAS:-2}"
YAML
expect_fail "$root" "api replicas: \"\${API_REPLICAS:-2}\" (quoted non-literal, fail-closed)"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
#!/usr/bin/env bash
docker compose up -d --scale api=2
SH
expect_fail "$root" "--scale api=2"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api 2
SH
expect_fail "$root" "--scale api 2 (space-separated)"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale=api=2
SH
expect_fail "$root" "--scale=api=2"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale "api=2"
SH
expect_fail "$root" "--scale \"api=2\""

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale 'api=2'
SH
expect_fail "$root" "--scale 'api=2'"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api=02
SH
expect_fail "$root" "--scale api=02 (zero-padded)"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api=${API_REPLICAS:-2}
SH
expect_fail "$root" "--scale api=\${API_REPLICAS:-2} (non-literal, fail-closed)"

root="$(make_fixture_root)"
write_file "$root/.github/workflows/deploy.yml" <<'YAML'
jobs:
  deploy:
    steps:
      - run: docker compose up -d --scale api=2
YAML
expect_fail "$root" ".github/workflows --scale api=2"

root="$(make_fixture_root)"
write_file "$root/Makefile" <<'MK'
deploy:
	docker compose up -d --scale api=2
MK
expect_fail "$root" "Makefile --scale api=2"

root="$(make_fixture_root)"
write_file "$root/Justfile" <<'JF'
deploy:
    docker compose up -d --scale api=2
JF
expect_fail "$root" "Justfile --scale api=2"

root="$(make_fixture_root)"
write_file "$root/.devcontainer/post-create.sh" <<'SH'
docker compose up -d --scale api=2
SH
expect_fail "$root" ".devcontainer --scale api=2"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080 api-2:8080
  }
}
CADDY
expect_fail "$root" "Caddy reverse_proxy api:8080 api-2:8080"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy http://api:8080 http://api-2:8080
  }
}
CADDY
expect_fail "$root" "Caddy reverse_proxy with http:// scheme upstreams"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy {
      to api:8080 api-2:8080
    }
  }
}
CADDY
expect_fail "$root" "Caddy reverse_proxy block: to api:8080 api-2:8080"

# ----------------------------------------------------------------------------
# Positive tests — must PASS
# ----------------------------------------------------------------------------

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.core.yml" <<'YAML'
services:
  api:
    image: weltgewebe-api:latest
  db:
    image: postgres:16
YAML
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
}
CADDY
expect_pass "$root" "Clean single-instance stack"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: 1
YAML
expect_pass "$root" "api replicas: 1 (single instance)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    image: weltgewebe-api:latest
  db:
    deploy:
      replicas: 2
YAML
expect_pass "$root" "non-api db deploy.replicas: 2 (not flagged)"

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
docker compose up -d --scale api=1
SH
expect_pass "$root" "--scale api=1 (single instance)"

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
docker compose up -d --build --scale caddy=0
SH
expect_pass "$root" "--scale caddy=0 (non-api)"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
}
CADDY
expect_pass "$root" "Single API upstream + separate web upstream"

# ----------------------------------------------------------------------------
# Real repository drift check (not a guard-logic test — asserts the working
# tree currently satisfies the single-instance boundary).
# ----------------------------------------------------------------------------
expect_pass "$REPO_ROOT" "real repository drift check"

echo ""
echo "test_domain_single_instance_guard: $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
