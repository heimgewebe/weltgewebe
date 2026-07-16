#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${WELTGEWEBE_SOURCE_CHECKOUT:-/opt/weltgewebe}"
BUILD_USER="${WELTGEWEBE_BUILD_USER:-alex}"
COMMIT=""
staging=""

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

cleanup() {
  local rc=$?
  trap - EXIT
  if [[ -n "$staging" && -d "$staging" && ! -L "$staging" ]]; then
    rm -rf -- "$staging"
  fi
  exit "$rc"
}
trap cleanup EXIT

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit)
      [[ $# -ge 2 ]] || fail "--commit requires a value"
      COMMIT="$2"
      shift 2
      ;;
    --build-user)
      [[ $# -ge 2 ]] || fail "--build-user requires a value"
      BUILD_USER="$2"
      shift 2
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ "$EUID" -eq 0 ]] || fail "install-production-reconciler.sh must run as root"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "--commit must be a full lowercase SHA-1"
[[ "$BUILD_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*\$?$ ]] || fail "build user name is unsafe"
getent passwd "$BUILD_USER" > /dev/null || fail "build user does not exist: $BUILD_USER"
[[ -d "$REPO_DIR" && ! -L "$REPO_DIR" ]] || fail "source checkout is missing or unsafe: $REPO_DIR"

git_common_dir="$(git -C "$REPO_DIR" rev-parse --git-common-dir)"
if [[ "$git_common_dir" != /* ]]; then
  git_common_dir="$REPO_DIR/$git_common_dir"
fi
git_common_dir="$(realpath "$git_common_dir")"
[[ -d "$git_common_dir" && ! -L "$git_common_dir" ]] || fail "Git object store is unsafe"
[[ "$(stat --format=%u "$REPO_DIR")" == "0" ]] || fail "source checkout is not root-owned"
unsafe_git_path="$(find "$git_common_dir" -xdev \( ! -user root -o -perm /022 \) -print -quit)"
[[ -z "$unsafe_git_path" ]] || fail "Git object store is not entirely root-owned and non-writable by group/world: $unsafe_git_path"

git -C "$REPO_DIR" fetch --no-tags origin \
  "+refs/heads/main:refs/remotes/origin/main"
remote_main="$(git -C "$REPO_DIR" rev-parse refs/remotes/origin/main)"
[[ "$remote_main" == "$COMMIT" ]] ||
  fail "installation commit is not current origin/main: expected $COMMIT, got $remote_main"
git -C "$REPO_DIR" cat-file -e "$COMMIT^{commit}"

staging="$(mktemp -d /run/weltgewebe-reconciler-install.XXXXXX)"
chmod 0700 "$staging"

stage_file() {
  local source_path="$1"
  local target_name="$2"
  local mode="$3"
  git -C "$REPO_DIR" show "$COMMIT:$source_path" > "$staging/$target_name"
  chmod "$mode" "$staging/$target_name"
}

stage_file scripts/ops/deploy-exact-commit-vps.sh weltgewebe-deploy-exact-commit 0755
stage_file scripts/ops/reconcile-production-main-vps.sh weltgewebe-reconcile-production-main 0755
stage_file scripts/ops/validate_web_deploy_archive.py weltgewebe-validate-web-deploy-archive 0755
stage_file scripts/ops/verify_public_release_commit.py weltgewebe-verify-public-release 0755
stage_file infra/systemd/system/weltgewebe-production-reconcile.service weltgewebe-production-reconcile.service 0644
stage_file infra/systemd/system/weltgewebe-production-reconcile.timer weltgewebe-production-reconcile.timer 0644

bash -n "$staging/weltgewebe-deploy-exact-commit"
bash -n "$staging/weltgewebe-reconcile-production-main"
python3 -m py_compile \
  "$staging/weltgewebe-validate-web-deploy-archive" \
  "$staging/weltgewebe-verify-public-release"

install -d -o root -g root -m 0755 /usr/local/libexec
install -o root -g root -m 0755 "$staging/weltgewebe-deploy-exact-commit" \
  /usr/local/libexec/weltgewebe-deploy-exact-commit
install -o root -g root -m 0755 "$staging/weltgewebe-reconcile-production-main" \
  /usr/local/libexec/weltgewebe-reconcile-production-main
install -o root -g root -m 0755 "$staging/weltgewebe-validate-web-deploy-archive" \
  /usr/local/libexec/weltgewebe-validate-web-deploy-archive
install -o root -g root -m 0755 "$staging/weltgewebe-verify-public-release" \
  /usr/local/libexec/weltgewebe-verify-public-release
install -o root -g root -m 0644 "$staging/weltgewebe-production-reconcile.service" \
  /etc/systemd/system/weltgewebe-production-reconcile.service
install -o root -g root -m 0644 "$staging/weltgewebe-production-reconcile.timer" \
  /etc/systemd/system/weltgewebe-production-reconcile.timer

systemd-analyze verify \
  /etc/systemd/system/weltgewebe-production-reconcile.service \
  /etc/systemd/system/weltgewebe-production-reconcile.timer

install -d -o root -g root -m 0700 /etc/weltgewebe
printf 'WELTGEWEBE_BUILD_USER=%s\n' "$BUILD_USER" > "$staging/production-reconciler.env"
install -o root -g root -m 0600 "$staging/production-reconciler.env" \
  /etc/weltgewebe/production-reconciler.env

install -d -o root -g root -m 0711 /var/lib/weltgewebe-main-reconciler
install -d -o root -g root -m 0700 \
  /var/lib/weltgewebe-main-reconciler/artifacts \
  /var/lib/weltgewebe-main-reconciler/receipts \
  /var/lib/weltgewebe-main-reconciler/reconcile-receipts \
  /var/lib/weltgewebe-main-reconciler/docker-config
install -d -o root -g root -m 0755 /opt/weltgewebe-releases

manifest="/var/lib/weltgewebe-main-reconciler/installed-contract.sha256"
{
  printf 'commit  %s\n' "$COMMIT"
  sha256sum \
    /usr/local/libexec/weltgewebe-deploy-exact-commit \
    /usr/local/libexec/weltgewebe-reconcile-production-main \
    /usr/local/libexec/weltgewebe-validate-web-deploy-archive \
    /usr/local/libexec/weltgewebe-verify-public-release \
    /etc/systemd/system/weltgewebe-production-reconcile.service \
    /etc/systemd/system/weltgewebe-production-reconcile.timer
} > "$staging/installed-contract.sha256"
install -o root -g root -m 0600 "$staging/installed-contract.sha256" "$manifest"

systemctl daemon-reload
systemctl enable --now weltgewebe-production-reconcile.timer
systemctl start weltgewebe-production-reconcile.service

echo "production_reconciler=installed commit=$COMMIT build_user=$BUILD_USER manifest=$manifest"
