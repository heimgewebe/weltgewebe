#!/usr/bin/env bash
set -euo pipefail

# Build, deep-validate and publish the Germany artifact to an explicit target.
# The default target is the repository build directory. This prepares the
# stable basemap-germany aliases but never changes PUBLIC_BASEMAP_VARIANT or a
# production deployment. Production activation remains a separate reviewed act.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
BUILD_DIR="${BASEMAP_DIR:-$REPO_ROOT/build/basemap}"
TARGET_DIR="${1:-$BUILD_DIR}"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
ARTIFACT="$BUILD_DIR/basemap-germany-v${BASEMAP_VERSION}.pmtiles"
META="$BUILD_DIR/basemap-germany-v${BASEMAP_VERSION}.meta.json"
PROOF_OUTPUT="${GERMANY_BASEMAP_PROOF_OUTPUT:-$BUILD_DIR/basemap-germany-v${BASEMAP_VERSION}.validation.json}"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v node >/dev/null 2>&1 || fail "node is required"
command -v pnpm >/dev/null 2>&1 || fail "pnpm is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"
[[ -d "$TARGET_DIR" ]] || fail "target directory does not exist: $TARGET_DIR"

if [[ "${GERMANY_BASEMAP_SKIP_BUILD:-0}" != "1" ]]; then
  bash "$SCRIPT_DIR/build-germany-pmtiles.sh"
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

[[ -e "$TARGET_DIR/basemap-germany.pmtiles" ]] || fail "stable Germany PMTiles alias missing"
[[ -e "$TARGET_DIR/basemap-germany.meta.json" ]] || fail "stable Germany metadata alias missing"

python3 - "$TARGET_DIR/basemap-germany.meta.json" <<'PY'
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
echo "Target aliases:"
echo "  $TARGET_DIR/basemap-germany.pmtiles"
echo "  $TARGET_DIR/basemap-germany.meta.json"
echo "Validation: $PROOF_OUTPUT"
echo "Activation was NOT changed. A reviewed frontend build must explicitly set:"
echo "  PUBLIC_BASEMAP_MODE=local-sovereign"
echo "  PUBLIC_BASEMAP_VARIANT=germany"
