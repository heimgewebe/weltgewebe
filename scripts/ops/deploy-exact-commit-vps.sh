#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_CHECKOUT="${WELTGEWEBE_SOURCE_CHECKOUT:-/opt/weltgewebe}"
RELEASE_ROOT="${WELTGEWEBE_RELEASE_ROOT:-/opt/weltgewebe-releases}"
RUNTIME_ENV="${WELTGEWEBE_RUNTIME_ENV:-/etc/weltgewebe/weltgewebe.env}"
STATE_ROOT="${WELTGEWEBE_DEPLOY_STATE_ROOT:-/var/lib/weltgewebe-main-reconciler}"
ARTIFACT_ROOT="$STATE_ROOT/artifacts"
FRONTEND_URL="${WELTGEWEBE_FRONTEND_VERSION_URL:-https://weltgewebe.net/_app/version.json}"
API_URL="${WELTGEWEBE_API_VERSION_URL:-https://weltgewebe.net/api/version}"
ARCHIVE_VALIDATOR="${WELTGEWEBE_ARCHIVE_VALIDATOR:-/usr/local/libexec/weltgewebe-validate-web-deploy-archive}"
LOCK_FILE="${STATE_ROOT}/deploy.lock"
readonly EX_TEMPFAIL=75

COMMIT=""
WEB_ARTIFACT=""
WEB_SHA256=""
api_headers=""
api_body_file=""
frontend_body_file=""
started_at=""
release_dir=""
api_commit=""
frontend_commit=""
last_observed_main=""
migration_completed_at=""
receipt_started=false
receipt_terminal=false

usage() {
  cat << 'EOF'
Usage: deploy-exact-commit-vps.sh \
  --commit <40-char-sha> \
  --web-artifact <absolute-path> \
  --web-sha256 <sha256>
EOF
}

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

run_release_deploy() {
  local scope="$1"
  local -a arguments=(--no-pull --force-build --no-build-web)
  case "$scope" in
    migration)
      arguments+=(--deploy-scope migration)
      ;;
    full)
      arguments+=(--with-caddy)
      ;;
    *)
      fail "unsupported release deployment scope: $scope"
      ;;
  esac
  DEPLOY_TARGET=vps ENV_FILE="$RUNTIME_ENV" \
    "$release_dir/scripts/weltgewebe-up" "${arguments[@]}"
}

require_command() {
  command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"
}

write_bounded_response() {
  local output="$1"
  local limit="$2"
  python3 -c '
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
limit = int(sys.argv[2])
data = sys.stdin.buffer.read(limit + 1)
if len(data) > limit:
    print(f"response exceeds byte limit: more than {limit} bytes", file=sys.stderr)
    raise SystemExit(1)
with path.open("wb") as handle:
    handle.write(data)
    handle.flush()
    os.fsync(handle.fileno())
' "$output" "$limit"
}

fetch_main() {
  git -C "$SOURCE_CHECKOUT" fetch --no-tags origin \
    "+refs/heads/main:refs/remotes/origin/main"
  git -C "$SOURCE_CHECKOUT" rev-parse refs/remotes/origin/main
}

write_deploy_receipt() {
  local result="$1"
  local completed_at="$2"
  local api_commit_value="$3"
  local frontend_commit_value="$4"
  local observed_main="$5"
  local receipt="$STATE_ROOT/receipts/$COMMIT.json"
  python3 - "$receipt" "$COMMIT" "$WEB_SHA256" "$started_at" "$completed_at" \
    "$api_commit_value" "$frontend_commit_value" "$observed_main" "$migration_completed_at" "$result" << 'PY'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "schema_version": 3,
    "environment": "production",
    "commit": sys.argv[2],
    "web_artifact_sha256": sys.argv[3],
    "started_at": sys.argv[4] or None,
    "completed_at": sys.argv[5] or None,
    "api_commit": sys.argv[6] or None,
    "frontend_commit": sys.argv[7] or None,
    "observed_main_after_deploy": sys.argv[8] or None,
    "migration_completed_at": sys.argv[9] or None,
    "result": sys.argv[10],
}
temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
with temporary.open("w", encoding="utf-8") as handle:
    json.dump(payload, handle, sort_keys=True, indent=2)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())
