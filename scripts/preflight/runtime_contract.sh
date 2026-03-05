#!/usr/bin/env bash
set -euo pipefail

ROOT=${ROOT:-/opt/weltgewebe}

required=(
"$ROOT/policies/limits.yaml"
"$ROOT/apps/web/build/index.html"
)

for f in "${required[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing runtime artifact: $f" >&2
    exit 1
  fi
done

if [[ ! -s "$ROOT/apps/web/build/index.html" ]]; then
  echo "ERROR: frontend build artifact is empty: $ROOT/apps/web/build/index.html" >&2
  exit 1
fi

echo "runtime contract OK"
