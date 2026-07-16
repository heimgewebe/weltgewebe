#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
BUILD_USER="${WELTGEWEBE_BUILD_USER:-alex}"

[[ "$EUID" -eq 0 ]] || {
  echo "ERROR: install-production-reconciler.sh must run as root" >&2
  exit 1
}
getent passwd "$BUILD_USER" > /dev/null || {
  echo "ERROR: build user does not exist: $BUILD_USER" >&2
  exit 1
}

install -d -m 0755 /usr/local/libexec
install -m 0755 "$REPO_DIR/scripts/ops/deploy-exact-commit-vps.sh" \
  /usr/local/libexec/weltgewebe-deploy-exact-commit
install -m 0755 "$REPO_DIR/scripts/ops/reconcile-production-main-vps.sh" \
  /usr/local/libexec/weltgewebe-reconcile-production-main
install -m 0755 "$REPO_DIR/scripts/ops/validate_web_deploy_archive.py" \
  /usr/local/libexec/weltgewebe-validate-web-deploy-archive
install -m 0755 "$REPO_DIR/scripts/ops/verify_public_release_commit.py" \
  /usr/local/libexec/weltgewebe-verify-public-release

install -m 0644 "$REPO_DIR/infra/systemd/system/weltgewebe-production-reconcile.service" \
  /etc/systemd/system/weltgewebe-production-reconcile.service
install -m 0644 "$REPO_DIR/infra/systemd/system/weltgewebe-production-reconcile.timer" \
  /etc/systemd/system/weltgewebe-production-reconcile.timer

install -d -o root -g root -m 0711 /var/lib/weltgewebe-main-reconciler
install -d -o root -g root -m 0700 \
  /var/lib/weltgewebe-main-reconciler/artifacts \
  /var/lib/weltgewebe-main-reconciler/receipts \
  /var/lib/weltgewebe-main-reconciler/reconcile-receipts
install -d -o root -g root -m 0755 /opt/weltgewebe-releases

systemctl daemon-reload
systemctl enable --now weltgewebe-production-reconcile.timer
systemctl start weltgewebe-production-reconcile.service

echo "production_reconciler=installed build_user=$BUILD_USER"
