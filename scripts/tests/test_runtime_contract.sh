#!/usr/bin/env bash
set -euo pipefail

echo "== Testing scripts/preflight/runtime_contract.sh =="

# Setup temp dir as mocked ROOT
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

# Mock dependencies
mkdir -p "$TEST_ROOT/policies"
mkdir -p "$TEST_ROOT/apps/web/build"

SCRIPT_PATH="$(pwd)/scripts/preflight/runtime_contract.sh"

export ROOT="$TEST_ROOT"

# Test 1: Missing limits.yaml -> exit 1
echo "[Test 1] Missing limits.yaml"
if bash "$SCRIPT_PATH" 2>/dev/null; then
    echo "FAIL: Expected guard to exit 1 for missing limits.yaml"
    exit 1
else
    echo "PASS: Guard exited 1 as expected."
fi

# Create limits.yaml
touch "$TEST_ROOT/policies/limits.yaml"

# Test 2: Missing index.html -> exit 1
echo "[Test 2] Missing index.html"
if bash "$SCRIPT_PATH" 2>/dev/null; then
    echo "FAIL: Expected guard to exit 1 for missing index.html"
    exit 1
else
    echo "PASS: Guard exited 1 as expected."
fi

# Create empty index.html
touch "$TEST_ROOT/apps/web/build/index.html"

# Test 3: Empty index.html -> exit 1
echo "[Test 3] Empty index.html"
if bash "$SCRIPT_PATH" 2>/dev/null; then
    echo "FAIL: Expected guard to exit 1 for empty index.html"
    exit 1
else
    echo "PASS: Guard exited 1 as expected."
fi

# Create non-empty index.html
echo "<html></html>" > "$TEST_ROOT/apps/web/build/index.html"

# Test 4: All files present and valid -> exit 0
echo "[Test 4] Valid configuration"
if ! bash "$SCRIPT_PATH" >/dev/null; then
    echo "FAIL: Expected guard to exit 0 when all files are valid."
    exit 1
else
    echo "PASS: Guard exited 0 as expected."
fi

echo "All tests passed for runtime_contract.sh."
