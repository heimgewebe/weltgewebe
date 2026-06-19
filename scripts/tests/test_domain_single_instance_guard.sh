#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
GUARD="$ROOT/scripts/guard/domain-single-instance-guard.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

# A fake scanner that always hard-fails (exit 2), to prove a broken scanner
# surfaces as an internal error rather than a silent pass / passed negative test.
FAKE_FAIL="$TMP/fail-scanner"
printf '#!/usr/bin/env bash\nexit 2\n' >"$FAKE_FAIL"
chmod +x "$FAKE_FAIL"

# check <pass|fail|0|1|2> <name> <path> <body>
# Asserts the EXACT exit code (pass=0, fail=1). Exit 2 (internal error) never
# satisfies a "fail" expectation.
check() {
  local expect="$1" name="$2" path="$3" body="$4" root out rc=0 want
  case "$expect" in
    pass) want=0 ;;
    fail) want=1 ;;
    *) want="$expect" ;;
  esac
  root="$(mktemp -d "$TMP/case.XXXX")"
  mkdir -p "$root/$(dirname "$path")"
  printf '%s\n' "$body" >"$root/$path"
  out="$(REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$?
  if [ "$rc" -eq "$want" ]; then
    pass=$((pass+1)); echo "PASS: $name"
  else
    fail=$((fail+1)); echo "FAIL: $name (want=$want rc=$rc; $out)"
  fi
}

# check_cat <want-rc> <name> <path> <body> <stderr-substring>
# Asserts the exact exit code AND a diagnostic-category substring on stderr.
check_cat() {
  local want="$1" name="$2" path="$3" body="$4" needle="$5" root out rc=0
  root="$(mktemp -d "$TMP/case.XXXX")"
  mkdir -p "$root/$(dirname "$path")"
  printf '%s\n' "$body" >"$root/$path"
  out="$(REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$?
  if [ "$rc" -eq "$want" ] && printf '%s\n' "$out" | grep -qF -- "$needle"; then
    pass=$((pass+1)); echo "PASS: $name"
  else
    fail=$((fail+1)); echo "FAIL: $name (want=$want rc=$rc needle='$needle'; $out)"
  fi
}

# check_internal <name> <find|grep> <path> <body>
# Asserts exit 2 and the "scan failed" diagnostic when a scanner hard-fails.
check_internal() {
  local name="$1" which="$2" path="$3" body="$4" root out rc=0
  root="$(mktemp -d "$TMP/case.XXXX")"
  mkdir -p "$root/$(dirname "$path")"
  printf '%s\n' "$body" >"$root/$path"
  case "$which" in
    find) out="$(FIND_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$? ;;
    grep) out="$(GREP_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$? ;;
    *) fail=$((fail+1)); echo "FAIL: $name (unknown scanner $which)"; return ;;
  esac
  if [ "$rc" -eq 2 ] && printf '%s\n' "$out" | grep -qF -- "scan failed"; then
    pass=$((pass+1)); echo "PASS: $name"
  else
    fail=$((fail+1)); echo "FAIL: $name (want=2 rc=$rc; $out)"
  fi
}

check fail 'direct scale-out' infra/compose/compose.yml $'services:\n  api:\n    scale: 2'
check fail 'deploy replicas scale-out' infra/compose/compose.yml $'services:\n  api:\n    deploy:\n      replicas: 02'
check fail 'symbolic replicas fail closed' infra/compose/compose.yml $'services:\n  api:\n    deploy:\n      replicas: *api_scale'
check fail 'empty replicas fail closed' infra/compose/compose.yml $'services:\n  api:\n    replicas:'
check pass 'nested replicas ignored' infra/compose/compose.yml $'services:\n  api:\n    environment:\n      replicas: 2\n    labels:\n      my.custom.replicas: 2\n    deploy:\n      replicas: 1'
check pass 'non-api scaling ignored' infra/compose/compose.yml $'services:\n  api:\n    scale: 1\n  db:\n    scale: 4'

