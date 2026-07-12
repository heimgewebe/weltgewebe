#!/usr/bin/env bash
set -euo pipefail
umask 077
fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}
require_cmd() { command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"; }
require_cmd docker
require_cmd gzip
require_cmd sha256sum
BACKUP_DIR="${BACKUP_DIR:-/var/backups/weltgewebe/postgres}"
BACKUP_PREFIX="${BACKUP_PREFIX:-weltgewebe-postgres}"
RESTORE_PROOF_DIR="${RESTORE_PROOF_DIR:-${BACKUP_DIR}/proofs}"
RESTORE_POSTGRES_IMAGE="${RESTORE_POSTGRES_IMAGE:-postgres:16@sha256:be01cf82fc7dbba824acf0a82e150b4b360f3ff93c6631d7844af431e841a95c}"
[[ -d "$BACKUP_DIR" ]] || fail "backup directory does not exist: $BACKUP_DIR"
latest="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "${BACKUP_PREFIX}-*.sql.gz" -printf '%f\n' | sort | tail -n1)"
[[ -n "$latest" ]] || fail "no backup files found in $BACKUP_DIR"
latest="${BACKUP_DIR}/${latest}"
container="weltgewebe-restore-proof-$(date -u +%Y%m%d%H%M%S)-$$"
cleanup() { docker rm -f "$container" > /dev/null 2>&1 || true; }
trap cleanup EXIT

docker run -d --name "$container" --network none \
  --tmpfs /var/lib/postgresql/data:rw,nosuid,nodev,size=512m \
  -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=weltgewebe_restore_proof \
  "$RESTORE_POSTGRES_IMAGE" > /dev/null
for _ in $(seq 1 60); do
  if docker exec "$container" pg_isready -U postgres -d weltgewebe_restore_proof > /dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$container" pg_isready -U postgres -d weltgewebe_restore_proof > /dev/null || fail "disposable PostgreSQL did not become ready"
export BACKUP_FILE="$latest"
export BACKUP_MANIFEST="${latest%.sql.gz}.sha256.manifest"
export RESTORE_POSTGRES_CONTAINER="$container"
export RESTORE_PROOF_DIR
"$(dirname "$0")/postgres-restore-proof.sh"
