#!/usr/bin/env bash
# No `set -e`: the guard's exit code is the unit under test, so we must observe
# it rather than abort on the first non-zero status.
set -uo pipefail

# Test: scripts/guard/domain-single-instance-guard.sh
#
# Verifies the DOMAIN-PG-002 single-instance guard against its three parser
# surfaces (compose api scaling, docker compose --scale/scale, Caddy upstreams),
# the executable-vs-docs value policy, the strict Caddy API host family, and the
# exit-code contract (0 = ok, 1 = policy violation, 2 = internal error).
#
# Tests call the REAL guard via REPO_ROOT override — no shadow reimplementation.
# A crashed or fail-closed scanner must surface as exit 2 (internal error) and
# must never be counted as a passed negative test.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT_REAL="$(dirname "$(dirname "$SCRIPT_DIR")")"
GUARD_SCRIPT="$REPO_ROOT_REAL/scripts/guard/domain-single-instance-guard.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

# A fake scanner that always fails with a hard error (exit 2), used to prove the
# guard reports internal errors instead of silently passing.
FAKE_FAIL="$TEMP_DIR/fail-scanner"
printf '#!/usr/bin/env bash\nexit 2\n' >"$FAKE_FAIL"
chmod +x "$FAKE_FAIL"

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

# expect_code <root> <want-exit> <description>
expect_code() {
  local root="$1" want="$2" desc="$3" got
  REPO_ROOT="$root" bash "$GUARD_SCRIPT" >/dev/null 2>&1
  got=$?
  if [ "$got" -eq "$want" ]; then
    report 0 "$desc"
  else
    report 1 "$desc (want exit $want, got $got)"
  fi
}

expect_pass() { expect_code "$1" 0 "$2"; }      # only exit 0 passes
expect_violation() { expect_code "$1" 1 "$2"; } # only exit 1 passes

# expect_internal_error <root> <which-scanner: find|grep> <description>
expect_internal_error() {
  local root="$1" which="$2" desc="$3" got
  case "$which" in
    find) FIND_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD_SCRIPT" >/dev/null 2>&1 ;;
    grep) GREP_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD_SCRIPT" >/dev/null 2>&1 ;;
    *) report 1 "$desc (unknown scanner $which)"; return ;;
  esac
  got=$?
  if [ "$got" -eq 2 ]; then
    report 0 "$desc"
  else
    report 1 "$desc (want exit 2, got $got)"
  fi
}

# expect_stderr_contains <root> <description> <fragment...>
expect_stderr_contains() {
  local root="$1" desc="$2"
  shift 2
  local err frag ok=0
  err="$(REPO_ROOT="$root" bash "$GUARD_SCRIPT" 2>&1 >/dev/null)"
  for frag in "$@"; do
    if ! printf '%s\n' "$err" | grep -qF -- "$frag"; then
      report 1 "$desc (stderr missing: $frag)"
      return
    fi
  done
  ok=1
  [ "$ok" -eq 1 ] && report 0 "$desc"
}

# ============================================================================
# Compose — PASS (exit 0)
# ============================================================================

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
expect_pass "$root" "clean single-instance stack"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: 1
YAML
expect_pass "$root" "api.deploy.replicas: 1"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: "1"
YAML
expect_pass "$root" "api.deploy.replicas: \"1\" (quoted literal)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    scale: 0
YAML
expect_pass "$root" "api.scale: 0"

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
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    environment:
      API_REPLICAS: 2
      api_replicas: 2
YAML
expect_pass "$root" "nested environment API_REPLICAS keys ignored"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    labels:
      my.custom.replicas: 2
      scale: 2
YAML
expect_pass "$root" "nested labels scale/replicas keys ignored"

# ============================================================================
# Compose — VIOLATION (exit 1)
# ============================================================================

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    scale: 2
YAML
expect_violation "$root" "api.scale: 2"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    scale: ${API_SCALE:-1}
YAML
expect_violation "$root" "api.scale: \${API_SCALE:-1} (non-literal, fail-closed)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: 3
YAML
expect_violation "$root" "api.deploy.replicas: 3"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: "2"
YAML
expect_violation "$root" "api.deploy.replicas: \"2\" (quoted)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: 02
YAML
expect_violation "$root" "api.deploy.replicas: 02 (zero-padded)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: two
YAML
expect_violation "$root" "api.deploy.replicas: two (non-numeric)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy:
      replicas: *api_scale
YAML
expect_violation "$root" "api.deploy.replicas: *api_scale (alias)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: 1
YAML
expect_violation "$root" "api direct replicas key (even value 1)"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    replicas: 2
YAML
expect_violation "$root" "api direct replicas: 2"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    <<: *api_defaults
YAML
expect_violation "$root" "api merge key <<: *anchor"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api: *api_defaults
YAML
expect_violation "$root" "api service is an alias"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api: { image: example, scale: 2 }
YAML
expect_violation "$root" "api service inline flow mapping"

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    deploy: { replicas: 2 }
YAML
expect_violation "$root" "api.deploy inline flow mapping"

