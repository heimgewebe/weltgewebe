#!/bin/bash
set -euo pipefail

# Scripts for reproducible generation of the sovereign PMTiles basemap artifact.
# Phase 1: Local generation (Hamburg) with planetiler

BASEMAP_DIR="build/basemap"
OSM_FILE="hamburg-latest.osm.pbf"
OSM_URL="https://download.geofabrik.de/europe/germany/hamburg-latest.osm.pbf"
OUTPUT_PMTILES="hamburg.pmtiles"

echo "=== Weltgewebe Basemap Builder ==="
echo "Target: Hamburg"
echo "Tool: Planetiler"
echo "Format: PMTiles"
echo "=================================="

mkdir -p "$BASEMAP_DIR"
cd "$BASEMAP_DIR"

if [ ! -f "$OSM_FILE" ]; then
  echo "=> Downloading OSM data for Hamburg..."
  wget -O "$OSM_FILE" "$OSM_URL"
else
  echo "=> OSM data '$OSM_FILE' already exists, skipping download."
fi

echo "=> Running Planetiler via Docker to generate $OUTPUT_PMTILES..."
# Using docker to ensure reproducible builds without requiring local java/planetiler installation
docker run --rm \
  -v "$(pwd)":/data \
  ghcr.io/onthegomap/planetiler:latest \
  --osm-path="/data/$OSM_FILE" \
  --output="/data/$OUTPUT_PMTILES"

echo "=> Basemap generation complete!"
echo "Artifact: $BASEMAP_DIR/$OUTPUT_PMTILES"
