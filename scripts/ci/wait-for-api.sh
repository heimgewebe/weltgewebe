#!/usr/bin/env bash
set -euo pipefail

API_URL="${GEWEBE_API_BASE:-http://127.0.0.1:8080}"
MAX_RETRIES=30
SLEEP_SECONDS=2

echo "Waiting for API at $API_URL to be ready..."

check_endpoint() {
  local endpoint="$1"
  local url="$API_URL$endpoint"
  local temp_out
  temp_out=$(mktemp)

  if curl -sSf "$url" > "$temp_out" 2>/dev/null; then
    # Check if response is not empty (e.g. > 2 bytes, minimal for JSON "[]")
    if [ -s "$temp_out" ] && [ "$(wc -c < "$temp_out")" -gt 2 ]; then
      rm "$temp_out"
      return 0
    fi
  fi
  rm -f "$temp_out"
  return 1
}

count=0
while [ $count -lt $MAX_RETRIES ]; do
  if check_endpoint "/api/nodes" && check_endpoint "/api/accounts" && check_endpoint "/api/edges"; then
    echo "✅ API is ready: /api/nodes, /api/accounts, /api/edges are reachable and non-empty."
    exit 0
  fi

  echo "API not yet ready (or empty response). Retrying in ${SLEEP_SECONDS}s... ($((count+1))/$MAX_RETRIES)"
  sleep $SLEEP_SECONDS
  count=$((count+1))
done

echo "❌ API failed to become ready within $((MAX_RETRIES * SLEEP_SECONDS)) seconds."
echo "Diagnostics:"
echo "--- /api/nodes ---"
curl -v "$API_URL/api/nodes" || true
echo "--- /api/accounts ---"
curl -v "$API_URL/api/accounts" || true
exit 1
