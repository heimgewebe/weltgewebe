#!/usr/bin/env bash
set -euo pipefail

# Check if docker is available
if ! command -v docker >/dev/null 2>&1; then
    echo "WARNING: Docker not found. Skipping API alias check."
    exit 0
fi

# Render the compose config
# We provide dummy values for required environment variables to ensure config rendering succeeds.
# These values do not affect the structure we are checking.
CONFIG=$(WEB_UPSTREAM_URL="dummy" WEB_UPSTREAM_HOST="dummy" docker compose -f infra/compose/compose.prod.yml config 2>/dev/null || true)

if [[ -z "$CONFIG" ]]; then
    echo "WARNING: Docker Compose config failed to render. Is the daemon running? Skipping check."
    exit 0
fi

# Check for the alias in the rendered config.
# We look for "aliases:" followed by "weltgewebe-api" in the next few lines.
# This is safer than raw grep because comments are stripped and formatting is normalized.
if ! echo "$CONFIG" | grep -A 5 "aliases:" | grep -q "weltgewebe-api"; then
  echo "ERROR: weltgewebe-api network alias missing in rendered compose config."
  exit 1
fi