os.replace(temporary, path)
directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(directory_fd)
finally:
    os.close(directory_fd)
PY
}

cleanup() {
  local rc=$?
  trap - EXIT
  if ((rc != 0)) && [[ "$receipt_started" == true && "$receipt_terminal" == false ]]; then
    completed_at="$(date --utc +%Y-%m-%dT%H:%M:%SZ 2> /dev/null || true)"
    write_deploy_receipt \
      "failed" "$completed_at" "$api_commit" "$frontend_commit" "$last_observed_main" || true
  fi
  local temporary_path
  for temporary_path in "$api_headers" "$api_body_file" "$frontend_body_file"; do
    if [[ -n "$temporary_path" && -f "$temporary_path" && ! -L "$temporary_path" ]]; then
      rm -f -- "$temporary_path"
    fi
  done
  exit "$rc"
}
trap cleanup EXIT

validate_release_tree() {
  local line
  if ! git -C "$release_dir" diff --quiet --no-ext-diff --ignore-submodules -- ||
    ! git -C "$release_dir" diff --cached --quiet --no-ext-diff --ignore-submodules --; then
    fail "release contains modified tracked files"
  fi
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    case "$line" in
      "?? build/" | "?? apps/web/build/") ;;
      *) fail "release contains unexpected state: $line" ;;
    esac
  done < <(git -C "$release_dir" status --porcelain --untracked-files=normal)
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit)
      [[ $# -ge 2 ]] || fail "--commit requires a value"
      COMMIT="$2"
      shift 2
      ;;
    --web-artifact)
      [[ $# -ge 2 ]] || fail "--web-artifact requires a value"
      WEB_ARTIFACT="$2"
      shift 2
      ;;
    --web-sha256)
      [[ $# -ge 2 ]] || fail "--web-sha256 requires a value"
      WEB_SHA256="$2"
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *) fail "unknown argument: $1" ;;
  esac
done

[[ "$EUID" -eq 0 ]] || fail "this helper must run as root"
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "commit must be a full lowercase SHA-1"
[[ "$WEB_SHA256" =~ ^[0-9a-f]{64}$ ]] || fail "web artifact SHA-256 is invalid"
[[ "$WEB_ARTIFACT" == /* ]] || fail "web artifact path must be absolute"
[[ -f "$WEB_ARTIFACT" && ! -L "$WEB_ARTIFACT" ]] || fail "web artifact is missing or not a regular file"
[[ -d "$SOURCE_CHECKOUT" && ! -L "$SOURCE_CHECKOUT" ]] || fail "source checkout is unsafe: $SOURCE_CHECKOUT"
[[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]] || fail "runtime environment is missing or unsafe: $RUNTIME_ENV"
[[ -x "$ARCHIVE_VALIDATOR" ]] || fail "archive validator is missing or not executable: $ARCHIVE_VALIDATOR"

for command_name in git docker curl jq sha256sum tar flock install rm python3 awk date realpath readlink ln stat find grep chmod chown mktemp; do
  require_command "$command_name"
done

install -d -o root -g root -m 0711 "$STATE_ROOT"
install -d -o root -g root -m 0700 "$STATE_ROOT/receipts" "$ARTIFACT_ROOT"
install -d -o root -g root -m 0755 "$RELEASE_ROOT"

artifact_real="$(realpath "$WEB_ARTIFACT")"
artifact_root_real="$(realpath "$ARTIFACT_ROOT")"
case "$artifact_real" in
  "$artifact_root_real"/*) ;;
  *) fail "web artifact escaped the root-owned artifact directory" ;;
esac
[[ "$(stat --format=%u "$artifact_real")" == "0" ]] || fail "web artifact is not root-owned"
artifact_mode="$(stat --format=%a "$artifact_real")"
(((8#$artifact_mode & 022) == 0)) || fail "web artifact is group- or world-writable"
[[ "$(stat --format=%h "$artifact_real")" == "1" ]] || fail "web artifact has unexpected hard links"
[[ "$(stat --format=%u "$RUNTIME_ENV")" == "0" ]] || fail "runtime environment is not root-owned"
runtime_mode="$(stat --format=%a "$RUNTIME_ENV")"
(((8#$runtime_mode & 022) == 0)) || fail "runtime environment is group- or world-writable"

[[ "$(stat --format=%u "$SOURCE_CHECKOUT")" == "0" ]] || fail "source checkout is not root-owned"
git_common_dir="$(git -C "$SOURCE_CHECKOUT" rev-parse --git-common-dir)"
[[ "$git_common_dir" == /* ]] || git_common_dir="$SOURCE_CHECKOUT/$git_common_dir"
git_common_dir="$(readlink -f "$git_common_dir")"
unsafe_git_path="$(find "$git_common_dir" -xdev \( ! -user root -o -perm /022 \) -print -quit)"
[[ -z "$unsafe_git_path" ]] || fail "Git object store is not entirely root-owned and non-writable by group/world: $unsafe_git_path"
exec 9> "$LOCK_FILE"
flock -n 9 || fail "another production deployment is already active"

actual_artifact_sha="$(sha256sum "$artifact_real" | awk '{print $1}')"
[[ "$actual_artifact_sha" == "$WEB_SHA256" ]] ||
  fail "web artifact checksum mismatch: expected $WEB_SHA256, got $actual_artifact_sha"

remote_main="$(fetch_main)"
[[ "$remote_main" == "$COMMIT" ]] ||
  fail "requested commit is no longer current origin/main: expected $COMMIT, got $remote_main"
git -C "$SOURCE_CHECKOUT" cat-file -e "$COMMIT^{commit}"

release_dir="$RELEASE_ROOT/$COMMIT"
if [[ -e "$release_dir" ]]; then
  [[ -d "$release_dir" && ! -L "$release_dir" ]] || fail "release path is not a directory"
  release_head="$(git -C "$release_dir" rev-parse HEAD)"
  [[ "$release_head" == "$COMMIT" ]] ||
    fail "existing release directory points to $release_head instead of $COMMIT"
else
  git -C "$SOURCE_CHECKOUT" worktree add --detach "$release_dir" "$COMMIT"
fi

release_real="$(realpath "$release_dir")"
release_root_real="$(realpath "$RELEASE_ROOT")"
case "$release_real" in
  "$release_root_real"/*) ;;
  *) fail "release directory escaped the configured release root" ;;
esac
[[ "$(stat --format=%u "$release_dir")" == "0" ]] || fail "release directory is not root-owned"
release_mode="$(stat --format=%a "$release_dir")"
(((8#$release_mode & 022) == 0)) || fail "release directory is group- or world-writable"
[[ -d "$release_dir/apps/web" && ! -L "$release_dir/apps/web" ]] || fail "release web directory is unsafe"
[[ -f "$release_dir/scripts/weltgewebe-up" && ! -L "$release_dir/scripts/weltgewebe-up" ]] || fail "release deploy entrypoint is unsafe"
[[ -x "$release_dir/scripts/weltgewebe-up" ]] || fail "release deploy entrypoint is not executable"
validate_release_tree

basemap_source="$SOURCE_CHECKOUT/build/basemap"
[[ -d "$basemap_source" && ! -L "$basemap_source" ]] || fail "persistent basemap artifacts are missing or unsafe"
basemap_real="$(realpath "$basemap_source")"
source_real="$(realpath "$SOURCE_CHECKOUT")"
[[ "$basemap_real" == "$source_real/build/basemap" ]] || fail "basemap source escaped the production checkout"
[[ "$(stat --format=%u "$basemap_real")" == "0" ]] || fail "basemap root is not root-owned"
unsafe_basemap_path="$(find "$basemap_real" -xdev \( -type f -o -type d \) \( ! -user root -o -perm /022 \) -print -quit)"
[[ -z "$unsafe_basemap_path" ]] || fail "basemap files or directories are not root-owned and read-only: $unsafe_basemap_path"
while IFS= read -r -d '' basemap_link; do
  link_target="$(realpath "$basemap_link")" || fail "basemap link is broken: $basemap_link"
  case "$link_target" in
    "$basemap_real"/*) ;;
    *) fail "basemap link escapes the canonical data root: $basemap_link" ;;
  esac
  [[ -f "$link_target" ]] || fail "basemap link does not target a regular file: $basemap_link"
done < <(find "$basemap_real" -xdev -type l -print0)
install -d -m 0755 "$release_dir/build"
if [[ -e "$release_dir/build/basemap" || -L "$release_dir/build/basemap" ]]; then
  [[ -L "$release_dir/build/basemap" ]] || fail "release basemap path is not the expected link"
  [[ "$(realpath "$release_dir/build/basemap")" == "$basemap_real" ]] || fail "release basemap link targets unexpected data"
else
  ln -s "$basemap_real" "$release_dir/build/basemap"
fi
validate_release_tree

"$ARCHIVE_VALIDATOR" "$artifact_real"
validated_artifact_sha="$(sha256sum "$artifact_real" | awk '{print $1}')"
[[ "$validated_artifact_sha" == "$WEB_SHA256" ]] || fail "web artifact changed during validation"
rm -rf -- "$release_dir/apps/web/build"
tar --no-same-owner --no-same-permissions -xzf "$artifact_real" -C "$release_dir/apps/web"
chown -R --no-dereference root:root "$release_dir/apps/web/build"
find "$release_dir/apps/web/build" -type d -exec chmod 0755 {} +
find "$release_dir/apps/web/build" -type f -exec chmod 0644 {} +
validate_release_tree

artifact_commit="$(jq -er '.commit' "$release_dir/apps/web/build/_app/version.json")"
artifact_version="$(jq -er '.version' "$release_dir/apps/web/build/_app/version.json")"
[[ "$artifact_commit" == "$COMMIT" ]] || fail "web artifact commit does not match target"
[[ "$artifact_version" == "${COMMIT:0:8}" ]] || fail "web artifact short version does not match target"
[[ -s "$release_dir/apps/web/build/index.html" ]] || fail "web artifact has no index.html"

remote_main="$(fetch_main)"
last_observed_main="$remote_main"
[[ "$remote_main" == "$COMMIT" ]] ||
  fail "origin/main advanced immediately before deployment: expected $COMMIT, got $remote_main"

started_at="$(date --utc +%Y-%m-%dT%H:%M:%SZ)"
write_deploy_receipt "deploying" "" "" "" "$remote_main"
receipt_started=true

# Apply all pending embedded migrations through the existing bounded API-only
# path before the full stack is reconciled. The migration scope restores the
# API to verify-applied itself and leaves PostgreSQL, NATS and any existing
# Caddy container untouched. This is intentionally idempotent when no migration
# is pending. The receipt records completion for diagnosis, but never authorizes
# a later retry to skip database verification.
echo "production_deployment_phase=migration state=starting commit=$COMMIT" >&2
run_release_deploy migration
migration_completed_at="$(date --utc +%Y-%m-%dT%H:%M:%SZ)"
write_deploy_receipt "deploying" "" "" "" "$last_observed_main"
echo "production_deployment_phase=migration state=completed commit=$COMMIT checking_origin_main=true" >&2

remote_main="$(fetch_main)"
last_observed_main="$remote_main"
if [[ "$remote_main" != "$COMMIT" ]]; then
  completed_at="$(date --utc +%Y-%m-%dT%H:%M:%SZ)"
  write_deploy_receipt "superseded_after_migration" "$completed_at" "" "" "$remote_main"
  receipt_terminal=true
  echo "production_deployment=superseded_after_migration commit=$COMMIT current=$remote_main" >&2
  exit "$EX_TEMPFAIL"
fi

echo "production_deployment_phase=full state=starting commit=$COMMIT" >&2
run_release_deploy full
echo "production_deployment_phase=full state=completed commit=$COMMIT" >&2

api_headers="$(mktemp "$STATE_ROOT/.api-headers.XXXXXX")"
api_body_file="$(mktemp "$STATE_ROOT/.api-body.XXXXXX")"
frontend_body_file="$(mktemp "$STATE_ROOT/.frontend-body.XXXXXX")"
if ! curl --fail --silent --show-error --max-redirs 0 --connect-timeout 5 --max-time 15 --max-filesize 1048576 --retry 2 --retry-all-errors -D "$api_headers" "$API_URL" |
  write_bounded_response "$api_body_file" 1048576; then
  fail "live API readback failed or exceeded the byte limit"
fi
if ! curl --fail --silent --show-error --max-redirs 0 --connect-timeout 5 --max-time 15 --max-filesize 1048576 --retry 2 --retry-all-errors "$FRONTEND_URL" |
  write_bounded_response "$frontend_body_file" 1048576; then
  fail "live frontend readback failed or exceeded the byte limit"
fi
api_commit="$(jq -er '.commit' "$api_body_file")"
frontend_commit="$(jq -er '.commit' "$frontend_body_file")"
[[ "$api_commit" == "$COMMIT" ]] || fail "live API serves $api_commit instead of $COMMIT"
[[ "$frontend_commit" == "$COMMIT" ]] || fail "live frontend serves $frontend_commit instead of $COMMIT"
api_header="$(awk -F':' 'tolower($1)=="x-weltgewebe-api-build" {gsub(/^[ \t]+|[ \t\r]+$/, "", $2); print $2}' "$api_headers")"
edge_header="$(awk -F':' 'tolower($1)=="x-weltgewebe-build" {gsub(/^[ \t]+|[ \t\r]+$/, "", $2); print $2}' "$api_headers")"
[[ "$api_header" == "$COMMIT" ]] || fail "live API build header does not match target commit"
[[ "$edge_header" == "${COMMIT:0:8}" ]] || fail "live edge build header does not match target commit"

if [[ -L "$STATE_ROOT/current-release" ]]; then
  previous_release="$(readlink -f "$STATE_ROOT/current-release")"
  case "$previous_release" in
    "$release_root_real"/*) ln -sfn "$previous_release" "$STATE_ROOT/previous-release" ;;
    *) fail "current release marker escapes release root" ;;
  esac
fi
ln -sfn "$release_real" "$STATE_ROOT/current-release"

post_deploy_main="$(fetch_main)"
last_observed_main="$post_deploy_main"
completed_at="$(date --utc +%Y-%m-%dT%H:%M:%SZ)"
if [[ "$post_deploy_main" != "$COMMIT" ]]; then
  write_deploy_receipt "superseded_after_deploy" "$completed_at" "$api_commit" "$frontend_commit" "$post_deploy_main"
  receipt_terminal=true
  echo "production_deployment=superseded commit=$COMMIT current=$post_deploy_main" >&2
  exit "$EX_TEMPFAIL"
fi

write_deploy_receipt "verified" "$completed_at" "$api_commit" "$frontend_commit" "$post_deploy_main"
receipt_terminal=true
ln -sfn "receipts/$COMMIT.json" "$STATE_ROOT/current.json"
echo "production_deployment=verified commit=$COMMIT receipt=$STATE_ROOT/receipts/$COMMIT.json"
