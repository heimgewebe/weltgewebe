#!/usr/bin/env bash
set -euo pipefail

GUARD_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/guard/prod-public-base-url-guard.sh"
if [ ! -f "$GUARD_SCRIPT" ]; then
    echo "Guard script not found at $GUARD_SCRIPT" >&2
    exit 1
fi

TEST_TMP=$(mktemp -d)
trap 'rm -rf "$TEST_TMP"' EXIT

# Provide a mock REPO_ROOT structure
mkdir -p "$TEST_TMP/infra/compose"
cp "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/infra/compose/compose.prod.yml" "$TEST_TMP/infra/compose/"

# Helper to write override and run guard
run_guard() {
    local exit_code=0
    REPO_ROOT="$TEST_TMP" "$GUARD_SCRIPT" >/dev/null 2>&1 || exit_code=$?
    echo "$exit_code"
}

write_override() {
    local app_base="$1"
    local web_host="$2"
    local web_url="$3"
    cat > "$TEST_TMP/infra/compose/compose.prod.override.yml" <<EOF
services:
  api:
    environment:
      APP_BASE_URL: $app_base
      AUTH_PUBLIC_LOGIN: '1'
      AUTH_LOG_MAGIC_TOKEN: '0'
      WEB_UPSTREAM_HOST: $web_host
      WEB_UPSTREAM_URL: $web_url
EOF
}

echo "Running prod-public-base-url-guard tests..."

# 1. Positiv: aktueller Repo-Zustand besteht
write_override "https://weltgewebe.net" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa"
if [ "$(run_guard)" -ne 0 ]; then
    echo "FAIL: Expected success for correct configuration" >&2
    exit 1
fi

# 2. Negativ: interne APP_BASE_URL schlägt fehl
write_override "https://weltgewebe.home.arpa" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa"
if [ "$(run_guard)" -ne 1 ]; then
    echo "FAIL: Expected exit 1 for internal APP_BASE_URL" >&2
    exit 1
fi

# 3. Negativ: öffentliche WEB_UPSTREAM_URL schlägt fehl
write_override "https://weltgewebe.net" "weltgewebe.home.arpa" "https://weltgewebe.net"
if [ "$(run_guard)" -ne 1 ]; then
    echo "FAIL: Expected exit 1 for public WEB_UPSTREAM_URL" >&2
    exit 1
fi

# 4. Negativ: öffentliche WEB_UPSTREAM_HOST schlägt fehl
write_override "https://weltgewebe.net" "weltgewebe.net" "https://weltgewebe.home.arpa"
if [ "$(run_guard)" -ne 1 ]; then
    echo "FAIL: Expected exit 1 for public WEB_UPSTREAM_HOST" >&2
    exit 1
fi

# 5. Negativ: fehlende Compose-Datei schlägt kontrolliert fehl (Exit 2)
rm "$TEST_TMP/infra/compose/compose.prod.override.yml"
if [ "$(run_guard)" -ne 2 ]; then
    echo "FAIL: Expected exit 2 for missing compose file" >&2
    exit 1
fi

echo "All tests passed."
