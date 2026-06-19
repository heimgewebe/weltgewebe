#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -- "$HERE/../.." && pwd)"
GUARD="$ROOT/scripts/guard/domain-single-instance-guard.sh"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
pass=0; fail=0

check() {
  local expect="$1" name="$2" path="$3" body="$4" root out rc=0
  root="$(mktemp -d "$TMP/case.XXXX")"
  mkdir -p "$root/$(dirname "$path")"
  printf '%s\n' "$body" >"$root/$path"
  out="$(REPO_ROOT="$root" bash "$GUARD" 2>&1)" || rc=$?
  if { [ "$expect" = pass ] && [ "$rc" -eq 0 ]; } || { [ "$expect" = fail ] && [ "$rc" -ne 0 ]; }; then
    pass=$((pass+1)); echo "PASS: $name"
  else
    fail=$((fail+1)); echo "FAIL: $name (rc=$rc; $out)"
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

if REPO_ROOT="$ROOT" bash "$GUARD" >/dev/null 2>&1; then pass=$((pass+1)); echo 'PASS: real repository drift check'; else fail=$((fail+1)); echo 'FAIL: real repository drift check'; fi

echo "test_domain_single_instance_guard: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
