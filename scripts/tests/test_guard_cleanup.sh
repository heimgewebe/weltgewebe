#!/usr/bin/env bash
set -euo pipefail

# This test verifies that scripts/guard_api_alias.sh cleans up its
# temporary stderr file properly, without needing to manipulate traps.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_TO_TEST="$REPO_ROOT/scripts/guard_api_alias.sh"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Running test in $TEMP_DIR"

# Mock docker
mkdir -p "$TEMP_DIR/bin"
cat > "$TEMP_DIR/bin/docker" <<EOF
#!/bin/sh
# Mock 'docker compose version'
if [ "\$1" = "compose" ] && [ "\$2" = "version" ]; then
  echo "Docker Compose version v2.20.2"
  exit 0
fi
# Mock 'docker compose config'
if [ "\$1" = "compose" ] && echo "\$@" | grep -q "config"; then
  # Simulate config output.
  # We test two scenarios:
  # 1. Success (valid config)
  # 2. Failure (empty output + stderr)

  if [ -f "$TEMP_DIR/FAIL_CONFIG" ]; then
     echo "Simulated config error" >&2
     exit 1
  else
     echo "services:
  api:
    networks:
      default:
        aliases:
          - weltgewebe-api"
     exit 0
  fi
fi
exit 0
EOF
chmod +x "$TEMP_DIR/bin/docker"

# Prepend mock bin to PATH
export PATH="$TEMP_DIR/bin:$PATH"

# Override TMPDIR so mktemp creates files in our monitored directory
export TMPDIR="$TEMP_DIR"

echo ">>> Test 1: Successful config rendering (should cleanup)"
"$SCRIPT_TO_TEST" >/dev/null

# Check for leaked files (pattern guard_api_alias.* or tmp.* depending on mktemp)
# Since we control TMPDIR, any file created there by mktemp should be gone.
# We ignore the bin directory and FAIL_CONFIG marker.
# Note: Parentheses are escaped for shell safety and grouping the OR condition.
LEAK_COUNT=$(find "$TEMP_DIR" -maxdepth 1 -type f \( -name "tmp.*" -o -name "guard_api_alias.*" \) | wc -l)

if [[ "$LEAK_COUNT" -ne 0 ]]; then
  echo "FAIL: Temporary files leaked after success run."
  ls -l "$TEMP_DIR"
  exit 1
else
  echo "PASS: No leaks after success run."
fi

echo ">>> Test 2: Failed config rendering (should cleanup)"
touch "$TEMP_DIR/FAIL_CONFIG"
# Script should exit 1, so we allow failure
"$SCRIPT_TO_TEST" >/dev/null 2>&1 || true

LEAK_COUNT=$(find "$TEMP_DIR" -maxdepth 1 -type f \( -name "tmp.*" -o -name "guard_api_alias.*" \) | wc -l)

if [[ "$LEAK_COUNT" -ne 0 ]]; then
  echo "FAIL: Temporary files leaked after failure run."
  ls -l "$TEMP_DIR"
  exit 1
else
  echo "PASS: No leaks after failure run."
fi
