#!/usr/bin/env bash
set -Eeuo pipefail
umask 022

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
run_ops_python() {
  WELTGEWEBE_OPS_SCRIPT_DIR="$SCRIPT_DIR" python3 -I - "$@"
}

SOURCE_CHECKOUT="${WELTGEWEBE_SOURCE_CHECKOUT:-/opt/weltgewebe}"
RELEASE_ROOT="${WELTGEWEBE_RELEASE_ROOT:-/opt/weltgewebe-releases}"
RUNTIME_ENV="${WELTGEWEBE_RUNTIME_ENV:-/etc/weltgewebe/weltgewebe.env}"
STATE_ROOT="${WELTGEWEBE_DEPLOY_STATE_ROOT:-/var/lib/weltgewebe-main-reconciler}"
DOCKER_CONFIG="$STATE_ROOT/docker-config"
export DOCKER_CONFIG
BUILD_USER="${WELTGEWEBE_BUILD_USER:-alex}"
FRONTEND_URL="${WELTGEWEBE_FRONTEND_VERSION_URL:-https://weltgewebe.net/_app/version.json}"
API_URL="${WELTGEWEBE_API_VERSION_URL:-https://weltgewebe.net/api/version}"
NODE_BUILD_IMAGE="${WELTGEWEBE_NODE_BUILD_IMAGE:-docker.io/library/node@sha256:8898f8ed3c0126667837b678979b4ed83306c856a1227c8bf5f5f77740c25cd6}"
DEPLOY_HELPER="${WELTGEWEBE_DEPLOY_HELPER:-/usr/local/libexec/weltgewebe-deploy-exact-commit}"
LIVE_VERIFIER="${WELTGEWEBE_LIVE_VERIFIER:-/usr/local/libexec/weltgewebe-verify-public-release}"
ARCHIVE_VALIDATOR="${WELTGEWEBE_ARCHIVE_VALIDATOR:-/usr/local/libexec/weltgewebe-validate-web-deploy-archive}"
readonly PRODUCTION_LOCK_DOMAIN="weltgewebe-production-deployment-v1"
readonly PRODUCTION_LOCK_FILE="$STATE_ROOT/production-deployment.lock"
readonly PRODUCTION_LOCK_FD=9
readonly EX_TEMPFAIL=75
readonly EXIT_SUPERSEDED_AFTER_MIGRATION=79
readonly EXIT_SUPERSEDED_AFTER_DEPLOY=80
ARTIFACT_ROOT="$STATE_ROOT/artifacts"
RECEIPT_ROOT="$STATE_ROOT/reconcile-receipts"
DEPLOY_RECEIPT_ROOT="$STATE_ROOT/receipts"
MIN_FREE_KIB="${WELTGEWEBE_MIN_FREE_KIB:-4194304}"
temporary_artifact=""
temporary_source=""
source_archive=""
target_commit=""
artifact_sha=""
state_result=""
deploy_invocation_id=""

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" > /dev/null 2>&1 || fail "required command not found: $1"
}

write_lock_contention_receipt() {
  local receipt="$RECEIPT_ROOT/last-contention.json"
  run_ops_python "$receipt" "$PRODUCTION_LOCK_DOMAIN" "$PRODUCTION_LOCK_FILE" << 'PY'
import json
import os
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.environ["WELTGEWEBE_OPS_SCRIPT_DIR"])
from weltgewebe_secure_receipt_io import (SecureMetadataError, SecurePayloadError, read_secure_json, write_secure_json)

path = Path(sys.argv[1])
payload = {
    "schema_version": 1,
    "kind": "weltgewebe_production_lock_contention",
    "environment": "production",
    "lock_domain": sys.argv[2],
    "lock_file": sys.argv[3],
    "entrypoint": "reconciler",
    "requested_commit": None,
    "result": "already_running",
    "recorded_at": datetime.now(timezone.utc).isoformat(),
}
write_secure_json(path, payload)
PY
  printf '%s\n' "$receipt"
}

