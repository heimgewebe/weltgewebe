#!/usr/bin/env bash
set -euo pipefail

# Fail-closed activation wrapper for the nationwide Germany PMTiles variant.
#
# Preparation publishes immutable versioned files only. This operator binds a
# device release proof to the exact version, switches both stable aliases inside
# the activation transaction, forces a fresh Germany frontend build, verifies
# the complete public archive and restores aliases plus the regional frontend
# whenever deployment, readback or receipt creation fails.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." > /dev/null 2>&1 && pwd)"
BASEMAP_DIR="${BASEMAP_DIR:-$REPO_ROOT/build/basemap}"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
MAX_SOURCE_AGE_DAYS="${GERMANY_BASEMAP_MAX_SOURCE_AGE_DAYS:-45}"
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
LOCAL_BUILD_IDENTITY="${WELTGEWEBE_BUILD_IDENTITY_PATH:-$REPO_ROOT/apps/web/build/_app/basemap-build.json}"
ACTIVATION_RECEIPT="$STATE_DIR/germany-basemap-activation.json"
ALIASES_SWITCHED=0
PREVIOUS_ARTIFACT_ALIAS_PRESENT=0
PREVIOUS_META_ALIAS_PRESENT=0
PREVIOUS_ARTIFACT_ALIAS_TARGET=""
PREVIOUS_META_ALIAS_TARGET=""

fail() {
  echo "ERROR: $*" >&2
  exit 1
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
  local restored=0

  if ! restore_one_alias \
    "$PREVIOUS_ARTIFACT_ALIAS_PRESENT" \
    "$PREVIOUS_ARTIFACT_ALIAS_TARGET" \
    "$ALIAS_ARTIFACT"; then
    echo "CRITICAL: Could not restore the previous Germany artifact alias." >&2
    restored=1
  fi
  if ! restore_one_alias \
    "$PREVIOUS_META_ALIAS_PRESENT" \
    "$PREVIOUS_META_ALIAS_TARGET" \
    "$ALIAS_META"; then
    echo "CRITICAL: Could not restore the previous Germany metadata alias." >&2
    restored=1
  fi
  return "$restored"
}

switch_alias_pair() {
  local artifact_target="$(basename -- "$VERSIONED_ARTIFACT")"
  local meta_target="$(basename -- "$VERSIONED_META")"

  atomic_symlink "$artifact_target" "$ALIAS_ARTIFACT" ||
    fail "could not switch the stable Germany artifact alias"
  if ! atomic_symlink "$meta_target" "$ALIAS_META"; then
    restore_one_alias \
      "$PREVIOUS_ARTIFACT_ALIAS_PRESENT" \
      "$PREVIOUS_ARTIFACT_ALIAS_TARGET" \
      "$ALIAS_ARTIFACT" || true
    fail "could not switch the stable Germany metadata alias"
  fi
  ALIASES_SWITCHED=1
}

rollback_activation() {
  local rollback_failed=0

  echo "WARNING: Germany activation failed; restoring aliases and the regional frontend." >&2
  if [[ "$ALIASES_SWITCHED" == "1" ]] && ! restore_alias_pair; then
    rollback_failed=1
  fi
  if ! deploy_frontend_variant "regional" "${DEPLOY_ARGS[@]}"; then
    echo "CRITICAL: Automatic regional frontend rollback failed." >&2
    rollback_failed=1
  else
    echo "[✓] Regional frontend rollback completed." >&2
  fi
  return "$rollback_failed"
}

post_activation_failure() {
  local message="$1"

  rollback_activation || true
  fail "$message"
}

verify_identity_file() {
  local identity_path="$1"
  IDENTITY_PATH="$identity_path" python3 << 'PY'
import json
import os
from pathlib import Path

identity = json.loads(Path(os.environ["IDENTITY_PATH"]).read_text(encoding="utf-8"))
expected = {
    "schema_version": 1,
    "mode": "local-sovereign",
    "variant": "germany",
    "style_path": "/local-basemap/style-germany.json",
}
if identity != expected:
    raise SystemExit(f"unexpected basemap build identity: {identity!r}")
PY
}

