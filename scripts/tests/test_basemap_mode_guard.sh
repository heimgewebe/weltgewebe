#!/usr/bin/env bash
# Contract tests for the PUBLIC_BASEMAP_MODE validation logic in weltgewebe-up.
#
# Tests the case-statement guard that rejects invalid values before the
# edge-default injection and the frontend build. Mirrors the production logic
# without invoking the full deploy script (no Docker, no pnpm, no git required).
set -euo pipefail

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# validate_basemap_mode: mirrors the case statement in weltgewebe-up.
# Returns 0 for allowed values, 1 for invalid ones (same exit codes as script).
# ---------------------------------------------------------------------------
validate_basemap_mode() {
  local value="${1:-}"
  case "$value" in
    "" | "local-sovereign" | "remote-style")
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# ---------------------------------------------------------------------------
# apply_edge_default: mirrors the edge-default injection logic.
# Prints the effective mode given an initial value and an edge-detected flag.
# ---------------------------------------------------------------------------
apply_edge_default() {
  local mode="${1:-}"
  local edge_detected="${2:-0}"
  if [[ -z "$mode" ]]; then
    if [[ "$edge_detected" == "1" ]]; then
      echo "local-sovereign"
    else
      echo ""
    fi
  else
    echo "$mode"
  fi
}

# ===========================================================================
# Part 1: validate_basemap_mode — valid values are accepted
# ===========================================================================

validate_basemap_mode "" || fail "empty string must be accepted"
echo "PASS: PUBLIC_BASEMAP_MODE='' accepted"

validate_basemap_mode "local-sovereign" || fail "local-sovereign must be accepted"
echo "PASS: PUBLIC_BASEMAP_MODE=local-sovereign accepted"

validate_basemap_mode "remote-style" || fail "remote-style must be accepted"
echo "PASS: PUBLIC_BASEMAP_MODE=remote-style accepted"

# ===========================================================================
# Part 2: validate_basemap_mode — invalid values are rejected
# ===========================================================================

if validate_basemap_mode "local_sovereign" 2>/dev/null; then
  fail "local_sovereign (underscore typo) must be rejected"
fi
echo "PASS: PUBLIC_BASEMAP_MODE=local_sovereign rejected"

if validate_basemap_mode "garbage" 2>/dev/null; then
  fail "garbage must be rejected"
fi
echo "PASS: PUBLIC_BASEMAP_MODE=garbage rejected"

if validate_basemap_mode "local" 2>/dev/null; then
  fail "partial value 'local' must be rejected"
fi
echo "PASS: PUBLIC_BASEMAP_MODE=local rejected"

if validate_basemap_mode "REMOTE-STYLE" 2>/dev/null; then
  fail "uppercase REMOTE-STYLE must be rejected (case-sensitive)"
fi
echo "PASS: PUBLIC_BASEMAP_MODE=REMOTE-STYLE rejected (case-sensitive)"

if validate_basemap_mode " local-sovereign" 2>/dev/null; then
  fail "leading-space value must be rejected"
fi
echo "PASS: PUBLIC_BASEMAP_MODE=' local-sovereign' (leading space) rejected"

# ===========================================================================
# Part 3: edge-default injection — unset + edge detected → local-sovereign
# ===========================================================================

result=$(apply_edge_default "" "1")
[[ "$result" == "local-sovereign" ]] || fail "unset + edge → expected local-sovereign, got '$result'"
echo "PASS: unset + edge detected → local-sovereign default"

result=$(apply_edge_default "" "0")
[[ "$result" == "" ]] || fail "unset + no edge → expected empty (web app default), got '$result'"
echo "PASS: unset + no edge → web app default (unset)"

result=$(apply_edge_default "local-sovereign" "1")
[[ "$result" == "local-sovereign" ]] || fail "explicit local-sovereign + edge → must not be overridden"
echo "PASS: explicit local-sovereign + edge detected → not overridden"

result=$(apply_edge_default "remote-style" "1")
[[ "$result" == "remote-style" ]] || fail "explicit remote-style + edge → must not be overridden"
echo "PASS: explicit remote-style + edge detected → not overridden"

# ===========================================================================
# Part 4: integration — validation happens before default injection
# ===========================================================================

# A typo must be caught before we ever reach the edge-default logic.
# Simulate the full guard → inject sequence for a bad value.
bad_mode="local_sovereign"
if validate_basemap_mode "$bad_mode"; then
  fail "bad mode '$bad_mode' should have been caught before edge-default injection"
fi
echo "PASS: typo caught before edge-default injection (deploy would have aborted)"

# ===========================================================================
# Part 5: bash -n syntax check for the deploy script itself
# ===========================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
bash -n "$REPO_ROOT/scripts/weltgewebe-up" || fail "bash -n scripts/weltgewebe-up failed"
echo "PASS: bash -n scripts/weltgewebe-up OK"

echo
echo "All basemap-mode-guard tests passed."
