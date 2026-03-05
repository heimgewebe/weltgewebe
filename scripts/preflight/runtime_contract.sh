#!/usr/bin/env bash
set -euo pipefail

required=(
/opt/weltgewebe/policies/limits.yaml
/opt/weltgewebe/apps/web/build/index.html
)

for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "missing runtime artifact: $f"
    exit 1
  fi
done

echo "runtime contract OK"