# ============================================================================
# CLI scale — executable surfaces (only 0/1 pass)
# ============================================================================

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
docker compose up -d --scale api=1
SH
expect_pass "$root" "exec --scale api=1"

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
docker compose up -d --build --scale caddy=0
SH
expect_pass "$root" "exec --scale caddy=0 (non-api)"

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
some-tool --scale api=2
SH
expect_pass "$root" "exec non-docker tool --scale api=2 (not a compose cmd)"

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
# docker compose up -d --scale api=2
SH
expect_pass "$root" "exec fully-commented --scale api=2"

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
docker compose up -d --scale api=1 # formerly api=2
SH
expect_pass "$root" "exec inline-comment after valid --scale api=1"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api=2
SH
expect_violation "$root" "exec --scale api=2"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api 2
SH
expect_violation "$root" "exec --scale api 2 (space-separated)"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale=api=2
SH
expect_violation "$root" "exec --scale=api=2"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale "api=2"
SH
expect_violation "$root" "exec --scale \"api=2\""

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale 'api=2'
SH
expect_violation "$root" "exec --scale 'api=2'"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api
SH
expect_violation "$root" "exec --scale api (missing value)"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api=two
SH
expect_violation "$root" "exec --scale api=two"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api=*api_scale
SH
expect_violation "$root" "exec --scale api=*api_scale (alias)"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api=${API_REPLICAS:-1}
SH
expect_violation "$root" "exec --scale api=\${API_REPLICAS:-1} (non-literal)"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale web=2 --scale api=2
SH
expect_violation "$root" "exec multiple --scale on one line"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose scale api=2
SH
expect_violation "$root" "exec compose scale subcommand api=2"

root="$(make_fixture_root)"
write_file "$root/.github/workflows/deploy.yml" <<'YAML'
jobs:
  deploy:
    steps:
      - run: docker compose up -d --scale api=2
YAML
expect_violation "$root" ".github/workflows --scale api=2"

root="$(make_fixture_root)"
write_file "$root/Makefile" <<'MK'
deploy:
	docker compose up -d --scale api=2
MK
expect_violation "$root" "Makefile --scale api=2"

root="$(make_fixture_root)"
write_file "$root/Justfile" <<'JF'
deploy:
    docker compose up -d --scale api=2
JF
expect_violation "$root" "Justfile --scale api=2"

root="$(make_fixture_root)"
write_file "$root/.devcontainer/post-create.sh" <<'SH'
docker compose up -d --scale api=2
SH
expect_violation "$root" ".devcontainer --scale api=2"

# ============================================================================
# CLI scale — docs surface (N and <value> placeholders additionally allowed)
# ============================================================================

root="$(make_fixture_root)"
write_file "$root/docs/x.md" <<'MD'
docker compose up -d --scale api=N
MD
expect_pass "$root" "docs --scale api=N placeholder"

root="$(make_fixture_root)"
write_file "$root/docs/x.md" <<'MD'
docker compose up -d --scale api=<value>
MD
expect_pass "$root" "docs --scale api=<value> placeholder"

root="$(make_fixture_root)"
write_file "$root/docs/x.md" <<'MD'
docker compose up -d --scale=api=N
MD
expect_pass "$root" "docs --scale=api=N placeholder"

root="$(make_fixture_root)"
write_file "$root/docs/x.md" <<'MD'
docker compose up -d --scale api N
MD
expect_pass "$root" "docs --scale api N placeholder"

root="$(make_fixture_root)"
write_file "$root/docs/x.md" <<'MD'
docker compose up -d --scale api=2
MD
expect_violation "$root" "docs --scale api=2 still blocks"

root="$(make_fixture_root)"
write_file "$root/docs/x.md" <<'MD'
docker compose up -d --scale api=two
MD
expect_violation "$root" "docs --scale api=two blocks"

