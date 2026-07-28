#!/usr/bin/env bash
#
# Local helper to validate Weltgewebe domain contracts with the pinned
# repository-owned AJV libraries, without the deprecated ajv-cli wrapper.
# Mirrors the domain-schema portion of .github/workflows/contracts-domain.yml.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v node > /dev/null 2>&1; then
  echo "error: node is required; install the repository Node toolchain first" >&2
  exit 2
fi
if [[ ! -d node_modules/ajv || ! -d node_modules/ajv-formats ]]; then
  echo "error: pinned AJV libraries are missing; run pnpm install first" >&2
  exit 2
fi

SCHEMA_CHECK=(node scripts/json-schema-check.mjs)

echo "==> Compiling domain schemas with pinned AJV libraries..."

shopt -s nullglob
SCHEMAS=(contracts/domain/*.schema.json)
if [[ ${#SCHEMAS[@]} -eq 0 ]]; then
  echo "warning: no schemas found under contracts/domain/*.schema.json" >&2
else
  for schema in "${SCHEMAS[@]}"; do
    echo "  - $schema"
    "${SCHEMA_CHECK[@]}" compile --schema "$schema" --spec draft7
  done
fi

echo
echo "==> Validating example instances against schemas..."

EXAMPLES=(contracts/domain/examples/*.example.json)
if [[ ${#EXAMPLES[@]} -eq 0 ]]; then
  echo "warning: no examples found under contracts/domain/examples/*.example.json" >&2
else
  for example in "${EXAMPLES[@]}"; do
    filename="$(basename "$example")"
    entity="${filename%.example.json}"
    schema="contracts/domain/${entity}.schema.json"
    echo "  - $example -> $schema"
    "${SCHEMA_CHECK[@]}" validate --schema "$schema" --data "$example" --spec draft7
  done
fi

echo
echo "✓ Domain contracts check completed."
