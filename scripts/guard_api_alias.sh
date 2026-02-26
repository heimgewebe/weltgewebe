#!/usr/bin/env bash
set -euo pipefail

# Check if docker and docker compose are available
if ! command -v docker >/dev/null 2>&1; then
    echo "WARNING: Docker not found. Skipping API alias check."
    exit 0
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "WARNING: Docker Compose not found or not working. Skipping API alias check."
    exit 0
fi

if ! docker info >/dev/null 2>&1; then
    echo "WARNING: Docker daemon not reachable. Skipping API alias check."
    exit 0
fi

# Render the compose config
# We provide dummy values for required environment variables to ensure config rendering succeeds.
CONFIG=$(WEB_UPSTREAM_URL="dummy" WEB_UPSTREAM_HOST="dummy" docker compose -f infra/compose/compose.prod.yml config 2>/dev/null || true)

if [[ -z "$CONFIG" ]]; then
    echo "ERROR: Docker Compose config failed to render. Please ensure required environment variables are set or .env is present."
    exit 1
fi

# Precise check: Extract only the 'api' service block.
# We implement a strict state machine to avoid false positives:
# 1. Wait for 'services:' top-level key.
# 2. Inside services, wait for '  api:' (indentation level 2).
# 3. Capture lines until the next service key at the same indentation level.
SERVICE_BLOCK=$(echo "$CONFIG" | awk '
  /^services:/ { in_services=1; next }
  in_services && /^  api:/ { in_api=1; print; next }
  in_services && in_api && /^  [a-zA-Z0-9_-]+:/ { in_api=0; exit }
  in_services && in_api { print }
')

if [[ -z "$SERVICE_BLOCK" ]]; then
    echo "ERROR: Service 'api' not found in rendered compose config."
    # Dump config snippet for debugging if verbose
    # echo "$CONFIG" | head -n 20
    exit 1
fi

# Check for "aliases:" and "weltgewebe-api" within the api block.
FAIL=0
if ! echo "$SERVICE_BLOCK" | grep -q "aliases:"; then
     echo "ERROR: No 'aliases' section found for service 'api'. The alias is mandatory."
     FAIL=1
fi

if ! echo "$SERVICE_BLOCK" | grep -q "\- weltgewebe-api"; then
    echo "ERROR: compose.prod.yml: services.api.networks.default.aliases must include 'weltgewebe-api'"
    FAIL=1
fi

if [[ "$FAIL" == "1" ]]; then
    echo
    echo "--- Extracted API Service Block ---"
    echo "$SERVICE_BLOCK"
    echo "-----------------------------------"
    exit 1
fi
