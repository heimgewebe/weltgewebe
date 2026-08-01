#!/usr/bin/env bash
set -euo pipefail

# Scripts for operational bootstrap of the sovereign PMTiles basemap artifact.
# Phase 1: Local generation (Hamburg) with planetiler

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." > /dev/null 2>&1 && pwd)"
BASEMAP_DIR="$REPO_ROOT/build/basemap"

OSM_FILE="hamburg-250101.osm.pbf"
OSM_URL="https://download.geofabrik.de/europe/germany/hamburg-250101.osm.pbf"
OSM_SHA256="e9beba6f27594a3abe571dd632e752fb43c8a136b2517fa162988fd641f8cdc9"

BASEMAP_VERSION="0.1.0"
BASEMAP_TAG="v${BASEMAP_VERSION}"
OUTPUT_PMTILES="basemap-hamburg-${BASEMAP_TAG}.pmtiles"
OUTPUT_META="basemap-hamburg-${BASEMAP_TAG}.meta.json"
PLANETILER_IMAGE="ghcr.io/onthegomap/planetiler@sha256:10e4d6850664bd2ad7a223623383c48281e7d87fb427360838b13342cac012bb"
PLANETILER_HTTP_TIMEOUT="${BASEMAP_PLANETILER_HTTP_TIMEOUT:-120s}"
PLANETILER_HTTP_RETRIES="${BASEMAP_PLANETILER_HTTP_RETRIES:-3}"
PLANETILER_HTTP_RETRY_WAIT="${BASEMAP_PLANETILER_HTTP_RETRY_WAIT:-10s}"

echo "=== Weltgewebe Basemap Builder ==="
echo "Target:  Hamburg"
echo "Version: ${BASEMAP_VERSION} (Tag: ${BASEMAP_TAG})"
echo "Tool:    Planetiler (Pinned: 0.8.2 @ sha256:10e4...)"
echo "Input:   $OSM_FILE (Pinned & Hash-Verified)"
echo "Format:  PMTiles"
echo "=================================="

command -v docker > /dev/null 2>&1 || {
  echo "Error: 'docker' is required but not installed or not in PATH." >&2
  exit 1
}

DOWNLOADER=""
if command -v wget > /dev/null 2>&1; then
  DOWNLOADER="wget"
elif command -v curl > /dev/null 2>&1; then
  DOWNLOADER="curl"
else
  echo "Error: Neither 'wget' nor 'curl' is available for downloading the OSM data." >&2
  exit 1
fi

mkdir -p "$BASEMAP_DIR"
cd "$BASEMAP_DIR"

if [[ ! -f "$OSM_FILE" ]]; then
  echo "=> Downloading OSM data for Hamburg ($OSM_FILE)..."
  if [[ "$DOWNLOADER" == "wget" ]]; then
    wget --tries=5 --waitretry=3 --retry-connrefused --timeout=30 -O "$OSM_FILE" "$OSM_URL" || {
      rm -f "$OSM_FILE"
      exit 1
    }
  else
    curl -fL --retry 5 --retry-delay 3 -o "$OSM_FILE" "$OSM_URL" || {
      rm -f "$OSM_FILE"
      exit 1
    }
  fi
else
  echo "=> OSM data '$OSM_FILE' already exists locally, skipping download."
fi

echo "=> Verifying integrity of $OSM_FILE..."
if command -v sha256sum > /dev/null 2>&1; then
  SHA256_CMD=(sha256sum)
elif command -v shasum > /dev/null 2>&1; then
  SHA256_CMD=(shasum -a 256)
else
  echo "Error: 'sha256sum' or 'shasum' is required for artifact verification but not installed." >&2
  exit 1
fi

ACTUAL_SHA256="$("${SHA256_CMD[@]}" "$OSM_FILE" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$OSM_SHA256" ]]; then
  echo "Error: Checksum mismatch for $OSM_FILE!" >&2
  echo "Expected: $OSM_SHA256" >&2
  echo "Actual:   $ACTUAL_SHA256" >&2
  echo "The file may be corrupted or modified. Aborting to preserve reproducibility." >&2
  exit 1
fi
echo "   [✓] Integrity verified (SHA256 match)."

echo "=> Running Planetiler via Docker to generate $OUTPUT_PMTILES..."
if ! docker run --rm \
  --platform linux/amd64 \
  --user "$(id -u):$(id -g)" \
  -v "$BASEMAP_DIR":/data \
  "$PLANETILER_IMAGE" \
  --osm-path="/data/$OSM_FILE" \
  --output="/data/$OUTPUT_PMTILES" \
  --download=true \
  --http-timeout="$PLANETILER_HTTP_TIMEOUT" \
  --http-retries="$PLANETILER_HTTP_RETRIES" \
  --http-retry-wait="$PLANETILER_HTTP_RETRY_WAIT"; then
  echo "Error: Docker execution failed." >&2
  exit 1
fi

echo "=> Generating metadata manifest..."
if [[ ! -f "$BASEMAP_DIR/$OUTPUT_PMTILES" ]]; then
  echo "Error: Artifact $OUTPUT_PMTILES not found. Cannot generate ready status." >&2
  exit 1
fi

PMTILES_SIZE="$(wc -c < "$BASEMAP_DIR/$OUTPUT_PMTILES" | tr -d '[:space:]')"
PMTILES_SHA256="$("${SHA256_CMD[@]}" "$BASEMAP_DIR/$OUTPUT_PMTILES" | awk '{print $1}')"
if [[ -z "$PMTILES_SHA256" || "$PMTILES_SIZE" -eq 0 ]]; then
  echo "Error: Failed to determine valid size or hash for $OUTPUT_PMTILES." >&2
  exit 1
fi

BUILD_TIMESTAMP_VALUE=""
if [[ "${NON_REPRODUCIBLE_BUILD_TIMESTAMP:-}" == "1" ]]; then
  BUILD_TIMESTAMP_VALUE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
elif [[ -n "${SOURCE_DATE_EPOCH:-}" ]]; then
  BUILD_TIMESTAMP_VALUE="$(date -u -d "@${SOURCE_DATE_EPOCH}" +"%Y-%m-%dT%H:%M:%SZ")" || BUILD_TIMESTAMP_VALUE=""
fi

if [[ -n "$BUILD_TIMESTAMP_VALUE" ]]; then
  BUILD_TIMESTAMP_JSON="  \"build_timestamp\": \"${BUILD_TIMESTAMP_VALUE}\","
else
  BUILD_TIMESTAMP_JSON=""
fi

cat << EOF_META > "$BASEMAP_DIR/$OUTPUT_META"
{
  "version": "${BASEMAP_VERSION}",
  "region": "hamburg",
${BUILD_TIMESTAMP_JSON}
  "toolchain": {
    "generator": "planetiler",
    "image": "${PLANETILER_IMAGE}"
  },
  "input": {
    "url": "${OSM_URL}",
    "sha256": "${OSM_SHA256}",
    "note": "Pinned historical snapshot with verified SHA256 integrity"
  },
  "artifact_name": "${OUTPUT_PMTILES}",
  "sha256": "${PMTILES_SHA256}",
  "size_bytes": ${PMTILES_SIZE},
  "status": "ready"
}
EOF_META

echo "=> Basemap generation complete!"
echo "Artifact: $BASEMAP_DIR/$OUTPUT_PMTILES"
echo "Metadata: $BASEMAP_DIR/$OUTPUT_META"
