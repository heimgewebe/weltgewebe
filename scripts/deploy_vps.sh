#!/usr/bin/env bash
set -e

# Load environment variables if needed, or assume they are in .env
# docker compose will pick up .env automatically

echo "Deploying to VPS..."

# Try to pull latest images (if registry is configured)
# If pull fails (e.g. no registry auth or local build intended), we continue to build
echo "Pulling images..."
docker compose -f infra/compose/compose.prod.yml pull || echo "Pull failed or images not found, proceeding to build..."

# Start services (build if missing or forced by changes)
echo "Starting services..."
docker compose -f infra/compose/compose.prod.yml up -d --build

# Cleanup unused images
echo "Pruning unused images..."
docker image prune -f

echo "Deployment complete."
