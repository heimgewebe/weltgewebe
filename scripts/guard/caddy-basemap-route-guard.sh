#!/usr/bin/env bash
set -euo pipefail

# Guard: Caddy basemap route contract
#
# Verifies that infra/caddy/Caddyfile serves the sovereign basemap under the
# canonical public edge path /local-basemap/, which is the contract shared by:
#   - the frontend (basemap.ts, basemap.current.ts)
#   - the Vite dev-server middleware (vite.config.ts)
#   - the blueprint (docs/blueprints/map-blaupause.md §7)
#
# Regression protection: prevents silent re-introduction of the old /basemap/*
# route, which caused the sovereign hosting path to be factually inactive.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)}"

CADDYFILE="${REPO_ROOT}/infra/caddy/Caddyfile"

if [[ ! -f "$CADDYFILE" ]]; then
  echo "ERROR: Caddyfile not found: $CADDYFILE" >&2
  exit 2
fi

# Check that the canonical /local-basemap/* route is present
if ! grep -qE '^\s*handle_path /local-basemap/\*' "$CADDYFILE"; then
  echo "ERROR: Caddy basemap route contract violated." >&2
  echo "  Expected:  handle_path /local-basemap/* in $CADDYFILE" >&2
  echo "  Not found. The sovereign basemap hosting path would be inactive." >&2
  echo "" >&2
  echo "  The public edge contract is /local-basemap/ (frontend + blueprint)." >&2
  echo "  Ensure infra/caddy/Caddyfile contains: handle_path /local-basemap/*" >&2
  exit 1
fi

# Check that the old conflicting /basemap/* route is NOT present
# (bare /basemap/, not /local-basemap/)
if grep -qE '^\s*handle_path /basemap/\*' "$CADDYFILE"; then
  echo "ERROR: Caddy basemap route drift detected." >&2
  echo "  Found:    handle_path /basemap/* in $CADDYFILE" >&2
  echo "  Conflict: frontend requests /local-basemap/, Caddy serves /basemap/*." >&2
  echo "" >&2
  echo "  Replace handle_path /basemap/* with handle_path /local-basemap/*" >&2
  exit 1
fi

echo "OK: Caddy basemap route contract verified (/local-basemap/* in $CADDYFILE)"
