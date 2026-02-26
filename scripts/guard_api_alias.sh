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

# Pragmatic checks on the rendered config
# We need to ensure:
# 1. The 'api' service is defined.
# 2. 'aliases' keyword is present (implies network aliases are used).
# 3. 'weltgewebe-api' is present as an alias.

if ! echo "$CONFIG" | grep -q "api:"; then
    echo "ERROR: Service 'api' not found in rendered compose config."
    exit 1
fi

if ! echo "$CONFIG" | grep -q "aliases:"; then
     echo "ERROR: No network aliases found in rendered compose config. The API alias is mandatory."
     exit 1
fi

if ! echo "$CONFIG" | grep -q "\- weltgewebe-api"; then
    echo "ERROR: compose.prod.yml: services.api.networks.default.aliases must include 'weltgewebe-api'"
    exit 1
fi
