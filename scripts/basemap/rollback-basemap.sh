#!/usr/bin/env bash
set -euo pipefail

# Rollback Strategy for Sovereign PMTiles Basemap
# Implements the Atomic Switch & Sentinel Verification Contract
# as defined in docs/blueprints/map-blaupause.md.

SCRIPT_NAME=$(basename "$0")

function print_usage() {
  echo "Usage: $SCRIPT_NAME <pmtiles_filename> <meta_filename> [target_directory]"
  echo ""
  echo "Arguments:"
  echo "  pmtiles_filename     Filename of the previous versioned .pmtiles artifact to rollback to (must exist in target_directory, e.g., basemap-hamburg-v0.1.0.pmtiles)"
  echo "  meta_filename        Filename of the corresponding .meta.json sentinel (must exist in target_directory, e.g., basemap-hamburg-v0.1.0.meta.json)"
  echo "  target_directory     Optional. The directory where the artifacts are published. Defaults to /srv/weltgewebe-basemap/"
  echo ""
  echo "Environment Variables:"
  echo "  TARGET_DIR           Can be used instead of the 3rd argument to set the target directory."
}

if [[ $# -lt 2 ]]; then
  print_usage
  EXIT_CODE=1
  exit $EXIT_CODE
fi

PMTILES_FILENAME="$1"
META_FILENAME="$2"
TARGET_DIR="${3:-${TARGET_DIR:-/srv/weltgewebe-basemap/}}"

# Enforce strict filename contract (no paths, no traversal)
if [[ "$PMTILES_FILENAME" == */* ]] || [[ "$PMTILES_FILENAME" == *..* ]]; then
  echo "ERROR: Invalid pmtiles_filename '$PMTILES_FILENAME'. Must be a simple filename without paths or traversal characters." >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

if [[ "$META_FILENAME" == */* ]] || [[ "$META_FILENAME" == *..* ]]; then
  echo "ERROR: Invalid meta_filename '$META_FILENAME'. Must be a simple filename without paths or traversal characters." >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

echo "=== Weltgewebe Basemap Rollback ==="
echo "Artifact: $PMTILES_FILENAME"
echo "Sentinel: $META_FILENAME"
echo "Target:   $TARGET_DIR"
echo "==================================="

# 1. Input Validation
if [[ ! -d "$TARGET_DIR" ]]; then
  echo "ERROR: Target directory does not exist: $TARGET_DIR" >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

if [[ ! -f "$TARGET_DIR/$PMTILES_FILENAME" ]]; then
  echo "ERROR: PMTiles artifact not found in target directory: $TARGET_DIR/$PMTILES_FILENAME" >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

if [[ ! -f "$TARGET_DIR/$META_FILENAME" ]]; then
  echo "ERROR: Meta JSON sentinel not found in target directory: $TARGET_DIR/$META_FILENAME" >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

# Determine verification tools
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: 'python3' is required for sentinel verification but not installed." >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

if command -v sha256sum >/dev/null 2>&1; then
  SHA256_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  SHA256_CMD=(shasum -a 256)
else
  echo "ERROR: 'sha256sum' or 'shasum' is required for artifact verification but not installed." >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

# 2. Sentinel Contract Verification
echo ">> Verifying Sentinel Contract ($TARGET_DIR/$META_FILENAME)..."

# Use python to parse the json safely and robustly
VERIFY_OUTPUT=$(mktemp)
if python3 - "$TARGET_DIR/$META_FILENAME" > "$VERIFY_OUTPUT" << 'PY'; then
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
    EXIT_CODE=1
    exit $EXIT_CODE
fi

META_ARTIFACT_NAME=$(sed -n '1p' "$VERIFY_OUTPUT")
META_SHA256=$(sed -n '2p' "$VERIFY_OUTPUT")
META_SIZE=$(sed -n '3p' "$VERIFY_OUTPUT")
rm -f "$VERIFY_OUTPUT"

case "$META_SIZE" in
  ''|*[!0-9]*)
    echo "ERROR: META_SIZE from sentinel is missing or non-numeric: '$META_SIZE'" >&2
    EXIT_CODE=1
    exit $EXIT_CODE
    ;;
esac

echo "   [✓] Schema valid. Status is 'ready'. Size parsed: $META_SIZE bytes."

if [[ "$META_ARTIFACT_NAME" != "$PMTILES_FILENAME" ]]; then
   echo "ERROR: artifact_name in meta ($META_ARTIFACT_NAME) does not match the provided PMTiles filename ($PMTILES_FILENAME)." >&2
   EXIT_CODE=1
   exit $EXIT_CODE
fi

# 3. Artifact Verification
echo ">> Verifying PMTiles Artifact ($TARGET_DIR/$PMTILES_FILENAME)..."

ACTUAL_SIZE=$(wc -c < "$TARGET_DIR/$PMTILES_FILENAME" | tr -d '[:space:]')
case "$ACTUAL_SIZE" in
  ''|*[!0-9]*)
    echo "ERROR: Could not determine valid size for $TARGET_DIR/$PMTILES_FILENAME." >&2
    EXIT_CODE=1
    exit $EXIT_CODE
    ;;
