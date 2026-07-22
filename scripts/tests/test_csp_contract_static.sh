#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR=$(dirname "$0")
GUARD_SCRIPT="$SCRIPT_DIR/../preflight/csp_contract_static.sh"
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT
mkdir -p "$TEST_DIR/apps/web/build"
export ROOT="$TEST_DIR"
export CADDYFILE_PATH="$TEST_DIR/Caddyfile"
INDEX_HTML="$TEST_DIR/apps/web/build/index.html"

run_test() {
  local name="$1" expected_exit="$2"
  set +e
  output=$(bash "$GUARD_SCRIPT" 2>&1)
  actual=$?
  set -e
  if [[ "$actual" -ne "$expected_exit" ]]; then
    echo "FAIL: $name (expected $expected_exit, got $actual)" >&2
    echo "$output" >&2
    exit 1
  fi
  echo "PASS: $name"
}

export REQUIRE_FRONTEND=0
run_test "frontend-disabled" 0
export REQUIRE_FRONTEND=1
printf '%s\n' 'header { Content-Security-Policy "frame-ancestors '\''none'\'';" }' > "$CADDYFILE_PATH"
rm -f "$INDEX_HTML"
run_test "missing-index" 1

printf '%s\n' '<meta http-equiv="content-security-policy" content="script-src '\''self'\''"><script src="/app.js"></script>' > "$INDEX_HTML"
run_test "external-script-strict" 0

printf '%s\n' '<meta http-equiv="content-security-policy" content="script-src '\''self'\''"><script>console.log("inline")</script>' > "$INDEX_HTML"
run_test "inline-without-hash" 1

hash=$(python3 - <<'PY'
import base64, hashlib
body='console.log("inline")'
print(base64.b64encode(hashlib.sha256(body.encode()).digest()).decode())
PY
)
printf '%s\n' "<meta http-equiv=\"content-security-policy\" content=\"script-src 'self' 'sha256-$hash'\"><script>console.log(\"inline\")</script>" > "$INDEX_HTML"
run_test "inline-with-matching-hash" 0

printf '%s\n' '<meta http-equiv="content-security-policy" content="script-src '\''self'\'' '\''unsafe-inline'\''"><script>console.log("inline")</script>' > "$INDEX_HTML"
run_test "inline-unsafe-inline-rejected" 1

printf '%s\n' 'header { Content-Security-Policy "script-src '\''self'\'' '\''unsafe-inline'\'';" }' > "$CADDYFILE_PATH"
run_test "edge-unsafe-inline-rejected" 1

echo "All csp_contract_static tests passed"