write_activation_receipt() {
  local receipt_tmp="${ACTIVATION_RECEIPT}.tmp.$$"

  install -d -m 0700 "$STATE_DIR" || return 1
  rm -f "$receipt_tmp"
  RECEIPT_PATH="$receipt_tmp" \
    PUBLIC_APP_URL="$PUBLIC_APP_URL" \
    ARTIFACT_SHA256="$ARTIFACT_SHA256" \
    ARTIFACT_SIZE="$ARTIFACT_SIZE" \
    BASEMAP_VERSION="$BASEMAP_VERSION" \
    RELEASE_PROOF_SHA256="$RELEASE_PROOF_SHA256" \
    python3 << 'PY' || {
      rm -f "$receipt_tmp"
      return 1
    }
import datetime as dt
import json
import os
from pathlib import Path

receipt = {
    "schema_version": 1,
    "status": "activation_verified",
    "scope": "predeployment-device-proof-plus-complete-public-artifact",
    "verified_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "mode": "local-sovereign",
    "variant": "germany",
    "basemap_version": os.environ["BASEMAP_VERSION"],
    "artifact_sha256": os.environ["ARTIFACT_SHA256"],
    "artifact_size_bytes": int(os.environ["ARTIFACT_SIZE"]),
    "release_proof_sha256": os.environ["RELEASE_PROOF_SHA256"],
    "public_app_url": os.environ["PUBLIC_APP_URL"],
    "proofs": [
        "fresh-deep-validation",
        "predeployment-device-release-proof",
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
  chmod 0600 "$receipt_tmp" || {
    rm -f "$receipt_tmp"
    return 1
  }
  mv -f "$receipt_tmp" "$ACTIVATION_RECEIPT" || {
    rm -f "$receipt_tmp"
    return 1
  }
}

case "$BASEMAP_VERSION" in
  *[!0-9.]* | .* | *. | *..*) fail "BASEMAP_VERSION must be numeric semantic versioning" ;;
esac
[[ "$BASEMAP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  fail "BASEMAP_VERSION must use numeric semantic versioning"
case "$MAX_SOURCE_AGE_DAYS" in
  '' | *[!0-9]*) fail "GERMANY_BASEMAP_MAX_SOURCE_AGE_DAYS must be a positive integer" ;;
esac
((MAX_SOURCE_AGE_DAYS > 0)) ||
  fail "GERMANY_BASEMAP_MAX_SOURCE_AGE_DAYS must be greater than zero"
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

for argument in "${DEPLOY_ARGS[@]}"; do
  case "$argument" in
    --no-build-web)
      fail "--no-build-web is incompatible with Germany activation"
      ;;
  esac
done

for required_path in \
  "$VERSIONED_ARTIFACT" \
  "$VERSIONED_META" \
  "$VERSIONED_VALIDATION" \
  "$RELEASE_PROOF_PATH" \
  "$REPO_ROOT/map-style/style-germany.json"; do
  require_nonempty_path "$required_path"
done

capture_alias_state "$ALIAS_ARTIFACT" "artifact"
capture_alias_state "$ALIAS_META" "metadata"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT
FRESH_VALIDATION_REPORT="$TMP_DIR/basemap-germany.validation.json"

if [[ ! -d "$REPO_ROOT/apps/web/node_modules" ]]; then
  fail "apps/web/node_modules is missing; install pinned dependencies before activation"
fi

pnpm -C "$REPO_ROOT/apps/web" validate:pmtiles -- \
  --archive "germany=$VERSIONED_ARTIFACT" \
  --style "$REPO_ROOT/map-style/style-germany.json" \
  --output "$FRESH_VALIDATION_REPORT"
require_nonempty_path "$FRESH_VALIDATION_REPORT"

ARTIFACT_SHA256="$(sha256sum "$VERSIONED_ARTIFACT" | awk '{print $1}')"
ARTIFACT_SIZE="$(wc -c < "$VERSIONED_ARTIFACT" | tr -d '[:space:]')"
RELEASE_PROOF_SHA256="$(sha256sum "$RELEASE_PROOF_PATH" | awk '{print $1}')"

META_PATH="$VERSIONED_META" \
  PREPARED_VALIDATION_PATH="$VERSIONED_VALIDATION" \
  FRESH_VALIDATION_PATH="$FRESH_VALIDATION_REPORT" \
  RELEASE_PROOF_PATH="$RELEASE_PROOF_PATH" \
  VERSIONED_ARTIFACT_PATH="$VERSIONED_ARTIFACT" \
  EXPECTED_VERSION="$BASEMAP_VERSION" \
  EXPECTED_SHA256="$ARTIFACT_SHA256" \
  EXPECTED_SIZE="$ARTIFACT_SIZE" \
  MAX_SOURCE_AGE_DAYS="$MAX_SOURCE_AGE_DAYS" \
  python3 << 'PY'
import datetime as dt
import json
import os
from pathlib import Path


def reject(message: str) -> None:
    raise SystemExit(message)


def verify_validation(validation: dict, artifact: Path, size: int, label: str) -> None:
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
    if Path(archive.get("archive_path", "")).resolve() != artifact:
        reject(f"Germany {label} validation archive path mismatch")
    if archive.get("file_size") != size:
        reject(f"Germany {label} validation file size mismatch")
    if archive.get("directory", {}).get("tile_entry_count", 0) <= 0:
        reject(f"Germany {label} validation contains no tile entries")
    if not archive.get("samples"):
        reject(f"Germany {label} validation contains no decoded tile samples")


meta_path = Path(os.environ["META_PATH"])
prepared_validation_path = Path(os.environ["PREPARED_VALIDATION_PATH"])
fresh_validation_path = Path(os.environ["FRESH_VALIDATION_PATH"])
release_proof_path = Path(os.environ["RELEASE_PROOF_PATH"])
artifact = Path(os.environ["VERSIONED_ARTIFACT_PATH"]).resolve()
meta = json.loads(meta_path.read_text(encoding="utf-8"))
prepared_validation = json.loads(prepared_validation_path.read_text(encoding="utf-8"))
fresh_validation = json.loads(fresh_validation_path.read_text(encoding="utf-8"))
release_proof = json.loads(release_proof_path.read_text(encoding="utf-8"))
expected_size = int(os.environ["EXPECTED_SIZE"])
expected_sha256 = os.environ["EXPECTED_SHA256"]
expected_version = os.environ["EXPECTED_VERSION"]

if meta.get("schema_version") != 1:
    reject("Germany metadata schema mismatch")
if meta.get("status") != "ready" or meta.get("region") != "germany":
    reject("Germany metadata sentinel is not ready for the Germany region")
if meta.get("activation") != "opt-in":
    reject("Germany metadata must remain opt-in before the reviewed activation")
if meta.get("version") != expected_version:
    reject("Germany metadata version mismatch")
if meta.get("artifact_name") != artifact.name:
    reject("Germany metadata artifact_name mismatch")
if meta.get("sha256") != expected_sha256:
    reject("Germany metadata SHA256 mismatch")
if meta.get("size_bytes") != expected_size:
    reject("Germany metadata size mismatch")

snapshot_date = meta.get("input", {}).get("snapshot_date")
try:
    snapshot = dt.date.fromisoformat(snapshot_date)
except (TypeError, ValueError):
    reject("Germany metadata snapshot_date is invalid")
age_days = (dt.datetime.now(dt.timezone.utc).date() - snapshot).days
if age_days < 0:
    reject("Germany metadata snapshot_date lies in the future")
if age_days > int(os.environ["MAX_SOURCE_AGE_DAYS"]):
    reject(
        f"Germany OSM snapshot is {age_days} days old; maximum is "
        f"{os.environ['MAX_SOURCE_AGE_DAYS']} days"
    )

verify_validation(prepared_validation, artifact, expected_size, "prepared")
verify_validation(fresh_validation, artifact, expected_size, "fresh")

required_release_proofs = {
    "desktop-maplibre",
    "ipad-maplibre",
    "five-region-visual",
    "no-external-map-requests",
    "staging-caddy-range",
}
if release_proof.get("schema_version") != 1:
    reject("Germany release proof schema mismatch")
if release_proof.get("verdict") != "PROVEN":
    reject("Germany release proof verdict is not PROVEN")
if release_proof.get("basemap_version") != expected_version:
    reject("Germany release proof version mismatch")
if release_proof.get("artifact_sha256") != expected_sha256:
    reject("Germany release proof artifact hash mismatch")
if release_proof.get("artifact_size_bytes") != expected_size:
    reject("Germany release proof artifact size mismatch")
proofs = release_proof.get("proofs")
if not isinstance(proofs, list) or not required_release_proofs.issubset(proofs):
    reject("Germany release proof is missing required browser/device evidence")
PY

echo "[✓] Germany version, prepared proof, fresh validation and device release proof verified."

switch_alias_pair

if ! deploy_frontend_variant "germany" "${DEPLOY_ARGS[@]}"; then
  post_activation_failure "Germany deployment failed; alias and regional rollback were attempted"
fi

if [[ ! -s "$LOCAL_BUILD_IDENTITY" ]] || ! verify_identity_file "$LOCAL_BUILD_IDENTITY"; then
  post_activation_failure "local frontend artifact does not prove the Germany build variant"
fi

PUBLIC_IDENTITY="$TMP_DIR/basemap-build.json"
PUBLIC_STYLE="$TMP_DIR/style-germany.json"
PUBLIC_META="$TMP_DIR/basemap-germany.meta.json"
RANGE_HEADERS="$TMP_DIR/range.headers"
RANGE_PAYLOAD="$TMP_DIR/range.payload"
PUBLIC_ARTIFACT_URL="$PUBLIC_APP_URL/local-basemap/basemap-germany.pmtiles"

curl -fsS "$PUBLIC_APP_URL/_app/basemap-build.json" -o "$PUBLIC_IDENTITY" ||
  post_activation_failure "public basemap build identity is unavailable"
verify_identity_file "$PUBLIC_IDENTITY" ||
  post_activation_failure "public frontend does not prove the Germany build variant"

curl -fsS "$PUBLIC_APP_URL/local-basemap/style-germany.json" -o "$PUBLIC_STYLE" ||
  post_activation_failure "public Germany style is unavailable"
STYLE_PATH="$PUBLIC_STYLE" python3 << 'PY' ||
  post_activation_failure "public Germany style contract mismatch"
import json
import os
from pathlib import Path

style = json.loads(Path(os.environ["STYLE_PATH"]).read_text(encoding="utf-8"))
source = style.get("sources", {}).get("basemap-germany")
if source != {"type": "vector", "url": "pmtiles://basemap-germany.pmtiles"}:
    raise SystemExit("Germany style source mismatch")
if style.get("metadata", {}).get("weltgewebe:variant") != "germany":
    raise SystemExit("Germany style variant metadata mismatch")
PY

curl -fsS "$PUBLIC_APP_URL/local-basemap/basemap-germany.meta.json" -o "$PUBLIC_META" ||
  post_activation_failure "public Germany metadata is unavailable"
PUBLIC_META_PATH="$PUBLIC_META" \
  EXPECTED_SHA256="$ARTIFACT_SHA256" \
  EXPECTED_SIZE="$ARTIFACT_SIZE" \
  python3 << 'PY' ||
  post_activation_failure "public Germany metadata does not match the selected version"
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

HTTP_STATUS="$(curl -sS \
  -H 'Range: bytes=0-126' \
  -D "$RANGE_HEADERS" \
  -o "$RANGE_PAYLOAD" \
  -w '%{http_code}' \
  "$PUBLIC_ARTIFACT_URL")" ||
  post_activation_failure "public Germany PMTiles range request failed"
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

if ! PUBLIC_ARTIFACT_SHA256="$(curl -fsS "$PUBLIC_ARTIFACT_URL" | sha256sum | awk '{print $1}')"; then
  post_activation_failure "could not hash the complete public Germany PMTiles artifact"
fi
[[ "$PUBLIC_ARTIFACT_SHA256" == "$ARTIFACT_SHA256" ]] ||
  post_activation_failure "complete public Germany PMTiles hash mismatch"

if ! write_activation_receipt; then
  post_activation_failure "could not persist the Germany activation receipt"
fi

echo "[✓] Germany PMTiles activation committed with alias, device, public hash and receipt proof."
echo "Receipt: $ACTIVATION_RECEIPT"
