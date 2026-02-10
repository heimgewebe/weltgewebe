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

if [[ -n "$bad_lines" ]]; then
  # Allow known legitimate relative mounts ONLY in compose.prod.yml
  # These are explicitly allowed Caddy configuration mounts
  base="$(basename "$COMPOSE_FILE")"
  
  if [[ "$base" == "compose.prod.yml" ]]; then
    allowed_line_re='^[0-9]+:[[:space:]]*-[[:space:]]*(\.\.\/caddy\/Caddyfile\.prod:\/etc\/caddy\/Caddyfile(:ro)?|\.\.\/caddy\/heimserver:\/etc\/caddy\/heimserver(:ro)?)$'
    filtered="$(echo "$bad_lines" | grep -vE "$allowed_line_re" || true)"
  else
    # No allowlist for other compose files
    filtered="$bad_lines"
  fi
  
  if [[ -n "$filtered" ]]; then
    echo "ERROR: relative host volume paths are forbidden in $COMPOSE_FILE" >&2
    echo >&2
    echo "$filtered" >&2
    echo >&2
    if [[ "$base" == "compose.prod.yml" ]]; then
      echo "Allowed exceptions in compose.prod.yml (not shown above):" >&2
      echo "  - ../caddy/Caddyfile.prod:/etc/caddy/Caddyfile:ro" >&2
      echo "  - ../caddy/heimserver:/etc/caddy/heimserver:ro" >&2
      echo >&2
    fi
    echo "Fix: use absolute host paths, e.g. /opt/weltgewebe/policies:/app/policies:ro" >&2
    exit 1
  else
    # All bad_lines were filtered out = only allowed exceptions present
    echo "OK: only allowed exceptions present in $COMPOSE_FILE"
    exit 0
  fi
fi

echo "OK: no relative host volume paths in $COMPOSE_FILE"
