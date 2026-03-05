#!/usr/bin/env bash
set -euo pipefail

ROOT=${ROOT:-/opt/weltgewebe}

# Always required artifacts
required_core=(
  "$ROOT/policies/limits.yaml"
)

for f in "${required_core[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: missing runtime artifact: $f" >&2
    exit 1
  fi
done

# Optional web artifacts
WEB_INDEX="$ROOT/apps/web/build/index.html"
WEB_APP="$ROOT/apps/web/build/_app"

if [[ -f "$WEB_INDEX" ]]; then
  if [[ ! -s "$WEB_INDEX" ]]; then
    echo "ERROR: frontend build artifact is empty: $WEB_INDEX" >&2
    exit 1
  fi

  if [[ ! -d "$WEB_APP" ]]; then
    echo "ERROR: frontend build directory missing '_app': $WEB_APP" >&2
    exit 1
  fi
fi

echo "runtime contract OK"
