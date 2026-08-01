#!/usr/bin/env bash
set -euo pipefail

# Fail-closed activation wrapper for the nationwide Germany PMTiles variant.
#
# This is intentionally separate from the normal deployment entrypoint. It
# proves the prepared artifact, re-runs deep validation against the current
# bytes, forces a fresh Germany frontend build, verifies the public build
# identity/style/range contract and rolls the frontend back to the regional
# variant when a post-deploy check fails.

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

VERSIONED_ARTIFACT="$BASEMAP_DIR/basemap-germany-v${BASEMAP_VERSION}.pmtiles"
VERSIONED_META="$BASEMAP_DIR/basemap-germany-v${BASEMAP_VERSION}.meta.json"
ALIAS_ARTIFACT="$BASEMAP_DIR/basemap-germany.pmtiles"
ALIAS_META="$BASEMAP_DIR/basemap-germany.meta.json"
PREPARED_VALIDATION_REPORT="${GERMANY_BASEMAP_PROOF_OUTPUT:-$BASEMAP_DIR/basemap-germany-v${BASEMAP_VERSION}.validation.json}"
LOCAL_BUILD_IDENTITY="${WELTGEWEBE_BUILD_IDENTITY_PATH:-$REPO_ROOT/apps/web/build/_app/basemap-build.json}"
ACTIVATION_RECEIPT="$STATE_DIR/germany-basemap-activation.json"

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
[[ "$PUBLIC_APP_URL" =~ ^https://[^/]+([/:].*)?$ ]] ||
  fail "WELTGEWEBE_PUBLIC_APP_URL must use HTTPS"
[[ -x "$DEPLOY_COMMAND" ]] || fail "deployment command is not executable: $DEPLOY_COMMAND"
command -v python3 > /dev/null 2>&1 || fail "python3 is required"
command -v curl > /dev/null 2>&1 || fail "curl is required"
command -v sha256sum > /dev/null 2>&1 || fail "sha256sum is required"
command -v readlink > /dev/null 2>&1 || fail "readlink is required"
command -v pnpm > /dev/null 2>&1 || fail "pnpm is required"

for argument in "$@"; do
  case "$argument" in
    --no-build-web)
      fail "--no-build-web is incompatible with Germany activation"
      ;;
  esac
done

for required_path in \
  "$VERSIONED_ARTIFACT" \
  "$VERSIONED_META" \
  "$ALIAS_ARTIFACT" \
  "$ALIAS_META" \
  "$PREPARED_VALIDATION_REPORT" \
  "$REPO_ROOT/map-style/style-germany.json"; do
  require_nonempty_path "$required_path"
done

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

ARTIFACT_SHA256="$(sha256sum "$ALIAS_ARTIFACT" | awk '{print $1}')"
ARTIFACT_SIZE="$(wc -c < "$ALIAS_ARTIFACT" | tr -d '[:space:]')"

META_PATH="$ALIAS_META" \
  VERSIONED_META_PATH="$VERSIONED_META" \
  ALIAS_META_PATH="$ALIAS_META" \
  VALIDATION_PATH="$FRESH_VALIDATION_REPORT" \
  VERSIONED_ARTIFACT_PATH="$VERSIONED_ARTIFACT" \
  ALIAS_ARTIFACT_PATH="$ALIAS_ARTIFACT" \
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


meta_path = Path(os.environ["META_PATH"])
validation_path = Path(os.environ["VALIDATION_PATH"])
versioned_meta = Path(os.environ["VERSIONED_META_PATH"]).resolve()
alias_meta = Path(os.environ["ALIAS_META_PATH"]).resolve()
versioned_artifact = Path(os.environ["VERSIONED_ARTIFACT_PATH"]).resolve()
alias_artifact = Path(os.environ["ALIAS_ARTIFACT_PATH"]).resolve()
meta = json.loads(meta_path.read_text(encoding="utf-8"))
validation = json.loads(validation_path.read_text(encoding="utf-8"))

if alias_artifact != versioned_artifact:
    reject("stable Germany artifact alias does not resolve to the selected version")
if alias_meta != versioned_meta:
    reject("stable Germany metadata alias does not resolve to the selected version")
if meta.get("schema_version") != 1:
    reject("Germany metadata schema mismatch")
if meta.get("status") != "ready" or meta.get("region") != "germany":
    reject("Germany metadata sentinel is not ready for the Germany region")
if meta.get("activation") != "opt-in":
    reject("Germany metadata must remain opt-in before the reviewed activation")
if meta.get("version") != os.environ["EXPECTED_VERSION"]:
    reject("Germany metadata version mismatch")
if meta.get("artifact_name") != versioned_artifact.name:
    reject("Germany metadata artifact_name mismatch")
if meta.get("sha256") != os.environ["EXPECTED_SHA256"]:
    reject("Germany metadata SHA256 mismatch")
if meta.get("size_bytes") != int(os.environ["EXPECTED_SIZE"]):
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

if validation.get("schema_version") != 1 or validation.get("verdict") != "PROVEN":
    reject("Germany deep-validation verdict is not PROVEN")
if validation.get("validator") != "bounded-pmtiles-deep-validation-v1":
    reject("Germany deep-validation validator identity mismatch")
archives = validation.get("archives")
if not isinstance(archives, list) or len(archives) != 1:
    reject("Germany deep-validation must contain exactly one archive")
archive = archives[0]
if archive.get("region") != "germany":
    reject("Germany deep-validation region mismatch")
if Path(archive.get("archive_path", "")).resolve() != versioned_artifact:
    reject("Germany deep-validation archive path mismatch")
if archive.get("file_size") != int(os.environ["EXPECTED_SIZE"]):
    reject("Germany deep-validation file size mismatch")
if archive.get("directory", {}).get("tile_entry_count", 0) <= 0:
    reject("Germany deep-validation contains no tile entries")
if not archive.get("samples"):
    reject("Germany deep-validation contains no decoded tile samples")
PY

echo "[✓] Current Germany artifact, aliases, sentinel and deep validation verified."

rollback_frontend() {
  echo "WARNING: Germany deployment or post-deploy proof failed; rebuilding the regional rollback variant." >&2
  if deploy_frontend_variant "regional" "$@"; then
    echo "[✓] Regional frontend rollback completed." >&2
  else
    echo "CRITICAL: Automatic regional frontend rollback failed." >&2
  fi
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

if ! deploy_frontend_variant "germany" "$@"; then
  rollback_frontend "$@"
  fail "Germany deployment command failed; regional rollback was attempted"
fi

if [[ ! -s "$LOCAL_BUILD_IDENTITY" ]] || ! verify_identity_file "$LOCAL_BUILD_IDENTITY"; then
  rollback_frontend "$@"
  fail "local frontend artifact does not prove the Germany build variant"
fi

PUBLIC_IDENTITY="$TMP_DIR/basemap-build.json"
PUBLIC_STYLE="$TMP_DIR/style-germany.json"
PUBLIC_META="$TMP_DIR/basemap-germany.meta.json"
RANGE_HEADERS="$TMP_DIR/range.headers"
RANGE_PAYLOAD="$TMP_DIR/range.payload"

post_deploy_failure() {
  local message="$1"
  shift
  rollback_frontend "$@"
  fail "$message"
}

curl -fsS "$PUBLIC_APP_URL/_app/basemap-build.json" -o "$PUBLIC_IDENTITY" ||
  post_deploy_failure "public basemap build identity is unavailable" "$@"
verify_identity_file "$PUBLIC_IDENTITY" ||
  post_deploy_failure "public frontend does not prove the Germany build variant" "$@"

curl -fsS "$PUBLIC_APP_URL/local-basemap/style-germany.json" -o "$PUBLIC_STYLE" ||
  post_deploy_failure "public Germany style is unavailable" "$@"
STYLE_PATH="$PUBLIC_STYLE" python3 << 'PY' ||
  post_deploy_failure "public Germany style contract mismatch" "$@"
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
  post_deploy_failure "public Germany metadata is unavailable" "$@"
PUBLIC_META_PATH="$PUBLIC_META" \
  EXPECTED_SHA256="$ARTIFACT_SHA256" \
  EXPECTED_SIZE="$ARTIFACT_SIZE" \
  python3 << 'PY' ||
  post_deploy_failure "public Germany metadata does not match the prepared artifact" "$@"
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
    "$PUBLIC_APP_URL/local-basemap/basemap-germany.pmtiles")" ||
  post_deploy_failure "public Germany PMTiles range request failed" "$@"
[[ "$HTTP_STATUS" == "206" ]] ||
  post_deploy_failure "public Germany PMTiles range request returned HTTP $HTTP_STATUS" "$@"
grep -qi '^content-type:[[:space:]]*application/octet-stream' "$RANGE_HEADERS" ||
  post_deploy_failure "public Germany PMTiles response has the wrong Content-Type" "$@"
grep -qi '^content-range:[[:space:]]*bytes 0-126/' "$RANGE_HEADERS" ||
  post_deploy_failure "public Germany PMTiles response lacks the expected Content-Range" "$@"
grep -qi '^accept-ranges:[[:space:]]*bytes' "$RANGE_HEADERS" ||
  post_deploy_failure "public Germany PMTiles response lacks Accept-Ranges: bytes" "$@"
[[ "$(wc -c < "$RANGE_PAYLOAD" | tr -d '[:space:]')" == "127" ]] ||
  post_deploy_failure "public Germany PMTiles range payload has the wrong length" "$@"
[[ "$(head -c 7 "$RANGE_PAYLOAD")" == "PMTiles" ]] ||
  post_deploy_failure "public Germany PMTiles signature mismatch" "$@"

install -d -m 0700 "$STATE_DIR"
RECEIPT_TMP="${ACTIVATION_RECEIPT}.tmp.$$"
RECEIPT_PATH="$RECEIPT_TMP" \
  PUBLIC_APP_URL="$PUBLIC_APP_URL" \
  ARTIFACT_SHA256="$ARTIFACT_SHA256" \
  ARTIFACT_SIZE="$ARTIFACT_SIZE" \
  BASEMAP_VERSION="$BASEMAP_VERSION" \
  python3 << 'PY'
import datetime as dt
import json
import os
from pathlib import Path

receipt = {
    "schema_version": 1,
    "status": "verified",
    "activated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    "mode": "local-sovereign",
    "variant": "germany",
    "basemap_version": os.environ["BASEMAP_VERSION"],
    "artifact_sha256": os.environ["ARTIFACT_SHA256"],
    "artifact_size_bytes": int(os.environ["ARTIFACT_SIZE"]),
    "public_app_url": os.environ["PUBLIC_APP_URL"],
    "proofs": [
        "fresh-deep-validation",
        "public-build-identity",
        "public-style-source",
        "public-metadata-sentinel",
        "http-206-range",
        "pmtiles-signature",
    ],
}
Path(os.environ["RECEIPT_PATH"]).write_text(
    json.dumps(receipt, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
chmod 0600 "$RECEIPT_TMP"
mv -f "$RECEIPT_TMP" "$ACTIVATION_RECEIPT"

echo "[✓] Germany PMTiles activation verified end to end."
echo "Receipt: $ACTIVATION_RECEIPT"
