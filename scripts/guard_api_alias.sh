#!/usr/bin/env bash
set -euo pipefail

# Ensure we are operating relative to the repo root
# This script is expected to be in scripts/
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Check if docker and docker compose command are available
if ! command -v docker >/dev/null 2>&1; then
    if [[ "${GUARD_STRICT:-0}" == "1" ]]; then
        echo "ERROR: Docker not found, but GUARD_STRICT=1. Aborting."
        exit 1
    fi
    echo "NOTE: Docker not found. Guard skipped."
    exit 0
fi

if ! docker compose version >/dev/null 2>&1; then
    if [[ "${GUARD_STRICT:-0}" == "1" ]]; then
        echo "ERROR: Docker Compose not found, but GUARD_STRICT=1. Aborting."
        exit 1
    fi
    echo "NOTE: Docker Compose not found or not working. Guard skipped."
    exit 0
fi

# Note: We intentionally DO NOT check for a running docker daemon (docker info).
# 'docker compose config' should work statically without a daemon in most modern versions.
# If it fails, we catch the error below.

# Prepare rendering arguments
# If a .env file exists in the repo root, use it. This helps with variable substitution.
COMPOSE_ARGS=("--project-directory" "$REPO_DIR")
if [[ -f "$REPO_DIR/.env" ]]; then
    COMPOSE_ARGS+=("--env-file" "$REPO_DIR/.env")
fi

# Render the compose config
# We provide dummy values for known required environment variables to ensure config rendering succeeds
# even if .env is missing or partial.
# Capture stderr for better diagnostics on failure.
if command -v mktemp >/dev/null 2>&1; then
    ERR_FILE="$(mktemp)"
else
    ERR_FILE="${TMPDIR:-/tmp}/guard_api_alias.$$"
    : > "$ERR_FILE"
fi
trap 'rm -f "$ERR_FILE"' EXIT

CONFIG=$(WEB_UPSTREAM_URL="dummy" WEB_UPSTREAM_HOST="dummy" \
    docker compose "${COMPOSE_ARGS[@]}" \
    -f "$REPO_DIR/infra/compose/compose.prod.yml" config 2> "$ERR_FILE" || true)

if [[ -z "$CONFIG" ]]; then
    echo "ERROR: Docker Compose config failed to render. Please ensure required environment variables are set or .env is present."
    echo "Diagnostic output (stderr):"
    head -n 20 "$ERR_FILE" 2>/dev/null || true
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

if ! echo "$SERVICE_BLOCK" | grep -qw "weltgewebe-api"; then
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
