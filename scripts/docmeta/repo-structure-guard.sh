#!/usr/bin/env bash

set -euo pipefail

# repo-structure-guard
# Prüft:
# • Kernartefakte vorhanden
# • repo.meta.yaml enthält die geforderten Top-Level-Schlüssel (über String-Check, da python-yaml in CI evtl. fehlt)
# • docs/index.md vorhanden
# • generated Bereich vorhanden

echo "Checking repo structure..."

FAIL=0

if [ ! -f "repo.meta.yaml" ]; then
    echo "ERROR: repo.meta.yaml missing."
    FAIL=1
else
    # parse yaml keys via python basic string parsing
    python3 -c "
import sys
try:
    with open('repo.meta.yaml', 'r', encoding='utf-8') as f:
        lines = f.readlines()

    required_keys = ['repo_name', 'repo_type', 'entrypoints', 'canonical_sources']
    found_keys = []

    for line in lines:
        for key in required_keys:
            if line.startswith(key + ':'):
                found_keys.append(key)

    for key in required_keys:
        if key not in found_keys:
            print(f'ERROR: repo.meta.yaml missing required top-level key: {key}')
            sys.exit(1)
except Exception as e:
    print(f'ERROR: repo.meta.yaml parsing failed: {e}')
    sys.exit(1)
" || FAIL=1
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
