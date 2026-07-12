#!/usr/bin/env bash
set -euo pipefail
umask 077

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}
require_cmd() { command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"; }
sha256_file() { if command -v sha256sum > /dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }
read_version_field() { python3 "$REPO_DIR/scripts/lib/parse-version-json.py" "$1" | sed -n "${2}p"; }
run_cmd() { sh -c "$1"; }

REPO_DIR="${REPO_DIR:-$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." > /dev/null 2>&1 && pwd)}"
WEB_ARTIFACT_ARCHIVE="${WEB_ARTIFACT_ARCHIVE:-}"
WEB_ARTIFACT_SHA256="${WEB_ARTIFACT_SHA256:-}"
WEB_ARTIFACT_VERSION="${WEB_ARTIFACT_VERSION:-}"
WEB_ARTIFACT_COMMIT="${WEB_ARTIFACT_COMMIT:-}"
WEB_ROOT="${WEB_ROOT:-/opt/weltgewebe/apps/web/build}"
WEB_RELEASES_DIR="${WEB_RELEASES_DIR:-/opt/weltgewebe/apps/web/releases}"
WEB_RELEASE_RETENTION="${WEB_RELEASE_RETENTION:-5}"
PUBLIC_VERSION_URL="${PUBLIC_VERSION_URL:-}"
CADDY_VALIDATE_CMD="${CADDY_VALIDATE_CMD:-}"
CADDY_RELOAD_CMD="${CADDY_RELOAD_CMD:-}"

for cmd in gzip tar awk curl python3; do require_cmd "$cmd"; done
[[ -n "$WEB_ARTIFACT_ARCHIVE" && -f "$WEB_ARTIFACT_ARCHIVE" ]] || fail "WEB_ARTIFACT_ARCHIVE must name an existing archive"
[[ "$WEB_ARTIFACT_SHA256" =~ ^[0-9a-fA-F]{64}$ ]] || fail "WEB_ARTIFACT_SHA256 must be a 64-character digest"
[[ -n "$WEB_ARTIFACT_VERSION" && -n "$WEB_ARTIFACT_COMMIT" ]] || fail "expected artifact version and commit are required"
[[ -n "$PUBLIC_VERSION_URL" && -n "$CADDY_VALIDATE_CMD" && -n "$CADDY_RELOAD_CMD" ]] || fail "public readback, Caddy validation, and Caddy recreate commands are required"
case "$WEB_RELEASE_RETENTION" in '' | *[!0-9]*) fail "WEB_RELEASE_RETENTION must be a non-negative integer" ;; esac

actual_sha="$(sha256_file "$WEB_ARTIFACT_ARCHIVE")"
[[ "$actual_sha" == "$WEB_ARTIFACT_SHA256" ]] || fail "artifact sha256 mismatch"
gzip -t "$WEB_ARTIFACT_ARCHIVE" || fail "artifact gzip integrity test failed"

# Reject traversal, links and device nodes before extraction. Static builds need only files/directories.
python3 - "$WEB_ARTIFACT_ARCHIVE" << 'PY'
import pathlib, sys, tarfile
archive=sys.argv[1]
with tarfile.open(archive, 'r:gz') as tf:
    for member in tf.getmembers():
        path=pathlib.PurePosixPath(member.name)
        if path.is_absolute() or '..' in path.parts:
            raise SystemExit(f"unsafe archive path: {member.name}")
        if not (member.isfile() or member.isdir()):
            raise SystemExit(f"unsupported archive member: {member.name}")
PY

install -d -m 0755 "$WEB_RELEASES_DIR"
stage_dir="$(mktemp -d "${WEB_RELEASES_DIR}/.stage.XXXXXX")"
tmp_link="${WEB_ROOT}.tmp.$$"
previous_kind=absent
previous_target=""
previous_dir=""
cleanup() { rm -rf "$stage_dir" "$tmp_link"; }
trap cleanup EXIT

tar -xzf "$WEB_ARTIFACT_ARCHIVE" -C "$stage_dir" --no-same-owner --no-same-permissions
artifact_root="$stage_dir"
[[ -f "$artifact_root/index.html" ]] || { [[ -f "$stage_dir/build/index.html" ]] && artifact_root="$stage_dir/build"; }
version_json="$artifact_root/_app/version.json"
[[ -f "$artifact_root/index.html" && -f "$version_json" ]] || fail "artifact must contain index.html and _app/version.json"
artifact_version="$(read_version_field "$version_json" 1)"
artifact_build_id="$(read_version_field "$version_json" 2)"
artifact_commit="$(read_version_field "$version_json" 3)"
[[ "$artifact_version" == "$WEB_ARTIFACT_VERSION" ]] || fail "artifact version mismatch"
if [[ -n "$artifact_commit" ]]; then
  [[ "$artifact_commit" == "$WEB_ARTIFACT_COMMIT" ]] || fail "artifact commit mismatch"
