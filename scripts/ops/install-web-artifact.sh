#!/usr/bin/env bash
set -euo pipefail
umask 077

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}
warn() { printf 'WARNING: %s\n' "$*" >&2; }
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
WEB_INSTALL_LOCK_WAIT_SECONDS="${WEB_INSTALL_LOCK_WAIT_SECONDS:-0}"
PUBLIC_VERSION_URL="${PUBLIC_VERSION_URL:-}"
CADDY_VALIDATE_CMD="${CADDY_VALIDATE_CMD:-}"
CADDY_RELOAD_CMD="${CADDY_RELOAD_CMD:-}"
PUBLIC_READBACK_ATTEMPTS="${PUBLIC_READBACK_ATTEMPTS:-30}"
PUBLIC_READBACK_TOTAL_SECONDS="${PUBLIC_READBACK_TOTAL_SECONDS:-30}"
PUBLIC_READBACK_INTERVAL_SECONDS="${PUBLIC_READBACK_INTERVAL_SECONDS:-1}"
PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS="${PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS:-2}"
PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS="${PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS:-4}"

for cmd in gzip tar awk curl python3 sleep flock realpath stat diff find sort sed date grep readlink dirname mv ln rm chmod install mktemp; do require_cmd "$cmd"; done
[[ -n "$WEB_ARTIFACT_ARCHIVE" && -f "$WEB_ARTIFACT_ARCHIVE" ]] || fail "WEB_ARTIFACT_ARCHIVE must name an existing archive"
[[ "$WEB_ARTIFACT_SHA256" =~ ^[0-9a-fA-F]{64}$ ]] || fail "WEB_ARTIFACT_SHA256 must be a 64-character digest"
[[ -n "$WEB_ARTIFACT_VERSION" && -n "$WEB_ARTIFACT_COMMIT" ]] || fail "expected artifact version and commit are required"
[[ -n "$PUBLIC_VERSION_URL" && -n "$CADDY_VALIDATE_CMD" && -n "$CADDY_RELOAD_CMD" ]] || fail "public readback, Caddy validation, and Caddy recreate commands are required"
case "$WEB_RELEASE_RETENTION" in '' | *[!0-9]*) fail "WEB_RELEASE_RETENTION must be a non-negative integer" ;; esac
case "$WEB_INSTALL_LOCK_WAIT_SECONDS" in '' | *[!0-9]*) fail "WEB_INSTALL_LOCK_WAIT_SECONDS must be a non-negative integer" ;; esac
case "$PUBLIC_READBACK_ATTEMPTS" in '' | *[!0-9]* | 0) fail "PUBLIC_READBACK_ATTEMPTS must be a positive integer" ;; esac
case "$PUBLIC_READBACK_TOTAL_SECONDS" in '' | *[!0-9]* | 0) fail "PUBLIC_READBACK_TOTAL_SECONDS must be a positive integer" ;; esac
case "$PUBLIC_READBACK_INTERVAL_SECONDS" in '' | *[!0-9]*) fail "PUBLIC_READBACK_INTERVAL_SECONDS must be a non-negative integer" ;; esac
case "$PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS" in '' | *[!0-9]* | 0) fail "PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS must be a positive integer" ;; esac
case "$PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS" in '' | *[!0-9]* | 0) fail "PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS must be a positive integer" ;; esac
((PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS <= PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS)) || fail "public readback connect timeout must not exceed request timeout"
case "$WEB_RELEASES_DIR" in /*) ;; *) fail "WEB_RELEASES_DIR must be an absolute path" ;; esac
case "$WEB_ROOT" in /*) ;; *) fail "WEB_ROOT must be an absolute path" ;; esac
[[ "$WEB_RELEASES_DIR" != / && "$WEB_ROOT" != / ]] || fail "web release and root paths must not be filesystem root"

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

[[ ! -L "$WEB_RELEASES_DIR" ]] || fail "WEB_RELEASES_DIR must not be a symlink"
install -d -m 0755 "$WEB_RELEASES_DIR"
WEB_RELEASES_DIR="$(realpath -e -- "$WEB_RELEASES_DIR")"
[[ "$WEB_RELEASES_DIR" != / ]] || fail "resolved WEB_RELEASES_DIR must not be filesystem root"
web_root_normalized="$(realpath -ms -- "$WEB_ROOT")"
case "$web_root_normalized/" in "$WEB_RELEASES_DIR"/*) fail "WEB_ROOT must remain outside WEB_RELEASES_DIR" ;; esac
[[ -d "$(dirname -- "$WEB_ROOT")" ]] || fail "WEB_ROOT parent directory must already exist"

lock_path="$WEB_RELEASES_DIR/.install.lock"
exec {web_install_lock_fd}> "$lock_path"
if ! flock -w "$WEB_INSTALL_LOCK_WAIT_SECONDS" "$web_install_lock_fd"; then
  fail "another web artifact installation is active"
fi

stage_dir="$(mktemp -d "${WEB_RELEASES_DIR}/.stage.XXXXXX")"
tmp_link="${WEB_ROOT}.tmp.$$"
previous_kind=absent
previous_target=""
previous_dir=""
readback=""
headers=""
release_dir=""
release_identity=""
release_created=0
release_reused=0
switched=0
remove_created_release() {
  ((release_created == 1)) || return 0
  if [[ ! -d "$release_dir" || -L "$release_dir" ]]; then
    warn "refusing to remove changed release path during cleanup: $release_dir"
    return 1
  fi
  current_identity="$(stat -Lc '%d:%i' -- "$release_dir" 2> /dev/null || true)"
  if [[ -z "$current_identity" || "$current_identity" != "$release_identity" ]]; then
    warn "refusing to remove release whose filesystem identity changed: $release_dir"
    return 1
  fi
  resolved_release="$(realpath -e -- "$release_dir" 2> /dev/null || true)"
  if [[ -z "$resolved_release" || "$(dirname -- "$resolved_release")" != "$WEB_RELEASES_DIR" ]]; then
    warn "refusing to remove release outside the canonical release directory: $release_dir"
    return 1
  fi
  rm -rf --one-file-system -- "$release_dir"
  release_created=0
}

cleanup() {
  [[ -z "$stage_dir" ]] || rm -rf -- "$stage_dir"
  rm -f -- "$tmp_link"
  [[ -z "$readback" ]] || rm -f -- "$readback"
  [[ -z "$headers" ]] || rm -f -- "$headers"
  if ((release_created == 1 && switched == 0)); then
    remove_created_release || true
  fi
}
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
else
  [[ "$WEB_ARTIFACT_VERSION" == "$WEB_ARTIFACT_COMMIT" ]] || fail "artifact lacks commit and version does not match expected commit"
fi

release_name="$artifact_version${artifact_build_id:+-$artifact_build_id}"
case "$release_name" in '' | *[!A-Za-z0-9._-]*) fail "artifact version/build id contains unsupported characters" ;; esac
case "$release_name" in [A-Za-z0-9]*) ;; *) fail "artifact release name must begin with an alphanumeric character" ;; esac
release_dir="$WEB_RELEASES_DIR/$release_name"
if [[ -e "$release_dir" || -L "$release_dir" ]]; then
  [[ -d "$release_dir" && ! -L "$release_dir" ]] || fail "existing release path is not a real directory: $release_dir"
  if ! diff -qr --no-dereference -- "$artifact_root" "$release_dir" > /dev/null; then
    fail "existing release directory differs from the supplied artifact: $release_dir"
  fi
  release_reused=1
  rm -rf -- "$stage_dir"
  stage_dir=""
else
  mv -- "$artifact_root" "$release_dir"
  release_created=1
  release_identity="$(stat -Lc '%d:%i' -- "$release_dir")"
  find "$release_dir" -type d -exec chmod 0755 {} +
  find "$release_dir" -type f -exec chmod 0644 {} +
fi

# Validate configuration before changing the bind-mount source.
if ! run_cmd "$CADDY_VALIDATE_CMD"; then
  if ((release_created == 0)); then
    fail "Caddy validation command failed; existing release left unchanged"
  fi
  if remove_created_release; then
    fail "Caddy validation command failed; newly staged release removed"
  fi
  fail "Caddy validation command failed and staged release cleanup was incomplete"
fi

current_target=""
if [[ -L "$WEB_ROOT" ]]; then
  previous_kind=symlink
  previous_target="$(readlink "$WEB_ROOT")"
  current_target="$(readlink -f "$WEB_ROOT" 2> /dev/null || true)"
elif [[ -d "$WEB_ROOT" ]]; then
  previous_kind=directory
  previous_dir="$WEB_RELEASES_DIR/pre-artifact-$(date -u +%Y%m%dT%H%M%SZ)-$$"
elif [[ -e "$WEB_ROOT" ]]; then
  fail "WEB_ROOT is neither a directory nor a symlink: $WEB_ROOT"
fi

rollback() {
  rollback_failed=0
  if ((switched == 1)); then
    active_now="$(readlink -f "$WEB_ROOT" 2> /dev/null || true)"
    if [[ "$active_now" != "$release_dir" ]]; then
      warn "refusing to overwrite WEB_ROOT because its target changed during rollback"
      rollback_failed=1
    else
      rm -f -- "$WEB_ROOT" "$tmp_link"
      case "$previous_kind" in
        symlink)
          ln -s -- "$previous_target" "$tmp_link"
          mv -Tf -- "$tmp_link" "$WEB_ROOT"
          ;;
        directory)
          if [[ -d "$previous_dir" ]]; then
            mv -- "$previous_dir" "$WEB_ROOT"
          else
            warn "previous web directory is unavailable during rollback"
            rollback_failed=1
          fi
          ;;
      esac
      # A bind mount follows the old inode until Caddy is recreated.
      if ! run_cmd "$CADDY_RELOAD_CMD" > /dev/null 2>&1; then
        warn "Caddy recreate failed while restoring the previous web release"
        rollback_failed=1
      fi
      switched=0
    fi
  fi
  remove_created_release || rollback_failed=1
  return "$rollback_failed"
}

if ((release_reused == 1)) && [[ "$current_target" == "$release_dir" ]]; then
  printf 'Web release already active; validating public readback: %s\n' "$release_dir"
else
  [[ ! -e "$tmp_link" && ! -L "$tmp_link" ]] || fail "temporary web-root link already exists: $tmp_link"
  ln -s -- "$release_dir" "$tmp_link"
  if [[ "$previous_kind" == directory ]]; then
    mv -- "$WEB_ROOT" "$previous_dir"
  fi
  if ! mv -Tf -- "$tmp_link" "$WEB_ROOT"; then
    if [[ "$previous_kind" == directory && ! -e "$WEB_ROOT" && -d "$previous_dir" ]]; then
      mv -- "$previous_dir" "$WEB_ROOT" || warn "failed to restore previous web directory after switch failure"
    fi
    fail "atomic web-root switch failed"
  fi
  switched=1
  if ! run_cmd "$CADDY_RELOAD_CMD"; then
    if rollback; then
      fail "Caddy recreate command failed; previous web release restored"
    fi
    fail "Caddy recreate command failed and rollback was incomplete"
  fi
fi

readback="$(mktemp)"
headers="$(mktemp)"
readback_reason="not-attempted"
public_readback_matches() {
  local request_timeout="$1"
  readback_reason="unknown"
  : > "$readback"
  : > "$headers"
  if ! curl -fsS \
    --connect-timeout "$PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS" \
    --max-time "$request_timeout" \
    -D "$headers" -o "$readback" "$PUBLIC_VERSION_URL"; then
    readback_reason="curl-failed"
    return 1
  fi
  if ! grep -iq '^Cache-Control:.*no-store' "$headers"; then
    readback_reason="cache-control-mismatch"
    return 1
  fi
  public_build="$(awk '
    tolower($1) == "x-weltgewebe-build:" {
      sub(/^[^:]+:[[:space:]]*/, "")
      gsub(/[[:space:]]+$/, "")
      print
      exit
    }
  ' "$headers")"
  public_version="$(read_version_field "$readback" 1)" || {
    readback_reason="version-json-invalid"
    return 1
  }
  public_commit="$(read_version_field "$readback" 3)" || {
    readback_reason="version-json-invalid"
    return 1
  }
  [[ "$public_version" == "$WEB_ARTIFACT_VERSION" ]] || {
    readback_reason="version-mismatch"
    return 1
  }
  [[ "$public_commit" == "$WEB_ARTIFACT_COMMIT" ]] || {
    readback_reason="commit-mismatch"
    return 1
  }
  [[ "$public_build" == "$WEB_ARTIFACT_VERSION" || "$public_build" == "$WEB_ARTIFACT_COMMIT" ]] || {
    readback_reason="build-header-mismatch"
    return 1
  }
  readback_reason="ok"
}

