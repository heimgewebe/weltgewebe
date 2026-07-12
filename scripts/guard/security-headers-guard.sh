#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." >/dev/null 2>&1 && pwd)}"
POLICY_FILE="${REPO_ROOT}/policies/security.yml"

failures=0

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  failures=$((failures + 1))
}

policy_value() {
  local key="$1"
  awk -F: -v key="$key" '
    $1 ~ "^[[:space:]]*" key "$" {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
      print $2
      exit
    }
  ' "$POLICY_FILE"
}

if [[ ! -f "$POLICY_FILE" ]]; then
  fail "security policy missing: $POLICY_FILE"
  exit 1
fi

max_age="$(policy_value max_age_seconds)"
if [[ -z "$max_age" || "$max_age" == *[!0-9]* ]]; then
  fail "policies/security.yml must define numeric strict_transport_security.max_age_seconds"
fi

expected_hsts="Strict-Transport-Security \"max-age=${max_age}; includeSubDomains\""

for caddy in \
  "${REPO_ROOT}/infra/caddy/Caddyfile.vps" \
  "${REPO_ROOT}/infra/caddy/Caddyfile.heim" \
  "${REPO_ROOT}/infra/caddy/Caddyfile.prod"; do
  if [[ ! -f "$caddy" ]]; then
    fail "production-relevant Caddyfile missing: $caddy"
    continue
  fi

  if ! grep -Fq "$expected_hsts" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing HSTS policy: $expected_hsts"
  fi
  for header in \
    'X-Frame-Options "DENY"' \
    'Referrer-Policy "no-referrer"' \
    'X-Content-Type-Options "nosniff"' \
    'X-Weltgewebe-Build "{$WELTGEWEBE_BUILD}"'; do
    if ! grep -Fq "$header" "$caddy"; then
      fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing header: $header"
    fi
  done
done

for caddy in \
  "${REPO_ROOT}/infra/caddy/Caddyfile.vps" \
  "${REPO_ROOT}/infra/caddy/Caddyfile.heim"; do
  if [[ ! -f "$caddy" ]]; then
    continue
  fi
  if ! grep -Fq "Content-Security-Policy" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing static-app CSP"
    continue
  fi
  for directive in \
    "default-src 'self'" \
    "script-src 'self' 'unsafe-inline'" \
    "style-src 'self' 'unsafe-inline'" \
    "connect-src 'self'" \
    "img-src 'self' data: blob:" \
    "object-src 'none'"; do
    if ! grep -Fq "$directive" "$caddy"; then
      fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") CSP missing directive: $directive"
    fi
  done
done

if ! grep -Fq "script-src 'unsafe-inline'" "$POLICY_FILE"; then
  fail "policies/security.yml must record the current script-src unsafe-inline exception"
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi

printf 'PASS: security header policy matches production Caddyfiles\n'
