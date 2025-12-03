#!/usr/bin/env bash
set -euo pipefail

printf "[drill] Starting disaster recovery smoke sequence...\n"

# Placeholder: ensure core services are up
if ! docker compose -f infra/compose/compose.core.yml ps >/dev/null 2>&1; then
  printf "[drill] Hinweis: Compose-Stack scheint nicht zu laufen. Bitte zuerst 'just up' ausführen.\n"
  exit 1
fi

docker compose -f infra/compose/compose.core.yml ps

printf "[drill] Running smoke tests on API endpoints...\n"

# API_BASE defaults to localhost:8081 (Proxy) but allows override
API_BASE="${API_BASE:-http://localhost:8081}"

# Test /api/nodes (Proxy strips /api -> API receives /nodes)
if curl -fsS "${API_BASE}/api/nodes?limit=1" >/dev/null; then
  printf "  [ok] GET /api/nodes\n"
else
  printf "  [fail] GET /api/nodes - Check if API is running and routing is correct.\n"
  exit 1
fi

# Test /api/edges
if curl -fsS "${API_BASE}/api/edges?limit=1" >/dev/null; then
  printf "  [ok] GET /api/edges\n"
else
  printf "  [fail] GET /api/edges\n"
  exit 1
fi

printf "[drill] Smoke tests passed.\n"
