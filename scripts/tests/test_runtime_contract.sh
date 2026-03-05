#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
PREFLIGHT_SCRIPT="$REPO_ROOT/scripts/preflight/runtime_contract.sh"

export ROOT="$(mktemp -d)"

cleanup() {
  rm -rf "$ROOT"
}
trap cleanup EXIT

# Helper to create valid state
setup_valid() {
  mkdir -p "$ROOT/policies" "$ROOT/apps/web/build/_app"
  echo "---" > "$ROOT/policies/limits.yaml"
  echo "html" > "$ROOT/apps/web/build/index.html"
}

# Case 1: missing limits.yaml
setup_valid
rm "$ROOT/policies/limits.yaml"
if bash "$PREFLIGHT_SCRIPT" 2>/dev/null; then
  echo "FAIL: Should have exited 1 on missing limits.yaml"
  exit 1
fi


# Case 2: empty index.html
cleanup; ROOT="$(mktemp -d)"
setup_valid
> "$ROOT/apps/web/build/index.html"
if bash "$PREFLIGHT_SCRIPT" 2>/dev/null; then
  echo "FAIL: Should have exited 1 on empty index.html"
  exit 1
fi

# Case 3: API-only deploy (no web build)
cleanup; ROOT="$(mktemp -d)"
mkdir -p "$ROOT/policies"
echo "---" > "$ROOT/policies/limits.yaml"

if ! bash "$PREFLIGHT_SCRIPT" >/dev/null; then
  echo "FAIL: API-only deploy should pass without frontend artifacts"
  exit 1
fi

# Case 4: success
cleanup; ROOT="$(mktemp -d)"
setup_valid
if ! bash "$PREFLIGHT_SCRIPT" >/dev/null; then
  echo "FAIL: Should have exited 0 on valid structure"
  exit 1
fi

echo "test_runtime_contract: OK"
