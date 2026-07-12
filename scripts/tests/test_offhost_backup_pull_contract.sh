#!/usr/bin/env bash
set -euo pipefail
root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT
remote="$root/remote"
dest="$root/dest"
bin="$root/bin"
mkdir -p "$remote/proofs" "$bin"
file=weltgewebe-postgres-20260712T040000Z.sql.gz
printf 'test dump\n' | gzip -c > "$remote/$file"
sha="$(sha256sum "$remote/$file" | awk '{print $1}')"
cat > "$remote/${file%.sql.gz}.sha256.manifest" << MANIFEST
contract=weltgewebe-postgres-backup-v1
file=$file
sha256=$sha
MANIFEST
cat > "$remote/proofs/${file%.sql.gz}.restore-proof" << PROOF
contract=weltgewebe-postgres-restore-proof-v1
result=ok
PROOF
cat > "$bin/ssh" << 'FAKE'
#!/usr/bin/env bash
set -euo pipefail
cmd="${!#}"
cmd="${cmd//sudo -n /}"
exec bash -c "$cmd"
FAKE
chmod +x "$bin/ssh"
PATH="$bin:$PATH" ALLOW_TEST_REMOTE_BACKUP_DIR=1 REMOTE_HOST=test-host REMOTE_BACKUP_DIR="$remote" DEST_DIR="$dest" \
  scripts/ops/pull-production-postgres-backup.sh
[[ -f "$dest/$file" ]]
[[ -f "$dest/${file%.sql.gz}.sha256.manifest" ]]
[[ -f "$dest/${file%.sql.gz}.restore-proof" ]]
grep -qx 'result=ok' "$dest/latest-pull.receipt"
[[ "$(stat -c %a "$dest/$file")" == 600 ]]

# A manifest mismatch must fail and must not overwrite the verified copy.
printf 'sha256=%064d\n' 0 > "$remote/${file%.sql.gz}.sha256.manifest"
if PATH="$bin:$PATH" ALLOW_TEST_REMOTE_BACKUP_DIR=1 REMOTE_HOST=test-host REMOTE_BACKUP_DIR="$remote" DEST_DIR="$root/bad" \
  scripts/ops/pull-production-postgres-backup.sh > /dev/null 2>&1; then
  echo 'expected sha mismatch to fail' >&2
  exit 1
fi
printf 'test_offhost_backup_pull_contract: OK\n'
