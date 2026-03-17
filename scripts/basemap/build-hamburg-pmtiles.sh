#!/usr/bin/env bash
set -euo pipefail

# Scripts for operational bootstrap of the sovereign PMTiles basemap artifact.
# Phase 1: Local generation (Hamburg) with planetiler
#
# Determinism status:
# - Pinned Planetiler container version (deterministic toolchain)
# - Explicit host path and user mapping (reproducible environment)
# - Tool presence checks
# - OSM input is currently volatile (outputs are not yet strictly reproducible)

# 1. Resolve repo root securely
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
BASEMAP_DIR="$REPO_ROOT/build/basemap"

# 2. Pin tools (OSM input pin is currently missing / volatile)
# TODO: To guarantee reproducible output hashes, we need a stable OSM snapshot
# mirror. Currently, Geofabrik's latest URL redirects daily, breaking reproducible builds.
OSM_FILE="hamburg-latest.osm.pbf"
OSM_URL="https://download.geofabrik.de/europe/germany/hamburg-latest.osm.pbf"

# Versioning
BASEMAP_VERSION="0.1.0"
BASEMAP_TAG="v${BASEMAP_VERSION}"
OUTPUT_PMTILES="basemap-hamburg-${BASEMAP_TAG}.pmtiles"
OUTPUT_META="basemap-hamburg-${BASEMAP_TAG}.meta.json"

# Planetiler 0.8.2 (linux/amd64) pinned by digest for a truly deterministic toolchain
PLANETILER_IMAGE="ghcr.io/onthegomap/planetiler@sha256:10e4d6850664bd2ad7a223623383c48281e7d87fb427360838b13342cac012bb"

echo "=== Weltgewebe Basemap Builder ==="
echo "Target:  Hamburg"
echo "Version: ${BASEMAP_VERSION} (Tag: ${BASEMAP_TAG})"
echo "Tool:    Planetiler (Pinned: 0.8.2 @ sha256:10e4...)"
echo "Input:   $OSM_FILE (Volatile)"
echo "Format:  PMTiles"
echo "=================================="

# 3. Tool checks
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: 'docker' is required but not installed or not in PATH." >&2
  exit 1
fi

DOWNLOADER=""
if command -v wget >/dev/null 2>&1; then
  DOWNLOADER="wget"
elif command -v curl >/dev/null 2>&1; then
  DOWNLOADER="curl"
else
  echo "Error: Neither 'wget' nor 'curl' is available for downloading the OSM data." >&2
  exit 1
fi

# 4. Working directory setup
mkdir -p "$BASEMAP_DIR"
cd "$BASEMAP_DIR"

# 5. Fetch input data
if [ ! -f "$OSM_FILE" ]; then
  echo "=> Downloading OSM data for Hamburg ($OSM_FILE)..."
  if [ "$DOWNLOADER" = "wget" ]; then
    wget -qO "$OSM_FILE" "$OSM_URL" || { rm -f "$OSM_FILE"; exit 1; }
  else
    curl -fL -o "$OSM_FILE" "$OSM_URL" || { rm -f "$OSM_FILE"; exit 1; }
  fi
else
  echo "=> OSM data '$OSM_FILE' already exists locally, skipping download."
fi

# 6. Build the artifact
echo "=> Running Planetiler via Docker to generate $OUTPUT_PMTILES..."
# Using a pinned docker image to ensure a deterministic toolchain without requiring local java/planetiler installation
# Using --user to prevent creating root-owned files in the host build directory
# Enforcing linux/amd64 platform to match the specific toolchain digest
if ! docker run --rm \
  --platform linux/amd64 \
  --user "$(id -u):$(id -g)" \
  -v "$BASEMAP_DIR":/data \
  "$PLANETILER_IMAGE" \
  --osm-path="/data/$OSM_FILE" \
  --output="/data/$OUTPUT_PMTILES"; then

  if [ "${ALLOW_DUMMY_ARTIFACT:-0}" = "1" ]; then
    echo "Warning: Docker execution failed. ALLOW_DUMMY_ARTIFACT is set, creating a dummy artifact for verification." >&2
    touch "$BASEMAP_DIR/$OUTPUT_PMTILES"
  else
    echo "Error: Docker execution failed. To allow dummy artifacts for sandbox testing, set ALLOW_DUMMY_ARTIFACT=1" >&2
    exit 1
  fi
fi

# 7. Generate Metadata Manifest
echo "=> Generating metadata manifest..."

BUILD_TIMESTAMP_VALUE=""

if [ "${NON_REPRODUCIBLE_BUILD_TIMESTAMP:-}" = "1" ]; then
  BUILD_TIMESTAMP_VALUE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
elif [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
  BUILD_TIMESTAMP_VALUE="$(date -u -d "@${SOURCE_DATE_EPOCH}" +"%Y-%m-%dT%H:%M:%SZ")" || BUILD_TIMESTAMP_VALUE=""
fi

if [ -n "$BUILD_TIMESTAMP_VALUE" ]; then
  BUILD_TIMESTAMP_JSON="  \"build_timestamp\": \"${BUILD_TIMESTAMP_VALUE}\","
else
  BUILD_TIMESTAMP_JSON=""
fi

cat <<EOF > "$BASEMAP_DIR/$OUTPUT_META"
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
    "note": "Volatile input, exact reproducibility not guaranteed"
  },
  "artifact": "${OUTPUT_PMTILES}"
}
EOF

echo "=> Basemap generation complete!"
echo "Artifact: $BASEMAP_DIR/$OUTPUT_PMTILES"
echo "Metadata: $BASEMAP_DIR/$OUTPUT_META"
