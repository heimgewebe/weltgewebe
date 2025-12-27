#!/usr/bin/env bash
set -euo pipefail

# Load environment variables robustly
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

echo "Deploying to VPS..."

# --- Validation ---

if [ ! -f "infra/compose/compose.prod.yml" ]; then
    echo "Error: infra/compose/compose.prod.yml not found."
    exit 1
fi

if [ -z "${WEB_UPSTREAM_HOST:-}" ]; then
    echo "Error: WEB_UPSTREAM_HOST is not set in .env or environment."
    exit 1
fi

if [[ "${WEB_UPSTREAM_HOST:-}" =~ ^https?:// ]]; then
    echo "Error: WEB_UPSTREAM_HOST should not contain http:// or https:// (just the domain)."
    exit 1
fi

if [[ ! "${WEB_UPSTREAM_URL:-}" =~ ^https:// ]]; then
    echo "Error: WEB_UPSTREAM_URL is not set or does not start with 'https://'."
    exit 1
fi

# --- Deployment ---

# Generate robust API version tag (fallback to date if git fails or no .git)
API_VERSION=$(git rev-parse --short HEAD 2>/dev/null || date +%F-%s)
export API_VERSION
echo "Deploying with API_VERSION=${API_VERSION}"

# Try to pull latest images (if registry is configured)
# If pull fails (e.g. no registry auth or local build intended), we continue to build
echo "Pulling images..."
docker compose -f infra/compose/compose.prod.yml pull || echo "Pull failed or images not found, proceeding to build..."

# Start services (build if missing or forced by changes)
echo "Starting services..."
docker compose -f infra/compose/compose.prod.yml up -d --build

# Cleanup unused images (Optional)
PRUNE_IMAGES=${PRUNE_IMAGES:-0}

if [ "$PRUNE_IMAGES" -eq 1 ]; then
    echo "Pruning unused images..."
    docker image prune -f
else
    echo "Skipping image prune (set PRUNE_IMAGES=1 to enable)."
fi

echo "Deployment complete."
