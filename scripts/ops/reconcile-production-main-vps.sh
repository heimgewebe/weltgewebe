#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_CHECKOUT="${WELTGEWEBE_SOURCE_CHECKOUT:-/opt/weltgewebe}"
RUNTIME_ENV="${WELTGEWEBE_RUNTIME_ENV:-/etc/weltgewebe/weltgewebe.env}"
STATE_ROOT="${WELTGEWEBE_DEPLOY_STATE_ROOT:-/var/lib/weltgewebe-main-reconciler}"
BUILD_USER="${WELTGEWEBE_BUILD_USER:-alex}"
FRONTEND_URL="${WELTGEWEBE_FRONTEND_VERSION_URL:-https://weltgewebe.net/_app/version.json}"
API_URL="${WELTGEWEBE_API_VERSION_URL:-https://weltgewebe.net/api/version}"
NODE_BUILD_IMAGE="${WELTGEWEBE_NODE_BUILD_IMAGE:-docker.io/library/node@sha256:8898f8ed3c0126667837b678979b4ed83306c856a1227c8bf5f5f77740c25cd6}"
DEPLOY_HELPER="${WELTGEWEBE_DEPLOY_HELPER:-/usr/local/libexec/weltgewebe-deploy-exact-commit}"
LIVE_VERIFIER="${WELTGEWEBE_LIVE_VERIFIER:-/usr/local/libexec/weltgewebe-verify-public-release}"
ARCHIVE_VALIDATOR="${WELTGEWEBE_ARCHIVE_VALIDATOR:-/usr/local/libexec/weltgewebe-validate-web-deploy-archive}"
LOCK_FILE="$STATE_ROOT/reconcile.lock"
ARTIFACT_ROOT="$STATE_ROOT/artifacts"
RECEIPT_ROOT="$STATE_ROOT/reconcile-receipts"
temporary_artifact=""
temporary_source=""

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"
}

cleanup() {
  local rc=$?
  trap - EXIT
  if [[ -n "$temporary_artifact" && -f "$temporary_artifact" && ! -L "$temporary_artifact" ]]; then
    rm -f -- "$temporary_artifact"
  fi
  if [[ -n "$temporary_source" && -f "$temporary_source" && ! -L "$temporary_source" ]]; then
    rm -f -- "$temporary_source"
  fi
  exit "$rc"
}
trap cleanup EXIT

[[ "$EUID" -eq 0 ]] || fail "production reconciler must run as root"
[[ -d "$SOURCE_CHECKOUT/.git" ]] || fail "source checkout is not a Git repository: $SOURCE_CHECKOUT"
[[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]] || fail "runtime environment is missing or unsafe: $RUNTIME_ENV"
[[ -x "$DEPLOY_HELPER" ]] || fail "deploy helper is not installed: $DEPLOY_HELPER"
[[ -x "$LIVE_VERIFIER" ]] || fail "live verifier is not installed: $LIVE_VERIFIER"
[[ -x "$ARCHIVE_VALIDATOR" ]] || fail "archive validator is not installed: $ARCHIVE_VALIDATOR"
getent passwd "$BUILD_USER" > /dev/null || fail "build user does not exist: $BUILD_USER"

for command_name in git docker sha256sum flock install id rm mv awk getent chmod ln; do
  require_command "$command_name"
done

install -d -m 0711 "$STATE_ROOT"
install -d -m 0700 "$ARTIFACT_ROOT" "$RECEIPT_ROOT"
exec 9> "$LOCK_FILE"
if ! flock -n 9; then
  echo "production_reconcile=skipped reason=already-running"
  exit 0
fi

# Fetch only. The legacy checkout may contain operational changes and backup
# files. It is never switched, reset, cleaned, merged, or fast-forwarded.
git -C "$SOURCE_CHECKOUT" fetch --no-tags origin \
  "+refs/heads/main:refs/remotes/origin/main"
target_commit="$(git -C "$SOURCE_CHECKOUT" rev-parse refs/remotes/origin/main)"
[[ "$target_commit" =~ ^[0-9a-f]{40}$ ]] || fail "origin/main did not resolve to a full commit"

initial_receipt="$RECEIPT_ROOT/observed-$target_commit.json"
if "$LIVE_VERIFIER" \
  --expected-commit "$target_commit" \
  --frontend-url "$FRONTEND_URL" \
  --api-url "$API_URL" \
  --output "$initial_receipt"; then
  echo "production_reconcile=noop commit=$target_commit"
  exit 0
fi

