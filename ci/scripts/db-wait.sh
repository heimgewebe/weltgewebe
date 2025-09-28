#!/usr/bin/env bash
set -euo pipefail

HOST=${PGHOST:-localhost}
PORT=${PGPORT:-5432}
TIMEOUT=${DB_WAIT_TIMEOUT:-60}
INTERVAL=${DB_WAIT_INTERVAL:-2}

declare -i end=$((SECONDS + TIMEOUT))

while (( SECONDS < end )); do
    if (echo >"/dev/tcp/${HOST}/${PORT}") >/dev/null 2>&1; then
        printf 'Postgres is available at %s:%s\n' "$HOST" "$PORT"
        exit 0
    fi
    sleep "$INTERVAL"
done

printf 'Timed out waiting for Postgres at %s:%s after %ss\n' "$HOST" "$PORT" "$TIMEOUT" >&2
exit 1
