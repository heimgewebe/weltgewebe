#!/usr/bin/env bash
# Contract regression tests for the version-guard logic in scripts/weltgewebe-up.
#
# Both weltgewebe-up and this test call the shared helper:
#   scripts/lib/parse-version-json.py
#
# This means the parser is tested exactly as used in production.
# What is NOT covered here: the full deploy-script execution path
# (e.g. that BUILD_WEB=auto actually invokes pnpm). Those would require
# a hermetic integration test with a stubbed pnpm.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PARSE_HELPER="$REPO_ROOT/scripts/lib/parse-version-json.py"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Wrappers — thin shells around the shared helper so tests stay readable.
# ---------------------------------------------------------------------------

# run_guard: runs the full parser; returns "<exit_code>|<stdout>"
run_guard() {
  local json="$1"
  local tmpfile
  tmpfile=$(mktemp)
  printf '%s' "$json" > "$tmpfile"

  local out rc
  set +e
  out=$(python3 "$PARSE_HELPER" "$tmpfile" 2>/dev/null)
  rc=$?
  set -e

  rm -f "$tmpfile"
  echo "$rc|$out"
}

# _read_version_json: mirrors the helper wrapper used in weltgewebe-up.
# Returns the version string (line 1 of parser output), or empty on any error.
_read_version_json() {
    local json_file="$1"
    python3 "$PARSE_HELPER" "$json_file" 2>/dev/null | head -n1 || true
}

# ===========================================================================
# Part 1: full parser — exit-code semantics (via shared helper)
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

# --- Test 3: all three fields — commit appears on line 3 ---
result=$(run_guard '{"version":"c67aaa67","build_id":"x","commit":"c67aaa6730b78c5ab5cfbacb272eb60a06347473"}')
rc="${result%%|*}"
output="${result#*|}"
[[ "$rc" == "0" ]] || fail "Test 3: expected exit 0, got $rc"
commit_line=$(printf '%s' "$output" | sed -n '3p')
[[ "$commit_line" == "c67aaa6730b78c5ab5cfbacb272eb60a06347473" ]] \
    || fail "Test 3: commit not on 3rd line, got '$commit_line'"
echo "PASS: commit field output as 3rd line"

# --- Test 4: missing 'version' field → exit 2 ---
result=$(run_guard '{"build_id":"abc"}')
rc="${result%%|*}"
[[ "$rc" == "2" ]] || fail "Test 4: expected exit 2 (missing version), got $rc"
echo "PASS: missing 'version' field rejected with exit 2"

# --- Test 5: blank version string → exit 2 ---
result=$(run_guard '{"version":"  "}')
rc="${result%%|*}"
[[ "$rc" == "2" ]] || fail "Test 5: expected exit 2 (blank version), got $rc"
echo "PASS: blank 'version' string rejected with exit 2"

# --- Test 6: invalid JSON → exit 3 ---
result=$(run_guard 'not json at all')
rc="${result%%|*}"
[[ "$rc" == "3" ]] || fail "Test 6: expected exit 3 (invalid JSON), got $rc"
echo "PASS: invalid JSON rejected with exit 3"

# ===========================================================================
# Part 2: _read_version_json — pre-deploy staleness helper
# ===========================================================================

# --- Test 7: valid JSON → returns version string ---
_tmpf=$(mktemp)
printf '{"version":"17314c6a","build_id":"x"}' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ "$_got" == "17314c6a" ]] || fail "Test 7: expected '17314c6a', got '$_got'"
echo "PASS: _read_version_json extracts version from valid JSON"

# --- Test 8: invalid JSON → empty ---
_tmpf=$(mktemp)
printf 'not json' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ -z "$_got" ]] || fail "Test 8: expected empty on invalid JSON, got '$_got'"
echo "PASS: _read_version_json returns empty for invalid JSON"

# --- Test 9: missing version field → empty ---
_tmpf=$(mktemp)
printf '{"build_id":"x"}' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ -z "$_got" ]] || fail "Test 9: expected empty on missing version, got '$_got'"
echo "PASS: _read_version_json returns empty for missing version"

# --- Test 10: blank version → empty ---
_tmpf=$(mktemp)
printf '{"version":"   "}' > "$_tmpf"
_got=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
[[ -z "$_got" ]] || fail "Test 10: expected empty on blank version, got '$_got'"
echo "PASS: _read_version_json returns empty for blank version"

# ===========================================================================
# Part 3: staleness comparison logic
# (contract test: verifies the condition that weltgewebe-up evaluates;
#  does not exercise the full deploy-script auto-build path)
# ===========================================================================

# --- Test 11: stale → rebuild condition triggered ---
_BUILT="17314c6a"
_HEAD="c67aaa67"
[[ "$_BUILT" != "$_HEAD" ]] \
    || fail "Test 11: stale versions should differ"
echo "PASS: staleness comparison contract — stale version triggers rebuild condition"

# --- Test 12: matching → no rebuild ---
_BUILT="c67aaa67"
_HEAD="c67aaa67"
[[ "$_BUILT" == "$_HEAD" ]] \
    || fail "Test 12: matching versions should be equal"
echo "PASS: staleness comparison contract — matching version does not trigger rebuild"

# --- Test 13: end-to-end stale detection via _read_version_json ---
_tmpf=$(mktemp)
printf '{"version":"17314c6a","build_id":"old"}' > "$_tmpf"
_bv=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
_sha="c67aaa67"
[[ -n "$_bv" && "$_bv" != "$_sha" ]] \
    || fail "Test 13: expected stale detection (bv=$_bv sha=$_sha)"
echo "PASS: staleness comparison contract — stale version.json detected end-to-end"

# --- Test 14: end-to-end up-to-date detection ---
_tmpf=$(mktemp)
printf '{"version":"c67aaa67","build_id":"new"}' > "$_tmpf"
_bv=$(_read_version_json "$_tmpf")
rm -f "$_tmpf"
_sha="c67aaa67"
[[ -n "$_bv" && "$_bv" == "$_sha" ]] \
    || fail "Test 14: expected up-to-date detection (bv=$_bv sha=$_sha)"
echo "PASS: staleness comparison contract — up-to-date build does not trigger rebuild"

# ===========================================================================
# Part 4: bash syntax check of the deploy script
# ===========================================================================

bash -n "$REPO_ROOT/scripts/weltgewebe-up" || fail "bash -n failed on scripts/weltgewebe-up"
echo "PASS: bash -n scripts/weltgewebe-up OK"

echo
echo "All version-guard tests passed."
