#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${1:-infra/compose/compose.prod.yml}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: compose file not found: $COMPOSE_FILE" >&2
  exit 2
fi

# Fail patterns:
# - "./something:/container"
# - "../something:/container"
# Allow named volumes like "db_data:/var/lib/..."
# Also allow absolute paths "/opt/..."
bad_lines="$(
  # strip comments, then grep for suspicious relative host paths in volume mappings
  sed 's/[[:space:]]#.*$//' "$COMPOSE_FILE" \
  | grep -nE '^[[:space:]]*-[[:space:]]*(\./|\.\./)[^:]*:[^:]+'
)" || true

# Allowlist for legitimate relative mounts (repo-relative Caddy config)
# These are intentional and safe in the deployment context
allowed_re='(\.\./caddy/Caddyfile\.prod:|\.\./caddy/heimserver:)'

# Filter out allowed patterns
filtered="$(echo "$bad_lines" | grep -vE "$allowed_re" || true)"

if [[ -n "$filtered" ]]; then
  echo "ERROR: relative host volume paths are forbidden in $COMPOSE_FILE" >&2
  echo >&2
  echo "$filtered" >&2
  echo >&2
  echo "Allowed exceptions: ../caddy/Caddyfile.prod, ../caddy/heimserver" >&2
  echo "Fix: use absolute host paths, e.g. /opt/weltgewebe/policies:/app/policies:ro" >&2
  exit 1
fi

echo "OK: no relative host volume paths in $COMPOSE_FILE"
