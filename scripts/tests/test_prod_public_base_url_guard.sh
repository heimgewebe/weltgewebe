#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(
  cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1
  pwd
)"
GUARD_SCRIPT="${SCRIPT_DIR}/../guard/prod-public-base-url-guard.sh"

if [ ! -f "$GUARD_SCRIPT" ]; then
    echo "Guard script not found at $GUARD_SCRIPT" >&2
    exit 1
fi

TEST_TMP=$(mktemp -d)
trap 'rm -rf "$TEST_TMP"' EXIT

mkdir -p "$TEST_TMP/infra/compose"
cp "${SCRIPT_DIR}/../../infra/compose/compose.prod.yml" "$TEST_TMP/infra/compose/"

run_guard() {
    local caddy_web_host="$1"
    local caddy_web_url="$2"

    local tmp_env="$TEST_TMP/test.env"
    cat > "$tmp_env" <<EOF
DATABASE_URL=postgres://dummy:dummy@localhost:5432/dummy
POSTGRES_USER=dummy
POSTGRES_PASSWORD=dummy
POSTGRES_DB=dummy
WEB_UPSTREAM_HOST=$caddy_web_host
WEB_UPSTREAM_URL=$caddy_web_url
EOF

    local out
    local exit_code=0
    # Provide the env file to the guard through WELTGEWEBE_ENV_FILE but actually we can't easily override the TMP_ENV inside the guard unless we export it or it uses an argument.
    # Wait, the guard creates its own TMP_ENV. We can't override its TMP_ENV directly.
    # Instead, the guard's TMP_ENV has hardcoded values!
    # Ah! The prompt says "Die Fixture muss WEB_UPSTREAM_* dort setzen, wo der reale gerenderte Vertrag sie benötigt ... Caddy-Werte über die synthetische Env beziehungsweise einen gezielten Caddy-Override."
    # Since the guard script hardcodes its TMP_ENV, the test script can't change the Caddy env via the guard's TMP_ENV easily unless we provide an override file for caddy too!

    # We can inject Caddy values via the override file in the test.
    out=$(REPO_ROOT="$TEST_TMP" bash "$GUARD_SCRIPT" 2>&1) || exit_code=$?

    echo "$exit_code"
    echo "$out"
}

write_override() {
    local app_base="$1"
    local web_host="$2"
    local web_url="$3"
    local caddy_web_host="$4"
    local caddy_web_url="$5"
    local auth_login="$6"
    local auth_token="$7"

    cat > "$TEST_TMP/infra/compose/compose.prod.override.yml" <<EOF
services:
  api:
    environment:
      APP_BASE_URL: $app_base
      AUTH_PUBLIC_LOGIN: '$auth_login'
      AUTH_LOG_MAGIC_TOKEN: '$auth_token'
      WEB_UPSTREAM_HOST: $web_host
      WEB_UPSTREAM_URL: $web_url
  caddy:
    environment:
      WEB_UPSTREAM_HOST: $caddy_web_host
      WEB_UPSTREAM_URL: $caddy_web_url
EOF
}

check_result() {
    local name="$1"
    local exit_code="$2"
    local expected_code="$3"
    local output="$4"
    local expected_msg="$5"

    if [ "$exit_code" -ne "$expected_code" ]; then
        echo "FAIL: $name - Expected exit $expected_code, got $exit_code" >&2
        echo "Output was: $output" >&2
        exit 1
    fi
    if [ -n "$expected_msg" ] && [[ "$output" != *"$expected_msg"* ]]; then
        echo "FAIL: $name - Expected message '$expected_msg' not found in output" >&2
        echo "Output was: $output" >&2
        exit 1
    fi
    echo "PASS: $name"
}

echo "Running prod-public-base-url-guard tests..."

# Helper to run and check
run_test() {
    local name="$1"
    local app_base="$2"
    local web_host="$3"
    local web_url="$4"
    local caddy_host="$5"
    local caddy_url="$6"
    local auth_login="${7:-1}"
    local auth_token="${8:-0}"
    local expected_code="$9"
    local expected_msg="${10}"

    write_override "$app_base" "$web_host" "$web_url" "$caddy_host" "$caddy_url" "$auth_login" "$auth_token"

    # We pass the Caddy host/url to run_guard, but right now run_guard uses the override file to set Caddy env.
    local res
    res=$(run_guard "$caddy_host" "$caddy_url")
    local exit_code
    exit_code=$(echo "$res" | head -n1)
    local output
    output=$(echo "$res" | tail -n +2)

    check_result "$name" "$exit_code" "$expected_code" "$output" "$expected_msg"
}

# 1. Positiv
run_test "1. Positiv: gültige Konfiguration" \
    "https://weltgewebe.net" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "1" "0" \
    0 ""

# 2. Negativ: interne APP_BASE_URL
run_test "2. Negativ: interne APP_BASE_URL" \
    "https://weltgewebe.home.arpa" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "1" "0" \
    1 "api.environment.APP_BASE_URL"

# 3. Negativ: öffentliche Caddy-WEB_UPSTREAM_URL
run_test "3. Negativ: öffentliche Caddy-WEB_UPSTREAM_URL" \
    "https://weltgewebe.net" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "weltgewebe.home.arpa" "https://weltgewebe.net" \
    "1" "0" \
    1 "caddy.environment.WEB_UPSTREAM_URL"

# 4. Negativ: öffentlicher Caddy-WEB_UPSTREAM_HOST
run_test "4. Negativ: öffentlicher Caddy-WEB_UPSTREAM_HOST" \
    "https://weltgewebe.net" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "weltgewebe.net" "https://weltgewebe.home.arpa" \
    "1" "0" \
    1 "caddy.environment.WEB_UPSTREAM_HOST"

# 5. Negativ: AUTH_PUBLIC_LOGIN ungleich 1
run_test "5. Negativ: AUTH_PUBLIC_LOGIN ungleich 1" \
    "https://weltgewebe.net" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "0" "0" \
    1 "api.environment.AUTH_PUBLIC_LOGIN"

# 6. Negativ: AUTH_LOG_MAGIC_TOKEN ungleich 0
run_test "6. Negativ: AUTH_LOG_MAGIC_TOKEN ungleich 0" \
    "https://weltgewebe.net" "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "weltgewebe.home.arpa" "https://weltgewebe.home.arpa" \
    "1" "1" \
    1 "api.environment.AUTH_LOG_MAGIC_TOKEN"

# 7. fehlende Basisdatei
rm "$TEST_TMP/infra/compose/compose.prod.yml"
res=$(REPO_ROOT="$TEST_TMP" bash "$GUARD_SCRIPT" 2>&1) || exit_code=$?
check_result "7. Negativ: fehlende Basisdatei" "$exit_code" 2 "$res" "Error: Compose files not found"
cp "${SCRIPT_DIR}/../../infra/compose/compose.prod.yml" "$TEST_TMP/infra/compose/"

# 8. fehlende Override-Datei
rm "$TEST_TMP/infra/compose/compose.prod.override.yml"
res=$(REPO_ROOT="$TEST_TMP" bash "$GUARD_SCRIPT" 2>&1) || exit_code=$?
check_result "8. Negativ: fehlende Override-Datei" "$exit_code" 2 "$res" "Error: Compose files not found"

echo "All tests passed."
