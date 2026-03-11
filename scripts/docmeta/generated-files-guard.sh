#!/usr/bin/env bash

set -euo pipefail

echo "Checking generated files guard..."

FAIL=0

if [ ! -d "docs/_generated" ]; then
    echo "ERROR: docs/_generated missing."
    FAIL=1
fi

for file in docs/_generated/*.md; do
    if [ -f "$file" ]; then
        if ! grep -q "Generated automatically." "$file"; then
            echo "ERROR: Generated file $file missing header."
            FAIL=1
        fi
    fi
done

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "generated-files-guard pass."
