#!/usr/bin/env bash
set -euo pipefail

# Reproducible nationwide Germany PMTiles build.
#
# The default input remains a pinned historical Geofabrik snapshot. A newer
# snapshot may be supplied only as a complete provenance tuple: filename, URL,
# SHA256 and snapshot date. The integrity check remains mandatory. This script
# builds a versioned artifact and sentinel metadata. It never changes a stable
# alias or production config.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
BASEMAP_DIR="${BASEMAP_DIR:-$REPO_ROOT/build/basemap}"

DEFAULT_OSM_FILE="germany-260101.osm.pbf"
DEFAULT_OSM_URL="https://download.geofabrik.de/europe/germany-260101.osm.pbf"
DEFAULT_OSM_SHA256="4a2e3181c2cef4795b62ef9b447d4fa5f7f9bb2352d563292a7b98baa75279f8"
DEFAULT_OSM_SNAPSHOT_DATE="2026-01-01"

OSM_FILE_WAS_SET="${OSM_FILE+x}"
OSM_URL_WAS_SET="${OSM_URL+x}"
OSM_SHA256_WAS_SET="${OSM_SHA256+x}"
OSM_SNAPSHOT_DATE_WAS_SET="${OSM_SNAPSHOT_DATE+x}"

OSM_FILE="${OSM_FILE:-$DEFAULT_OSM_FILE}"
OSM_URL="${OSM_URL:-$DEFAULT_OSM_URL}"
OSM_SHA256="${OSM_SHA256:-$DEFAULT_OSM_SHA256}"
OSM_SNAPSHOT_DATE="${OSM_SNAPSHOT_DATE:-$DEFAULT_OSM_SNAPSHOT_DATE}"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
BASEMAP_TAG="v${BASEMAP_VERSION}"
OUTPUT_PMTILES="basemap-germany-${BASEMAP_TAG}.pmtiles"
PARTIAL_PMTILES="basemap-germany-${BASEMAP_TAG}.partial.pmtiles"
OUTPUT_META="basemap-germany-${BASEMAP_TAG}.meta.json"
MIN_FREE_BYTES="${BASEMAP_MIN_FREE_BYTES:-68719476736}"

PLANETILER_IMAGE="ghcr.io/onthegomap/planetiler@sha256:10e4d6850664bd2ad7a223623383c48281e7d87fb427360838b13342cac012bb"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

SNAPSHOT_OVERRIDE_COUNT=0
for marker in \
  "$OSM_FILE_WAS_SET" \
  "$OSM_URL_WAS_SET" \
  "$OSM_SHA256_WAS_SET" \
  "$OSM_SNAPSHOT_DATE_WAS_SET"; do
  [[ -n "$marker" ]] && SNAPSHOT_OVERRIDE_COUNT=$((SNAPSHOT_OVERRIDE_COUNT + 1))
done
if ((SNAPSHOT_OVERRIDE_COUNT != 0 && SNAPSHOT_OVERRIDE_COUNT != 4)); then
  fail "override OSM_FILE, OSM_URL, OSM_SHA256 and OSM_SNAPSHOT_DATE together"
fi

[[ "$OSM_FILE" == "$(basename -- "$OSM_FILE")" ]] ||
  fail "OSM_FILE must be a plain filename inside BASEMAP_DIR"
