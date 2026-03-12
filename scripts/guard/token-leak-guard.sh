#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)"

echo "Checking for accidental token/secret leaks in text files..."

set +e
MATCHES=$(git -C "$REPO_ROOT" grep -i -E "token=[a-zA-Z0-9-]{10,}|/api/auth/login/consume|Authorization:[[:space:]]*Bearer[[:space:]]+[a-zA-Z0-9-]{10,}|secret=[a-zA-Z0-9-]{10,}|password=[a-zA-Z0-9-]{10,}" \
  -- . \
  ':!scripts/guard/token-leak-guard.sh' \
  ':!apps/api/src/routes/auth.rs' \
  ':!apps/api/tests/api_auth.rs' \
  ':!docs/runbook.md' \
  ':!docs/blueprints/weltgewebe.auth-and-ui-routing.md' \
  ':!verification/verify_magic_link.py')
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -eq 0 ]; then
    echo "ERROR: Found potential token leaks or secrets in repository files:"
    echo "$MATCHES"
    exit 1
elif [ $EXIT_CODE -eq 1 ]; then
    echo "OK: No token leaks detected."
    exit 0
else
    echo "ERROR: git grep failed with exit code $EXIT_CODE."
    exit $EXIT_CODE
fi