else [[ "$WEB_ARTIFACT_VERSION" == "$WEB_ARTIFACT_COMMIT" ]] || fail "artifact lacks commit and version does not match expected commit"; fi

release_name="$artifact_version${artifact_build_id:+-$artifact_build_id}"
case "$release_name" in '' | *[!A-Za-z0-9._-]*) fail "artifact version/build id contains unsupported characters" ;; esac
release_dir="$WEB_RELEASES_DIR/$release_name"
[[ ! -e "$release_dir" ]] || fail "release directory already exists: $release_dir"
mv "$artifact_root" "$release_dir"
find "$release_dir" -type d -exec chmod 0755 {} +
find "$release_dir" -type f -exec chmod 0644 {} +

# Validate configuration before changing the bind-mount source.
run_cmd "$CADDY_VALIDATE_CMD" || fail "Caddy validation command failed"

if [[ -L "$WEB_ROOT" ]]; then
  previous_kind=symlink
  previous_target="$(readlink "$WEB_ROOT")"
elif [[ -d "$WEB_ROOT" ]]; then
  previous_kind=directory
  previous_dir="$WEB_RELEASES_DIR/pre-artifact-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  mv "$WEB_ROOT" "$previous_dir"
elif [[ -e "$WEB_ROOT" ]]; then
  fail "WEB_ROOT is neither a directory nor a symlink: $WEB_ROOT"
fi

rollback() {
  rm -f "$WEB_ROOT" "$tmp_link"
  case "$previous_kind" in
    symlink)
      ln -s "$previous_target" "$tmp_link"
      mv -Tf "$tmp_link" "$WEB_ROOT"
      ;;
    directory) [[ -d "$previous_dir" ]] && mv "$previous_dir" "$WEB_ROOT" ;;
  esac
  # A bind mount follows the old inode until Caddy is recreated.
  run_cmd "$CADDY_RELOAD_CMD" > /dev/null 2>&1 || true
}

ln -s "$release_dir" "$tmp_link"
mv -Tf "$tmp_link" "$WEB_ROOT"
if ! run_cmd "$CADDY_RELOAD_CMD"; then
  rollback
  fail "Caddy recreate command failed; previous web release restored"
fi

readback="$(mktemp)"
headers="$(mktemp)"
if ! curl -fsS -D "$headers" -o "$readback" "$PUBLIC_VERSION_URL"; then
  rollback
  fail "public version readback failed; previous web release restored"
fi
if ! grep -iq '^Cache-Control:.*no-store' "$headers"; then
  rollback
  fail "public version readback lacks no-store; previous web release restored"
fi
public_build="$(awk 'BEGIN{IGNORECASE=1} /^X-Weltgewebe-Build:/ {sub(/^[^:]+:[[:space:]]*/,""); sub(/\r$/,""); print; exit}' "$headers")"
public_version="$(read_version_field "$readback" 1)"
public_commit="$(read_version_field "$readback" 3)"
rm -f "$readback" "$headers"
[[ "$public_version" == "$WEB_ARTIFACT_VERSION" ]] || {
  rollback
  fail "public version mismatch; previous web release restored"
}
[[ -z "$public_commit" || "$public_commit" == "$WEB_ARTIFACT_COMMIT" ]] || {
  rollback
  fail "public commit mismatch; previous web release restored"
}
[[ "$public_build" == "$WEB_ARTIFACT_VERSION" || "$public_build" == "$WEB_ARTIFACT_COMMIT" ]] || {
  rollback
  fail "public build header mismatch; previous web release restored"
}

# Keep the current target and the newest older releases. Never follow or delete the active symlink target.
if ((WEB_RELEASE_RETENTION > 0)); then
  active="$(readlink -f "$WEB_ROOT")"
  mapfile -t old < <(find "$WEB_RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d ! -name '.stage.*' -printf '%T@ %p\n' | sort -nr | awk '{print $2}')
  kept=0
  for dir in "${old[@]}"; do
    [[ "$(readlink -f "$dir")" == "$active" ]] && continue
    kept=$((kept + 1))
    ((kept <= WEB_RELEASE_RETENTION)) || rm -rf "$dir"
  done
fi
printf 'Web artifact installed: %s\nWeb root now points to: %s\n' "$release_dir" "$(readlink "$WEB_ROOT")"
