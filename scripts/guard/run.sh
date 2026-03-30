#!/usr/bin/env bash
set -euo pipefail

# Core guard orchestrator — runs all canonical CI guards.
#
# Core guards are fast, deterministic, and require no external runtime
# dependencies (no Docker daemon, no network, no running services).
# Guards that need Docker Compose or other environment-specific tooling
# are non-core and live outside this orchestration (see guard_api_alias.sh).

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)"

echo "== guard: compose no relative volumes =="
"${REPO_ROOT}/scripts/guard-compose-no-relative-volumes.sh" \
  "${REPO_ROOT}/infra/compose/compose.prod.yml"

echo "== guard: token leak =="
"${REPO_ROOT}/scripts/guard/token-leak-guard.sh"

echo "== guard: metrics ref consistency =="
"${REPO_ROOT}/scripts/guard/metrics-ref-guard.sh"

echo "== guard: caddy basemap route contract =="
"${REPO_ROOT}/scripts/guard/caddy-basemap-route-guard.sh"
