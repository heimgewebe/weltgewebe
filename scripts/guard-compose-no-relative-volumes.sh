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

# If no relative paths found at all, exit early
if [[ -z "$bad_lines" ]]; then
  echo "OK: no relative host volume paths in $COMPOSE_FILE"
  exit 0
fi

# Determine if this is compose.prod.yml to apply specific allowlist
base="$(basename "$COMPOSE_FILE")"

if [[ "$base" == "compose.prod.yml" ]]; then
  # Allow exactly these repo-relative mounts in compose.prod.yml only:
  # - ../caddy/Caddyfile.prod:/etc/caddy/Caddyfile(:ro)?
  # - ../caddy/heimserver:/etc/caddy/heimserver(:ro)?
  # Pattern matches grep -n output format: line_number:content
  # Note: :ro is optional to allow flexibility in mount options
  allowed_line_re='^[0-9]+:[[:space:]]*-[[:space:]]*(\.\.\/caddy\/Caddyfile\.prod:\/etc\/caddy\/Caddyfile(:ro)?|\.\.\/caddy\/heimserver:\/etc\/caddy\/heimserver(:ro)?)$'
  
  # Filter out allowed patterns
  filtered="$(echo "$bad_lines" | grep -vE "$allowed_line_re" || true)"
else
  # For other compose files, no exceptions - all relative paths are forbidden
  filtered="$bad_lines"
fi

if [[ -n "$filtered" ]]; then
  echo "ERROR: relative host volume paths are forbidden in $COMPOSE_FILE" >&2
  echo >&2
  echo "$filtered" >&2
  echo >&2
  if [[ "$base" == "compose.prod.yml" ]]; then
    echo "Allowed exceptions in compose.prod.yml:" >&2
    echo "  - ../caddy/Caddyfile.prod:/etc/caddy/Caddyfile(:ro)?" >&2
    echo "  - ../caddy/heimserver:/etc/caddy/heimserver(:ro)?" >&2
  fi
  echo "Fix: use absolute host paths, e.g. /opt/weltgewebe/policies:/app/policies:ro" >&2
  exit 1
fi

if [[ "$base" == "compose.prod.yml" ]]; then
  echo "OK: only allowed relative mounts present in $COMPOSE_FILE"
else
  echo "OK: no relative host volume paths in $COMPOSE_FILE"
fi
