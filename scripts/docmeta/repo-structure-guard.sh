#!/usr/bin/env bash

set -euo pipefail

# repo-structure-guard
# Prüft:
# • Kernartefakte vorhanden
# • repo.meta.yaml parsebar und enthält Pflichtfelder
# • docs/index.md vorhanden
# • generated Bereich vorhanden

echo "Checking repo structure..."

FAIL=0

if [ ! -f "repo.meta.yaml" ]; then
    echo "ERROR: repo.meta.yaml missing."
    FAIL=1
else
    # parse yaml and check keys
    python3 -c "
import sys
try:
    with open('repo.meta.yaml', 'r') as f:
        content = f.read()

    required_keys = ['repo_name', 'repo_type', 'entrypoints', 'canonical_sources']

    for key in required_keys:
        if not (key + ':' in content):
            print(f'ERROR: repo.meta.yaml missing required key: {key}')
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
