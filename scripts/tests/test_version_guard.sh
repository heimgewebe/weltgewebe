#!/usr/bin/env bash
# Tests the inline Python version-guard block extracted from scripts/weltgewebe-up.
# Covers: valid JSON, missing 'version', invalid JSON.
set -euo pipefail

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

run_guard() {
  local json="$1"
  local tmpfile
  tmpfile=$(mktemp)
  printf '%s' "$json" > "$tmpfile"

  local out rc
  set +e
  out=$(python3 -c '
import sys, json
try:
    with open(sys.argv[1], "r") as f:
        data = json.load(f)
        v = data.get("version")
        if not isinstance(v, str) or not v.strip():
            sys.exit(2)
        print(v)
        print(data.get("build_id", ""))
except json.JSONDecodeError:
    sys.exit(3)
except Exception:
    sys.exit(1)
' "$tmpfile" 2>/dev/null)
  rc=$?
  set -e

  rm -f "$tmpfile"
  echo "$rc|$out"
}

# --- Test 1: valid JSON with version and build_id ---
result=$(run_guard '{"version":"1.2.3","build_id":"abc42"}')
rc="${result%%|*}"
output="${result#*|}"
[[ "$rc" == "0" ]] || fail "Test 1: expected exit 0, got $rc"
[[ "$output" == *"1.2.3"* ]] || fail "Test 1: version not in output"
[[ "$output" == *"abc42"* ]] || fail "Test 1: build_id not in output"
echo "PASS: valid JSON with version and build_id accepted"

# --- Test 2: valid JSON with version only (no build_id) ---
result=$(run_guard '{"version":"0.9.0"}')
rc="${result%%|*}"
output="${result#*|}"
[[ "$rc" == "0" ]] || fail "Test 2: expected exit 0, got $rc"
[[ "$output" == *"0.9.0"* ]] || fail "Test 2: version not in output"
echo "PASS: valid JSON without build_id accepted"

# --- Test 3: valid JSON missing 'version' field ---
result=$(run_guard '{"build_id":"abc"}')
rc="${result%%|*}"
[[ "$rc" == "2" ]] || fail "Test 3: expected exit 2 (missing version), got $rc"
echo "PASS: missing 'version' field rejected with exit 2"

# --- Test 4: valid JSON with empty version string ---
result=$(run_guard '{"version":"  "}')
rc="${result%%|*}"
[[ "$rc" == "2" ]] || fail "Test 4: expected exit 2 (blank version), got $rc"
echo "PASS: blank 'version' string rejected with exit 2"

# --- Test 5: invalid JSON ---
result=$(run_guard 'not json at all')
rc="${result%%|*}"
[[ "$rc" == "3" ]] || fail "Test 5: expected exit 3 (invalid JSON), got $rc"
echo "PASS: invalid JSON rejected with exit 3"

# --- Test 6: bash syntax check of the deploy script ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/../weltgewebe-up"
bash -n "$DEPLOY_SCRIPT" || fail "bash -n failed on scripts/weltgewebe-up"
echo "PASS: bash -n scripts/weltgewebe-up OK"

echo
echo "All version-guard tests passed."
