#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)}"
COMPOSE_PROD="${REPO_ROOT}/infra/compose/compose.prod.yml"
UP_SCRIPT="${REPO_ROOT}/scripts/weltgewebe-up"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -f "$COMPOSE_PROD" ]] || fail "production compose file missing"
[[ -f "$UP_SCRIPT" ]] || fail "scripts/weltgewebe-up missing"

if ! grep -Fq 'WELTGEWEBE_BUILD: ${WELTGEWEBE_BUILD:?WELTGEWEBE_BUILD must be set}' "$COMPOSE_PROD"; then
  fail "compose.prod.yml must require WELTGEWEBE_BUILD for Caddy"
fi

if ! grep -Fq 'export WELTGEWEBE_BUILD="$HEAD_AFTER"' "$UP_SCRIPT"; then
  fail "weltgewebe-up must seed WELTGEWEBE_BUILD from deploy HEAD before compose config"
fi

for caddy in \
  "$REPO_ROOT/infra/caddy/Caddyfile.vps" \
  "$REPO_ROOT/infra/caddy/Caddyfile.heim" \
  "$REPO_ROOT/infra/caddy/Caddyfile.prod"; do
  [[ -f "$caddy" ]] || fail "Caddyfile missing: $caddy"
  if ! grep -Fq 'X-Weltgewebe-Build "{$WELTGEWEBE_BUILD}"' "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") must emit X-Weltgewebe-Build from environment"
  fi
done

printf 'PASS: Caddy build header contract is wired\n'
