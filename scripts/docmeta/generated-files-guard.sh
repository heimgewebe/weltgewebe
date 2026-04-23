#!/usr/bin/env bash

set -euo pipefail

echo "Checking generated files guard..."

FAIL=0

if [ ! -d "docs/_generated" ]; then
    echo "ERROR: docs/_generated missing."
    FAIL=1
fi

REQUIRED_FILES=(
    "doc-index.md"
    "system-map.md"
    "backlinks.md"
    "impl-index.md"
    "orphans.md"
    "supersession-map.md"
    "architecture-drift.md"
    "doc-coverage.md"
    "knowledge-gaps.md"
    "implicit-dependencies.md"
    "change-resonance.md"
    "staleness-report.md"
    "agent-readiness.md"
)

for req in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "docs/_generated/$req" ]; then
        echo "ERROR: Missing expected generated file docs/_generated/$req"
        FAIL=1
    fi
done

for file in docs/_generated/*.md; do
    if [ -f "$file" ]; then
        if ! grep -q "Generated automatically." "$file"; then
            echo "ERROR: Generated file $file missing 'Generated automatically.' string."
            FAIL=1
        fi
        if ! head -n 1 "$file" | grep -q "^---$"; then
            echo "ERROR: Generated file $file missing frontmatter block."
            FAIL=1
        fi
    fi
done

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "generated-files-guard pass."
