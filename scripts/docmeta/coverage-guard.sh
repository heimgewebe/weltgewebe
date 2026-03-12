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

REGISTERED_PATHS=$(grep -E '^[[:space:]]*path:' audit/impl-registry.yaml | awk -F ': ' '{print $2}' | tr -d '"' | tr -d "'" | sed 's/\/$//')

for path in "${CRITICAL_PATHS[@]}"; do
    if [ -d "$path" ] || [ -f "$path" ]; then
        found=0
        for reg in $REGISTERED_PATHS; do
            if [[ "$reg" == "$path" ]]; then
                found=1
                break
            fi
        done

        if [ "$found" -eq 0 ]; then
            echo "ERROR: Critical implementation missing from registry: $path"
            FAIL=1
        fi
    fi
done

# Verify that documented_by links exist
DOC_REFS=$(python3 -c "
import sys
import os

try:
    with open('audit/impl-registry.yaml', 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    current_list = None
    for line in lines:
        line_s = line.strip()
        if line_s.startswith('documented_by:'):
            current_list = 'documented_by'
        elif line_s.startswith('verified_by:') or line_s.startswith('supersedes:') or line_s.startswith('deprecated_by:'):
            current_list = None
        elif line_s.startswith('- ') and current_list == 'documented_by':
            doc = line_s[2:].strip()
            print(doc)
except Exception:
    pass
")

for doc in $DOC_REFS; do
    if [ ! -f "$doc" ]; then
        echo "ERROR: Registered implementation points to dead doc link: $doc"
        FAIL=1
    fi
done

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "coverage-guard pass."
