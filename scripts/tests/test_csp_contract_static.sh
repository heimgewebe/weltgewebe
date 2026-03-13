#!/usr/bin/env bash
set -euo pipefail

echo "Running tests for csp_contract_static.sh..."

SCRIPT_DIR=$(dirname "$0")
GUARD_SCRIPT="$SCRIPT_DIR/../preflight/csp_contract_static.sh"

TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

mkdir -p "$TEST_DIR/apps/web/build"

export ROOT="$TEST_DIR"
export CADDYFILE_PATH="$TEST_DIR/Caddyfile"
INDEX_HTML="$TEST_DIR/apps/web/build/index.html"

run_test() {
  local name="$1"
  local expected_exit="$2"

  echo "Test: $name"

  set +e
  output=$(bash "$GUARD_SCRIPT" 2>&1)
  exit_code=$?
  set -e

  if [[ "$exit_code" -eq "$expected_exit" ]]; then
    echo "  -> PASS"
  else
    echo "  -> FAIL (expected $expected_exit, got $exit_code)"
    echo "  Output: $output"
    exit 1
  fi
}

# Test 1: REQUIRE_FRONTEND=0 -> pass
export REQUIRE_FRONTEND=0
run_test "REQUIRE_FRONTEND=0 skips check" 0
export REQUIRE_FRONTEND=1

# Test 2: index.html missing when REQUIRE_FRONTEND=1 -> fail
rm -f "$INDEX_HTML"
touch "$CADDYFILE_PATH"
run_test "Missing index.html with REQUIRE_FRONTEND=1 fails check" 1

# Test 3: index.html has only external script, CSP lacks unsafe-inline -> pass
echo '<script type="module" src="/app.js"></script>' > "$INDEX_HTML"
echo 'Content-Security-Policy "default-src '"'self'"'; script-src '"'self'"';"' > "$CADDYFILE_PATH"
run_test "External script only, strict CSP passes" 0

# Test 4: index.html has inline script, CSP lacks unsafe-inline -> fail
echo '<script>console.log("inline")</script>' > "$INDEX_HTML"
echo 'Content-Security-Policy "default-src '"'self'"'; script-src '"'self'"';"' > "$CADDYFILE_PATH"
run_test "Inline script with strict CSP fails" 1

export CADDY_TARGET_SITE="weltgewebe.home.arpa"

# Test 5: index.html has inline script, CSP has unsafe-inline -> pass
echo '<script>console.log("inline")</script>' > "$INDEX_HTML"
echo 'weltgewebe.home.arpa { Content-Security-Policy "default-src '"'self'"'; script-src '"'self'"' '"'unsafe-inline'"';"' > "$CADDYFILE_PATH"
echo '}' >> "$CADDYFILE_PATH"
run_test "Inline script with unsafe-inline CSP passes" 0

# Test 6: index.html has inline script, CSP has nonce -> pass
echo '<script>console.log("inline")</script>' > "$INDEX_HTML"
echo 'weltgewebe.home.arpa { Content-Security-Policy "default-src '"'self'"'; script-src '"'self'"' '"'nonce-1234'"';"' > "$CADDYFILE_PATH"
echo '}' >> "$CADDYFILE_PATH"
run_test "Inline script with nonce CSP passes" 0

# Test 7: Minified HTML with inline script -> fail
echo '<html><head><title>test</title><script>let x=1;</script></head><body></body></html>' > "$INDEX_HTML"
echo 'weltgewebe.home.arpa { Content-Security-Policy "default-src '"'self'"'; script-src '"'self'"';"' > "$CADDYFILE_PATH"
echo '}' >> "$CADDYFILE_PATH"
run_test "Minified HTML with inline script and strict CSP fails" 1

export CADDY_TARGET_SITE="weltgewebe.home.arpa"

# Test 8: Target host strict, other host lenient -> FAIL
echo '<script>console.log("inline")</script>' > "$INDEX_HTML"
cat <<EOF > "$CADDYFILE_PATH"
weltgewebe.home.arpa {
  Content-Security-Policy "default-src 'self'; script-src 'self';"
}
other.host {
  Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline';"
}
EOF
run_test "Target host strict, other host lenient -> FAIL" 1

# Test 9: Target host lenient, other host strict -> PASS
echo '<script>console.log("inline")</script>' > "$INDEX_HTML"
cat <<EOF > "$CADDYFILE_PATH"
other.host {
  Content-Security-Policy "default-src 'self'; script-src 'self';"
}
weltgewebe.home.arpa {
  Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline';"
}
EOF
run_test "Target host lenient, other host strict -> PASS" 0

echo "All tests passed!"
