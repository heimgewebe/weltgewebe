#!/usr/bin/env bash
set -euo pipefail

# Smoke-checks that the real seed data is served by a running stack.
#
# Defaults target the dev Caddy origin, where /api/* is reverse-proxied to the
# Rust API (JSONL-backed) and /map is served by the web app.
#
# Usage:
#   ./scripts/dev/smoke-seed.sh
#   BASE_URL=http://127.0.0.1:8081 ./scripts/dev/smoke-seed.sh
#   # Hit the Rust API directly (no /api prefix):
#   BASE_URL=http://127.0.0.1:8080 API_PREFIX= ./scripts/dev/smoke-seed.sh

BASE_URL="${BASE_URL:-http://127.0.0.1:8081}"
API_PREFIX="${API_PREFIX-/api}"

ACCOUNT_ID="a0000001-0000-4000-8000-000000000001"
NODE_ID="b0000001-0000-4000-8000-000000000001"
EDGE_ID="c0000001-0000-4000-8000-000000000001"

fail=0
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

check() {
  local label="$1"
  local url="$2"
  local needle="$3"
  local code
  code="$(curl -sS -o "$tmp" -w '%{http_code}' "$url" || true)"

  if [ "$code" != "200" ]; then
    echo "✗ $label: HTTP $code ($url)"
    fail=1
    return
  fi
  if [ -n "$needle" ] && ! grep -q "$needle" "$tmp"; then
    echo "✗ $label: 200 but expected id $needle not found ($url)"
    fail=1
    return
  fi
  if [ -n "$needle" ]; then
    echo "✓ $label: 200, contains $needle"
  else
    echo "✓ $label: 200"
  fi
}

echo "Smoke against $BASE_URL (api prefix: '${API_PREFIX}')"
check "accounts" "$BASE_URL$API_PREFIX/accounts" "$ACCOUNT_ID"
check "nodes" "$BASE_URL$API_PREFIX/nodes" "$NODE_ID"
check "edges" "$BASE_URL$API_PREFIX/edges" "$EDGE_ID"
check "map" "$BASE_URL/map" ""

if [ "$fail" -ne 0 ]; then
  echo "Smoke FAILED" >&2
  exit 1
fi
echo "Smoke OK"
