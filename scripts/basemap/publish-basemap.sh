#!/usr/bin/env bash
set -euo pipefail

# Publish and Rollback Strategy for Sovereign PMTiles Basemap
# Implements the Atomic Switch & Sentinel Verification Contract
# as defined in docs/blueprints/map-blaupause.md.

SCRIPT_NAME=$(basename "$0")

function print_usage() {
  echo "Usage: $SCRIPT_NAME <path_to_pmtiles> <path_to_meta_json> [target_directory]"
  echo ""
  echo "Arguments:"
  echo "  path_to_pmtiles      Path to the generated versioned .pmtiles artifact (e.g., basemap-hamburg-v0.1.0.pmtiles)"
  echo "  path_to_meta_json    Path to the corresponding .meta.json sentinel (e.g., basemap-hamburg-v0.1.0.meta.json)"
  echo "  target_directory     Optional. The directory where the artifacts will be published. Defaults to /srv/weltgewebe-basemap/"
  echo ""
  echo "Environment Variables:"
  echo "  TARGET_DIR           Can be used instead of the 3rd argument to set the target directory."
}

if [[ $# -lt 2 ]]; then
  print_usage
  exit 1
fi

SOURCE_PMTILES="$1"
SOURCE_META="$2"
TARGET_DIR="${3:-${TARGET_DIR:-/srv/weltgewebe-basemap/}}"

echo "=== Weltgewebe Basemap Publisher ==="
echo "Artifact: $SOURCE_PMTILES"
echo "Sentinel: $SOURCE_META"
echo "Target:   $TARGET_DIR"
echo "===================================="

# 1. Input Validation
if [[ ! -f "$SOURCE_PMTILES" ]]; then
  echo "ERROR: PMTiles artifact not found: $SOURCE_PMTILES" >&2
  exit 1
fi

if [[ ! -f "$SOURCE_META" ]]; then
  echo "ERROR: Meta JSON sentinel not found: $SOURCE_META" >&2
  exit 1
fi

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "ERROR: Target directory does not exist: $TARGET_DIR" >&2
  echo "       Please ensure the target directory is created and accessible." >&2
  exit 1
fi

# Determine verification tools
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: 'python3' is required for sentinel verification but not installed." >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  SHA256_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  SHA256_CMD=(shasum -a 256)
else
  echo "ERROR: 'sha256sum' or 'shasum' is required for artifact verification but not installed." >&2
  exit 1
fi

# 2. Sentinel Contract Verification
echo ">> Verifying Sentinel Contract ($SOURCE_META)..."

# Use python to parse the json safely and robustly
VERIFY_OUTPUT=$(mktemp)
if python3 - "$SOURCE_META" > "$VERIFY_OUTPUT" << 'PY'; then
import sys, json
try:
    with open(sys.argv[1], "r") as f:
        data = json.load(f)

    req_fields = ["version", "artifact_name", "sha256", "size_bytes", "status"]
    missing = [f for f in req_fields if f not in data]
    if missing:
        print("Missing fields: " + ", ".join(missing), file=sys.stderr)
        sys.exit(2)

    if data["status"] != "ready":
        print('Status is not "ready", found: ' + str(data.get("status")), file=sys.stderr)
        sys.exit(3)

    print(f"{data['artifact_name']}\n{data['sha256']}\n{data['size_bytes']}")
except json.JSONDecodeError:
    print("Invalid JSON.", file=sys.stderr)
    sys.exit(4)
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(5)
PY
else
    PY_STATUS=$?
    echo "ERROR: Sentinel contract validation failed (Exit Code: $PY_STATUS)." >&2
    rm -f "$VERIFY_OUTPUT"
    exit 1
fi

META_ARTIFACT_NAME=$(sed -n '1p' "$VERIFY_OUTPUT")
META_SHA256=$(sed -n '2p' "$VERIFY_OUTPUT")
META_SIZE=$(sed -n '3p' "$VERIFY_OUTPUT")
rm -f "$VERIFY_OUTPUT"

case "$META_SIZE" in
  ''|*[!0-9]*)
    echo "ERROR: META_SIZE from sentinel is missing or non-numeric: '$META_SIZE'" >&2
    exit 1
    ;;
esac

echo "   [✓] Schema valid. Status is 'ready'. Size parsed: $META_SIZE bytes."

# Check if the filename in meta matches the provided pmtiles filename
BASENAME_PMTILES=$(basename "$SOURCE_PMTILES")
if [[ "$META_ARTIFACT_NAME" != "$BASENAME_PMTILES" ]]; then
   echo "ERROR: artifact_name in meta ($META_ARTIFACT_NAME) does not match the provided PMTiles filename ($BASENAME_PMTILES)." >&2
   exit 1
fi

# 3. Artifact Verification
echo ">> Verifying PMTiles Artifact ($SOURCE_PMTILES)..."

ACTUAL_SIZE=$(wc -c < "$SOURCE_PMTILES" | tr -d '[:space:]')
case "$ACTUAL_SIZE" in
  ''|*[!0-9]*)
    echo "ERROR: Could not determine valid size for $SOURCE_PMTILES." >&2
    exit 1
    ;;
