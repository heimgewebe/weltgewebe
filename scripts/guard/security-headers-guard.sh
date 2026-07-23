#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." > /dev/null 2>&1 && pwd)}"
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

# Caddy expands this placeholder at runtime; it is intentionally literal here.
# shellcheck disable=SC2016
expected_build_header='X-Weltgewebe-Build "{$WELTGEWEBE_BUILD}"'

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
    "$expected_build_header"; do
    if ! grep -Fq "$header" "$caddy"; then
      fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing header: $header"
    fi
  done
done

for caddy in \
  "${REPO_ROOT}/infra/caddy/Caddyfile" \
  "${REPO_ROOT}/infra/caddy/Caddyfile.vps" \
  "${REPO_ROOT}/infra/caddy/Caddyfile.heim"; do
  if [[ ! -f "$caddy" ]]; then
    fail "static-app Caddyfile missing: $caddy"
    continue
  fi
  if ! grep -Fq "Content-Security-Policy" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing static-app CSP"
    continue
  fi
  if grep -Eq "script-src[^;]*'unsafe-inline'" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") must not allow script-src unsafe-inline"
  fi
  if ! grep -Fq "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing strict non-document/error CSP baseline"
  fi
  if ! grep -Fq "@magicLinkConfirm {" "$caddy" || ! grep -Fq "path /api/auth/magic-link/consume" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing exact magic-link confirmation CSP matcher"
  fi
  if ! grep -Fq "method GET" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") magic-link confirmation CSP must be GET-only"
  fi
  if ! grep -Fq "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none';" "$caddy"; then
    fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") missing narrow magic-link confirmation CSP"
  fi
  for directive in \
    "style-src 'self' 'unsafe-inline'" \
    "connect-src 'self'" \
    "img-src 'self' data: blob:" \
    "worker-src 'self' blob:" \
    "font-src 'self'" \
    "media-src 'self'" \
    "manifest-src 'self'" \
    "child-src 'self'" \
    "frame-src 'self'" \
    "object-src 'none'" \
    "base-uri 'self'" \
    "form-action 'self'" \
    "frame-ancestors 'none'"; do
    if ! grep -Fq "$directive" "$caddy"; then
      fail "$(realpath --relative-to "$REPO_ROOT" "$caddy") CSP missing directive: $directive"
    fi
  done
done

if grep -Fq "script-src 'unsafe-inline'" "$POLICY_FILE"; then
  fail "policies/security.yml must not retain a script-src unsafe-inline exception"
fi
if ! grep -Fq "script_mode: hash" "$POLICY_FILE"; then
  fail "policies/security.yml must record hash-bound script delivery"
fi
SVELTE_CONFIG="${REPO_ROOT}/apps/web/svelte.config.js"
if ! grep -Fq 'mode: "hash"' "$SVELTE_CONFIG" || ! grep -Fq '"script-src": ["self"]' "$SVELTE_CONFIG"; then
  fail "apps/web/svelte.config.js must enable SvelteKit hash CSP for script-src"
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi

printf 'PASS: security header policy matches production Caddyfiles\n'