readback_ok=0
readback_attempts_made=0
readback_started=$SECONDS
for ((attempt = 1; attempt <= PUBLIC_READBACK_ATTEMPTS; attempt++)); do
  elapsed=$((SECONDS - readback_started))
  remaining=$((PUBLIC_READBACK_TOTAL_SECONDS - elapsed))
  ((remaining > 0)) || break
  request_timeout=$PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS
  ((request_timeout <= remaining)) || request_timeout=$remaining
  readback_attempts_made=$attempt
  if public_readback_matches "$request_timeout"; then
    readback_ok=1
    break
  fi
  elapsed=$((SECONDS - readback_started))
  printf 'Web artifact readback attempt %d failed after %ss: %s\n' \
    "$attempt" "$elapsed" "$readback_reason" >&2
  remaining=$((PUBLIC_READBACK_TOTAL_SECONDS - elapsed))
  if ((attempt < PUBLIC_READBACK_ATTEMPTS && remaining > 0 && PUBLIC_READBACK_INTERVAL_SECONDS > 0)); then
    sleep_for=$PUBLIC_READBACK_INTERVAL_SECONDS
    ((sleep_for <= remaining)) || sleep_for=$remaining
    ((sleep_for > 0)) && sleep "$sleep_for"
  fi
done
readback_elapsed=$((SECONDS - readback_started))
if ((readback_ok == 0)); then
  if ((switched == 0 && release_created == 0)); then
    fail "active web release failed public verification after ${readback_attempts_made} attempt(s) and ${readback_elapsed}s (${readback_reason}); active files were left unchanged"
  fi
  if rollback; then
    fail "public version readback did not converge after ${readback_attempts_made} attempt(s) and ${readback_elapsed}s (${readback_reason}); previous web release restored"
  fi
  fail "public version readback failed and rollback was incomplete after ${readback_attempts_made} attempt(s) and ${readback_elapsed}s (${readback_reason})"
fi
printf 'Web artifact public readback converged after %d attempt(s) in %ss.\n' \
  "$readback_attempts_made" "$readback_elapsed"
rm -f -- "$readback" "$headers"
readback=""
headers=""

# Keep the current target and the newest older releases. Never follow or delete the active symlink target.
if ((WEB_RELEASE_RETENTION > 0)); then
  active="$(readlink -f "$WEB_ROOT")"
  mapfile -t old < <(find "$WEB_RELEASES_DIR" -mindepth 1 -maxdepth 1 -type d ! -name '.stage.*' -printf '%T@ %p\n' | sort -nr | awk '{print $2}')
  kept=0
  for dir in "${old[@]}"; do
    [[ "$(readlink -f "$dir")" == "$active" ]] && continue
    kept=$((kept + 1))
    ((kept <= WEB_RELEASE_RETENTION)) || rm -rf --one-file-system -- "$dir"
  done
fi
if ((release_reused == 1)); then
  printf 'Web artifact verified idempotently: %s\nWeb root points to: %s\n' "$release_dir" "$(readlink "$WEB_ROOT")"
else
  printf 'Web artifact installed: %s\nWeb root now points to: %s\n' "$release_dir" "$(readlink "$WEB_ROOT")"
fi
