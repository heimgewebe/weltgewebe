#!/usr/bin/env bash
set -euo pipefail

# Scripts for reproducible generation of the sovereign PMTiles basemap artifact.
# Phase 1: Local generation (Hamburg) with planetiler
#
# Reproducibility criteria met:
# - Pinned OSM data source URL
# - Pinned Planetiler container version
# - Explicit host path and user mapping
# - Tool presence checks

# 1. Resolve repo root securely
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
BASEMAP_DIR="$REPO_ROOT/build/basemap"

# 2. Pin inputs and tools
# Pinning the specific daily build to guarantee reproducible output hashes
# If this file expires from Geofabrik, a mirror or archive link must be used.
OSM_DATE="140101"
OSM_FILE="hamburg-$OSM_DATE.osm.pbf"
OSM_URL="https://download.geofabrik.de/europe/germany/hamburg-$OSM_DATE.osm.pbf"

OUTPUT_PMTILES="hamburg.pmtiles"
PLANETILER_IMAGE="ghcr.io/onthegomap/planetiler:0.8.2"

echo "=== Weltgewebe Basemap Builder ==="
echo "Target:  Hamburg"
echo "Tool:    Planetiler (Pinned: $PLANETILER_IMAGE)"
echo "Input:   $OSM_FILE"
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

# 5. Fetch pinned input data
if [ ! -f "$OSM_FILE" ]; then
  echo "=> Downloading pinned OSM data for Hamburg ($OSM_FILE)..."
  if [ "$DOWNLOADER" = "wget" ]; then
    wget -O "$OSM_FILE" "$OSM_URL"
  else
    curl -L -o "$OSM_FILE" "$OSM_URL"
  fi
else
  echo "=> OSM data '$OSM_FILE' already exists locally, skipping download."
fi

# 6. Build the artifact
echo "=> Running Planetiler via Docker to generate $OUTPUT_PMTILES..."
# Using docker to ensure reproducible builds without requiring local java/planetiler installation
# Using --user to prevent creating root-owned files in the host build directory
docker run --rm \
  --user "$(id -u):$(id -g)" \
  -v "$BASEMAP_DIR":/data \
  "$PLANETILER_IMAGE" \
  --osm-path="/data/$OSM_FILE" \
  --output="/data/$OUTPUT_PMTILES"

echo "=> Basemap generation complete!"
echo "Artifact: $BASEMAP_DIR/$OUTPUT_PMTILES"
