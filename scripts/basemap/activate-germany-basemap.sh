#!/usr/bin/env bash
set -euo pipefail

# Fail-closed activation wrapper for the nationwide Germany PMTiles variant.
# Preparation publishes immutable versioned files only. Activation binds the
# selected version to deep validation, device proof, frontend commit, style
# hash, bounded public readback and an atomic receipt. Any failure restores the
# previous aliases and rebuilds the regional frontend.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." > /dev/null 2>&1 && pwd)"
BASEMAP_DIR="${BASEMAP_DIR:-$REPO_ROOT/build/basemap}"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
MAX_SOURCE_AGE_DAYS="${GERMANY_BASEMAP_MAX_SOURCE_AGE_DAYS:-45}"
MAX_RELEASE_PROOF_AGE_HOURS="${GERMANY_BASEMAP_RELEASE_PROOF_MAX_AGE_HOURS:-24}"
HTTP_CONNECT_TIMEOUT_SECONDS="${GERMANY_BASEMAP_HTTP_CONNECT_TIMEOUT_SECONDS:-10}"
HTTP_MAX_TIME_SECONDS="${GERMANY_BASEMAP_HTTP_MAX_TIME_SECONDS:-900}"
ACTIVATION_CONFIRM="${GERMANY_BASEMAP_ACTIVATION_CONFIRM:-}"
EXPECTED_CONFIRMATION="deploy-germany-pmtiles"
DEPLOY_COMMAND="${WELTGEWEBE_DEPLOY_COMMAND:-$REPO_ROOT/scripts/weltgewebe-up}"
PUBLIC_APP_URL="${WELTGEWEBE_PUBLIC_APP_URL:-https://weltgewebe.net}"
PUBLIC_APP_URL="${PUBLIC_APP_URL%/}"
STATE_DIR="${WELTGEWEBE_STATE_DIR:-$REPO_ROOT/.ops}"
RELEASE_PROOF_PATH="${GERMANY_BASEMAP_RELEASE_PROOF_PATH:-}"
DEPLOY_ARGS=("$@")

VERSIONED_ARTIFACT="$BASEMAP_DIR/basemap-germany-v${BASEMAP_VERSION}.pmtiles"
VERSIONED_META="$BASEMAP_DIR/basemap-germany-v${BASEMAP_VERSION}.meta.json"
VERSIONED_VALIDATION="$BASEMAP_DIR/basemap-germany-v${BASEMAP_VERSION}.validation.json"
ALIAS_ARTIFACT="$BASEMAP_DIR/basemap-germany.pmtiles"
ALIAS_META="$BASEMAP_DIR/basemap-germany.meta.json"
STYLE_PATH="$REPO_ROOT/map-style/style-germany.json"
LOCAL_BUILD_IDENTITY="${WELTGEWEBE_BUILD_IDENTITY_PATH:-$REPO_ROOT/apps/web/build/_app/basemap-build.json}"
ACTIVATION_RECEIPT="$STATE_DIR/germany-basemap-activation.json"
ALIASES_TOUCHED=0
PREVIOUS_ARTIFACT_ALIAS_PRESENT=0
PREVIOUS_META_ALIAS_PRESENT=0
PREVIOUS_ARTIFACT_ALIAS_TARGET=""
PREVIOUS_META_ALIAS_TARGET=""
ACTIVATION_TRANSACTION_OPEN=0
ACTIVATION_COMMITTED=0
ROLLBACK_IN_PROGRESS=0
ROLLBACK_COMPLETE=0
TMP_DIR=""

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_positive_integer() {
  local name="$1"
  local value="$2"
  case "$value" in
    '' | *[!0-9]*) fail "$name must be a positive integer" ;;
  esac
  ((value > 0)) || fail "$name must be greater than zero"
}

