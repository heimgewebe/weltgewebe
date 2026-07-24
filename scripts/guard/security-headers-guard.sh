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

named_matcher_block() {
  local file="$1"
  local matcher="$2"
  python3 - "$file" "$matcher" << 'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
matcher = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
start_re = re.compile(rf"^\s*@{re.escape(matcher)}\s*\{{\s*$")
for index, line in enumerate(lines):
    if not start_re.match(line):
        continue
    depth = 0
    block = []
    for candidate in lines[index:]:
        block.append(candidate)
        depth += candidate.count("{") - candidate.count("}")
        if depth == 0:
            print("\n".join(block))
            raise SystemExit(0)
    break
raise SystemExit(1)
PY
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
  relative_caddy="$(realpath --relative-to "$REPO_ROOT" "$caddy")"
  if ! magic_block="$(named_matcher_block "$caddy" magicLinkConfirm)"; then
    fail "$relative_caddy missing exact magic-link confirmation CSP matcher"
  else
    if [[ "$(printf '%s\n' "$magic_block" | grep -Ec '^[[:space:]]*method[[:space:]]+GET[[:space:]]*$')" -ne 1 ]]; then
      fail "$relative_caddy magic-link confirmation matcher must contain exactly one GET method constraint"
    fi
    if [[ "$(printf '%s\n' "$magic_block" | grep -Ec '^[[:space:]]*path[[:space:]]+/api/auth/magic-link/consume[[:space:]]*$')" -ne 1 ]]; then
      fail "$relative_caddy magic-link confirmation matcher must contain the exact consume path"
    fi
  fi

  magic_policy="default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none';"
  if ! grep -Fq "header @magicLinkConfirm >Content-Security-Policy \"${magic_policy}\"" "$caddy"; then
    fail "$relative_caddy must defer and overwrite the canonical magic-link confirmation CSP"
  fi

  strict_policy="default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';"
  strict_matcher="@apiResponse"
  if [[ "$(basename "$caddy")" == "Caddyfile.vps" ]]; then
    strict_matcher="@nonDocumentResponse"
  fi
  if ! grep -Fq "header ${strict_matcher} >Content-Security-Policy \"${strict_policy}\"" "$caddy"; then
    fail "$relative_caddy must defer and overwrite the canonical strict API CSP"
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
