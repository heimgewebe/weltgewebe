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

BASE_FILE="${REPO_ROOT}/infra/compose/compose.prod.yml"
OVERRIDE_FILE="${REPO_ROOT}/infra/compose/compose.prod.override.yml"

for required_file in "$BASE_FILE" "$OVERRIDE_FILE"; do
  if [[ ! -f "$required_file" ]]; then
    echo "ERROR: required Compose file missing: $required_file" >&2
    exit 2
  fi
done

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose is required" >&2
  exit 2
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required" >&2
  exit 2
fi

TMP_ENV="$(mktemp)"
TMP_JSON="$(mktemp)"
TMP_ERR="$(mktemp)"

cleanup() {
  rm -f "$TMP_ENV" "$TMP_JSON" "$TMP_ERR"
}
trap cleanup EXIT

cat >"$TMP_ENV" <<'EOF_ENV'
DATABASE_URL=postgres://dummy:dummy@localhost:5432/dummy
POSTGRES_USER=dummy
POSTGRES_PASSWORD=dummy
POSTGRES_DB=dummy
WEB_UPSTREAM_HOST=weltgewebe.home.arpa
WEB_UPSTREAM_URL=https://weltgewebe.home.arpa
EOF_ENV

if ! WELTGEWEBE_ENV_FILE="$TMP_ENV" \
  REPO_DIR="$REPO_ROOT" \
  docker compose \
    --env-file "$TMP_ENV" \
    -f "$BASE_FILE" \
    -f "$OVERRIDE_FILE" \
    config --format json >"$TMP_JSON" 2>"$TMP_ERR"
then
  echo "ERROR: docker compose config failed" >&2
  cat "$TMP_ERR" >&2
  exit 2
fi

python3 - "$TMP_JSON" <<'PY'
import json
import sys
from pathlib import Path
from typing import Any


def fail_structural(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(2)


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail_structural(f"{label} must be a mapping")
    return value


try:
    config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    fail_structural(f"cannot parse Compose JSON: {exc}")

config_map = require_mapping(config, "Compose root")
services = require_mapping(config_map.get("services"), "services")
api = require_mapping(services.get("api"), "services.api")
caddy = require_mapping(services.get("caddy"), "services.caddy")
api_env = require_mapping(api.get("environment"), "services.api.environment")
caddy_env = require_mapping(caddy.get("environment"), "services.caddy.environment")

expected = {
    "services.api.environment.APP_BASE_URL": (
        api_env.get("APP_BASE_URL"),
        "https://weltgewebe.net",
    ),
    "services.api.environment.AUTH_PUBLIC_LOGIN": (
        api_env.get("AUTH_PUBLIC_LOGIN"),
        "1",
    ),
    "services.api.environment.AUTH_LOG_MAGIC_TOKEN": (
        api_env.get("AUTH_LOG_MAGIC_TOKEN"),
        "0",
    ),
    "services.api.environment.WEB_UPSTREAM_HOST": (
        api_env.get("WEB_UPSTREAM_HOST"),
        "weltgewebe.home.arpa",
    ),
    "services.api.environment.WEB_UPSTREAM_URL": (
        api_env.get("WEB_UPSTREAM_URL"),
        "https://weltgewebe.home.arpa",
    ),
    "services.caddy.environment.WEB_UPSTREAM_HOST": (
        caddy_env.get("WEB_UPSTREAM_HOST"),
        "weltgewebe.home.arpa",
    ),
    "services.caddy.environment.WEB_UPSTREAM_URL": (
        caddy_env.get("WEB_UPSTREAM_URL"),
        "https://weltgewebe.home.arpa",
    ),
}

errors = [
    f"{label} expected {wanted!r}, got {actual!r}"
    for label, (actual, wanted) in expected.items()
    if actual != wanted
]

if errors:
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    raise SystemExit(1)

print("prod-public-base-url guard passed")
PY