require_nonempty_path() {
  local required_path="$1"
  local resolved_path=""
  [[ -e "$required_path" ]] ||
    fail "required Germany rollout evidence is missing: $required_path"
  resolved_path="$(readlink -f -- "$required_path")" ||
    fail "cannot resolve Germany rollout evidence: $required_path"
  [[ -n "$resolved_path" && -s "$resolved_path" ]] ||
    fail "required Germany rollout evidence is empty: $required_path"
}

deploy_frontend_variant() {
  local variant="$1"
  shift
  PUBLIC_BASEMAP_MODE=local-sovereign \
    PUBLIC_BASEMAP_VARIANT="$variant" \
    "$DEPLOY_COMMAND" --build-web "$@"
}

atomic_symlink() {
  local target="$1"
  local alias_path="$2"
  local temporary_link="${alias_path}.tmp.$$"

  rm -f "$temporary_link"
  ln -s "$target" "$temporary_link" || return 1
  if ! mv -Tf "$temporary_link" "$alias_path"; then
    rm -f "$temporary_link"
    return 1
  fi
}

capture_alias_state() {
  local alias_path="$1"
  local kind="$2"
  local target=""

  if [[ -L "$alias_path" ]]; then
    target="$(readlink -- "$alias_path")" ||
      fail "cannot read existing $kind alias: $alias_path"
    if [[ "$kind" == "artifact" ]]; then
      PREVIOUS_ARTIFACT_ALIAS_PRESENT=1
      PREVIOUS_ARTIFACT_ALIAS_TARGET="$target"
    else
      PREVIOUS_META_ALIAS_PRESENT=1
      PREVIOUS_META_ALIAS_TARGET="$target"
    fi
  elif [[ -e "$alias_path" ]]; then
    fail "stable Germany $kind alias path is not a symlink: $alias_path"
  fi
}

restore_one_alias() {
  local was_present="$1"
  local previous_target="$2"
  local alias_path="$3"

  if [[ "$was_present" == "1" ]]; then
    atomic_symlink "$previous_target" "$alias_path"
    return
  fi

  if [[ -L "$alias_path" ]]; then
    rm -f "$alias_path"
  elif [[ -e "$alias_path" ]]; then
    return 1
  fi
}

restore_alias_pair() {
  local failed=0

  if ! restore_one_alias \
    "$PREVIOUS_ARTIFACT_ALIAS_PRESENT" \
    "$PREVIOUS_ARTIFACT_ALIAS_TARGET" \
    "$ALIAS_ARTIFACT"; then
    echo "CRITICAL: Could not restore the previous Germany artifact alias." >&2
    failed=1
  fi
  if ! restore_one_alias \
    "$PREVIOUS_META_ALIAS_PRESENT" \
    "$PREVIOUS_META_ALIAS_TARGET" \
    "$ALIAS_META"; then
    echo "CRITICAL: Could not restore the previous Germany metadata alias." >&2
    failed=1
  fi
  return "$failed"
}

switch_alias_pair() {
  local artifact_target=""
  local meta_target=""

  artifact_target="$(basename -- "$VERSIONED_ARTIFACT")"
  meta_target="$(basename -- "$VERSIONED_META")"
  ALIASES_TOUCHED=1

  atomic_symlink "$artifact_target" "$ALIAS_ARTIFACT" || return 1
  atomic_symlink "$meta_target" "$ALIAS_META" || return 1

  [[ "$(readlink -f -- "$ALIAS_ARTIFACT")" == "$(readlink -f -- "$VERSIONED_ARTIFACT")" ]] || return 1
  [[ "$(readlink -f -- "$ALIAS_META")" == "$(readlink -f -- "$VERSIONED_META")" ]] || return 1
}

invalidate_activation_receipt() {
  if [[ -e "$ACTIVATION_RECEIPT" || -L "$ACTIVATION_RECEIPT" ]]; then
    rm -f -- "$ACTIVATION_RECEIPT" || return 1
  fi
}

