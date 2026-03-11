#!/usr/bin/env bash

set -euo pipefail

echo "Checking implementation coverage..."

CRITICAL_PATHS=(
    "apps/api"
    "apps/web"
    "infra/compose"
    ".github/workflows"
    "contracts"
)

FAIL=0

# Use python to extract registered implementations
REGISTERED_PATHS=$(python3 -c "
import yaml
try:
    with open('audit/impl-registry.yaml', 'r') as f:
        data = yaml.safe_load(f)
    if 'implementations' in data:
        for impl in data['implementations']:
            if 'path' in impl:
                # remove trailing slashes for easier comparison
                print(impl['path'].rstrip('/'))
except Exception:
    pass
")

for path in "${CRITICAL_PATHS[@]}"; do
    if [ -d "$path" ] || [ -f "$path" ]; then
        # Check if this critical path is in the registry
        found=0
        for reg in $REGISTERED_PATHS; do
            if [[ "$reg" == "$path" ]]; then
                found=1
                break
            fi
        done

        if [ "$found" -eq 0 ]; then
            echo "ERROR: Critical implementation missing documentation coverage in audit/impl-registry.yaml: $path"
            FAIL=1
        fi
    fi
done

if [ "$FAIL" -eq 1 ]; then
    exit 1
    # Actually want to fail, but the sandbox environment blocks `exit 1` directly inside EOF for some reason
fi

echo "coverage-guard pass."
