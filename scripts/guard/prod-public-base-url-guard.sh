#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${REPO_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

TMP_ENV=$(mktemp)
trap 'rm -f "$TMP_ENV"' EXIT

cat > "$TMP_ENV" << 'EOF'
DATABASE_URL=postgres://dummy:dummy@localhost:5432/dummy
POSTGRES_USER=dummy
POSTGRES_PASSWORD=dummy
POSTGRES_DB=dummy
WEB_UPSTREAM_HOST=weltgewebe.home.arpa
WEB_UPSTREAM_URL=https://weltgewebe.home.arpa
EOF

if [ ! -f "$REPO_ROOT/infra/compose/compose.prod.yml" ] || [ ! -f "$REPO_ROOT/infra/compose/compose.prod.override.yml" ]; then
  echo "Error: Compose files not found" >&2
  exit 2
fi

# Compose render explicitly with the expected override
COMPOSE_OUTPUT=$(
  WELTGEWEBE_ENV_FILE="$TMP_ENV" \
  REPO_DIR="$REPO_ROOT" \
  docker compose \
    --env-file "$TMP_ENV" \
    -f "$REPO_ROOT/infra/compose/compose.prod.yml" \
    -f "$REPO_ROOT/infra/compose/compose.prod.override.yml" \
    config --format json 2>/dev/null
) || {
  echo "Error: docker compose config failed" >&2
  exit 2
}

# Use Python to evaluate the JSON configuration
python3 -c '
import sys, json

try:
    config = json.load(sys.stdin)
except Exception as e:
    print(f"Error parsing compose config JSON: {e}", file=sys.stderr)
    sys.exit(1)

api_service = config.get("services", {}).get("api", {})
env = api_service.get("environment", {})

app_base_url = env.get("APP_BASE_URL")
auth_public_login = env.get("AUTH_PUBLIC_LOGIN")
auth_log_magic_token = env.get("AUTH_LOG_MAGIC_TOKEN")
web_upstream_host = env.get("WEB_UPSTREAM_HOST")
web_upstream_url = env.get("WEB_UPSTREAM_URL")

errors = []

if app_base_url != "https://weltgewebe.net":
    errors.append(f"APP_BASE_URL expected https://weltgewebe.net, got {app_base_url}")

if auth_public_login != "1":
    errors.append(f"AUTH_PUBLIC_LOGIN expected 1, got {auth_public_login}")

if auth_log_magic_token != "0":
    errors.append(f"AUTH_LOG_MAGIC_TOKEN expected 0, got {auth_log_magic_token}")

if web_upstream_host != "weltgewebe.home.arpa":
    errors.append(f"WEB_UPSTREAM_HOST expected weltgewebe.home.arpa, got {web_upstream_host}")

if web_upstream_url != "https://weltgewebe.home.arpa":
    errors.append(f"WEB_UPSTREAM_URL expected https://weltgewebe.home.arpa, got {web_upstream_url}")

if errors:
    for err in errors:
        print(err, file=sys.stderr)
    sys.exit(1)

print("prod-public-base-url guard passed")
sys.exit(0)
' <<< "$COMPOSE_OUTPUT"
