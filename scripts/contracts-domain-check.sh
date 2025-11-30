#!/usr/bin/env bash
#
# Local helper to validate Weltgewebe domain contracts.
# Mirrors the logic of .github/workflows/contracts-domain.yml:
# - compile all schemas
# - validate all example instances
#
# Usage:
#   ./scripts/contracts-domain-check.sh
# or (nach Eintrag ins Justfile):
#   just contracts-domain-check

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AJV_BIN=""
if ! AJV_BIN="$(command -v ajv 2> /dev/null)"; then
  echo "error: ajv executable not found in your PATH." >&2
  echo "Please install 'ajv-cli' and 'ajv-formats' globally (e.g., using pnpm or npm)." >&2
  exit 1
fi

export AJV_BIN

echo "==> Compiling domain schemas with ajv (using ajv-formats)..."

shopt -s nullglob
SCHEMAS=(contracts/domain/*.schema.json)

if [ ${#SCHEMAS[@]} -eq 0 ]; then
  echo "warning: no schemas found under contracts/domain/*.schema.json" >&2
else
  for schema in "${SCHEMAS[@]}"; do
    echo "  - $schema"
    "$AJV_BIN" compile -s "$schema" --strict=false -c ajv-formats
  done
fi

echo
echo "==> Validating example instances against schemas..."

EXAMPLES=(contracts/domain/examples/*.example.json)

if [ ${#EXAMPLES[@]} -eq 0 ]; then
  echo "warning: no examples found under contracts/domain/examples/*.example.json" >&2
else
  for example in "${EXAMPLES[@]}"; do
    filename="$(basename "$example")"
    entity="${filename%.example.json}"
    schema="contracts/domain/${entity}.schema.json"
    echo "  - $example -> $schema"
    "$AJV_BIN" validate -s "$schema" -d "$example" -c ajv-formats
  done
fi

echo
echo "✓ Domain contracts check completed."
