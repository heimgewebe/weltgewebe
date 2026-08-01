#!/usr/bin/env bash
set -euo pipefail

# Build, deep-validate and publish one immutable Germany version from isolated
# staging. Preparation deliberately does not touch stable aliases: the selected
# version is exposed only inside the separately reviewed activation transaction.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." > /dev/null 2>&1 && pwd)"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
BUILD_DIR="${GERMANY_BASEMAP_BUILD_DIR:-$REPO_ROOT/build/basemap-staging/germany}"
TARGET_DIR="${1:-${GERMANY_BASEMAP_TARGET_DIR:-$REPO_ROOT/build/basemap}}"
ARTIFACT_NAME="basemap-germany-v${BASEMAP_VERSION}.pmtiles"
META_NAME="basemap-germany-v${BASEMAP_VERSION}.meta.json"
PROOF_NAME="basemap-germany-v${BASEMAP_VERSION}.validation.json"
ALIAS_ARTIFACT_NAME="basemap-germany.pmtiles"
ALIAS_META_NAME="basemap-germany.meta.json"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

path_state() {
  local path="$1"
  if [[ -L "$path" ]]; then
    printf 'symlink:%s\n' "$(readlink -- "$path")"
  elif [[ -e "$path" ]]; then
    printf 'file:%s:%s\n' "$(wc -c < "$path" | tr -d '[:space:]')" "$(sha256sum "$path" | awk '{print $1}')"
  else
    printf 'absent\n'
  fi
}

