#!/usr/bin/env bash
set -euo pipefail

# Smoke-test for Account Creation v0: an Admin operator creates an account via
# POST /api/accounts; it must then be visible via GET /api/accounts.
# When pointed at the web/Caddy origin, the smoke also checks /map.
#
# Requirements:
#   - A running stack (default: dev Caddy origin on 127.0.0.1:8081).
#   - jq (for JSON response parsing). Install with: apt-get install jq
#   - AUTH_DEV_LOGIN=1 on the API (to obtain an admin session locally), OR a
#     pre-supplied ADMIN_SESSION_COOKIE for remote stacks.
#   - An existing ADMIN account. Its id is taken from ADMIN_ACCOUNT_ID, else from
#     .gewebe/in/bootstrap-first-account.env (bootstrap with ACCOUNT_ROLE=admin).
#
# Note: bootstrap-first-account.sh does NOT require jq; only this smoke script does.
#
# Usage:
#   ACCOUNT_ROLE=admin ACCOUNT_TITLE=Op PUBLIC_LAT=53.55 PUBLIC_LON=9.99 \
#     just bootstrap-first-account
#   AUTH_DEV_LOGIN=1 just up
#   just smoke-account-create
#
#   # Direct API (no /api prefix) with an explicit admin id:
#   BASE_URL=http://127.0.0.1:8080 API_PREFIX= ADMIN_ACCOUNT_ID=<uuid> \
#     ./scripts/dev/smoke-account-create.sh
#
#   # Remote stack with a real admin session cookie (skips dev-login):
#   BASE_URL=https://example ADMIN_SESSION_COOKIE="gewebe_session=..." \
#     ./scripts/dev/smoke-account-create.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8081}"
API_PREFIX="${API_PREFIX-/api}"
ORIGIN="${ORIGIN:-$BASE_URL}"
META_DIR="${GEWEBE_IN_DIR:-.gewebe/in}"
META_FILE="$META_DIR/bootstrap-first-account.env"

command -v jq > /dev/null 2>&1 || {
  echo "Error: jq is required." >&2
  exit 1
}

# --- Resolve admin account id and coordinates ---
ADMIN_ACCOUNT_ID="${ADMIN_ACCOUNT_ID:-}"
LAT="${TEST_LAT:-}"
LON="${TEST_LON:-}"
if [ -f "$META_FILE" ]; then
  # shellcheck source=/dev/null
  . "$META_FILE"
  ADMIN_ACCOUNT_ID="${ADMIN_ACCOUNT_ID:-${BOOTSTRAP_ACCOUNT_ID:-}}"
  LAT="${LAT:-${BOOTSTRAP_PUBLIC_LAT:-}}"
  LON="${LON:-${BOOTSTRAP_PUBLIC_LON:-}}"
fi
LAT="${LAT:-53.5503}"
LON="${LON:-9.9932}"

if [ -z "$ADMIN_ACCOUNT_ID" ] && [ -z "${ADMIN_SESSION_COOKIE:-}" ]; then
  echo "Error: no admin identity. Set ADMIN_ACCOUNT_ID or ADMIN_SESSION_COOKIE," >&2
  echo "or bootstrap an admin (ACCOUNT_ROLE=admin ... just bootstrap-first-account)." >&2
  exit 1
fi

fail=0
tmp="$(mktemp)"
jar="$(mktemp)"
trap 'rm -f "$tmp" "$jar"' EXIT

echo "Account-Create-Smoke gegen $BASE_URL (Prefix '$API_PREFIX', Origin $ORIGIN)"

# --- 1. Obtain an admin session ---
if [ -n "${ADMIN_SESSION_COOKIE:-}" ]; then
  cookie_args=(-H "Cookie: $ADMIN_SESSION_COOKIE")
  echo "→ using provided ADMIN_SESSION_COOKIE"
else
  code="$(curl -sS -o "$tmp" -w '%{http_code}' -c "$jar" \
    -X POST "$BASE_URL$API_PREFIX/auth/dev/login" \
    -H "Content-Type: application/json" \
    -H "Origin: $ORIGIN" \
    -d "{\"account_id\":\"$ADMIN_ACCOUNT_ID\"}" || true)"
  if [ "$code" != "200" ]; then
    echo "✗ dev-login: HTTP $code (need AUTH_DEV_LOGIN=1 and an existing admin account)" >&2
    exit 1
  fi
  cookie_args=(-b "$jar")
  echo "✓ dev-login: 200 (admin $ADMIN_ACCOUNT_ID)"
fi

# --- 2. Create account ---
new_title="Smoke $(date +%s)"
code="$(curl -sS -o "$tmp" -w '%{http_code}' "${cookie_args[@]}" \
  -X POST "$BASE_URL$API_PREFIX/accounts" \
  -H "Content-Type: application/json" \
  -H "Origin: $ORIGIN" \
  -d "{\"title\":\"$new_title\",\"location\":{\"lat\":$LAT,\"lon\":$LON}}" || true)"
if [ "$code" != "201" ]; then
  echo "✗ create: expected 201, got $code: $(cat "$tmp")" >&2
  exit 1
fi
new_id="$(jq -r '.id' < "$tmp")"
if ! jq -e '.public_pos | (.lat | type == "number") and (.lon | type == "number")' \
  < "$tmp" > /dev/null 2>&1; then
  echo "✗ create: response missing public_pos.{lat,lon}" >&2
  fail=1
fi
echo "✓ create: 201 (id $new_id, public_pos present)"

# --- 3. GET /accounts contains the new account with public_pos ---
code="$(curl -sS -o "$tmp" -w '%{http_code}' "$BASE_URL$API_PREFIX/accounts" || true)"
if [ "$code" = "200" ] && jq -e --arg id "$new_id" \
  '.[] | select(.id == $id) | .public_pos | (.lat | type == "number") and (.lon | type == "number")' \
  < "$tmp" > /dev/null 2>&1; then
  echo "✓ list: 200, enthält $new_id mit public_pos"
else
  echo "✗ list: Account $new_id nicht mit public_pos gefunden (HTTP $code)" >&2
  fail=1
fi

# --- 4. /map reachable, only for web/Caddy origin ---
if [ -n "$API_PREFIX" ]; then
  code="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/map" || true)"
  if [ "$code" = "200" ]; then
    echo "✓ map: 200"
  else
    echo "✗ map: HTTP $code" >&2
    fail=1
  fi
else
  echo "→ map: skipped (direct API mode)"
fi

if [ "$fail" -ne 0 ]; then
  echo "Account-Create-Smoke FEHLGESCHLAGEN" >&2
  exit 1
fi
echo "Account-Create-Smoke OK"