esac

ACTUAL_SHA256="$("${SHA256_CMD[@]}" "$TARGET_DIR/$PMTILES_FILENAME" | awk '{print $1}')"

if [[ "$ACTUAL_SIZE" -ne "$META_SIZE" ]]; then
  echo "ERROR: Size mismatch for $TARGET_DIR/$PMTILES_FILENAME!" >&2
  echo "Expected: $META_SIZE bytes" >&2
  echo "Actual:   $ACTUAL_SIZE bytes" >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

if [[ "$ACTUAL_SHA256" != "$META_SHA256" ]]; then
  echo "ERROR: Checksum mismatch for $TARGET_DIR/$PMTILES_FILENAME!" >&2
  echo "Expected: $META_SHA256" >&2
  echo "Actual:   $ACTUAL_SHA256" >&2
  EXIT_CODE=1
  exit $EXIT_CODE
fi

echo "   [✓] Integrity verified (SHA256 and Size match)."

# Extract base alias name from the artifact name, assuming format like basemap-REGION-vX.Y.Z.pmtiles
# We fallback to a generic name if parsing fails, but typical is basemap-hamburg.pmtiles
REGION=$(echo "$META_ARTIFACT_NAME" | grep -oE "basemap-[a-zA-Z0-9_-]+" | sed 's/-v[0-9].*//g' | sed 's/\.pmtiles//g' || true)
if [[ -z "$REGION" ]]; then
    REGION="basemap"
fi

ALIAS_PMTILES="${REGION}.pmtiles"
ALIAS_META="${REGION}.meta.json"

# 4. Atomic Switch (The core invariant: PMTiles first, then Meta)
echo ">> Executing Atomic Switch (Rollback)..."

TMP_STAGE_DIR="$(mktemp -d "$TARGET_DIR/.rollback-tmp.XXXXXX")"
trap 'rm -rf "$TMP_STAGE_DIR"' EXIT

echo "   1. Atomically linking $ALIAS_PMTILES -> $PMTILES_FILENAME"
ln -sfn "$PMTILES_FILENAME" "$TMP_STAGE_DIR/$ALIAS_PMTILES.tmp"
mv -Tf "$TMP_STAGE_DIR/$ALIAS_PMTILES.tmp" "$TARGET_DIR/$ALIAS_PMTILES"

echo "   2. Atomically linking $ALIAS_META -> $META_FILENAME"
ln -sfn "$META_FILENAME" "$TMP_STAGE_DIR/$ALIAS_META.tmp"
mv -Tf "$TMP_STAGE_DIR/$ALIAS_META.tmp" "$TARGET_DIR/$ALIAS_META"

echo "   [✓] Atomic switch complete."
echo ">> Rollback successful!"