[[ "$BASEMAP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  fail "BASEMAP_VERSION must use numeric semantic versioning"
command -v node > /dev/null 2>&1 || fail "node is required"
command -v pnpm > /dev/null 2>&1 || fail "pnpm is required"
command -v python3 > /dev/null 2>&1 || fail "python3 is required"
command -v readlink > /dev/null 2>&1 || fail "readlink is required"
command -v sha256sum > /dev/null 2>&1 || fail "sha256sum is required"

mkdir -p "$BUILD_DIR"
[[ -d "$TARGET_DIR" ]] || fail "target directory does not exist: $TARGET_DIR"
BUILD_DIR="$(cd "$BUILD_DIR" > /dev/null 2>&1 && pwd)"
TARGET_DIR="$(cd "$TARGET_DIR" > /dev/null 2>&1 && pwd)"
[[ "$BUILD_DIR" != "$TARGET_DIR" ]] ||
  fail "Germany build and published target directories must differ"

ARTIFACT="$BUILD_DIR/$ARTIFACT_NAME"
META="$BUILD_DIR/$META_NAME"
PROOF_OUTPUT="${GERMANY_BASEMAP_PROOF_OUTPUT:-$BUILD_DIR/$PROOF_NAME}"
TARGET_ARTIFACT="$TARGET_DIR/$ARTIFACT_NAME"
TARGET_META="$TARGET_DIR/$META_NAME"
TARGET_PROOF="$TARGET_DIR/$PROOF_NAME"
ALIAS_ARTIFACT="$TARGET_DIR/$ALIAS_ARTIFACT_NAME"
ALIAS_META="$TARGET_DIR/$ALIAS_META_NAME"

for published_path in "$TARGET_ARTIFACT" "$TARGET_META" "$TARGET_PROOF"; do
  if [[ -e "$published_path" || -L "$published_path" ]]; then
    fail "published Germany version already exists: $published_path; choose a new BASEMAP_VERSION"
  fi
done

ALIAS_ARTIFACT_STATE_BEFORE="$(path_state "$ALIAS_ARTIFACT")"
ALIAS_META_STATE_BEFORE="$(path_state "$ALIAS_META")"

if [[ "${GERMANY_BASEMAP_SKIP_BUILD:-0}" != "1" ]]; then
  BASEMAP_DIR="$BUILD_DIR" bash "$SCRIPT_DIR/build-germany-pmtiles.sh"
fi

[[ -s "$ARTIFACT" ]] || fail "Germany artifact missing: $ARTIFACT"
[[ -s "$META" ]] || fail "Germany metadata missing: $META"

python3 - "$META" "$ARTIFACT" "$BASEMAP_VERSION" << 'PY'
import hashlib
import json
import pathlib
import sys

meta_path = pathlib.Path(sys.argv[1])
artifact_path = pathlib.Path(sys.argv[2])
expected_version = sys.argv[3]
meta = json.loads(meta_path.read_text(encoding="utf-8"))
size = artifact_path.stat().st_size
sha256 = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
if meta.get("schema_version") != 1:
    raise SystemExit("Germany sentinel schema mismatch")
if meta.get("status") != "ready" or meta.get("region") != "germany":
    raise SystemExit("Germany sentinel is not ready for Germany")
if meta.get("activation") != "opt-in":
    raise SystemExit("Germany sentinel must remain opt-in during preparation")
if meta.get("version") != expected_version:
    raise SystemExit("Germany sentinel version mismatch")
if meta.get("artifact_name") != artifact_path.name:
    raise SystemExit("Germany sentinel artifact_name mismatch")
if meta.get("size_bytes") != size:
    raise SystemExit("Germany sentinel size mismatch")
if meta.get("sha256") != sha256:
    raise SystemExit("Germany sentinel SHA256 mismatch")
PY

if [[ ! -d "$REPO_ROOT/apps/web/node_modules" ]]; then
  pnpm -C "$REPO_ROOT/apps/web" install --frozen-lockfile
fi

pnpm -C "$REPO_ROOT/apps/web" validate:pmtiles -- \
  --archive "germany=$ARTIFACT" \
  --style "$REPO_ROOT/map-style/style-germany.json" \
  --output "$PROOF_OUTPUT"

[[ -s "$PROOF_OUTPUT" ]] || fail "deep-validation report was not written"

ARTIFACT_TMP="$TARGET_DIR/.${ARTIFACT_NAME}.tmp.$$"
PROOF_TMP="$TARGET_DIR/.${PROOF_NAME}.tmp.$$"
META_TMP="$TARGET_DIR/.${META_NAME}.tmp.$$"
ARTIFACT_CREATED=0
PROOF_CREATED=0
META_CREATED=0
PUBLISH_COMPLETE=0

cleanup_publish() {
  rm -f "$ARTIFACT_TMP" "$PROOF_TMP" "$META_TMP"
  if [[ "$PUBLISH_COMPLETE" != "1" ]]; then
    [[ "$META_CREATED" == "1" ]] && rm -f "$TARGET_META"
    [[ "$PROOF_CREATED" == "1" ]] && rm -f "$TARGET_PROOF"
    [[ "$ARTIFACT_CREATED" == "1" ]] && rm -f "$TARGET_ARTIFACT"
  fi
}
trap cleanup_publish EXIT

install -m 0644 "$ARTIFACT" "$ARTIFACT_TMP"
install -m 0644 "$PROOF_OUTPUT" "$PROOF_TMP"
install -m 0644 "$META" "$META_TMP"

ln "$ARTIFACT_TMP" "$TARGET_ARTIFACT" ||
  fail "could not publish immutable Germany artifact: $TARGET_ARTIFACT"
ARTIFACT_CREATED=1
ln "$PROOF_TMP" "$TARGET_PROOF" ||
  fail "could not publish immutable Germany validation report: $TARGET_PROOF"
PROOF_CREATED=1
ln "$META_TMP" "$TARGET_META" ||
  fail "could not publish immutable Germany sentinel: $TARGET_META"
META_CREATED=1

PUBLISH_COMPLETE=1
cleanup_publish
trap - EXIT

[[ -s "$TARGET_ARTIFACT" ]] || fail "published Germany artifact missing"
[[ -s "$TARGET_PROOF" ]] || fail "published Germany validation report missing"
[[ -s "$TARGET_META" ]] || fail "published Germany sentinel missing"

cmp -s "$ARTIFACT" "$TARGET_ARTIFACT" || fail "published Germany artifact differs from staging"
cmp -s "$PROOF_OUTPUT" "$TARGET_PROOF" || fail "published Germany validation report differs from staging"
cmp -s "$META" "$TARGET_META" || fail "published Germany sentinel differs from staging"

ALIAS_ARTIFACT_STATE_AFTER="$(path_state "$ALIAS_ARTIFACT")"
ALIAS_META_STATE_AFTER="$(path_state "$ALIAS_META")"
[[ "$ALIAS_ARTIFACT_STATE_AFTER" == "$ALIAS_ARTIFACT_STATE_BEFORE" ]] ||
  fail "preparation changed the stable Germany artifact alias"
[[ "$ALIAS_META_STATE_AFTER" == "$ALIAS_META_STATE_BEFORE" ]] ||
  fail "preparation changed the stable Germany metadata alias"

echo "Germany PMTiles version preparation is complete."
echo "Isolated build: $BUILD_DIR"
echo "Published version:"
echo "  $TARGET_ARTIFACT"
echo "  $TARGET_META"
echo "  $TARGET_PROOF"
echo "Stable aliases were NOT changed:"
echo "  $ALIAS_ARTIFACT"
echo "  $ALIAS_META"
echo "Activation remains a separate reviewed transaction."
