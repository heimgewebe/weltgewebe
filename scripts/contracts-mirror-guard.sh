#!/usr/bin/env bash
set -euo pipefail

# Compares a canonical contracts directory with the local mirror to prevent drift.
# Usage:
#   CANONICAL_CONTRACTS_DIR=/path/to/metarepo/contracts \
#   MIRROR_DIR=contracts-mirror/json \
#   bash ./scripts/contracts-mirror-guard.sh
#
# Exit 0: directories are byte-identical (ignoring .gitkeep)
# Exit 1: mismatch or missing directories/inputs

MIRROR_DIR=${MIRROR_DIR:-contracts-mirror/json}
CANONICAL_DIR=${CANONICAL_CONTRACTS_DIR:-}

usage() {
  cat <<'EOF'
contracts-mirror-guard: compare canonical contracts to the local mirror.

Required env:
  CANONICAL_CONTRACTS_DIR  Path to the canonical contracts directory (e.g., metarepo/contracts)

Optional env:
  MIRROR_DIR               Path to the mirror directory (default: contracts-mirror/json)

Example:
  CANONICAL_CONTRACTS_DIR=/home/me/metarepo/contracts \
  MIRROR_DIR=contracts-mirror/json \
  bash ./scripts/contracts-mirror-guard.sh
EOF
}

if [ -z "${CANONICAL_DIR}" ]; then
  echo "error: CANONICAL_CONTRACTS_DIR must be set." >&2
  usage
  exit 1
fi

if [ ! -d "${CANONICAL_DIR}" ]; then
  echo "error: canonical directory '${CANONICAL_DIR}' not found." >&2
  exit 1
fi

if [ ! -d "${MIRROR_DIR}" ]; then
  echo "error: mirror directory '${MIRROR_DIR}' not found." >&2
  exit 1
fi

echo "Comparing canonical '${CANONICAL_DIR}' to mirror '${MIRROR_DIR}'..."
if diff -ruN --exclude='.gitkeep' "${CANONICAL_DIR}" "${MIRROR_DIR}"; then
  echo "✓ contracts mirror matches canonical source."
  exit 0
else
  echo "✗ drift detected between canonical and mirror." >&2
  exit 1
fi