prepare_production_lock_file() {
  if [[ -e "$PRODUCTION_LOCK_FILE" || -L "$PRODUCTION_LOCK_FILE" ]]; then
    [[ -f "$PRODUCTION_LOCK_FILE" && ! -L "$PRODUCTION_LOCK_FILE" ]] ||
      fail "production deployment lock is not a regular file"
  else
    (umask 077 && : > "$PRODUCTION_LOCK_FILE")
  fi
  [[ "$(stat --format=%u "$PRODUCTION_LOCK_FILE")" == "0" ]] ||
    fail "production deployment lock is not root-owned"
  local lock_mode
  lock_mode="$(stat --format=%a "$PRODUCTION_LOCK_FILE")"
  (((8#$lock_mode & 022) == 0)) ||
    fail "production deployment lock is group- or world-writable"
}

acquire_production_lock() {
  local contention_receipt
  prepare_production_lock_file
  exec 9<> "$PRODUCTION_LOCK_FILE"
  if ! flock -n "$PRODUCTION_LOCK_FD"; then
    contention_receipt="$(write_lock_contention_receipt)"
    echo "production_reconcile=already_running lock_domain=$PRODUCTION_LOCK_DOMAIN receipt=$contention_receipt"
    exit 0
  fi
}

new_deploy_invocation_id() {
  python3 -I -c 'import secrets; print(secrets.token_hex(32))'
}

fetch_main() {
  git -C "$SOURCE_CHECKOUT" fetch --no-tags origin \
    "+refs/heads/main:refs/remotes/origin/main"
  git -C "$SOURCE_CHECKOUT" rev-parse refs/remotes/origin/main
}

write_state() {
  local result="$1"
  local observed_main="${2:-}"
  local detail="${3:-}"
  [[ -n "$target_commit" ]] || return 0
  local receipt="$RECEIPT_ROOT/$target_commit.json"
  run_ops_python "$receipt" "$target_commit" "$result" "$artifact_sha" "$observed_main" "$detail" << 'PY'
import json
import os
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.environ["WELTGEWEBE_OPS_SCRIPT_DIR"])
from weltgewebe_secure_receipt_io import (SecureMetadataError, SecurePayloadError, read_secure_json, write_secure_json)

path = Path(sys.argv[1])
payload = {
    "schema_version": 3,
    "target_commit": sys.argv[2],
    "result": sys.argv[3],
    "web_artifact_sha256": sys.argv[4] or None,
    "observed_main": sys.argv[5] or None,
    "detail": sys.argv[6] or None,
    "lock_domain": "weltgewebe-production-deployment-v1",
    "lock_owner_entrypoint": "reconciler",
    "recorded_at": datetime.now(timezone.utc).isoformat(),
}
write_secure_json(path, payload)
PY
  state_result="$result"
}

read_deploy_terminal_result() {
  local commit="$1"
  local invocation_id="$2"
  local deployment_receipt="$DEPLOY_RECEIPT_ROOT/$commit.json"

  run_ops_python "$deployment_receipt" "$commit" "$invocation_id" << 'PY'
import json
import os
import stat
import sys
from pathlib import Path
sys.path.insert(0, os.environ["WELTGEWEBE_OPS_SCRIPT_DIR"])
from weltgewebe_secure_receipt_io import (SecureMetadataError, SecurePayloadError, read_secure_json, write_secure_json)

MAX_RECEIPT_BYTES = 1048576
path = Path(sys.argv[1])
commit = sys.argv[2]
invocation_id = sys.argv[3]


try:
    payload = read_secure_json(path)
except (OSError, ValueError) as exc:
    raise SystemExit(f"terminal deployment receipt is unsafe: {exc}") from exc
if payload.get("schema_version") != 5:
    raise SystemExit("terminal deployment receipt schema is not current")
if payload.get("commit") != commit:
    raise SystemExit("terminal deployment receipt targets another commit")
if payload.get("deploy_invocation_id") != invocation_id:
    raise SystemExit("terminal deployment receipt does not match current invocation")
if payload.get("lock_domain") != "weltgewebe-production-deployment-v1":
    raise SystemExit("terminal deployment receipt has another lock domain")
if payload.get("lock_owner_entrypoint") != "reconciler":
    raise SystemExit("terminal deployment receipt has another lock owner")
if payload.get("lock_handoff") != "inherited":
    raise SystemExit("terminal deployment receipt is not bound to inherited handoff")
result = payload.get("result")
if result not in {"superseded_after_migration", "superseded_after_deploy"}:
    raise SystemExit(f"unexpected terminal deployment result: {result!r}")
print(result)
PY
}

read_deploy_tempfail_diagnostic() {
  local commit="$1"
  local invocation_id="$2"
  local deployment_receipt="$DEPLOY_RECEIPT_ROOT/$commit.json"
  local contention_receipt="$DEPLOY_RECEIPT_ROOT/contention/$invocation_id.json"
  local legacy_contention_receipt="$DEPLOY_RECEIPT_ROOT/last-contention.json"
  run_ops_python "$deployment_receipt" "$contention_receipt" \
    "$legacy_contention_receipt" "$commit" "$invocation_id" << 'PY'
import json
import os
import stat
import sys
from pathlib import Path
sys.path.insert(0, os.environ["WELTGEWEBE_OPS_SCRIPT_DIR"])
from weltgewebe_secure_receipt_io import (SecureMetadataError, SecurePayloadError, read_secure_json, write_secure_json)

MAX_RECEIPT_BYTES = 1048576
deployment_path = Path(sys.argv[1])
contention_path = Path(sys.argv[2])
legacy_contention_path = Path(sys.argv[3])
commit = sys.argv[4]
invocation_id = sys.argv[5]


def read_safe(path: Path):
    try:
        return read_secure_json(path)
    except FileNotFoundError:
        return None
    except (OSError, SecureMetadataError, SecurePayloadError):
        return "unsafe"


def is_current_contention(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get("schema_version") == 2
        and payload.get("kind") == "weltgewebe_production_lock_contention"
        and payload.get("requested_commit") == commit
        and payload.get("deploy_invocation_id") == invocation_id
        and payload.get("lock_domain") == "weltgewebe-production-deployment-v1"
        and payload.get("entrypoint") == "reconciler"
        and payload.get("result") == "already_running"
    )


deployment = read_safe(deployment_path)
if deployment == "unsafe":
    print("untrusted_receipt")
elif (
    isinstance(deployment, dict)
    and deployment.get("schema_version") == 5
    and deployment.get("commit") == commit
    and deployment.get("deploy_invocation_id") == invocation_id
    and deployment.get("lock_domain") == "weltgewebe-production-deployment-v1"
    and deployment.get("lock_owner_entrypoint") == "reconciler"
    and deployment.get("lock_handoff") == "inherited"
    and deployment.get("result") == "failed"
):
    print("failed_deployment")
else:
    contention = read_safe(contention_path)
    if contention == "unsafe":
        print("untrusted_receipt")
    elif is_current_contention(contention):
        print("lock_contention")
    elif contention is None:
        legacy_contention = read_safe(legacy_contention_path)
        if legacy_contention == "unsafe":
            print("untrusted_receipt")
        elif is_current_contention(legacy_contention):
            print("lock_contention")
        else:
            print("unexplained")
    else:
        # The invocation-specific slot is authoritative when present. A
        # conflicting object must not be overruled by the shared legacy slot.
        print("unexplained")
PY
}

repair_observed_deployment_state() {
  local verification_receipt="$1"
  local deployment_receipt="$DEPLOY_RECEIPT_ROOT/$target_commit.json"

  run_ops_python "$verification_receipt" "$deployment_receipt" "$target_commit" << 'PY'
import json
import os
import secrets
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, os.environ["WELTGEWEBE_OPS_SCRIPT_DIR"])
from weltgewebe_secure_receipt_io import (SecureMetadataError, SecurePayloadError, read_secure_json, write_secure_json)

MAX_RECEIPT_BYTES = 1048576
verification_path = Path(sys.argv[1])
deployment_path = Path(sys.argv[2])
commit = sys.argv[3]


try:
    verification = read_secure_json(verification_path)
except (OSError, SecureMetadataError, SecurePayloadError) as exc:
    raise SystemExit(f"public verification receipt evidence is unsafe: {exc}") from exc
try:
    existing = read_secure_json(deployment_path, missing_ok=True)
except SecurePayloadError:
    existing = None
except (OSError, SecureMetadataError) as exc:
    raise SystemExit(f"deployment receipt evidence is unsafe: {exc}") from exc
if verification.get("pass") is not True:
    raise SystemExit("public verification receipt is not passing")
if verification.get("expected_commit") != commit:
    raise SystemExit("public verification receipt targets another commit")
frontend = verification.get("frontend") or {}
api = verification.get("api") or {}
if frontend.get("commit") != commit or api.get("commit") != commit:
    raise SystemExit("public verification receipt does not bind both endpoints")


def is_lower_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


SCHEMA5_VERIFIED_KEYS = frozenset(
    {
        "schema_version",
        "environment",
        "commit",
        "web_artifact_sha256",
        "started_at",
        "completed_at",
        "api_commit",
        "frontend_commit",
        "observed_main_after_deploy",
        "migration_completed_at",
        "lock_domain",
        "lock_owner_entrypoint",
        "lock_handoff",
        "result",
        "deploy_invocation_id",
    }
)
SCHEMA5_VERIFIED_OBSERVED_KEYS = SCHEMA5_VERIFIED_KEYS | {"evidence_boundary"}


def parse_aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def is_current_verified_receipt(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False

    result = payload.get("result")
    if result == "verified":
        expected_keys = SCHEMA5_VERIFIED_KEYS
    elif result == "verified_observed":
        expected_keys = SCHEMA5_VERIFIED_OBSERVED_KEYS
    else:
        return False
    if set(payload) != expected_keys:
        return False

    completed_at = parse_aware_timestamp(payload.get("completed_at"))
    if (
        payload.get("schema_version") != 5
        or payload.get("environment") != "production"
        or payload.get("commit") != commit
        or payload.get("lock_domain") != "weltgewebe-production-deployment-v1"
        or payload.get("api_commit") != commit
        or payload.get("frontend_commit") != commit
        or payload.get("observed_main_after_deploy") != commit
        or completed_at is None
    ):
        return False

    owner = payload.get("lock_owner_entrypoint")
    handoff = payload.get("lock_handoff")
    invocation_id = payload.get("deploy_invocation_id")
    if result == "verified":
        started_at = parse_aware_timestamp(payload.get("started_at"))
        migration_completed_at = parse_aware_timestamp(
            payload.get("migration_completed_at")
        )
        if (
            not is_lower_hex(payload.get("web_artifact_sha256"), 64)
            or started_at is None
            or migration_completed_at is None
            or not started_at <= migration_completed_at <= completed_at
        ):
            return False
        return (
            owner == "deploy-helper"
            and handoff == "direct"
            and invocation_id is None
        ) or (
            owner == "reconciler"
            and handoff == "inherited"
            and is_lower_hex(invocation_id, 64)
        )

    evidence_boundary = payload.get("evidence_boundary")
    return (
        owner == "reconciler"
        and handoff == "public-observation"
        and invocation_id is None
        and payload.get("web_artifact_sha256") is None
        and payload.get("started_at") is None
        and payload.get("migration_completed_at") is None
        and isinstance(evidence_boundary, str)
        and bool(evidence_boundary.strip())
    )


def parse_aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def migrate_schema4_verified_receipt(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    started_at = parse_aware_timestamp(payload.get("started_at"))
    completed_at = parse_aware_timestamp(payload.get("completed_at"))
    migration_completed_at = parse_aware_timestamp(
        payload.get("migration_completed_at")
    )
    expected_keys = {
        "schema_version",
        "environment",
        "commit",
        "web_artifact_sha256",
        "started_at",
        "completed_at",
        "api_commit",
        "frontend_commit",
        "observed_main_after_deploy",
        "migration_completed_at",
        "lock_domain",
        "lock_owner_entrypoint",
        "lock_handoff",
        "result",
    }
    if set(payload) != expected_keys:
        return None
    if (
        payload.get("schema_version") != 4
        or payload.get("environment") != "production"
        or payload.get("commit") != commit
        or not is_lower_hex(payload.get("web_artifact_sha256"), 64)
        or started_at is None
        or completed_at is None
        or payload.get("api_commit") != commit
        or payload.get("frontend_commit") != commit
        or payload.get("observed_main_after_deploy") != commit
        or migration_completed_at is None
        or payload.get("lock_domain") != "weltgewebe-production-deployment-v1"
        or payload.get("lock_owner_entrypoint") != "deploy-helper"
        or payload.get("lock_handoff") != "direct"
        or payload.get("result") != "verified"
    ):
        return None
    if not started_at <= migration_completed_at <= completed_at:
        return None
    migrated = dict(payload)
    migrated["schema_version"] = 5
    migrated["deploy_invocation_id"] = None
    return migrated


if is_current_verified_receipt(existing):
    raise SystemExit(0)

migrated_schema4 = migrate_schema4_verified_receipt(existing)
if migrated_schema4 is not None:
    write_secure_json(deployment_path, migrated_schema4)
    raise SystemExit(0)

payload = {
    "schema_version": 5,
    "environment": "production",
    "commit": commit,
    "web_artifact_sha256": None,
    "started_at": None,
    "completed_at": verification.get("verified_at"),
    "api_commit": api.get("commit"),
    "frontend_commit": frontend.get("commit"),
    "observed_main_after_deploy": commit,
    "migration_completed_at": None,
    "lock_domain": "weltgewebe-production-deployment-v1",
    "lock_owner_entrypoint": "reconciler",
    "lock_handoff": "public-observation",
    "result": "verified_observed",
    "deploy_invocation_id": None,
    "evidence_boundary": (
        "Recovered from exact public readback; original web artifact hash and "
        "deployment start time are unavailable."
    ),
}
write_secure_json(deployment_path, payload)
PY

  ln -sfn "receipts/$target_commit.json" "$STATE_ROOT/current.json"

  local candidate_release="$RELEASE_ROOT/$target_commit"
  if [[ -e "$candidate_release" ]]; then
    [[ -d "$candidate_release" && ! -L "$candidate_release" ]] ||
      fail "observed release path is unsafe: $candidate_release"
    local release_root_real
    local candidate_real
    local candidate_head
    release_root_real="$(realpath "$RELEASE_ROOT")"
    candidate_real="$(realpath "$candidate_release")"
    case "$candidate_real" in
      "$release_root_real"/*) ;;
      *) fail "observed release escaped the release root" ;;
    esac
    [[ "$(stat --format=%u "$candidate_real")" == "0" ]] ||
      fail "observed release is not root-owned"
    candidate_head="$(git -C "$candidate_real" rev-parse HEAD)"
    [[ "$candidate_head" == "$target_commit" ]] ||
      fail "observed release does not match the public commit"
    if [[ -L "$STATE_ROOT/current-release" ]]; then
      local previous_release
      previous_release="$(readlink -f "$STATE_ROOT/current-release")" ||
        fail "current release marker is broken"
      case "$previous_release" in
        "$release_root_real"/*)
          if [[ "$previous_release" != "$candidate_real" ]]; then
            ln -sfn "$previous_release" "$STATE_ROOT/previous-release"
          fi
          ;;
        *) fail "current release marker escapes release root" ;;
      esac
    fi
    ln -sfn "$candidate_real" "$STATE_ROOT/current-release"
  fi
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
  if [[ -n "$source_archive" && -f "$source_archive" && ! -L "$source_archive" ]]; then
    rm -f -- "$source_archive"
  fi
  if ((rc != 0)) && [[ -n "$target_commit" && ! "$state_result" =~ ^(verified|superseded) ]]; then
    write_state "failed" "" "reconciler exit code $rc" || true
  fi
  exit "$rc"
}
trap cleanup EXIT

prune_artifacts() {
  local old_artifact
  local -a web_artifacts=()
  find "$ARTIFACT_ROOT" -maxdepth 1 -type f -name 'source-*.tar' -delete
  while IFS= read -r old_artifact; do
    [[ "$old_artifact" == "$ARTIFACT_ROOT/web-$target_commit.tar.gz" ]] && continue
    rm -f -- "$old_artifact"
  done < <(find "$ARTIFACT_ROOT" -maxdepth 1 -type f -name 'web-*.tar.gz' -mtime +7 -print)

  mapfile -t web_artifacts < <(find "$ARTIFACT_ROOT" -maxdepth 1 -type f -name 'web-*.tar.gz' -printf '%T@ %p\n' | sort -nr | cut -d' ' -f2-)
  if ((${#web_artifacts[@]} > 20)); then
    for old_artifact in "${web_artifacts[@]:20}"; do
      [[ "$old_artifact" == "$ARTIFACT_ROOT/web-$target_commit.tar.gz" ]] && continue
      rm -f -- "$old_artifact"
    done
  fi
}

prune_deploy_contention_receipts() {
  local contention_root="$DEPLOY_RECEIPT_ROOT/contention"
  local old_receipt
  local -a receipts=()

  find "$contention_root" -maxdepth 1 -type f -name '*.json' -mtime +7 -delete
  mapfile -t receipts < <(
    find "$contention_root" -maxdepth 1 -type f -name '*.json' \
      -printf '%T@ %p\n' | sort -nr | cut -d' ' -f2-
  )
  if ((${#receipts[@]} > 20)); then
    for old_receipt in "${receipts[@]:20}"; do
      rm -f -- "$old_receipt"
    done
  fi
}

prune_releases() {
  local current_release=""
  local previous_release=""
  local release_dir
  local release_name
  local release_head
  current_release="$(readlink -f "$STATE_ROOT/current-release" 2> /dev/null || true)"
  previous_release="$(readlink -f "$STATE_ROOT/previous-release" 2> /dev/null || true)"
  while IFS= read -r release_dir; do
    [[ "$release_dir" == "$current_release" || "$release_dir" == "$previous_release" ]] && continue
    release_name="${release_dir##*/}"
    [[ "$release_name" =~ ^[0-9a-f]{40}$ ]] || continue
    [[ -d "$release_dir" && ! -L "$release_dir" ]] || continue
    [[ "$(stat --format=%u "$release_dir")" == "0" ]] || continue
    release_head="$(git -C "$release_dir" rev-parse HEAD 2> /dev/null || true)"
    [[ "$release_head" == "$release_name" ]] || continue
    rm -rf -- "$release_dir/apps/web/build"
    rm -f -- "$release_dir/build/basemap"
    rmdir "$release_dir/build" 2> /dev/null || true
    if [[ -z "$(git -C "$release_dir" status --porcelain --untracked-files=normal)" ]]; then
      git -C "$SOURCE_CHECKOUT" worktree remove "$release_dir"
    fi
  done < <(find "$RELEASE_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +14 -print)
  git -C "$SOURCE_CHECKOUT" worktree prune --expire=now
}

[[ "$EUID" -eq 0 ]] || fail "production reconciler must run as root"
[[ -d "$SOURCE_CHECKOUT" && ! -L "$SOURCE_CHECKOUT" ]] || fail "source checkout is unsafe: $SOURCE_CHECKOUT"
[[ -f "$RUNTIME_ENV" && ! -L "$RUNTIME_ENV" ]] || fail "runtime environment is missing or unsafe: $RUNTIME_ENV"
[[ -x "$DEPLOY_HELPER" ]] || fail "deploy helper is not installed: $DEPLOY_HELPER"
[[ -x "$LIVE_VERIFIER" ]] || fail "live verifier is not installed: $LIVE_VERIFIER"
[[ -x "$ARCHIVE_VALIDATOR" ]] || fail "archive validator is not installed: $ARCHIVE_VALIDATOR"
getent passwd "$BUILD_USER" > /dev/null || fail "build user does not exist: $BUILD_USER"
[[ "$MIN_FREE_KIB" =~ ^[0-9]+$ ]] || fail "minimum free space is invalid"

for command_name in git docker sha256sum flock install id rm mv awk getent chmod ln readlink find sort cut df stat rmdir python3 realpath; do
  require_command "$command_name"
done

install -d -o root -g root -m 0711 "$STATE_ROOT"
install -d -o root -g root -m 0700 \
  "$ARTIFACT_ROOT" "$RECEIPT_ROOT" "$DEPLOY_RECEIPT_ROOT" "$DOCKER_CONFIG"
install -d -o root -g root -m 0700 "$DEPLOY_RECEIPT_ROOT/contention"
install -d -o root -g root -m 0755 "$RELEASE_ROOT"
acquire_production_lock
prune_deploy_contention_receipts

available_kib="$(df -Pk "$ARTIFACT_ROOT" | awk 'NR==2 {print $4}')"
[[ "$available_kib" =~ ^[0-9]+$ ]] || fail "could not determine free disk space"
((available_kib >= MIN_FREE_KIB)) || fail "insufficient free disk space: ${available_kib}KiB available"

[[ "$(stat --format=%u "$SOURCE_CHECKOUT")" == "0" ]] || fail "source checkout is not root-owned"
git_common_dir="$(git -C "$SOURCE_CHECKOUT" rev-parse --git-common-dir)"
[[ "$git_common_dir" == /* ]] || git_common_dir="$SOURCE_CHECKOUT/$git_common_dir"
git_common_dir="$(readlink -f "$git_common_dir")"
unsafe_git_path="$(find "$git_common_dir" -xdev \( ! -user root -o -perm /022 \) -print -quit)"
[[ -z "$unsafe_git_path" ]] || fail "Git object store is not entirely root-owned and non-writable by group/world: $unsafe_git_path"

target_commit="$(fetch_main)"
[[ "$target_commit" =~ ^[0-9a-f]{40}$ ]] || fail "origin/main did not resolve to a full commit"
write_state "observed" "$target_commit" "reconcile started"

initial_receipt="$RECEIPT_ROOT/observed-$target_commit.json"
if "$LIVE_VERIFIER" \
  --expected-commit "$target_commit" \
  --frontend-url "$FRONTEND_URL" \
  --api-url "$API_URL" \
  --output "$initial_receipt"; then
  observed_main="$(fetch_main)"
  if [[ "$observed_main" != "$target_commit" ]]; then
    write_state "superseded_after_observe" "$observed_main" "main advanced after public readback"
    echo "production_reconcile=superseded observed=$target_commit current=$observed_main"
    exit 0
  fi
  repair_observed_deployment_state "$initial_receipt"
  write_state "verified_observed" "$target_commit" "public state already matched; markers repaired"
  ln -sfn "reconcile-receipts/$target_commit.json" "$STATE_ROOT/reconcile-current.json"
  prune_artifacts
  prune_releases
  echo "production_reconcile=noop commit=$target_commit state=repaired"
  exit 0
fi

build_uid="$(id -u "$BUILD_USER")"
build_gid="$(id -g "$BUILD_USER")"
[[ "$build_uid" =~ ^[0-9]+$ && "$build_gid" =~ ^[0-9]+$ ]] || fail "build user IDs are invalid"
commit_epoch="$(git -C "$SOURCE_CHECKOUT" show -s --format=%ct "$target_commit")"
[[ "$commit_epoch" =~ ^[0-9]+$ ]] || fail "target commit timestamp is invalid"

source_archive="$ARTIFACT_ROOT/source-$target_commit.tar"
temporary_source="$source_archive.tmp.$$"
git -C "$SOURCE_CHECKOUT" archive --format=tar --output="$temporary_source" "$target_commit"
mv "$temporary_source" "$source_archive"
temporary_source=""
chmod 0444 "$source_archive"
write_state "building" "$target_commit" "source archive exported"

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
rm -f -- "$source_archive"
source_archive=""

[[ -s "$temporary_artifact" && ! -L "$temporary_artifact" ]] || fail "frontend build stream is missing or unsafe"
"$ARCHIVE_VALIDATOR" "$temporary_artifact"
artifact="$ARTIFACT_ROOT/web-$target_commit.tar.gz"
mv "$temporary_artifact" "$artifact"
temporary_artifact=""
chmod 0600 "$artifact"
artifact_sha="$(sha256sum "$artifact" | awk '{print $1}')"
[[ "$artifact_sha" =~ ^[0-9a-f]{64}$ ]] || fail "frontend artifact hash is invalid"
write_state "artifact_validated" "$target_commit" "frontend artifact ready"

current_main="$(fetch_main)"
if [[ "$current_main" != "$target_commit" ]]; then
  write_state "deferred" "$current_main" "main advanced after build"
  prune_artifacts
  echo "production_reconcile=deferred built=$target_commit current=$current_main"
  exit 0
fi

deploy_invocation_id="$(new_deploy_invocation_id)"
[[ "$deploy_invocation_id" =~ ^[0-9a-f]{64}$ ]] ||
  fail "deploy invocation identity generation failed"
set +e
WELTGEWEBE_PRODUCTION_LOCK_FD="$PRODUCTION_LOCK_FD" \
  WELTGEWEBE_PRODUCTION_LOCK_DOMAIN="$PRODUCTION_LOCK_DOMAIN" \
  WELTGEWEBE_PRODUCTION_LOCK_OWNER_ENTRYPOINT="reconciler" \
  WELTGEWEBE_DEPLOY_INVOCATION_ID="$deploy_invocation_id" \
  "$DEPLOY_HELPER" \
  --commit "$target_commit" \
  --web-artifact "$artifact" \
  --web-sha256 "$artifact_sha"
deploy_rc=$?
set -e
deploy_result=""
case "$deploy_rc" in
  0) ;;

  "$EXIT_SUPERSEDED_AFTER_MIGRATION")
    deploy_result="$(read_deploy_terminal_result "$target_commit" "$deploy_invocation_id")"
    [[ "$deploy_result" == "superseded_after_migration" ]] ||
      fail "deploy helper exit/result mismatch: exit=$deploy_rc result=$deploy_result"
    ;;
  "$EXIT_SUPERSEDED_AFTER_DEPLOY")
    deploy_result="$(read_deploy_terminal_result "$target_commit" "$deploy_invocation_id")"
    [[ "$deploy_result" == "superseded_after_deploy" ]] ||
      fail "deploy helper exit/result mismatch: exit=$deploy_rc result=$deploy_result"
    ;;
  "$EX_TEMPFAIL")
    tempfail_diagnostic="$(read_deploy_tempfail_diagnostic "$target_commit" "$deploy_invocation_id")"
    case "$tempfail_diagnostic" in
      failed_deployment)
        fail "deploy helper returned child temporary failure after writing a failed receipt for the current invocation"
        ;;
      lock_contention)
        fail "deploy helper reported production lock contention during inherited handoff"
        ;;
      untrusted_receipt)
        fail "deploy helper returned temporary failure with unsafe receipt evidence"
        ;;
      *)
        fail "deploy helper returned unexplained temporary failure under inherited production lock"
        ;;
    esac
    ;;
  *)
    fail "deploy helper failed with exit code $deploy_rc"
    ;;
esac

if [[ -n "$deploy_result" ]]; then
  current_main="$(fetch_main)"
  case "$deploy_result" in
    superseded_after_migration)
      write_state \
        "superseded_after_migration" \
        "$current_main" \
        "migration completed; full deploy skipped after main advanced"
      echo "production_reconcile=superseded_after_migration migrated=$target_commit current=$current_main"
      ;;
    superseded_after_deploy)
      write_state \
        "superseded_after_deploy" \
        "$current_main" \
        "full deploy completed after main advanced"
      echo "production_reconcile=superseded_after_deploy deployed=$target_commit current=$current_main"
      ;;
    *)
      fail "unexpected superseded reason: $deploy_result"
      ;;
  esac
  prune_artifacts
  exit 0
fi

final_receipt="$RECEIPT_ROOT/public-$target_commit.json"
"$LIVE_VERIFIER" \
  --expected-commit "$target_commit" \
  --frontend-url "$FRONTEND_URL" \
  --api-url "$API_URL" \
  --wait-seconds 120 \
  --poll-seconds 5 \
  --output "$final_receipt"

current_main="$(fetch_main)"
if [[ "$current_main" != "$target_commit" ]]; then
  write_state "superseded_after_verify" "$current_main" "public readback passed after main advanced"
  prune_artifacts
  echo "production_reconcile=superseded verified=$target_commit current=$current_main"
  exit 0
fi

write_state "verified" "$current_main" "public readback and main identity agree"
ln -sfn "reconcile-receipts/$target_commit.json" "$STATE_ROOT/reconcile-current.json"
prune_artifacts
prune_releases
echo "production_reconcile=verified commit=$target_commit artifact_sha256=$artifact_sha receipt=$RECEIPT_ROOT/$target_commit.json"
