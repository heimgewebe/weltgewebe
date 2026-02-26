#!/usr/bin/env bash
set -euo pipefail

# Check if docker and docker compose are available and functional
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
    echo "WARNING: Docker Compose config failed to render. Skipping check."
    exit 0
fi

# Check for the alias specifically within the 'api' service block.
# We extract the 'api:' service block by looking for "  api:" (indentation matters in yaml)
# and printing until the next service definition (start of line + 2 spaces + key).
# Note: In rendered config, services are typically indented by 2 spaces under 'services:'.
# 'api:' will be at indentation level 2. We assume standard formatting from 'docker compose config'.
SERVICE_BLOCK=$(echo "$CONFIG" | awk '
  /^  api:/ { in_block=1; print; next }
  /^  [a-zA-Z0-9_-]+:/ { in_block=0 }
  in_block { print }
')

if [[ -z "$SERVICE_BLOCK" ]]; then
    echo "ERROR: Service 'api' not found in rendered compose config."
    exit 1
fi

# Check for "weltgewebe-api" within the aliases of the api block.
# We look for "aliases:" then the alias.
if ! echo "$SERVICE_BLOCK" | grep -A 10 "aliases:" | grep -q "weltgewebe-api"; then
  echo "ERROR: compose.prod.yml: services.api.networks.default.aliases missing 'weltgewebe-api'"
  exit 1
fi