# ============================================================================
# Caddy — PASS (exit 0)
# ============================================================================

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
}
CADDY
expect_pass "$root" "caddy single API upstream + separate web upstream"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy api:8080 # api-2:8080
}
CADDY
expect_pass "$root" "caddy inline-comment second upstream ignored"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  # reverse_proxy api:8080 api-2:8080
}
CADDY
expect_pass "$root" "caddy fully-commented directive ignored"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy api-gateway:8080 web:5173
}
CADDY
expect_pass "$root" "caddy api-gateway is not an API host"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy capital-api:8080 web:5173
}
CADDY
expect_pass "$root" "caddy capital-api is not an API host"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy myapi:8080 web:5173
}
CADDY
expect_pass "$root" "caddy myapi is not an API host"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy capital:8080 web:5173
}
CADDY
expect_pass "$root" "caddy non-api hostname does not false-positive"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy [::1]:8080
}
CADDY
expect_pass "$root" "caddy bracketed IPv6 single non-api upstream"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy /* {env.WEB_UPSTREAM_URL} {
    header_up Host {upstream_hostport}
  }
}
CADDY
expect_pass "$root" "caddy dynamic env web upstream not blocked"

# ============================================================================
# Caddy — VIOLATION (exit 1)
# ============================================================================

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080 api-2:8080
  }
}
CADDY
expect_violation "$root" "caddy reverse_proxy api:8080 api-2:8080"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy http://api:8080 http://api-2:8080
  }
}
CADDY
expect_violation "$root" "caddy http:// scheme upstreams"

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
expect_violation "$root" "caddy to-block api:8080 api-2:8080"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy api:8080 [::1]:8080
  }
}
CADDY
expect_violation "$root" "caddy api plus bracketed IPv6 upstream"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  handle /api/* {
    reverse_proxy http://api:8080 http://[::1]:8080
  }
}
CADDY
expect_violation "$root" "caddy http scheme api plus IPv6 upstream"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy weltgewebe-api:8080 api-2:8080
}
CADDY
expect_violation "$root" "caddy weltgewebe-api + api-2"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy api-1:8080 api-2:8080
}
CADDY
expect_violation "$root" "caddy api-1 + api-2 (numbered family)"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy weltgewebe-api-1:8080 web:5173
}
CADDY
expect_violation "$root" "caddy weltgewebe-api-1 + web"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy @api api:8080 api-2:8080
}
CADDY
expect_violation "$root" "caddy named matcher before two api upstreams"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy /api/* api:8080 api-2:8080
}
CADDY
expect_violation "$root" "caddy path matcher before two api upstreams"

# ============================================================================
# Internal error (exit 2) — a failed scanner must never pass as a negative test
# ============================================================================

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    scale: 1
YAML
expect_internal_error "$root" find "find scanner failure -> exit 2"

root="$(make_fixture_root)"
write_file "$root/scripts/up.sh" <<'SH'
docker compose up -d --scale api=1
SH
expect_internal_error "$root" grep "grep scanner failure -> exit 2"

# Cleanup invariant: a failed run must not leak temp files (isolated TMPDIR).
root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    scale: 1
YAML
iso_tmp="$TEMP_DIR/isolated-tmp"
mkdir -p "$iso_tmp"
TMPDIR="$iso_tmp" FIND_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD_SCRIPT" >/dev/null 2>&1 || true
leftovers="$(find "$iso_tmp" -mindepth 1 2>/dev/null | wc -l | tr -d ' ')"
if [ "$leftovers" -eq 0 ]; then
  report 0 "internal-error run leaves no temp files"
else
  report 1 "internal-error run leaked $leftovers temp file(s)"
fi

# ============================================================================
# Output contract — stderr carries the marker, a reason, file:line and the ref
# ============================================================================

root="$(make_fixture_root)"
write_file "$root/infra/compose/compose.yml" <<'YAML'
services:
  api:
    scale: 2
YAML
expect_stderr_contains "$root" "compose finding output contract" \
  "DOMAIN-SINGLE-INSTANCE-GUARD" \
  "literal 0 or 1" \
  "compose.yml:3" \
  "docs/reports/domain-postgres-instance-coherence-decision.md"

root="$(make_fixture_root)"
write_file "$root/scripts/deploy.sh" <<'SH'
docker compose up -d --scale api=2
SH
expect_stderr_contains "$root" "cli finding output contract" \
  "DOMAIN-SINGLE-INSTANCE-GUARD" \
  "executable surface" \
  "deploy.sh:1" \
  "docs/reports/domain-postgres-instance-coherence-decision.md"

root="$(make_fixture_root)"
write_file "$root/infra/caddy/Caddyfile" <<'CADDY'
:8081 {
  reverse_proxy api:8080 api-2:8080
}
CADDY
expect_stderr_contains "$root" "caddy finding output contract" \
  "DOMAIN-SINGLE-INSTANCE-GUARD" \
  "reverse_proxy/to directive line" \
  "Caddyfile:2" \
  "docs/reports/domain-postgres-instance-coherence-decision.md"

# ============================================================================
# Results
# ============================================================================

echo ""
echo "fixture tests: $PASS passed, $FAIL failed"

# Repository drift check — an integration test, not a parser unit test: the
# working tree must currently satisfy the single-instance boundary (exit 0).
DRIFT_RC=0
if REPO_ROOT="$REPO_ROOT_REAL" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  echo "repository drift check: passed"
else
  echo "repository drift check: FAILED (exit $?)"
  DRIFT_RC=1
fi

if [ "$FAIL" -ne 0 ] || [ "$DRIFT_RC" -ne 0 ]; then
  exit 1
fi
