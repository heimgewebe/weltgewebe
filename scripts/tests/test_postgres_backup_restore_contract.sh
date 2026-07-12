#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_SCRIPT="$REPO_ROOT/scripts/ops/postgres-backup.sh"
RESTORE_SCRIPT="$REPO_ROOT/scripts/ops/postgres-restore-proof.sh"
BACKUP_UNIT="$REPO_ROOT/scripts/ops/systemd/weltgewebe-postgres-backup.service"
PREPARE_UNIT="$REPO_ROOT/scripts/ops/systemd/weltgewebe-postgres-backup-prepare.service"

grep -qxF 'Requires=docker.service weltgewebe-postgres-backup-prepare.service' "$BACKUP_UNIT"
grep -qxF 'After=docker.service weltgewebe-postgres-backup-prepare.service' "$BACKUP_UNIT"
grep -qxF 'ReadWritePaths=/var/backups/weltgewebe/postgres' "$BACKUP_UNIT"
if grep -q '^ExecStartPre=' "$BACKUP_UNIT" || grep -qxF 'ReadWritePaths=/var/backups' "$BACKUP_UNIT"; then
  echo "backup service must not prepare or write the broad backup parent" >&2
  exit 1
fi
grep -qxF 'Before=weltgewebe-postgres-backup.service' "$PREPARE_UNIT"
grep -qxF 'AssertPathIsDirectory=/var/backups' "$PREPARE_UNIT"
grep -qxF 'ExecStart=/usr/bin/install -d -o root -g root -m 0750 /var/backups/weltgewebe' "$PREPARE_UNIT"
grep -qxF 'ExecStart=/usr/bin/install -d -o root -g root -m 0700 /var/backups/weltgewebe/postgres' "$PREPARE_UNIT"
grep -qxF 'ProtectSystem=full' "$PREPARE_UNIT"
grep -qxF 'ReadOnlyPaths=/var' "$PREPARE_UNIT"
grep -qxF 'ReadWritePaths=/var/backups' "$PREPARE_UNIT"
grep -qxF 'CapabilityBoundingSet=CAP_CHOWN CAP_DAC_OVERRIDE CAP_FOWNER' "$PREPARE_UNIT"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

MOCK_BIN="$TEMP_DIR/bin"
mkdir -p "$MOCK_BIN"

cat > "$MOCK_BIN/psql" << 'SH'
#!/usr/bin/env bash
set -euo pipefail
args="$*"
if [[ "$args" == *"select 1"* ]]; then
  echo "1"
elif [[ "$args" == *"count(*)"* ]]; then
  echo "0"
elif [[ "$args" == *"string_agg"* ]]; then
  echo ""
else
  cat >/dev/null || true
fi
SH
chmod +x "$MOCK_BIN/psql"

cat > "$MOCK_BIN/pg_dump" << 'SH'
#!/usr/bin/env bash
set -euo pipefail
cat <<'SQL'
CREATE TABLE domain_accounts (id text primary key);
CREATE TABLE domain_nodes (id text primary key);
CREATE TABLE domain_edges (id text primary key);
CREATE TABLE sessions (id text primary key);
CREATE TABLE passkey_credentials (credential_id bytea primary key);
CREATE TABLE _sqlx_migrations (version bigint primary key);
SQL
SH
chmod +x "$MOCK_BIN/pg_dump"

export PATH="$MOCK_BIN:$PATH"

BACKUP_DIR="$TEMP_DIR/backups"
RESTORE_PROOF_DIR="$TEMP_DIR/proofs"

DATABASE_URL="postgres://welt:secret@db:5432/weltgewebe" \
  BACKUP_DIR="$BACKUP_DIR" \
  BACKUP_LABEL="fixture" \
  BACKUP_RETENTION_DAYS=1 \
  bash "$BACKUP_SCRIPT" > /dev/null

backup_file="$BACKUP_DIR/weltgewebe-postgres-fixture.sql.gz"
manifest_file="$BACKUP_DIR/weltgewebe-postgres-fixture.sha256.manifest"

test -f "$backup_file"
test -f "$manifest_file"
gzip -t "$backup_file"
grep -q '^contract=weltgewebe-postgres-backup-v1$' "$manifest_file"
grep -q '^sha256=' "$manifest_file"

mode="$(stat -c '%a' "$backup_file")"
if [[ "$mode" != "600" ]]; then
  echo "backup file mode should be 600, got $mode" >&2
  exit 1
fi

BACKUP_FILE="$backup_file" \
  BACKUP_MANIFEST="$manifest_file" \
  RESTORE_DATABASE_URL="postgres://welt:secret@db:5432/weltgewebe_restore_proof" \
  RESTORE_PROOF_DIR="$RESTORE_PROOF_DIR" \
  bash "$RESTORE_SCRIPT" > /dev/null

proof_file="$RESTORE_PROOF_DIR/weltgewebe-postgres-fixture.restore-proof"
test -f "$proof_file"
grep -q '^contract=weltgewebe-postgres-restore-proof-v1$' "$proof_file"
grep -q '^result=ok$' "$proof_file"

mode="$(stat -c '%a' "$proof_file")"
if [[ "$mode" != "600" ]]; then
  echo "restore proof mode should be 600, got $mode" >&2
  exit 1
fi

if BACKUP_FILE="$backup_file" \
  BACKUP_MANIFEST="$manifest_file" \
  RESTORE_DATABASE_URL="postgres://welt:secret@db:5432/weltgewebe" \
  RESTORE_PROOF_DIR="$RESTORE_PROOF_DIR" \
  bash "$RESTORE_SCRIPT" > /dev/null 2>&1; then
  echo "restore proof should reject non-disposable target database" >&2
  exit 1
fi

echo "PASS: postgres backup and restore-proof contract"
