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

AJV_BIN="/home/jules/.local/share/pnpm/ajv"

if ! [ -x "$AJV_BIN" ]; then
    echo "error: ajv executable not found at $AJV_BIN" >&2
    echo "Please ensure pnpm is set up and 'ajv-cli' is installed globally." >&2
    exit 1
fi

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