esac

ACTUAL_SHA256="$("${SHA256_CMD[@]}" "$SOURCE_PMTILES" | awk '{print $1}')"

if [[ "$ACTUAL_SIZE" -ne "$META_SIZE" ]]; then
  echo "ERROR: Size mismatch for $SOURCE_PMTILES!" >&2
  echo "Expected: $META_SIZE bytes" >&2
  echo "Actual:   $ACTUAL_SIZE bytes" >&2
  exit 1
fi

if [[ "$ACTUAL_SHA256" != "$META_SHA256" ]]; then
  echo "ERROR: Checksum mismatch for $SOURCE_PMTILES!" >&2
  echo "Expected: $META_SHA256" >&2
  echo "Actual:   $ACTUAL_SHA256" >&2
  exit 1
fi

echo "   [✓] Integrity verified (SHA256 and Size match)."

# 4. Transfer Artifacts
# We transfer the files explicitly to a staging directory before exposing them
BASENAME_META=$(basename "$SOURCE_META")

TARGET_PMTILES="$TARGET_DIR/$BASENAME_PMTILES"
TARGET_META="$TARGET_DIR/$BASENAME_META"

echo ">> Staging artifacts in $TARGET_DIR..."

TMP_STAGE_DIR="$(mktemp -d "$TARGET_DIR/.publish-tmp.XXXXXX")"
trap 'rm -rf "$TMP_STAGE_DIR"' EXIT

STAGED_PMTILES="$TMP_STAGE_DIR/$BASENAME_PMTILES"
STAGED_META="$TMP_STAGE_DIR/$BASENAME_META"

# Copy artifacts into the staging directory
cp -f "$SOURCE_PMTILES" "$STAGED_PMTILES"
cp -f "$SOURCE_META" "$STAGED_META"

echo "   [✓] Staging complete."

# Verify transferred PMTiles to ensure integrity during copy
TRANSFERRED_SHA256="$("${SHA256_CMD[@]}" "$STAGED_PMTILES" | awk '{print $1}')"
if [[ "$TRANSFERRED_SHA256" != "$META_SHA256" ]]; then
  echo "ERROR: Checksum mismatch for transferred artifact $STAGED_PMTILES!" >&2
  echo "Expected: $META_SHA256" >&2
  echo "Actual:   $TRANSFERRED_SHA256" >&2
  echo "Transfer failed. Aborting." >&2
  exit 1
fi

# Now that the staged artifact is verified, safely move them into place
# to satisfy the Sentinel visibility contract (PMTiles first, then Meta).
mv -f "$STAGED_PMTILES" "$TARGET_PMTILES"
mv -f "$STAGED_META" "$TARGET_META"

echo "   [✓] Artifacts are now verified and visible in target directory."

# Extract base alias name from the artifact name, assuming format like basemap-REGION-vX.Y.Z.pmtiles
# We fallback to a generic name if parsing fails, but typical is basemap-hamburg.pmtiles
REGION=$(echo "$META_ARTIFACT_NAME" | grep -oE "basemap-[a-zA-Z0-9_-]+" | sed 's/-v[0-9].*//g' | sed 's/\.pmtiles//g' || true)
if [[ -z "$REGION" ]]; then
    REGION="basemap"
fi

ALIAS_PMTILES="${REGION}.pmtiles"
ALIAS_META="${REGION}.meta.json"

# 5. Atomic Switch (The core invariant: PMTiles first, then Meta)
echo ">> Executing Atomic Switch..."

echo "   1. Atomically linking $ALIAS_PMTILES -> $BASENAME_PMTILES"
ln -sfn "$BASENAME_PMTILES" "$TMP_STAGE_DIR/$ALIAS_PMTILES.tmp"
mv -Tf "$TMP_STAGE_DIR/$ALIAS_PMTILES.tmp" "$TARGET_DIR/$ALIAS_PMTILES"

echo "   2. Atomically linking $ALIAS_META -> $BASENAME_META"
ln -sfn "$BASENAME_META" "$TMP_STAGE_DIR/$ALIAS_META.tmp"
mv -Tf "$TMP_STAGE_DIR/$ALIAS_META.tmp" "$TARGET_DIR/$ALIAS_META"

echo "   [✓] Atomic switch complete."
echo ">> Publish successful!"
