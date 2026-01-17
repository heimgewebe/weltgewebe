#!/usr/bin/env bash
set -e

# GEWEBE_IN_DIR should be set by docker-compose, default to .gewebe/in
DATA_DIR="${GEWEBE_IN_DIR:-.gewebe/in}"
echo "Ensuring data in $DATA_DIR..."

# Ensure directory exists
mkdir -p "$DATA_DIR"

# Run generation script to seed data if missing
# We assume generate-demo-data is in the PATH or at a known location.
if command -v generate-demo-data >/dev/null 2>&1; then
    generate-demo-data "$DATA_DIR"
else
    echo "Warning: generate-demo-data not found, skipping data seeding."
fi

# Exec the passed command (e.g. the API server)
exec "$@"
