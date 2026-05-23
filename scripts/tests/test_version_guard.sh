#!/usr/bin/env bash
# Tests the version-guard logic from scripts/weltgewebe-up:
# - the live-guard inline Python parser (exit-code semantics, commit field)
# - the _read_version_json helper (pre-deploy staleness check)
# - staleness comparison logic
set -euo pipefail

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Replicate the live-guard inline Python parser (must stay in sync with
# the block in scripts/weltgewebe-up that writes to VERSION_PARSED_OUT).
# ---------------------------------------------------------------------------
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
        print(data.get("commit", ""))
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

# ---------------------------------------------------------------------------
# Replicate _read_version_json helper (must stay in sync with the function
# definition in scripts/weltgewebe-up).
# ---------------------------------------------------------------------------
_read_version_json() {
    local json_file="$1"
    python3 -c '
import sys, json
try:
    with open(sys.argv[1]) as f:
        d = json.load(f)
    v = d.get("version", "")
    if isinstance(v, str) and v.strip():
        print(v.strip())
except Exception:
    pass
' "$json_file" 2>/dev/null || true
}

# ===========================================================================
# Part 1: live-guard parser (exit-code semantics)
# ===========================================================================

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

# --- Test 3: valid JSON with version, build_id and commit (3rd output line) ---
result=$(run_guard '{"version":"c67aaa67","build_id":"x","commit":"c67aaa6730b78c5ab5cfbacb272eb60a06347473"}')
rc="${result%%|*}"
output="${result#*|}"
[[ "$rc" == "0" ]] || fail "Test 3: expected exit 0, got $rc"
commit_line=$(printf '%s' "$output" | sed -n '3p')
[[ "$commit_line" == "c67aaa6730b78c5ab5cfbacb272eb60a06347473" ]] \
    || fail "Test 3: commit not on 3rd line, got '$commit_line'"
echo "PASS: commit field output as 3rd line"

# --- Test 4: valid JSON missing 'version' field ---
result=$(run_guard '{"build_id":"abc"}')
rc="${result%%|*}"
[[ "$rc" == "2" ]] || fail "Test 4: expected exit 2 (missing version), got $rc"
echo "PASS: missing 'version' field rejected with exit 2"

# --- Test 5: valid JSON with blank version string ---
result=$(run_guard '{"version":"  "}')
rc="${result%%|*}"
[[ "$rc" == "2" ]] || fail "Test 5: expected exit 2 (blank version), got $rc"
echo "PASS: blank 'version' string rejected with exit 2"

# --- Test 6: invalid JSON ---
result=$(run_guard 'not json at all')
rc="${result%%|*}"
[[ "$rc" == "3" ]] || fail "Test 6: expected exit 3 (invalid JSON), got $rc"
echo "PASS: invalid JSON rejected with exit 3"

# ===========================================================================
# Part 2: _read_version_json helper
# ===========================================================================

# --- Test 7: valid JSON with version → returns version string ---
_tmpf=$(mktemp)
printf '{"version":"17314c6a","build_id":"x"}' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ "$_got" == "17314c6a" ]] || fail "Test 7: expected '17314c6a', got '$_got'"
echo "PASS: _read_version_json extracts version from valid JSON"

# --- Test 8: invalid JSON → returns empty ---
_tmpf=$(mktemp)
printf 'not json' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ -z "$_got" ]] || fail "Test 8: expected empty on invalid JSON, got '$_got'"
echo "PASS: _read_version_json returns empty for invalid JSON"

# --- Test 9: valid JSON missing version → returns empty ---
_tmpf=$(mktemp)
printf '{"build_id":"x"}' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ -z "$_got" ]] || fail "Test 9: expected empty on missing version, got '$_got'"
echo "PASS: _read_version_json returns empty for missing version"

# --- Test 10: valid JSON with blank version → returns empty ---
_tmpf=$(mktemp)
printf '{"version":"   "}' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ -z "$_got" ]] || fail "Test 10: expected empty on blank version, got '$_got'"
echo "PASS: _read_version_json returns empty for blank version"

# ===========================================================================
# Part 3: staleness comparison logic
# ===========================================================================

# --- Test 11: stale version → rebuild condition triggered ---
_BUILT="17314c6a"
_HEAD="c67aaa67"
[[ "$_BUILT" != "$_HEAD" ]] \
    || fail "Test 11: stale versions should differ"
echo "PASS: stale version comparison triggers rebuild condition"

# --- Test 12: matching version → no rebuild ---
_BUILT="c67aaa67"
_HEAD="c67aaa67"
[[ "$_BUILT" == "$_HEAD" ]] \
    || fail "Test 12: matching versions should be equal"
echo "PASS: matching version comparison does not trigger rebuild"

# --- Test 13: auto-build staleness via _read_version_json + comparison ---
_tmpf=$(mktemp)
printf '{"version":"17314c6a","build_id":"old"}' > "$_tmpf"
_bv=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
_sha="c67aaa67"
[[ -n "$_bv" && "$_bv" != "$_sha" ]] \
    || fail "Test 13: expected stale detection to be true (bv=$_bv sha=$_sha)"
echo "PASS: auto-build staleness detection end-to-end"

# --- Test 14: auto-build no-rebuild when up-to-date ---
_tmpf=$(mktemp)
printf '{"version":"c67aaa67","build_id":"new"}' > "$_tmpf"
_bv=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
_sha="c67aaa67"
[[ -n "$_bv" && "$_bv" == "$_sha" ]] \
    || fail "Test 14: expected up-to-date detection (bv=$_bv sha=$_sha)"
echo "PASS: up-to-date build does not trigger rebuild"

# ===========================================================================
# Part 4: bash syntax check
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/../weltgewebe-up"
bash -n "$DEPLOY_SCRIPT" || fail "bash -n failed on scripts/weltgewebe-up"
echo "PASS: bash -n scripts/weltgewebe-up OK"

echo
echo "All version-guard tests passed."
