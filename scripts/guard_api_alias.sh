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
# We assume standard 2-space indentation for services under 'services:'.
# Logic:
# 1. Start capturing when we see '  api:' at the start of a line (with 2 spaces).
# 2. Stop capturing when we see another key at indentation level 2 (start of line + 2 spaces + key).
# 3. Print the captured lines.
SERVICE_BLOCK=$(echo "$CONFIG" | awk '
  /^  api:/ { in_block=1; print; next }
  /^  [a-zA-Z0-9_-]+:/ { in_block=0 }
  in_block { print }
')

if [[ -z "$SERVICE_BLOCK" ]]; then
    echo "ERROR: Service 'api' not found in rendered compose config."
    exit 1
fi

# Check for "aliases:" and "weltgewebe-api" within the api block.
if ! echo "$SERVICE_BLOCK" | grep -q "aliases:"; then
     echo "ERROR: No 'aliases' section found for service 'api'. The alias is mandatory."
     exit 1
fi

if ! echo "$SERVICE_BLOCK" | grep -q "\- weltgewebe-api"; then
    echo "ERROR: compose.prod.yml: services.api.networks.default.aliases must include 'weltgewebe-api'"
    exit 1
fi
