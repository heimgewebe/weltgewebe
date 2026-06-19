#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
GUARD="$ROOT/scripts/guard/domain-single-instance-guard.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
pass=0
fail=0

# A fake scanner that always hard-fails (exit 2), to prove a broken scanner
# surfaces as an internal error rather than a silent pass / passed negative test.
FAKE_FAIL="$TMP/fail-scanner"
printf '#!/usr/bin/env bash\nexit 2\n' > "$FAKE_FAIL"
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
  printf '%s\n' "$body" > "$root/$path"
  out="$(REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$?
  if [ "$rc" -eq "$want" ]; then
    pass=$((pass + 1))
    echo "PASS: $name"
  else
    fail=$((fail + 1))
    echo "FAIL: $name (want=$want rc=$rc; $out)"
  fi
}

# check_cat <want-rc> <name> <path> <body> <stderr-substring>
# Asserts the exact exit code AND a diagnostic-category substring on stderr.
check_cat() {
  local want="$1" name="$2" path="$3" body="$4" needle="$5" root out rc=0
  root="$(mktemp -d "$TMP/case.XXXX")"
  mkdir -p "$root/$(dirname "$path")"
  printf '%s\n' "$body" > "$root/$path"
  out="$(REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$?
  if [ "$rc" -eq "$want" ] && printf '%s\n' "$out" | grep -qF -- "$needle"; then
    pass=$((pass + 1))
    echo "PASS: $name"
  else
    fail=$((fail + 1))
    echo "FAIL: $name (want=$want rc=$rc needle='$needle'; $out)"
  fi
}

# check_internal <name> <find|grep|awk> <path> <body> <diagnostic-substring>
# Asserts exit 2 plus internal-error diagnostics when a scanner hard-fails.
check_internal() {
  local name="$1" which="$2" path="$3" body="$4" needle="${5:-scan failed}" root out rc=0
  root="$(mktemp -d "$TMP/case.XXXX")"
  mkdir -p "$root/$(dirname "$path")"
  printf '%s\n' "$body" > "$root/$path"
  case "$which" in
    find) out="$(FIND_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$? ;;
    grep) out="$(GREP_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$? ;;
    awk) out="$(AWK_BIN="$FAKE_FAIL" REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$? ;;
    *)
      fail=$((fail + 1))
      echo "FAIL: $name (unknown scanner $which)"
      return
      ;;
  esac
  if [ "$rc" -eq 2 ] &&
    printf '%s\n' "$out" | grep -qF -- "scan failed" &&
    printf '%s\n' "$out" | grep -qF -- "internal error" &&
    printf '%s\n' "$out" | grep -qF -- "$needle"; then
    pass=$((pass + 1))
    echo "PASS: $name"
  else
    fail=$((fail + 1))
    echo "FAIL: $name (want=2 rc=$rc needle='$needle'; $out)"
  fi
}

check fail 'direct scale-out' infra/compose/compose.yml $'services:\n  api:\n    scale: 2'
check fail 'deploy replicas scale-out' infra/compose/compose.yml $'services:\n  api:\n    deploy:\n      replicas: 02'
check fail 'symbolic replicas fail closed' infra/compose/compose.yml $'services:\n  api:\n    deploy:\n      replicas: *api_scale'
check fail 'empty replicas fail closed' infra/compose/compose.yml $'services:\n  api:\n    replicas:'
check fail 'direct replicas key forbidden even literal' infra/compose/compose.yml $'services:\n  api:\n    replicas: 1'
check fail 'empty scale fail closed' infra/compose/compose.yml $'services:\n  api:\n    scale:'
check pass 'nested replicas ignored' infra/compose/compose.yml $'services:\n  api:\n    environment:\n      replicas: 2\n    labels:\n      my.custom.replicas: 2\n    deploy:\n      replicas: 1'
check pass 'non-api scaling ignored' infra/compose/compose.yml $'services:\n  api:\n    scale: 1\n  db:\n    scale: 4'
check pass 'quoted mapping keys and quoted scale literal' infra/compose/compose.yml $'"services":\n  "api":\n    "scale": "1"'
check pass 'api block anchor children checked' infra/compose/compose.yml $'services:\n  api: &defaults\n    scale: 1'
check pass 'deploy block anchor children checked' infra/compose/compose.yml $'services:\n  api:\n    deploy: &deployment\n      replicas: 1'
check pass 'scale comment after whitespace allowed' infra/compose/compose.yml $'services:\n  api:\n    scale: 1 # single instance'
check fail 'quoted mapping keys scale-out' infra/compose/compose.yml $'"services":\n  "api":\n    "scale": 2'
check fail 'quoted deploy replicas scale-out' infra/compose/compose.yml $'services:\n  api:\n    "deploy":\n      "replicas": 2'
check fail 'merge key under deploy' infra/compose/compose.yml $'services:\n  api:\n    deploy:\n      <<: *deployment'
check fail 'inline anchored service mapping' infra/compose/compose.yml $'services:\n  api: &defaults { scale: 2 }'
check fail 'inline anchored deploy mapping' infra/compose/compose.yml $'services:\n  api:\n    deploy: &deployment { replicas: 2 }'
check fail 'mismatched quoted scale literal' infra/compose/compose.yml "services:
  api:
    scale: '1\"'"

# shellcheck disable=SC2016 # Literal Compose fixture values, not shell expansions.
for value in 01 -1 1.0 '"1x"' '${API_SCALE:-1}' '*alias'; do
  check fail "reject Compose scale literal: $value" infra/compose/compose.yml \
    $'services:\n  api:\n    scale: '"$value"
