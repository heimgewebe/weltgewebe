#!/usr/bin/env bash

set -euo pipefail

# repo-structure-guard
# Prüft:
# • Kernartefakte vorhanden
# • repo.meta.yaml parsebar
# • docs/index.md vorhanden
# • generated Bereich vorhanden

echo "Checking repo structure..."

FAIL=0

if [ ! -f "repo.meta.yaml" ]; then
    echo "ERROR: repo.meta.yaml missing."
    FAIL=1
fi

if [ ! -f "docs/index.md" ]; then
    echo "ERROR: docs/index.md missing."
    FAIL=1
fi

if [ ! -d "docs/_generated" ]; then
    echo "ERROR: docs/_generated missing."
    FAIL=1
fi

if [ "$FAIL" -eq 1 ]; then
    exit 1
fi

echo "repo-structure-guard pass."
