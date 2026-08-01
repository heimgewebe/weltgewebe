#!/usr/bin/env bash
set -euo pipefail

# Reproducible nationwide Germany PMTiles build.
#
# The default input remains a pinned historical Geofabrik snapshot. A newer
# snapshot may be supplied only together with an explicit URL and SHA256; the
# integrity check remains mandatory. This script builds a versioned artifact
# and sentinel metadata. It never changes a stable alias or production config.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
BASEMAP_DIR="${BASEMAP_DIR:-$REPO_ROOT/build/basemap}"

DEFAULT_OSM_FILE="germany-260101.osm.pbf"
DEFAULT_OSM_URL="https://download.geofabrik.de/europe/germany-260101.osm.pbf"
DEFAULT_OSM_SHA256="4a2e3181c2cef4795b62ef9b447d4fa5f7f9bb2352d563292a7b98baa75279f8"

OSM_FILE="${OSM_FILE:-$DEFAULT_OSM_FILE}"
OSM_URL="${OSM_URL:-$DEFAULT_OSM_URL}"
OSM_SHA256="${OSM_SHA256:-$DEFAULT_OSM_SHA256}"
OSM_SNAPSHOT_DATE="${OSM_SNAPSHOT_DATE:-2026-01-01}"
BASEMAP_VERSION="${BASEMAP_VERSION:-0.1.0}"
BASEMAP_TAG="v${BASEMAP_VERSION}"
OUTPUT_PMTILES="basemap-germany-${BASEMAP_TAG}.pmtiles"
OUTPUT_META="basemap-germany-${BASEMAP_TAG}.meta.json"
MIN_FREE_BYTES="${BASEMAP_MIN_FREE_BYTES:-68719476736}"

PLANETILER_IMAGE="ghcr.io/onthegomap/planetiler@sha256:10e4d6850664bd2ad7a223623383c48281e7d87fb427360838b13342cac012bb"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

case "$OSM_SHA256" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) fail "OSM_SHA256 must be exactly 64 lowercase hexadecimal characters" ;;
esac
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
AVAILABLE_BYTES="$(df -Pk "$BASEMAP_DIR" | awk 'NR==2 {print $4 * 1024}')"
case "$AVAILABLE_BYTES" in
  '' | *[!0-9]*) fail "could not determine free disk space for $BASEMAP_DIR" ;;
esac
if ((AVAILABLE_BYTES < MIN_FREE_BYTES)); then
  fail "insufficient free disk: ${AVAILABLE_BYTES} bytes available, ${MIN_FREE_BYTES} required"
fi

if [[ -r /proc/meminfo ]]; then
  AVAILABLE_MEMORY_BYTES="$(awk '/^MemAvailable:/ {print $2 * 1024}' /proc/meminfo)"
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
  PARTIAL_FILE="${OSM_FILE}.partial"
  rm -f "$PARTIAL_FILE"
  echo ">> Downloading pinned Germany OSM snapshot..."
  if [[ "$DOWNLOADER" == "wget" ]]; then
    wget -qO "$PARTIAL_FILE" "$OSM_URL" || {
      rm -f "$PARTIAL_FILE"
      fail "download failed: $OSM_URL"
    }
  else
    curl -fL --retry 3 --retry-delay 5 -o "$PARTIAL_FILE" "$OSM_URL" || {
      rm -f "$PARTIAL_FILE"
      fail "download failed: $OSM_URL"
    }
  fi
  mv -f "$PARTIAL_FILE" "$OSM_FILE"
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

rm -f "${OUTPUT_PMTILES}.partial"
DOCKER_ARGS=(
  run --rm
  --platform linux/amd64
  --user "$(id -u):$(id -g)"
  -v "$BASEMAP_DIR:/data"
)
if [[ -n "${BASEMAP_DOCKER_MEMORY:-}" ]]; then
  DOCKER_ARGS+=(--memory "$BASEMAP_DOCKER_MEMORY")
fi

if ! docker "${DOCKER_ARGS[@]}" "$PLANETILER_IMAGE" \
  --osm-path="/data/$OSM_FILE" \
  --output="/data/${OUTPUT_PMTILES}.partial"; then
  rm -f "${OUTPUT_PMTILES}.partial"
  fail "Planetiler execution failed"
fi

[[ -s "${OUTPUT_PMTILES}.partial" ]] || fail "Planetiler produced no non-empty artifact"
mv -f "${OUTPUT_PMTILES}.partial" "$OUTPUT_PMTILES"

PMTILES_SIZE="$(wc -c < "$OUTPUT_PMTILES" | tr -d '[:space:]')"
PMTILES_SHA256="$("${SHA256_CMD[@]}" "$OUTPUT_PMTILES" | awk '{print $1}')"
[[ -n "$PMTILES_SHA256" && "$PMTILES_SIZE" -gt 0 ]] || fail "invalid artifact hash or size"

BUILD_TIMESTAMP_VALUE=""
if [[ "${NON_REPRODUCIBLE_BUILD_TIMESTAMP:-}" == "1" ]]; then
  BUILD_TIMESTAMP_VALUE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
elif [[ -n "${SOURCE_DATE_EPOCH:-}" ]]; then
  BUILD_TIMESTAMP_VALUE="$(date -u -d "@${SOURCE_DATE_EPOCH}" +"%Y-%m-%dT%H:%M:%SZ")" || BUILD_TIMESTAMP_VALUE=""
fi

python3 - "$OUTPUT_META" <<PY
import json
import pathlib
import sys

payload = {
    "schema_version": 1,
    "version": "${BASEMAP_VERSION}",
    "region": "germany",
    "country_code": "DE",
    "activation": "opt-in",
    "toolchain": {
        "generator": "planetiler",
        "image": "${PLANETILER_IMAGE}",
    },
    "input": {
        "url": "${OSM_URL}",
        "file": "${OSM_FILE}",
        "snapshot_date": "${OSM_SNAPSHOT_DATE}",
        "sha256": "${OSM_SHA256}",
    },
    "artifact_name": "${OUTPUT_PMTILES}",
    "sha256": "${PMTILES_SHA256}",
    "size_bytes": int("${PMTILES_SIZE}"),
    "status": "ready",
}
if "${BUILD_TIMESTAMP_VALUE}":
    payload["build_timestamp"] = "${BUILD_TIMESTAMP_VALUE}"
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
