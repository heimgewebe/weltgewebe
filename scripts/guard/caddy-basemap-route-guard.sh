#!/usr/bin/env bash
set -euo pipefail

# Guard: Caddy basemap route contract
#
# Verifies that all production-relevant Caddy configs in the repo serve the
# sovereign basemap under the canonical public edge path /local-basemap/, and
# that the old /basemap/* route (which caused the contract drift) is absent.
#
# The contract is shared by:
#   - the frontend (basemap.ts, basemap.current.ts)
#   - the Vite dev-server middleware (vite.config.ts)
#   - the blueprint (docs/blueprints/map-blaupause.md §7)
#
# Checked configs:
#   - infra/caddy/Caddyfile       (canonical repo-side contract file)
#   - infra/caddy/Caddyfile.heim  (compose.prod.yml — primary production file)
#
# Not checked:
#   - infra/caddy/Caddyfile.dev   (dev-only; compose.core.yml mounts this file,
#                                   but /local-basemap/ is served by Vite middleware
#                                   in dev, not by Caddy)
#   - infra/caddy/Caddyfile.prod  (VPS proxy to external web upstream; no basemap route)
#   - docs/reference/caddy.heimserver.caddy  (reference only, not deployed from repo)
#
# Regression protection: prevents silent re-introduction of the old /basemap/*
# route, which caused the sovereign hosting path to be factually inactive.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)}"

FAILED=0

check_caddyfile() {
  local file="$1"

  if [[ ! -f "$file" ]]; then
    echo "ERROR: Caddyfile not found: $file" >&2
    FAILED=1
    return
  fi

  # Check that the canonical /local-basemap/* route is present
  if ! grep -qE '^[[:space:]]*handle_path /local-basemap/\*' "$file"; then
    echo "ERROR: Caddy basemap route contract violated in $file" >&2
    echo "  Expected:  handle_path /local-basemap/*" >&2
    echo "  Not found. The sovereign basemap hosting path would be inactive." >&2
    echo "  The public edge contract is /local-basemap/ (frontend + blueprint)." >&2
    FAILED=1
  fi

  # Check that the old conflicting /basemap/* route is NOT present
  if grep -qE '^[[:space:]]*handle_path /basemap/\*' "$file"; then
    echo "ERROR: Caddy basemap route drift in $file" >&2
    echo "  Found:    handle_path /basemap/*" >&2
    echo "  Conflict: frontend requests /local-basemap/, Caddy serves /basemap/*." >&2
    echo "  Remove handle_path /basemap/* and ensure handle_path /local-basemap/* is present." >&2
    FAILED=1
  fi
}

check_caddyfile "${REPO_ROOT}/infra/caddy/Caddyfile"
check_caddyfile "${REPO_ROOT}/infra/caddy/Caddyfile.heim"

if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi

echo "OK: Caddy basemap route contract verified (/local-basemap/*) in all production-relevant configs"