[[ "$OSM_FILE" == *.osm.pbf ]] || fail "OSM_FILE must end in .osm.pbf"
[[ "$OSM_URL" =~ ^https:// ]] || fail "OSM_URL must use HTTPS"
[[ "$OSM_SHA256" =~ ^[0-9a-f]{64}$ ]] ||
  fail "OSM_SHA256 must be exactly 64 lowercase hexadecimal characters"
[[ "$OSM_SNAPSHOT_DATE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] ||
  fail "OSM_SNAPSHOT_DATE must use YYYY-MM-DD"
[[ "$BASEMAP_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
  fail "BASEMAP_VERSION must use numeric semantic versioning"
case "$MIN_FREE_BYTES" in
  '' | *[!0-9]*) fail "BASEMAP_MIN_FREE_BYTES must be a positive integer" ;;
esac
((MIN_FREE_BYTES > 0)) || fail "BASEMAP_MIN_FREE_BYTES must be greater than zero"

command -v docker >/dev/null 2>&1 || fail "docker is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

if command -v sha256sum >/dev/null 2>&1; then
  SHA256_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  SHA256_CMD=(shasum -a 256)
else
  fail "sha256sum or shasum is required"
fi

if command -v wget >/dev/null 2>&1; then
  DOWNLOADER="wget"
elif command -v curl >/dev/null 2>&1; then
  DOWNLOADER="curl"
else
  fail "wget or curl is required"
fi

mkdir -p "$BASEMAP_DIR"
BASEMAP_DIR="$(cd "$BASEMAP_DIR" >/dev/null 2>&1 && pwd)"
AVAILABLE_BYTES="$(df -Pk "$BASEMAP_DIR" | awk 'NR==2 {printf "%.0f\n", $4 * 1024}')"
case "$AVAILABLE_BYTES" in
  '' | *[!0-9]*) fail "could not determine free disk space for $BASEMAP_DIR" ;;
esac
if ((AVAILABLE_BYTES < MIN_FREE_BYTES)); then
  fail "insufficient free disk: ${AVAILABLE_BYTES} bytes available, ${MIN_FREE_BYTES} required"
fi

if [[ -r /proc/meminfo ]]; then
  AVAILABLE_MEMORY_BYTES="$(awk '/^MemAvailable:/ {printf "%.0f\n", $2 * 1024}' /proc/meminfo)"
  echo "Available memory: ${AVAILABLE_MEMORY_BYTES:-unknown} bytes"
fi

echo "=== Weltgewebe Germany Basemap Builder ==="
echo "Version:       ${BASEMAP_VERSION}"
echo "Snapshot date: ${OSM_SNAPSHOT_DATE}"
echo "Input:         ${OSM_FILE}"
echo "Output:        ${OUTPUT_PMTILES}"
echo "Build dir:     ${BASEMAP_DIR}"
echo "Free bytes:    ${AVAILABLE_BYTES}"
echo "Toolchain:     ${PLANETILER_IMAGE}"
echo "========================================="

cd "$BASEMAP_DIR"

if [[ ! -f "$OSM_FILE" ]]; then
  PARTIAL_INPUT="${OSM_FILE}.partial"
  rm -f "$PARTIAL_INPUT"
  echo ">> Downloading pinned Germany OSM snapshot..."
  if [[ "$DOWNLOADER" == "wget" ]]; then
    wget -qO "$PARTIAL_INPUT" "$OSM_URL" || {
      rm -f "$PARTIAL_INPUT"
      fail "download failed: $OSM_URL"
    }
  else
    curl -fL --retry 3 --retry-delay 5 -o "$PARTIAL_INPUT" "$OSM_URL" || {
      rm -f "$PARTIAL_INPUT"
      fail "download failed: $OSM_URL"
    }
  fi
  mv -f "$PARTIAL_INPUT" "$OSM_FILE"
else
  echo ">> Reusing existing input: $OSM_FILE"
fi

ACTUAL_INPUT_SHA256="$("${SHA256_CMD[@]}" "$OSM_FILE" | awk '{print $1}')"
[[ "$ACTUAL_INPUT_SHA256" == "$OSM_SHA256" ]] || {
  echo "Expected: $OSM_SHA256" >&2
  echo "Actual:   $ACTUAL_INPUT_SHA256" >&2
  fail "input checksum mismatch"
}
echo "   [✓] Input integrity verified"

rm -f "$PARTIAL_PMTILES"
DOCKER_ARGS=(
  run --rm
  --platform linux/amd64
  --user "$(id -u):$(id -g)"
  --mount "type=bind,src=$BASEMAP_DIR,dst=/data"
)
if [[ -n "${BASEMAP_DOCKER_MEMORY:-}" ]]; then
  DOCKER_ARGS+=(--memory "$BASEMAP_DOCKER_MEMORY")
fi

if ! docker "${DOCKER_ARGS[@]}" "$PLANETILER_IMAGE" \
  --osm-path="/data/$OSM_FILE" \
  --output="/data/$PARTIAL_PMTILES"; then
  rm -f "$PARTIAL_PMTILES"
  fail "Planetiler execution failed"
fi

[[ -s "$PARTIAL_PMTILES" ]] || fail "Planetiler produced no non-empty artifact"
mv -f "$PARTIAL_PMTILES" "$OUTPUT_PMTILES"

PMTILES_SIZE="$(wc -c < "$OUTPUT_PMTILES" | tr -d '[:space:]')"
PMTILES_SHA256="$("${SHA256_CMD[@]}" "$OUTPUT_PMTILES" | awk '{print $1}')"
[[ -n "$PMTILES_SHA256" && "$PMTILES_SIZE" -gt 0 ]] || fail "invalid artifact hash or size"

BUILD_TIMESTAMP_VALUE=""
if [[ "${NON_REPRODUCIBLE_BUILD_TIMESTAMP:-}" == "1" ]]; then
  BUILD_TIMESTAMP_VALUE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
elif [[ -n "${SOURCE_DATE_EPOCH:-}" ]]; then
  BUILD_TIMESTAMP_VALUE="$(date -u -d "@${SOURCE_DATE_EPOCH}" +"%Y-%m-%dT%H:%M:%SZ")" || BUILD_TIMESTAMP_VALUE=""
fi

META_VERSION="$BASEMAP_VERSION" \
META_TOOLCHAIN="$PLANETILER_IMAGE" \
META_INPUT_URL="$OSM_URL" \
META_INPUT_FILE="$OSM_FILE" \
META_SNAPSHOT_DATE="$OSM_SNAPSHOT_DATE" \
META_INPUT_SHA256="$OSM_SHA256" \
META_ARTIFACT_NAME="$OUTPUT_PMTILES" \
META_ARTIFACT_SHA256="$PMTILES_SHA256" \
META_ARTIFACT_SIZE="$PMTILES_SIZE" \
META_BUILD_TIMESTAMP="$BUILD_TIMESTAMP_VALUE" \
  python3 - "$OUTPUT_META" <<'PY'
import json
import os
import pathlib
import sys

payload = {
    "schema_version": 1,
    "version": os.environ["META_VERSION"],
    "region": "germany",
    "country_code": "DE",
    "activation": "opt-in",
    "toolchain": {
        "generator": "planetiler",
        "image": os.environ["META_TOOLCHAIN"],
    },
    "input": {
        "url": os.environ["META_INPUT_URL"],
        "file": os.environ["META_INPUT_FILE"],
        "snapshot_date": os.environ["META_SNAPSHOT_DATE"],
        "sha256": os.environ["META_INPUT_SHA256"],
    },
    "artifact_name": os.environ["META_ARTIFACT_NAME"],
    "sha256": os.environ["META_ARTIFACT_SHA256"],
    "size_bytes": int(os.environ["META_ARTIFACT_SIZE"]),
    "status": "ready",
}
build_timestamp = os.environ.get("META_BUILD_TIMESTAMP", "")
if build_timestamp:
    payload["build_timestamp"] = build_timestamp
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY

[[ -s "$OUTPUT_META" ]] || fail "metadata sentinel was not written"

echo "   [✓] Germany artifact ready"
echo "Artifact: $BASEMAP_DIR/$OUTPUT_PMTILES"
echo "Metadata: $BASEMAP_DIR/$OUTPUT_META"
echo "SHA256:   $PMTILES_SHA256"
echo "Size:     $PMTILES_SIZE bytes"
echo "No stable alias or production setting was changed."