done

# shellcheck disable=SC2016 # Literal CLI fixture values, not shell expansions.
for cmd in \
  'docker compose up --scale api=2' \
  'docker compose up --scale api 2' \
  'docker compose up --scale=api=2' \
  'docker compose up --scale=api=two' \
  'docker compose up --scale=api=N' \
  'docker compose up --scale=api=<value>' \
  'docker compose up --scale=api=${API_SCALE}' \
  'docker compose scale api=2' \
  'docker compose scale api 2' \
  'docker-compose up --scale api=2' \
  'docker-compose up --scale=api=2' \
  'docker-compose scale api=2' \
  'docker compose up --scale api=two' \
  'docker compose up --scale api=*api_scale' \
  'docker compose up --scale api' \
  'docker compose scale api'; do
  check fail "reject CLI: $cmd" scripts/deploy.sh "$cmd"
done
check pass 'safe executable CLI' scripts/deploy.sh $'# docker compose up --scale api=9\ndocker compose up --scale api=1\ndocker compose up --scale api 0\ndocker compose up --scale=api=1\ndocker compose up --scale=api=0\ndocker compose scale api=1\ndocker compose scale api 0\ndocker-compose up --scale api=1\ndocker-compose up --scale=api=1\ndocker-compose scale api=1\ndocker compose up --scale caddy=0'
check pass 'non-compose command ignored' scripts/deploy.sh $'some compose scale api=2\nsome-tool --scale api=2'
for value in N '<value>' 0 1; do
  check pass "docs: api=$value" docs/example.md '`docker compose up --scale api='"$value"'`'
done
# shellcheck disable=SC2016 # Literal Markdown command fixture.
check pass 'docs: --scale=api=N placeholder' docs/example.md '`docker compose up --scale=api=N`'
# shellcheck disable=SC2016 # Literal Markdown command fixture.
check pass 'docs: --scale=api=<value> placeholder' docs/example.md '`docker compose up --scale=api=<value>`'
# shellcheck disable=SC2016 # Literal docs fixture values, not shell expansions.
for value in '<N>' banana '*alias' -1 1.5 '<whatever>' '${API_SCALE}' 2; do
  check fail "docs reject api=$value" docs/example.md '`docker compose up --scale api='"$value"'`'
done
# shellcheck disable=SC2016 # Literal Markdown command fixture.
check fail 'docs reject --scale=api=2' docs/example.md '`docker compose up --scale=api=2`'
# shellcheck disable=SC2016 # Literal Markdown command fixture.
check fail 'docs reject --scale=api=<N>' docs/example.md '`docker compose up --scale=api=<N>`'

check fail 'Caddy second upstream' infra/caddy/Caddyfile 'reverse_proxy api:8080 api-2:8080'
check fail 'Caddy IPv6 second upstream' infra/caddy/Caddyfile 'reverse_proxy http://api:8080 http://[::1]:8080'
check pass 'Caddy comments ignored' infra/caddy/Caddyfile $'reverse_proxy api:8080 # api-2:8080\n# reverse_proxy api:8080 api-2:8080'
check pass 'Caddy non-api names ignored' infra/caddy/Caddyfile $'reverse_proxy api-gateway:8080 web:5173\nreverse_proxy capital-api:8080 web:5173\nreverse_proxy myapi:8080 web:5173'

check pass 'target pruned' target/compose.generated.yml $'services:\n  api:\n    scale: 99'
check pass '.venv pruned' .venv/compose.generated.yml $'services:\n  api:\n    scale: 99'
check pass 'node_modules CLI pruned' node_modules/bad.sh 'docker compose up --scale api=2'
check pass 'target CLI pruned' target/bad.sh 'docker compose up --scale api=2'
check pass '.venv CLI pruned' .venv/bad.sh 'docker compose up --scale api=2'
# shellcheck disable=SC2016 # Literal Markdown command fixture.
check pass 'docs generated CLI pruned' docs/_generated/example.md '`docker compose up --scale api=2`'

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
# shellcheck disable=SC2016 # Literal Markdown command fixture.
check fail 'doc placeholder <N> rejected' docs/example.md '`docker compose up --scale api=<N>`'

# Negative tests assert the diagnostic category, not just any failure.
check_cat 1 'compose diagnostic category' infra/compose/compose.yml $'services:\n  api:\n    scale: 2' 'Compose'
check_cat 1 'cli diagnostic category' scripts/deploy.sh 'docker compose up --scale api=2' 'surface'
check_cat 1 'caddy diagnostic category' infra/caddy/Caddyfile 'reverse_proxy api:8080 api-2:8080' 'reverse_proxy/to directive'

# A failed scanner is an internal error (exit 2), never a passed negative test.
check_internal 'find failure -> exit 2' find infra/compose/compose.yml $'services:\n  api:\n    scale: 1' 'find failed'
check_internal 'grep failure -> exit 2' grep scripts/deploy.sh 'docker compose up --scale api=1' 'grep failed'
check_internal 'awk failure -> exit 2' awk infra/compose/compose.yml $'services:\n  api:\n    scale: 1' 'awk failed'

if REPO_ROOT="$ROOT" bash "$GUARD" > /dev/null 2>&1; then
  pass=$((pass + 1))
  echo 'PASS: real repository drift check'
else
  fail=$((fail + 1))
  echo 'FAIL: real repository drift check'
fi

echo "test_domain_single_instance_guard: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
