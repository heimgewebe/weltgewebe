#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${1:-infra/compose/compose.prod.yml}"

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: compose file not found: $COMPOSE_FILE" >&2
  exit 2
fi

# Detect relative host volume paths:
#  - ./something:/container
#  - ../something:/container
# Allow:
#  - named volumes (db_data:/var/lib/...)
#  - absolute paths (/opt/...)
bad_lines="$(
  sed 's/[[:space:]]#.*$//' "$COMPOSE_FILE" \
  | grep -nE '^[[:space:]]*-[[:space:]]*(\./|\.\./)[^:]*:[^:]+'
)" || true

# Fast path: no relative mounts at all
if [[ -z "$bad_lines" ]]; then
  echo "OK: no relative host volume paths in $COMPOSE_FILE"
  exit 0
fi

base="$(basename "$COMPOSE_FILE")"

if [[ "$base" == "compose.prod.yml" ]]; then
  # Explicit allowlist for prod only (Caddy mounts)
  # :ro is optional, whitespace tolerated
  allowed_line_re='^[0-9]+:[[:space:]]*-[[:space:]]*(\.\.\/caddy\/Caddyfile\.prod:\/etc\/caddy\/Caddyfile(:ro)?|\.\.\/caddy\/heimserver:\/etc\/caddy\/heimserver(:ro)?)[[:space:]]*$'
  filtered="$(echo "$bad_lines" | grep -vE "$allowed_line_re" || true)"
else
  # No allowlist for non-prod compose files
  filtered="$bad_lines"
fi

if [[ -n "$filtered" ]]; then
  echo "ERROR: relative host volume paths are forbidden in $COMPOSE_FILE" >&2
  echo >&2
  echo "$filtered" >&2
  echo >&2

  if [[ "$base" == "compose.prod.yml" ]]; then
    echo "Allowed exceptions in compose.prod.yml:" >&2
    echo "  - ../caddy/Caddyfile.prod:/etc/caddy/Caddyfile[:ro]" >&2
    echo "  - ../caddy/heimserver:/etc/caddy/heimserver[:ro]" >&2
    echo >&2
  fi

  echo "Fix: use absolute host paths, e.g. /opt/weltgewebe/policies:/app/policies:ro" >&2
  exit 1
fi

# Only allowed exceptions present
echo "OK: only allowed relative mounts present in $COMPOSE_FILE"