rollback_activation() {
  local failed=0

  if [[ "$ROLLBACK_COMPLETE" == "1" || "$ROLLBACK_IN_PROGRESS" == "1" ]]; then
    return 0
  fi
  ROLLBACK_IN_PROGRESS=1

  echo "WARNING: Germany activation failed; invalidating its receipt, restoring aliases and the regional frontend." >&2
  if ! invalidate_activation_receipt; then
    echo "CRITICAL: Could not invalidate the Germany activation receipt." >&2
    failed=1
  fi
  if [[ "$ALIASES_TOUCHED" == "1" ]] && ! restore_alias_pair; then
    failed=1
  fi
  if ! deploy_frontend_variant "regional" "${DEPLOY_ARGS[@]}"; then
    echo "CRITICAL: Automatic regional frontend rollback failed." >&2
    failed=1
  else
    echo "[✓] Regional frontend rollback completed." >&2
  fi

  ROLLBACK_IN_PROGRESS=0
  ROLLBACK_COMPLETE=1
  return "$failed"
}

cleanup_tmp() {
  if [[ -n "$TMP_DIR" ]]; then
    rm -rf -- "$TMP_DIR" || echo "WARNING: Could not remove activation temporary directory: $TMP_DIR" >&2
  fi
}

on_exit() {
  local status=$?
  local rollback_status=0

  trap - EXIT
  trap '' INT TERM
  if [[ "$ACTIVATION_TRANSACTION_OPEN" == "1" && "$ACTIVATION_COMMITTED" != "1" ]]; then
    rollback_activation || rollback_status=$?
    if [[ "$status" == "0" ]]; then
      status=1
    fi
  fi
  cleanup_tmp
  if [[ "$rollback_status" != "0" ]]; then
    echo "CRITICAL: Germany activation rollback was incomplete." >&2
  fi
  exit "$status"
}

on_interrupt() {
  exit 130
}

on_terminate() {
  exit 143
}

post_activation_failure() {
  fail "$1"
}

verify_checkout_clean() {
  local untracked_inputs=""

  git -C "$REPO_ROOT" diff --quiet --ignore-submodules -- ||
    fail "tracked worktree changes would make the Germany device proof stale"
  git -C "$REPO_ROOT" diff --cached --quiet --ignore-submodules -- ||
    fail "staged changes would make the Germany device proof stale"
  untracked_inputs="$(
    git -C "$REPO_ROOT" ls-files --others --exclude-standard -- \
      apps/web map-style policies/performance.v1.json
  )" || fail "could not inspect untracked frontend inputs"
  [[ -z "$untracked_inputs" ]] ||
    fail "untracked frontend or style inputs would make the Germany device proof stale: $untracked_inputs"
}

verify_snapshot_freshness() {
  META_PATH="$VERSIONED_META" \
    MAX_SOURCE_AGE_DAYS="$MAX_SOURCE_AGE_DAYS" \
    python3 << 'PY'
import datetime as dt
import json
import os
from pathlib import Path

meta = json.loads(Path(os.environ["META_PATH"]).read_text(encoding="utf-8"))
value = meta.get("input", {}).get("snapshot_date")
try:
    snapshot = dt.date.fromisoformat(value)
except (TypeError, ValueError) as exc:
    raise SystemExit("Germany metadata snapshot_date is invalid") from exc

today = dt.datetime.now(dt.timezone.utc).date()
age_days = (today - snapshot).days
if age_days < 0:
    raise SystemExit("Germany metadata snapshot_date lies in the future")
if age_days > int(os.environ["MAX_SOURCE_AGE_DAYS"]):
    raise SystemExit(
        f"Germany OSM snapshot is {age_days} days old; maximum is "
        f"{os.environ['MAX_SOURCE_AGE_DAYS']} days"
    )
PY
}

