#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Weltgewebe Update Script
# -----------------------------
REPO_DIR="${REPO_DIR:-/opt/weltgewebe}"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"

ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_FILE="${COMPOSE_FILE:-infra/compose/compose.prod.yml}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-compose}"

HEALTH_URL="${HEALTH_URL:-http://localhost/health/ready}"

# Optional: if you have a snapshot script, set SNAPSHOT_SCRIPT to its path.
# Keep naming "weltgewebe", not "wgx".
SNAPSHOT_SCRIPT="${SNAPSHOT_SCRIPT:-scripts/deploy-snapshot.sh}"

cd "$REPO_DIR"

echo "== Weltgewebe Update =="
echo "Repo:   $REPO_DIR"
echo "Target: $REMOTE/$BRANCH"
echo

# 1) Fetch desired state
git fetch "$REMOTE" --prune

HEAD_SHA="$(git rev-parse HEAD)"
TARGET_SHA="$(git rev-parse "$REMOTE/$BRANCH")"

echo "HEAD:   $HEAD_SHA"
echo "TARGET: $TARGET_SHA"
echo

# 2) Align working tree to target (note: untracked files are not removed)
if [[ "$HEAD_SHA" != "$TARGET_SHA" ]]; then
  echo "Updating working tree to $REMOTE/$BRANCH ..."
  git reset --hard "$REMOTE/$BRANCH"
else
  echo "No update needed (already at target)."
fi

# 3) Preflight: Compose must render
echo
echo "Preflight: docker compose config ..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" config >/dev/null
echo "OK"

# 4) Deploy: ensure containers are built / updated
echo
echo "Deploy: docker compose up -d --build ..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" up -d --build

# 5) Status
echo
echo "Status: docker compose ps"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" ps

# 6) Health
echo
echo "Health: $HEALTH_URL"
if curl -fsS --connect-timeout 2 --max-time 5 --retry 5 --retry-delay 1 "$HEALTH_URL" >/dev/null; then
  echo "Health OK"
else
  echo "ERROR: Health check failed"
  exit 20
fi

# 7) Optional: snapshot for evidence
echo
if [[ -x "$SNAPSHOT_SCRIPT" ]]; then
  echo "Snapshot: live"
  SNAPSHOT_MODE=live COMPOSE_PROJECT="$COMPOSE_PROJECT" COMPOSE_FILE="$COMPOSE_FILE" bash "$SNAPSHOT_SCRIPT"
else
  echo "No snapshot script found/executable at: $SNAPSHOT_SCRIPT (skipping)"
fi

echo
echo "Done."
