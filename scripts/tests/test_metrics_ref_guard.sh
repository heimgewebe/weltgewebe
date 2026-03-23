#!/usr/bin/env bash
set -euo pipefail

# Test: scripts/guard/metrics-ref-guard.sh
# Verifies that the metrics ref guard correctly detects mismatches
# between uses: ref and metarepo_ref in the metrics workflow.
#
# Tests call the REAL guard script via REPO_ROOT override — no
# shadow reimplementation of guard logic.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
GUARD_SCRIPT="$REPO_ROOT/scripts/guard/metrics-ref-guard.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

PASS=0
FAIL=0

report() {
  if [ "$1" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "PASS: $2"
  else
    FAIL=$((FAIL + 1))
    echo "FAIL: $2"
  fi
}

# Case 1: Matching refs — should pass
mkdir -p "$TEMP_DIR/case1/.github/workflows"
cat > "$TEMP_DIR/case1/.github/workflows/metrics.yml" <<'YAML'
name: Metrics
on:
  workflow_dispatch:
jobs:
  metrics:
    uses: heimgewebe/metarepo/.github/workflows/wgx-metrics.yml@abc123def456
    with:
      metarepo_ref: abc123def456
      post_url: https://example.com
YAML

if REPO_ROOT="$TEMP_DIR/case1" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 0 "Matching refs pass"
else
  report 1 "Matching refs should pass"
fi

# Case 2: Mismatched refs — should fail with exit 1
mkdir -p "$TEMP_DIR/case2/.github/workflows"
cat > "$TEMP_DIR/case2/.github/workflows/metrics.yml" <<'YAML'
name: Metrics
on:
  workflow_dispatch:
jobs:
  metrics:
    uses: heimgewebe/metarepo/.github/workflows/wgx-metrics.yml@abc123def456
    with:
      metarepo_ref: xyz789different
      post_url: https://example.com
YAML

if REPO_ROOT="$TEMP_DIR/case2" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 1 "Mismatched refs should fail"
else
  report 0 "Mismatched refs correctly detected"
fi

# Case 3: Missing workflow file — should fail with exit 2
if REPO_ROOT="$TEMP_DIR/nonexistent" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 1 "Missing workflow should fail"
else
  report 0 "Missing workflow correctly detected"
fi

# Case 4: Quoted metarepo_ref — should still match
mkdir -p "$TEMP_DIR/case4/.github/workflows"
cat > "$TEMP_DIR/case4/.github/workflows/metrics.yml" <<'YAML'
name: Metrics
on:
  workflow_dispatch:
jobs:
  metrics:
    uses: heimgewebe/metarepo/.github/workflows/wgx-metrics.yml@sha256abc123
    with:
      metarepo_ref: "sha256abc123"
      post_url: https://example.com
YAML

if REPO_ROOT="$TEMP_DIR/case4" bash "$GUARD_SCRIPT" >/dev/null 2>&1; then
  report 0 "Quoted metarepo_ref correctly matches"
else
  report 1 "Quoted metarepo_ref should be stripped and match"
fi

echo ""
echo "test_metrics_ref_guard: $PASS passed, $FAIL failed"
if [ "$FAIL" -ne 0 ]; then
  exit 1
fi
