#!/usr/bin/env bash
set -euo pipefail

# Find repo root
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

required=(
"${REPO_ROOT}/apps/api/policies/limits.yaml"
"${REPO_ROOT}/apps/web/build/index.html"
)

for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "missing runtime artifact: $f"
    exit 1
  fi
done

echo "runtime contract OK"