build_uid="$(id -u "$BUILD_USER")"
build_gid="$(id -g "$BUILD_USER")"
[[ "$build_uid" =~ ^[0-9]+$ && "$build_gid" =~ ^[0-9]+$ ]] || fail "build user IDs are invalid"
commit_epoch="$(git -C "$SOURCE_CHECKOUT" show -s --format=%ct "$target_commit")"
[[ "$commit_epoch" =~ ^[0-9]+$ ]] || fail "target commit timestamp is invalid"

# Export the reviewed commit as a root-owned, read-only input. Merged package
# scripts never receive a writable release checkout or host source tree.
source_archive="$ARTIFACT_ROOT/source-$target_commit.tar"
temporary_source="$source_archive.tmp.$$"
git -C "$SOURCE_CHECKOUT" archive --format=tar --output="$temporary_source" "$target_commit"
mv "$temporary_source" "$source_archive"
temporary_source=""
chmod 0444 "$source_archive"

# The build workspace is container tmpfs. The only bytes crossing back to the
# host are the gzip stream on stdout; package-manager logs are redirected to
# stderr. A host file-size limit bounds the stream before archive validation.
temporary_artifact="$ARTIFACT_ROOT/.web-$target_commit.$$.tmp"
(
  ulimit -f 262144
  docker run --rm \
    --platform linux/amd64 \
    --user "$build_uid:$build_gid" \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --pids-limit 512 \
    --memory 2g \
    --cpus 2 \
    --read-only \
    --tmpfs /tmp:rw,exec,nosuid,nodev,size=1g,mode=1777 \
    --tmpfs /workspace:rw,exec,nosuid,nodev,size=3g,mode=1777 \
    --network bridge \
    --mount "type=bind,src=$source_archive,dst=/source.tar,readonly" \
    --workdir /workspace \
    --env HOME=/tmp/home \
    --env COREPACK_HOME=/tmp/corepack \
    --env npm_config_cache=/tmp/npm-cache \
    --env CI=true \
    --env SOURCE_DATE_EPOCH="$commit_epoch" \
    --env GIT_COMMIT_SHA="$target_commit" \
    --env PUBLIC_BASEMAP_MODE=local-sovereign \
    "$NODE_BUILD_IMAGE" \
    sh -lc '{ /usr/bin/tar -xf /source.tar -C /workspace && cd /workspace/apps/web && mkdir -p "$HOME" "$COREPACK_HOME" "$npm_config_cache" /tmp/bin && corepack enable --install-directory /tmp/bin pnpm && export PATH="/tmp/bin:$PATH" && pnpm install --frozen-lockfile && pnpm build; } >&2 && exec /usr/bin/tar --sort=name --mtime="@$SOURCE_DATE_EPOCH" --owner=0 --group=0 --numeric-owner -czf - build'
) > "$temporary_artifact"

[[ -s "$temporary_artifact" && ! -L "$temporary_artifact" ]] || fail "frontend build stream is missing or unsafe"
"$ARCHIVE_VALIDATOR" "$temporary_artifact"
artifact="$ARTIFACT_ROOT/web-$target_commit.tar.gz"
mv "$temporary_artifact" "$artifact"
temporary_artifact=""
artifact_sha="$(sha256sum "$artifact" | awk '{print $1}')"
[[ "$artifact_sha" =~ ^[0-9a-f]{64}$ ]] || fail "frontend artifact hash is invalid"

# A build is never deployed after main advanced while dependencies compiled.
git -C "$SOURCE_CHECKOUT" fetch --no-tags origin \
  "+refs/heads/main:refs/remotes/origin/main"
current_main="$(git -C "$SOURCE_CHECKOUT" rev-parse refs/remotes/origin/main)"
if [[ "$current_main" != "$target_commit" ]]; then
  echo "production_reconcile=deferred built=$target_commit current=$current_main"
  exit 0
fi

"$DEPLOY_HELPER" \
  --commit "$target_commit" \
  --web-artifact "$artifact" \
  --web-sha256 "$artifact_sha"

final_receipt="$RECEIPT_ROOT/$target_commit.json"
"$LIVE_VERIFIER" \
  --expected-commit "$target_commit" \
  --frontend-url "$FRONTEND_URL" \
  --api-url "$API_URL" \
  --wait-seconds 120 \
  --poll-seconds 5 \
  --output "$final_receipt"
ln -sfn "reconcile-receipts/$target_commit.json" "$STATE_ROOT/reconcile-current.json"
echo "production_reconcile=verified commit=$target_commit artifact_sha256=$artifact_sha receipt=$final_receipt"
