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

# Basic string parsing to extract paths from impl-registry.yaml without relying on python yaml
REGISTERED_PATHS=$(grep -E '^[[:space:]]*path:' audit/impl-registry.yaml | awk -F ': ' '{print $2}' | tr -d '"' | tr -d "'" | sed 's/\/$//')

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
fi

echo "coverage-guard pass."