for cmd in \
  'docker compose up --scale api=2' \
  'docker compose up --scale api 2' \
  'docker compose up --scale api=two' \
  'docker compose up --scale api=*api_scale' \
  'docker compose up --scale api'; do
  check fail "reject CLI: $cmd" scripts/deploy.sh "$cmd"
done
check pass 'safe executable CLI' scripts/deploy.sh $'# docker compose up --scale api=9\ndocker compose up --scale api=1\ndocker compose up --scale caddy=0'
check pass 'documentation placeholders' docs/example.md $'`docker compose up --scale api=N`\n`docker compose up --scale api=<value>`'
check fail 'concrete bad documentation value' docs/example.md '`docker compose up --scale api=two`'

check fail 'Caddy second upstream' infra/caddy/Caddyfile 'reverse_proxy api:8080 api-2:8080'
check fail 'Caddy IPv6 second upstream' infra/caddy/Caddyfile 'reverse_proxy http://api:8080 http://[::1]:8080'
check pass 'Caddy comments ignored' infra/caddy/Caddyfile $'reverse_proxy api:8080 # api-2:8080\n# reverse_proxy api:8080 api-2:8080'
check pass 'Caddy non-api names ignored' infra/caddy/Caddyfile $'reverse_proxy api-gateway:8080 web:5173\nreverse_proxy capital-api:8080 web:5173\nreverse_proxy myapi:8080 web:5173'

check pass 'target pruned' target/compose.generated.yml $'services:\n  api:\n    scale: 99'
check pass '.venv pruned' .venv/compose.generated.yml $'services:\n  api:\n    scale: 99'

# --- Regression: hardened semantics -----------------------------------------

# Canonical weltgewebe-api host family (with numeric suffixes) is API; look-alike
# names are not. (api-gateway / capital-api / myapi are covered above.)
check fail 'Caddy weltgewebe-api upstream' infra/caddy/Caddyfile 'reverse_proxy weltgewebe-api:8080 web:5173'
check fail 'Caddy weltgewebe-api-1 upstream' infra/caddy/Caddyfile 'reverse_proxy weltgewebe-api-1:8080 web:5173'
check fail 'Caddy api-2 numeric family' infra/caddy/Caddyfile 'reverse_proxy api-2:8080 web:5173'

# Inline / alias / merge shapes on the api service or its deploy block fail closed.
check fail 'inline service mapping' infra/compose/compose.yml $'services:\n  api: { image: x, scale: 2 }'
check fail 'alias service value' infra/compose/compose.yml $'services:\n  api: *api_defaults'
check fail 'merge key under api' infra/compose/compose.yml $'services:\n  api:\n    <<: *api_defaults'
check fail 'inline deploy mapping' infra/compose/compose.yml $'services:\n  api:\n    deploy: { replicas: 2 }'
check pass 'quoted literal deploy replicas' infra/compose/compose.yml $'services:\n  api:\n    deploy:\n      replicas: "1"'

# <N> is not an evidence-backed placeholder; N and <value> remain accepted.
check fail 'doc placeholder <N> rejected' docs/example.md '`docker compose up --scale api=<N>`'

# Negative tests assert the diagnostic category, not just any failure.
check_cat 1 'compose diagnostic category' infra/compose/compose.yml $'services:\n  api:\n    scale: 2' 'Compose'
check_cat 1 'cli diagnostic category' scripts/deploy.sh 'docker compose up --scale api=2' 'surface'
check_cat 1 'caddy diagnostic category' infra/caddy/Caddyfile 'reverse_proxy api:8080 api-2:8080' 'reverse_proxy/to directive'

# A failed scanner is an internal error (exit 2), never a passed negative test.
check_internal 'find failure -> exit 2' find infra/compose/compose.yml $'services:\n  api:\n    scale: 1'
check_internal 'grep failure -> exit 2' grep scripts/deploy.sh 'docker compose up --scale api=1'

if REPO_ROOT="$ROOT" bash "$GUARD" >/dev/null 2>&1; then pass=$((pass+1)); echo 'PASS: real repository drift check'; else fail=$((fail+1)); echo 'FAIL: real repository drift check'; fi

echo "test_domain_single_instance_guard: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