verify_identity_file() {
  local identity_path="$1"

  IDENTITY_PATH="$identity_path" \
    EXPECTED_SOURCE_COMMIT="$SOURCE_COMMIT" \
    EXPECTED_STYLE_SHA256="$STYLE_SHA256" \
    python3 << 'PY'
import json
import os
from pathlib import Path

identity = json.loads(Path(os.environ["IDENTITY_PATH"]).read_text(encoding="utf-8"))
expected = {
    "schema_version": 1,
    "mode": "local-sovereign",
    "variant": "germany",
    "style_path": "/local-basemap/style-germany.json",
    "source_commit": os.environ["EXPECTED_SOURCE_COMMIT"],
    "style_sha256": os.environ["EXPECTED_STYLE_SHA256"],
}
if identity != expected:
    raise SystemExit(f"unexpected basemap build identity: {identity!r}")
PY
}

write_activation_receipt() {
  local receipt_tmp="${ACTIVATION_RECEIPT}.tmp.$$"

  install -d -m 0700 "$STATE_DIR" || return 1
  rm -f "$receipt_tmp"
  if ! RECEIPT_PATH="$receipt_tmp" \
    PUBLIC_APP_URL="$PUBLIC_APP_URL" \
    ARTIFACT_SHA256="$ARTIFACT_SHA256" \
    ARTIFACT_SIZE="$ARTIFACT_SIZE" \
    BASEMAP_VERSION="$BASEMAP_VERSION" \
    RELEASE_PROOF_SHA256="$RELEASE_PROOF_SHA256" \
    SOURCE_COMMIT="$SOURCE_COMMIT" \
    STYLE_SHA256="$STYLE_SHA256" \
    python3 << 'PY'; then
import datetime as dt
import json
import os
from pathlib import Path

receipt = {
    "schema_version": 1,
    "status": "activation_verified",
    "scope": "device-proof-plus-complete-public-artifact",
    "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "mode": "local-sovereign",
    "variant": "germany",
    "basemap_version": os.environ["BASEMAP_VERSION"],
    "artifact_sha256": os.environ["ARTIFACT_SHA256"],
    "artifact_size_bytes": int(os.environ["ARTIFACT_SIZE"]),
    "release_proof_sha256": os.environ["RELEASE_PROOF_SHA256"],
    "source_commit": os.environ["SOURCE_COMMIT"],
    "style_sha256": os.environ["STYLE_SHA256"],
    "public_app_url": os.environ["PUBLIC_APP_URL"],
    "proofs": [
        "prepared-deep-validation",
        "fresh-deep-validation",
        "device-release-proof",
        "public-build-identity",
        "public-style-source",
        "public-metadata-sentinel",
        "http-206-range",
        "complete-public-artifact-sha256",
    ],
}
Path(os.environ["RECEIPT_PATH"]).write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
    rm -f "$receipt_tmp"
    return 1
  fi
  chmod 0600 "$receipt_tmp" || {
    rm -f "$receipt_tmp"
    return 1
  }
  mv -f "$receipt_tmp" "$ACTIVATION_RECEIPT" || {
    rm -f "$receipt_tmp"
    return 1
  }
}

verify_activation_receipt() {
  RECEIPT_PATH="$ACTIVATION_RECEIPT" \
    EXPECTED_SHA256="$ARTIFACT_SHA256" \
    EXPECTED_SOURCE_COMMIT="$SOURCE_COMMIT" \
    python3 << 'PY'
import json
import os
from pathlib import Path

receipt = json.loads(Path(os.environ["RECEIPT_PATH"]).read_text(encoding="utf-8"))
if receipt.get("status") != "activation_verified":
    raise SystemExit("Germany activation receipt status mismatch")
if receipt.get("artifact_sha256") != os.environ["EXPECTED_SHA256"]:
    raise SystemExit("Germany activation receipt artifact mismatch")
if receipt.get("source_commit") != os.environ["EXPECTED_SOURCE_COMMIT"]:
    raise SystemExit("Germany activation receipt source commit mismatch")
PY
}

