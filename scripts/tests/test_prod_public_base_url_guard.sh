#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)"
REPO_ROOT="$(
  cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1
  pwd
)"
GUARD_SCRIPT="${REPO_ROOT}/scripts/guard/prod-public-base-url-guard.sh"
BASE_SOURCE="${REPO_ROOT}/infra/compose/compose.prod.yml"

for required_file in "$GUARD_SCRIPT" "$BASE_SOURCE"; do
  if [[ ! -f "$required_file" ]]; then
    echo "ERROR: required test input missing: $required_file" >&2
    exit 2
  fi
done

TEST_TMP="$(mktemp -d)"
LAST_EXIT=0
LAST_OUTPUT=""

cleanup() {
  rm -rf "$TEST_TMP"
}
trap cleanup EXIT

mkdir -p "$TEST_TMP/infra/compose"
cp "$BASE_SOURCE" "$TEST_TMP/infra/compose/compose.prod.yml"

write_override() {
  local app_base="$1"
  local api_web_host="$2"
  local api_web_url="$3"
  local caddy_web_host="$4"
  local caddy_web_url="$5"
  local auth_login="$6"
  local auth_token="$7"

  cat >"$TEST_TMP/infra/compose/compose.prod.override.yml" <<EOF_OVERRIDE
services:
  api:
    environment:
      APP_BASE_URL: $app_base
      AUTH_PUBLIC_LOGIN: '$auth_login'
      AUTH_LOG_MAGIC_TOKEN: '$auth_token'
      WEB_UPSTREAM_HOST: $api_web_host
      WEB_UPSTREAM_URL: $api_web_url
  caddy:
    environment:
      WEB_UPSTREAM_HOST: $caddy_web_host
      WEB_UPSTREAM_URL: $caddy_web_url
EOF_OVERRIDE
}

run_guard() {
  LAST_EXIT=0
  LAST_OUTPUT="$(REPO_ROOT="$TEST_TMP" bash "$GUARD_SCRIPT" 2>&1)" || LAST_EXIT=$?
}

assert_result() {
  local name="$1"
  local expected_exit="$2"
  local expected_fragment="$3"

  if [[ "$LAST_EXIT" -ne "$expected_exit" ]]; then
    echo "FAIL: $name: expected exit $expected_exit, got $LAST_EXIT" >&2
    echo "$LAST_OUTPUT" >&2
    exit 1
  fi

  if [[ -n "$expected_fragment" && "$LAST_OUTPUT" != *"$expected_fragment"* ]]; then
    echo "FAIL: $name: expected output fragment '$expected_fragment'" >&2
    echo "$LAST_OUTPUT" >&2
    exit 1
  fi

  echo "PASS: $name"
}

run_case() {
  local name="$1"
  local app_base="$2"
  local api_web_host="$3"
  local api_web_url="$4"
  local caddy_web_host="$5"
  local caddy_web_url="$6"
  local auth_login="$7"
  local auth_token="$8"
  local expected_exit="$9"
  local expected_fragment="${10}"

  write_override \
    "$app_base" \
    "$api_web_host" \
    "$api_web_url" \
    "$caddy_web_host" \
    "$caddy_web_url" \
    "$auth_login" \
    "$auth_token"
  run_guard
  assert_result "$name" "$expected_exit" "$expected_fragment"
}

echo "Running prod-public-base-url guard tests..."

run_case \
  "valid production contract" \
  "https://weltgewebe.net" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "1" "0" \
  0 "prod-public-base-url guard passed"

run_case \
  "internal APP_BASE_URL is rejected" \
  "https://weltgewebe.home.arpa" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "1" "0" \
  1 "services.api.environment.APP_BASE_URL"

run_case \
  "public API WEB_UPSTREAM_URL is rejected" \
  "https://weltgewebe.net" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.net" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "1" "0" \
  1 "services.api.environment.WEB_UPSTREAM_URL"

run_case \
  "public Caddy WEB_UPSTREAM_HOST is rejected" \
  "https://weltgewebe.net" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "weltgewebe.net" \
  "https://weltgewebe.home.arpa" \
  "1" "0" \
  1 "services.caddy.environment.WEB_UPSTREAM_HOST"

run_case \
  "public Caddy WEB_UPSTREAM_URL is rejected" \
  "https://weltgewebe.net" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.net" \
  "1" "0" \
  1 "services.caddy.environment.WEB_UPSTREAM_URL"

run_case \
  "disabled public login is rejected" \
  "https://weltgewebe.net" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "0" "0" \
  1 "services.api.environment.AUTH_PUBLIC_LOGIN"

run_case \
  "magic-token logging is rejected" \
  "https://weltgewebe.net" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "weltgewebe.home.arpa" \
  "https://weltgewebe.home.arpa" \
  "1" "1" \
  1 "services.api.environment.AUTH_LOG_MAGIC_TOKEN"

rm "$TEST_TMP/infra/compose/compose.prod.yml"
run_guard
assert_result \
  "missing base Compose file is an execution error" \
  2 \
  "required Compose file missing: $TEST_TMP/infra/compose/compose.prod.yml"
cp "$BASE_SOURCE" "$TEST_TMP/infra/compose/compose.prod.yml"

rm "$TEST_TMP/infra/compose/compose.prod.override.yml"
run_guard
assert_result \
  "missing override Compose file is an execution error" \
  2 \
  "required Compose file missing: $TEST_TMP/infra/compose/compose.prod.override.yml"

echo "All prod-public-base-url guard tests passed."
