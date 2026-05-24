#!/usr/bin/env bash
set -euo pipefail

# Smoke-checks that the bootstrapped account is served by a running stack.
#
# Reads account metadata from .gewebe/in/bootstrap-first-account.env (written
# by scripts/dev/bootstrap-first-account.sh). Checks:
#   - /api/accounts: account present and public_pos set
#   - /map: reachable (HTTP 200)
#
# Usage:
#   ./scripts/dev/smoke-seed.sh
#   BASE_URL=http://127.0.0.1:8081 ./scripts/dev/smoke-seed.sh
#   # Hit the Rust API directly (no /api prefix):
#   BASE_URL=http://127.0.0.1:8080 API_PREFIX= ./scripts/dev/smoke-seed.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8081}"
API_PREFIX="${API_PREFIX-/api}"
META_DIR="${GEWEBE_IN_DIR:-.gewebe/in}"
META_FILE="$META_DIR/bootstrap-first-account.env"

if [ ! -f "$META_FILE" ]; then
  echo "Error: Bootstrap-Metadaten nicht gefunden: $META_FILE" >&2
  echo "Erst Bootstrap ausführen:" >&2
  echo "  ACCOUNT_TITLE=\"...\" PUBLIC_LAT=\"...\" PUBLIC_LON=\"...\" just bootstrap-first-account" >&2
  exit 1
fi

# shellcheck source=/dev/null
. "$META_FILE"
ACCOUNT_ID="${BOOTSTRAP_ACCOUNT_ID:?BOOTSTRAP_ACCOUNT_ID not set in $META_FILE}"

fail=0
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

check_url() {
  local label="$1"
  local url="$2"
  local code
  code="$(curl -sS -o "$tmp" -w '%{http_code}' "$url" || true)"
  if [ "$code" != "200" ]; then
    echo "✗ $label: HTTP $code ($url)"
    fail=1
    return 1
  fi
  return 0
}

echo "Smoke gegen $BASE_URL (API-Prefix: '${API_PREFIX}')"
echo "Account-ID: $ACCOUNT_ID"

# Check /api/accounts — account present with public_pos
if check_url "accounts" "$BASE_URL$API_PREFIX/accounts"; then
  _ok=1
  if ! grep -q "\"$ACCOUNT_ID\"" "$tmp"; then
    echo "✗ accounts: Account $ACCOUNT_ID nicht gefunden"
    _ok=0
    fail=1
  fi
  if command -v jq > /dev/null 2>&1; then
    if ! jq -e --arg id "$ACCOUNT_ID" \
      '.[] | select(.id == $id) | .public_pos
       | (.lat | type == "number") and (.lon | type == "number")' \
      "$tmp" > /dev/null 2>&1; then
      echo "✗ accounts: public_pos.{lat,lon} fehlt für Account $ACCOUNT_ID"
      _ok=0
      fail=1
    fi
  else
    if ! grep -q '"public_pos"' "$tmp"; then
      echo "✗ accounts: public_pos nicht in Antwort gefunden (jq nicht verfügbar)"
      _ok=0
      fail=1
    fi
  fi
  if [ "$_ok" -eq 1 ]; then
    echo "✓ accounts: 200, Account $ACCOUNT_ID mit public_pos.{lat,lon}"
  fi
fi

# Check /map reachable (only if API_PREFIX is set, i.e., not hitting API directly)
if [ -n "$API_PREFIX" ]; then
  if check_url "map" "$BASE_URL/map"; then
    echo "✓ map: 200"
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo "Smoke FEHLGESCHLAGEN" >&2
  exit 1
fi
echo "Smoke OK"
