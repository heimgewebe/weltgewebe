#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." > /dev/null 2>&1 && pwd)}"
COMPOSE_PROD="${REPO_ROOT}/infra/compose/compose.prod.yml"
UP_SCRIPT="${REPO_ROOT}/scripts/weltgewebe-up"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -f "$COMPOSE_PROD" ]] || fail "production compose file missing"
[[ -f "$UP_SCRIPT" ]] || fail "scripts/weltgewebe-up missing"

# These strings are literals from Compose, shell and Caddy syntax.
# shellcheck disable=SC2016
expected_compose='WELTGEWEBE_BUILD: ${WELTGEWEBE_BUILD:?WELTGEWEBE_BUILD must be set}'
# shellcheck disable=SC2016
expected_export='export WELTGEWEBE_BUILD="$HEAD_AFTER"'
# shellcheck disable=SC2016
expected_header='X-Weltgewebe-Build "{$WELTGEWEBE_BUILD}"'

if ! grep -Fq "$expected_compose" "$COMPOSE_PROD"; then
  fail "compose.prod.yml must require WELTGEWEBE_BUILD for Caddy"
fi

if ! grep -Fq "$expected_export" "$UP_SCRIPT"; then
  fail "weltgewebe-up must seed WELTGEWEBE_BUILD from deploy HEAD before compose config"
fi

for caddy in \
  "$REPO_ROOT/infra/caddy/Caddyfile.vps" \
  "$REPO_ROOT/infra/caddy/Caddyfile.heim" \
  "$REPO_ROOT/infra/caddy/Caddyfile.prod"; do
  [[ -f "$caddy" ]] || fail "Caddyfile missing: $caddy"
  if ! grep -Fq "$expected_header" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") must emit X-Weltgewebe-Build from environment"
  fi
done

printf 'PASS: Caddy build header contract is wired\n'
