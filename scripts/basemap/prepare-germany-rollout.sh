#!/usr/bin/env bash
set -euo pipefail

# Build, deep-validate and publish the Germany artifact from isolated staging.
# The build directory and published target must differ. This prevents a stable
# alias from ever exposing newly built bytes before deep validation succeeds.
# Production activation remains a separate reviewed act.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." > /dev/null 2>&1 && pwd)"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
BUILD_DIR="${GERMANY_BASEMAP_BUILD_DIR:-$REPO_ROOT/build/basemap-staging/germany}"
TARGET_DIR="${1:-${GERMANY_BASEMAP_TARGET_DIR:-$REPO_ROOT/build/basemap}}"
ARTIFACT_NAME="basemap-germany-v${BASEMAP_VERSION}.pmtiles"
META_NAME="basemap-germany-v${BASEMAP_VERSION}.meta.json"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[[ "$BASEMAP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  fail "BASEMAP_VERSION must use numeric semantic versioning"
command -v node > /dev/null 2>&1 || fail "node is required"
command -v pnpm > /dev/null 2>&1 || fail "pnpm is required"
command -v python3 > /dev/null 2>&1 || fail "python3 is required"
command -v readlink > /dev/null 2>&1 || fail "readlink is required"

mkdir -p "$BUILD_DIR"
[[ -d "$TARGET_DIR" ]] || fail "target directory does not exist: $TARGET_DIR"
BUILD_DIR="$(cd "$BUILD_DIR" > /dev/null 2>&1 && pwd)"
TARGET_DIR="$(cd "$TARGET_DIR" > /dev/null 2>&1 && pwd)"
[[ "$BUILD_DIR" != "$TARGET_DIR" ]] ||
  fail "Germany build and published target directories must differ"

ARTIFACT="$BUILD_DIR/$ARTIFACT_NAME"
META="$BUILD_DIR/$META_NAME"
PROOF_OUTPUT="${GERMANY_BASEMAP_PROOF_OUTPUT:-$BUILD_DIR/basemap-germany-v${BASEMAP_VERSION}.validation.json}"
TARGET_ARTIFACT="$TARGET_DIR/$ARTIFACT_NAME"
TARGET_META="$TARGET_DIR/$META_NAME"

for published_path in "$TARGET_ARTIFACT" "$TARGET_META"; do
  if [[ -e "$published_path" || -L "$published_path" ]]; then
    fail "published Germany version already exists: $published_path; choose a new BASEMAP_VERSION"
  fi
done

if [[ "${GERMANY_BASEMAP_SKIP_BUILD:-0}" != "1" ]]; then
  BASEMAP_DIR="$BUILD_DIR" bash "$SCRIPT_DIR/build-germany-pmtiles.sh"
fi

[[ -s "$ARTIFACT" ]] || fail "Germany artifact missing: $ARTIFACT"
[[ -s "$META" ]] || fail "Germany metadata missing: $META"

if [[ ! -d "$REPO_ROOT/apps/web/node_modules" ]]; then
  pnpm -C "$REPO_ROOT/apps/web" install --frozen-lockfile
fi

pnpm -C "$REPO_ROOT/apps/web" validate:pmtiles -- \
  --archive "germany=$ARTIFACT" \
  --style "$REPO_ROOT/map-style/style-germany.json" \
  --output "$PROOF_OUTPUT"

[[ -s "$PROOF_OUTPUT" ]] || fail "deep-validation report was not written"

bash "$SCRIPT_DIR/publish-basemap.sh" "$ARTIFACT" "$META" "$TARGET_DIR"

ALIAS_ARTIFACT="$TARGET_DIR/basemap-germany.pmtiles"
ALIAS_META="$TARGET_DIR/basemap-germany.meta.json"
[[ -e "$ALIAS_ARTIFACT" ]] || fail "stable Germany PMTiles alias missing"
[[ -e "$ALIAS_META" ]] || fail "stable Germany metadata alias missing"
[[ "$(readlink -f -- "$ALIAS_ARTIFACT")" == "$TARGET_ARTIFACT" ]] ||
  fail "stable Germany PMTiles alias does not resolve to the published version"
[[ "$(readlink -f -- "$ALIAS_META")" == "$TARGET_META" ]] ||
  fail "stable Germany metadata alias does not resolve to the published version"

python3 - "$ALIAS_META" << 'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
if data.get("status") != "ready":
    raise SystemExit("Germany sentinel status is not ready")
if data.get("region") != "germany":
    raise SystemExit("Germany sentinel region mismatch")
if data.get("activation") != "opt-in":
    raise SystemExit("Germany sentinel must remain opt-in before deployment")
PY

echo "Germany PMTiles rollout preparation is complete."
echo "Isolated build: $BUILD_DIR"
echo "Published target: $TARGET_DIR"
echo "Target aliases:"
echo "  $ALIAS_ARTIFACT"
echo "  $ALIAS_META"
echo "Validation: $PROOF_OUTPUT"
echo "Activation was NOT changed. A reviewed frontend build must explicitly set:"
echo "  PUBLIC_BASEMAP_MODE=local-sovereign"
echo "  PUBLIC_BASEMAP_VARIANT=germany"
