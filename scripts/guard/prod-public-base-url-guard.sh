#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)"
REPO_ROOT="${REPO_ROOT:-$(
  cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1
  pwd
)}"

TMP_ENV="$(mktemp)"
TMP_JSON="$(mktemp)"
TMP_ERR="$(mktemp)"

cleanup() {
  rm -f "$TMP_ENV" "$TMP_JSON" "$TMP_ERR"
}
trap cleanup EXIT

cat > "$TMP_ENV" << 'EOF'
DATABASE_URL=postgres://dummy:dummy@localhost:5432/dummy
POSTGRES_USER=dummy
POSTGRES_PASSWORD=dummy
POSTGRES_DB=dummy
WEB_UPSTREAM_HOST=weltgewebe.home.arpa
WEB_UPSTREAM_URL=https://weltgewebe.home.arpa
EOF

if [ ! -f "$REPO_ROOT/infra/compose/compose.prod.yml" ] || [ ! -f "$REPO_ROOT/infra/compose/compose.prod.override.yml" ]; then
  echo "Error: Compose files not found at $REPO_ROOT/infra/compose/" >&2
  exit 2
fi

# Compose render explicitly with the expected override
if ! WELTGEWEBE_ENV_FILE="$TMP_ENV" \
  REPO_DIR="$REPO_ROOT" \
  docker compose \
    --env-file "$TMP_ENV" \
    -f "$REPO_ROOT/infra/compose/compose.prod.yml" \
    -f "$REPO_ROOT/infra/compose/compose.prod.override.yml" \
    config --format json >"$TMP_JSON" 2>"$TMP_ERR"
then
  echo "ERROR: docker compose config failed" >&2
  cat "$TMP_ERR" >&2
  exit 2
fi

# Use Python to evaluate the JSON configuration
python3 -c '
import sys, json

try:
    with open(sys.argv[1], "r") as f:
        config = json.load(f)
except Exception as e:
    print(f"Error parsing compose config JSON: {e}", file=sys.stderr)
    sys.exit(2)

services = config.get("services", {})
api_env = services.get("api", {}).get("environment", {})
caddy_env = services.get("caddy", {}).get("environment", {})

errors = []

# Check api_env
if api_env.get("APP_BASE_URL") != "https://weltgewebe.net":
    val = api_env.get("APP_BASE_URL")
    errors.append(f"api.environment.APP_BASE_URL expected https://weltgewebe.net, got {val}")

if api_env.get("AUTH_PUBLIC_LOGIN") != "1":
    val = api_env.get("AUTH_PUBLIC_LOGIN")
    errors.append(f"api.environment.AUTH_PUBLIC_LOGIN expected 1, got {val}")

if api_env.get("AUTH_LOG_MAGIC_TOKEN") != "0":
    val = api_env.get("AUTH_LOG_MAGIC_TOKEN")
    errors.append(f"api.environment.AUTH_LOG_MAGIC_TOKEN expected 0, got {val}")

if api_env.get("WEB_UPSTREAM_HOST") != "weltgewebe.home.arpa":
    val = api_env.get("WEB_UPSTREAM_HOST")
    errors.append(f"api.environment.WEB_UPSTREAM_HOST expected weltgewebe.home.arpa, got {val}")

if api_env.get("WEB_UPSTREAM_URL") != "https://weltgewebe.home.arpa":
    val = api_env.get("WEB_UPSTREAM_URL")
    errors.append(f"api.environment.WEB_UPSTREAM_URL expected https://weltgewebe.home.arpa, got {val}")

# Check caddy_env
if caddy_env.get("WEB_UPSTREAM_HOST") != "weltgewebe.home.arpa":
    val = caddy_env.get("WEB_UPSTREAM_HOST")
    errors.append(f"caddy.environment.WEB_UPSTREAM_HOST expected weltgewebe.home.arpa, got {val}")

if caddy_env.get("WEB_UPSTREAM_URL") != "https://weltgewebe.home.arpa":
    val = caddy_env.get("WEB_UPSTREAM_URL")
    errors.append(f"caddy.environment.WEB_UPSTREAM_URL expected https://weltgewebe.home.arpa, got {val}")

if errors:
    for err in errors:
        print(err, file=sys.stderr)
    sys.exit(1)

print("prod-public-base-url guard passed")
sys.exit(0)
' "$TMP_JSON"
