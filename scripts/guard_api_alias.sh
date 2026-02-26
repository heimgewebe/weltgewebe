#!/usr/bin/env bash
set -euo pipefail

# Check if "weltgewebe-api" appears in the context of "aliases:"
if ! grep -r -A 5 "aliases:" infra/compose | grep -q "weltgewebe-api"; then
  echo "ERROR: weltgewebe-api network alias missing in compose."
  exit 1
fi
