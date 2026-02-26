#!/usr/bin/env bash
set -euo pipefail

# This test verifies that scripts/guard_api_alias.sh does not overwrite
# an existing EXIT trap in the calling shell (or sourced context).

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT_TO_TEST="$REPO_ROOT/scripts/guard_api_alias.sh"
TEMP_DIR="$(mktemp -d)"
# Cleanup the temp dir for the test itself
trap 'rm -rf "$TEMP_DIR"' EXIT

echo "Running test in $TEMP_DIR"

# Mock docker to ensure the script proceeds to trap setup
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
  # Return a minimal valid config so the script doesn't error out early (though error is fine too, trap runs on exit)
  echo "services:
  api:
    networks:
      default:
        aliases:
          - weltgewebe-api"
  exit 0
fi
exit 0
EOF
chmod +x "$TEMP_DIR/bin/docker"

# Prepend mock bin to PATH
export PATH="$TEMP_DIR/bin:$PATH"

OUTPUT_FILE="$TEMP_DIR/output.txt"

# Run the guard script in a subshell with a pre-existing EXIT trap
(
  trap 'echo "OUTER_TRAP_EXECUTED"' EXIT
  # Source the script so it runs in this shell context
  # use || true to prevent failure of the test script if the guard exits 1
  . "$SCRIPT_TO_TEST" || true
) > "$OUTPUT_FILE" 2>&1

echo "--- Script Output ---"
cat "$OUTPUT_FILE"
echo "---------------------"

if grep -q "OUTER_TRAP_EXECUTED" "$OUTPUT_FILE"; then
  echo "PASS: Outer trap was executed."
else
  echo "FAIL: Outer trap was NOT executed."
  exit 1
fi
