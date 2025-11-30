#!/usr/bin/env bash
set -euo pipefail

printf "[drill] Starting disaster recovery smoke sequence...\n"

# Placeholder: ensure core services are up
if ! docker compose -f infra/compose/compose.core.yml ps > /dev/null 2>&1; then
  printf "[drill] Hinweis: Compose-Stack scheint nicht zu laufen. Bitte zuerst 'just up' ausführen.\n"
  exit 1
fi

docker compose -f infra/compose/compose.core.yml ps

printf "[drill] TODO: Automatisierte Smoke-Tests (Login, Thread-Erstellung) integrieren.\n"
