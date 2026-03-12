#!/usr/bin/env bash
set -euo pipefail

echo "Checking for accidental token/secret leaks in text files..."

# We check for authentication tokens, magic links, passwords, and secrets.
# We use git grep over tracked files to find matches.
MATCHES=$(git grep -i -E "token=[a-zA-Z0-9-]{10,}|/api/auth/login/consume|Authorization:[[:space:]]*Bearer[[:space:]]+[a-zA-Z0-9-]{10,}|secret=[a-zA-Z0-9-]{10,}|password=[a-zA-Z0-9-]{10,}" -- . || true)

if [ -n "$MATCHES" ]; then
    # Filter out matches in legitimate context such as source code, tests, docs, and the CI scripts themselves.
    FILTERED_MATCHES=$(echo "$MATCHES" | grep -vE "^apps/api/" | grep -vE "^apps/web/" | grep -vE "^docs/" | grep -vE "^verification/" | grep -vE "^scripts/" | grep -vE "^ci/" | grep -vE "^\.github/" | grep -vE "^\.wgx/" || true)

    if [ -n "$FILTERED_MATCHES" ]; then
        echo "ERROR: Found potential token leaks or secrets in repository files:"
        echo "$FILTERED_MATCHES"
        exit 1
    fi
fi

echo "OK: No token leaks detected."
