#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

bash "$REPO_ROOT/scripts/guard/lockfile-guard.sh" >/dev/null
bash "$REPO_ROOT/scripts/guard/compose-image-guard.sh" >/dev/null
bash "$REPO_ROOT/scripts/guard/caddy-build-header-guard.sh" >/dev/null

echo "PASS: repository contract guards"
