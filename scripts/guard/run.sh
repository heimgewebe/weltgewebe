#!/usr/bin/env bash
set -euo pipefail

echo "== guard: compose no relative volumes =="
scripts/guard-compose-no-relative-volumes.sh infra/compose/compose.prod.yml
