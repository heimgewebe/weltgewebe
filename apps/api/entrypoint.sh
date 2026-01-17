#!/usr/bin/env bash
set -e

# GEWEBE_IN_DIR should be set by docker-compose, default to .gewebe/in
DATA_DIR="${GEWEBE_IN_DIR:-.gewebe/in}"

# Check if seeding is enabled (default: false)
# We support "true", "1", "yes"
ENABLE_SEEDING="${GEWEBE_SEED_DEMO:-false}"

if [[ "$ENABLE_SEEDING" =~ ^(true|1|yes)$ ]]; then
    # Sentinel check: If core files exist and are not empty, we assume data is present.
    if [ -s "$DATA_DIR/demo.nodes.jsonl" ] && \
       [ -s "$DATA_DIR/demo.accounts.jsonl" ] && \
       [ -s "$DATA_DIR/demo.edges.jsonl" ]; then
        echo "Data files found in $DATA_DIR. Skipping generation."
    else
        echo "Ensuring data in $DATA_DIR (Seeding Enabled)..."

        # Ensure directory exists
        mkdir -p "$DATA_DIR"

        # Run generation script to seed data if missing
        if command -v generate-demo-data >/dev/null 2>&1; then
            generate-demo-data "$DATA_DIR"
        else
            echo "Warning: generate-demo-data not found, skipping data seeding."
        fi
    fi
else
    echo "Skipping data seeding (GEWEBE_SEED_DEMO=$ENABLE_SEEDING)"
fi

# Exec the passed command (e.g. the API server)
exec "$@"