[[ "$BASEMAP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  fail "BASEMAP_VERSION must use numeric semantic versioning"
require_positive_integer "GERMANY_BASEMAP_MAX_SOURCE_AGE_DAYS" "$MAX_SOURCE_AGE_DAYS"
require_positive_integer "GERMANY_BASEMAP_RELEASE_PROOF_MAX_AGE_HOURS" "$MAX_RELEASE_PROOF_AGE_HOURS"
require_positive_integer "GERMANY_BASEMAP_HTTP_CONNECT_TIMEOUT_SECONDS" "$HTTP_CONNECT_TIMEOUT_SECONDS"
require_positive_integer "GERMANY_BASEMAP_HTTP_MAX_TIME_SECONDS" "$HTTP_MAX_TIME_SECONDS"
[[ "$ACTIVATION_CONFIRM" == "$EXPECTED_CONFIRMATION" ]] ||
  fail "set GERMANY_BASEMAP_ACTIVATION_CONFIRM=$EXPECTED_CONFIRMATION for an intentional activation"
[[ -n "$RELEASE_PROOF_PATH" ]] ||
  fail "GERMANY_BASEMAP_RELEASE_PROOF_PATH is required before activation"
[[ "$PUBLIC_APP_URL" =~ ^https://[^/]+([/:].*)?$ ]] ||
  fail "WELTGEWEBE_PUBLIC_APP_URL must use HTTPS"
[[ -x "$DEPLOY_COMMAND" ]] || fail "deployment command is not executable: $DEPLOY_COMMAND"
command -v python3 > /dev/null 2>&1 || fail "python3 is required"
command -v curl > /dev/null 2>&1 || fail "curl is required"
command -v sha256sum > /dev/null 2>&1 || fail "sha256sum is required"
command -v readlink > /dev/null 2>&1 || fail "readlink is required"
command -v pnpm > /dev/null 2>&1 || fail "pnpm is required"
command -v git > /dev/null 2>&1 || fail "git is required"

for argument in "${DEPLOY_ARGS[@]}"; do
  case "$argument" in
    --no-build-web) fail "--no-build-web is incompatible with Germany activation" ;;
  esac
done

for required_path in \
  "$VERSIONED_ARTIFACT" \
  "$VERSIONED_META" \
  "$VERSIONED_VALIDATION" \
  "$RELEASE_PROOF_PATH" \
  "$STYLE_PATH"; do
  require_nonempty_path "$required_path"
done

verify_checkout_clean
SOURCE_COMMIT="$(git -C "$REPO_ROOT" rev-parse HEAD)"
[[ "$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "could not resolve a full source commit"
STYLE_SHA256="$(sha256sum "$STYLE_PATH" | awk '{print $1}')"
ARTIFACT_SHA256="$(sha256sum "$VERSIONED_ARTIFACT" | awk '{print $1}')"
ARTIFACT_SIZE="$(wc -c < "$VERSIONED_ARTIFACT" | tr -d '[:space:]')"
RELEASE_PROOF_SHA256="$(sha256sum "$RELEASE_PROOF_PATH" | awk '{print $1}')"

capture_alias_state "$ALIAS_ARTIFACT" "artifact"
capture_alias_state "$ALIAS_META" "metadata"

TMP_DIR="$(mktemp -d)"
trap on_exit EXIT
trap on_interrupt INT
trap on_terminate TERM
FRESH_VALIDATION_REPORT="$TMP_DIR/basemap-germany.validation.json"

if [[ ! -d "$REPO_ROOT/apps/web/node_modules" ]]; then
  fail "apps/web/node_modules is missing; install pinned dependencies before activation"
fi

pnpm -C "$REPO_ROOT/apps/web" validate:pmtiles -- \
  --archive "germany=$VERSIONED_ARTIFACT" \
  --style "$STYLE_PATH" \
  --output "$FRESH_VALIDATION_REPORT"
require_nonempty_path "$FRESH_VALIDATION_REPORT"

META_PATH="$VERSIONED_META" \
  PREPARED_VALIDATION_PATH="$VERSIONED_VALIDATION" \
  FRESH_VALIDATION_PATH="$FRESH_VALIDATION_REPORT" \
  RELEASE_PROOF_PATH="$RELEASE_PROOF_PATH" \
  VERSIONED_ARTIFACT_PATH="$VERSIONED_ARTIFACT" \
  EXPECTED_VERSION="$BASEMAP_VERSION" \
  EXPECTED_SHA256="$ARTIFACT_SHA256" \
  EXPECTED_SIZE="$ARTIFACT_SIZE" \
  EXPECTED_SOURCE_COMMIT="$SOURCE_COMMIT" \
  EXPECTED_STYLE_SHA256="$STYLE_SHA256" \
  MAX_RELEASE_PROOF_AGE_HOURS="$MAX_RELEASE_PROOF_AGE_HOURS" \
  python3 << 'PY'
import datetime as dt
import json
import os
from pathlib import Path


def reject(message: str) -> None:
    raise SystemExit(message)


def verify_raw_validation(validation: dict, size: int, label: str) -> None:
    if validation.get("schema_version") != 1 or validation.get("verdict") != "PROVEN":
        reject(f"Germany {label} validation verdict is not PROVEN")
    if validation.get("validator") != "bounded-pmtiles-deep-validation-v1":
        reject(f"Germany {label} validator identity mismatch")
    archives = validation.get("archives")
    if not isinstance(archives, list) or len(archives) != 1:
        reject(f"Germany {label} validation must contain exactly one archive")
    archive = archives[0]
    if archive.get("region") != "germany":
        reject(f"Germany {label} validation region mismatch")
    if archive.get("file_size") != size:
        reject(f"Germany {label} validation file size mismatch")
    if archive.get("directory", {}).get("tile_entry_count", 0) <= 0:
        reject(f"Germany {label} validation contains no tile entries")
    if not archive.get("samples"):
        reject(f"Germany {label} validation contains no decoded tile samples")


meta = json.loads(Path(os.environ["META_PATH"]).read_text(encoding="utf-8"))
prepared = json.loads(Path(os.environ["PREPARED_VALIDATION_PATH"]).read_text(encoding="utf-8"))
fresh = json.loads(Path(os.environ["FRESH_VALIDATION_PATH"]).read_text(encoding="utf-8"))
release = json.loads(Path(os.environ["RELEASE_PROOF_PATH"]).read_text(encoding="utf-8"))
artifact = Path(os.environ["VERSIONED_ARTIFACT_PATH"])
expected_size = int(os.environ["EXPECTED_SIZE"])
expected_sha256 = os.environ["EXPECTED_SHA256"]
expected_version = os.environ["EXPECTED_VERSION"]
expected_source_commit = os.environ["EXPECTED_SOURCE_COMMIT"]
expected_style_sha256 = os.environ["EXPECTED_STYLE_SHA256"]

if meta.get("schema_version") != 1:
    reject("Germany metadata schema mismatch")
if meta.get("status") != "ready" or meta.get("region") != "germany":
    reject("Germany metadata sentinel is not ready for the Germany region")
if meta.get("activation") != "opt-in":
    reject("Germany metadata must remain opt-in before activation")
if meta.get("version") != expected_version:
    reject("Germany metadata version mismatch")
if meta.get("artifact_name") != artifact.name:
    reject("Germany metadata artifact_name mismatch")
if meta.get("sha256") != expected_sha256:
    reject("Germany metadata SHA256 mismatch")
if meta.get("size_bytes") != expected_size:
    reject("Germany metadata size mismatch")

if prepared.get("schema_version") != 1 or prepared.get("verdict") != "PROVEN":
    reject("Germany prepared validation envelope is not PROVEN")
prepared_artifact = prepared.get("artifact", {})
if prepared_artifact != {
    "name": artifact.name,
    "sha256": expected_sha256,
    "size_bytes": expected_size,
}:
    reject("Germany prepared validation artifact binding mismatch")
verify_raw_validation(prepared.get("validation", {}), expected_size, "prepared")
verify_raw_validation(fresh, expected_size, "fresh")

required_release_proofs = {
    "desktop-maplibre",
    "ipad-maplibre",
    "five-region-visual",
    "no-external-map-requests",
    "staging-caddy-range",
}
if release.get("schema_version") != 1 or release.get("verdict") != "PROVEN":
    reject("Germany release proof is not PROVEN")
if release.get("basemap_version") != expected_version:
    reject("Germany release proof version mismatch")
if release.get("artifact_sha256") != expected_sha256:
    reject("Germany release proof artifact hash mismatch")
if release.get("artifact_size_bytes") != expected_size:
    reject("Germany release proof artifact size mismatch")
if release.get("frontend_commit") != expected_source_commit:
    reject("Germany release proof frontend commit mismatch")
if release.get("style_sha256") != expected_style_sha256:
    reject("Germany release proof style hash mismatch")
proofs = release.get("proofs")
if not isinstance(proofs, list) or not required_release_proofs.issubset(proofs):
    reject("Germany release proof is missing required browser/device evidence")

proofed_at_raw = release.get("proofed_at")
try:
    proofed_at = dt.datetime.fromisoformat(proofed_at_raw)
except (TypeError, ValueError) as exc:
    reject("Germany release proof proofed_at is invalid")
if proofed_at.tzinfo is None:
    reject("Germany release proof proofed_at must include a timezone")
now = dt.datetime.now(dt.timezone.utc)
age = now - proofed_at.astimezone(dt.timezone.utc)
if age.total_seconds() < 0:
    reject("Germany release proof lies in the future")
if age > dt.timedelta(hours=int(os.environ["MAX_RELEASE_PROOF_AGE_HOURS"])):
    reject("Germany release proof is too old")
PY

echo "[✓] Germany version, validation and device release proof verified."

# Re-evaluate checkout and freshness immediately before the first externally visible change.
verify_checkout_clean
verify_snapshot_freshness
ACTIVATION_TRANSACTION_OPEN=1
if ! invalidate_activation_receipt; then
  fail "could not invalidate a previous Germany activation receipt"
fi
if ! switch_alias_pair; then
  post_activation_failure "could not switch the Germany alias pair atomically"
fi

if ! deploy_frontend_variant "germany" "${DEPLOY_ARGS[@]}"; then
  post_activation_failure "Germany deployment failed"
fi

if [[ ! -s "$LOCAL_BUILD_IDENTITY" ]] || ! verify_identity_file "$LOCAL_BUILD_IDENTITY"; then
  post_activation_failure "local frontend artifact does not prove the Germany build identity"
fi

CURL_COMMON=(
  --fail
  --silent
  --show-error
  --connect-timeout "$HTTP_CONNECT_TIMEOUT_SECONDS"
  --max-time "$HTTP_MAX_TIME_SECONDS"
)
PUBLIC_IDENTITY="$TMP_DIR/basemap-build.json"
PUBLIC_STYLE="$TMP_DIR/style-germany.json"
PUBLIC_META="$TMP_DIR/basemap-germany.meta.json"
RANGE_HEADERS="$TMP_DIR/range.headers"
RANGE_PAYLOAD="$TMP_DIR/range.payload"
PUBLIC_ARTIFACT_URL="$PUBLIC_APP_URL/local-basemap/basemap-germany.pmtiles"

curl "${CURL_COMMON[@]}" "$PUBLIC_APP_URL/_app/basemap-build.json" -o "$PUBLIC_IDENTITY" ||
  post_activation_failure "public basemap build identity is unavailable"
verify_identity_file "$PUBLIC_IDENTITY" ||
  post_activation_failure "public frontend does not prove the Germany build identity"

curl "${CURL_COMMON[@]}" "$PUBLIC_APP_URL/local-basemap/style-germany.json" -o "$PUBLIC_STYLE" ||
  post_activation_failure "public Germany style is unavailable"
[[ "$(sha256sum "$PUBLIC_STYLE" | awk '{print $1}')" == "$STYLE_SHA256" ]] ||
  post_activation_failure "public Germany style hash mismatch"

curl "${CURL_COMMON[@]}" "$PUBLIC_APP_URL/local-basemap/basemap-germany.meta.json" -o "$PUBLIC_META" ||
  post_activation_failure "public Germany metadata is unavailable"
if ! PUBLIC_META_PATH="$PUBLIC_META" \
  EXPECTED_SHA256="$ARTIFACT_SHA256" \
  EXPECTED_SIZE="$ARTIFACT_SIZE" \
  python3 << 'PY'; then
import json
import os
from pathlib import Path

meta = json.loads(Path(os.environ["PUBLIC_META_PATH"]).read_text(encoding="utf-8"))
if meta.get("status") != "ready" or meta.get("region") != "germany":
    raise SystemExit("public Germany sentinel is not ready")
if meta.get("sha256") != os.environ["EXPECTED_SHA256"]:
    raise SystemExit("public Germany sentinel hash mismatch")
if meta.get("size_bytes") != int(os.environ["EXPECTED_SIZE"]):
    raise SystemExit("public Germany sentinel size mismatch")
PY
  post_activation_failure "public Germany metadata does not match the selected version"
fi

if ! HTTP_STATUS="$(curl "${CURL_COMMON[@]}" \
  -H 'Range: bytes=0-126' \
  -D "$RANGE_HEADERS" \
  -o "$RANGE_PAYLOAD" \
  -w '%{http_code}' \
  "$PUBLIC_ARTIFACT_URL")"; then
  post_activation_failure "public Germany PMTiles range request failed"
fi
[[ "$HTTP_STATUS" == "206" ]] ||
  post_activation_failure "public Germany PMTiles range request returned HTTP $HTTP_STATUS"
grep -qi '^content-type:[[:space:]]*application/octet-stream' "$RANGE_HEADERS" ||
  post_activation_failure "public Germany PMTiles response has the wrong Content-Type"
grep -qi "^content-range:[[:space:]]*bytes 0-126/${ARTIFACT_SIZE}" "$RANGE_HEADERS" ||
  post_activation_failure "public Germany PMTiles response lacks the exact Content-Range size"
grep -qi '^accept-ranges:[[:space:]]*bytes' "$RANGE_HEADERS" ||
  post_activation_failure "public Germany PMTiles response lacks Accept-Ranges: bytes"
[[ "$(wc -c < "$RANGE_PAYLOAD" | tr -d '[:space:]')" == "127" ]] ||
  post_activation_failure "public Germany PMTiles range payload has the wrong length"
[[ "$(head -c 7 "$RANGE_PAYLOAD")" == "PMTiles" ]] ||
  post_activation_failure "public Germany PMTiles signature mismatch"

if ! PUBLIC_ARTIFACT_SHA256="$(curl "${CURL_COMMON[@]}" "$PUBLIC_ARTIFACT_URL" | sha256sum | awk '{print $1}')"; then
  post_activation_failure "could not hash the complete public Germany PMTiles artifact within the readback deadline"
fi
[[ "$PUBLIC_ARTIFACT_SHA256" == "$ARTIFACT_SHA256" ]] ||
  post_activation_failure "complete public Germany PMTiles hash mismatch"

if ! write_activation_receipt; then
  post_activation_failure "could not persist the Germany activation receipt"
fi
if ! verify_activation_receipt; then
  post_activation_failure "persisted Germany activation receipt failed readback"
fi
ACTIVATION_COMMITTED=1
ACTIVATION_TRANSACTION_OPEN=0

echo "[✓] Germany PMTiles activation committed with device, identity, public hash and receipt proof."
echo "Receipt: $ACTIVATION_RECEIPT"
