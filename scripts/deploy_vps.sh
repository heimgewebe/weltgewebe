#!/usr/bin/env bash
set -euo pipefail

# Deprecated compatibility shim.
#
# This script used to run `docker compose -f infra/compose/compose.prod.yml up`
# directly. That deployed the base compose file *without*
# `infra/compose/compose.vps.override.yml`, which silently dropped every
# VPS-specific setting: the Caddyfile.vps mount, APP_BASE_URL, POLICY_LIMITS_PATH,
# the IPv6 port bindings, the AUTH_RL_* rate limits and AUTH_TRUSTED_PROXIES.
# It also left Caddy bound to 127.0.0.1 (compose.prod.yml's CADDY_BIND default),
# so the host was not publicly reachable.
#
# `scripts/weltgewebe-up` is the real VPS entrypoint. It selects the override
# file, resolves the runtime env file, and runs the deploy preflights. This shim
# delegates to it so existing runbooks and muscle memory keep working.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

echo "WARNING: scripts/deploy_vps.sh is deprecated." >&2
echo "         Use scripts/weltgewebe-up instead; delegating to it now." >&2

PRUNE_IMAGES="${PRUNE_IMAGES:-0}"

DEPLOY_TARGET="${DEPLOY_TARGET:-vps}" "${SCRIPT_DIR}/weltgewebe-up" "$@"

# Preserve the one capability weltgewebe-up does not offer.
if [ "$PRUNE_IMAGES" -eq 1 ]; then
  echo "Pruning unused images..."
  docker image prune -f
else
  echo "Skipping image prune (set PRUNE_IMAGES=1 to enable)."
fi
