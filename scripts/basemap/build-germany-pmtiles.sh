#!/usr/bin/env bash
set -euo pipefail

# Scripts for operational bootstrap of the sovereign PMTiles basemap artifact.
# Phase 1: Local generation (Germany) with planetiler
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

# 2. Pin tools and OSM input for reproducible input provenance
# We use a stable, historical OSM snapshot from Geofabrik instead of the daily latest.
# Geofabrik does not provide SHA256 hashes, so we determine and pin the SHA256 hash ourselves to maintain input integrity.
OSM_FILE="germany-260101.osm.pbf"
OSM_URL="https://download.geofabrik.de/europe/germany-260101.osm.pbf"
OSM_SHA256="4a2e3181c2cef4795b62ef9b447d4fa5f7f9bb2352d563292a7b98baa75279f8"

# Versioning
BASEMAP_VERSION="0.1.0"
BASEMAP_TAG="v${BASEMAP_VERSION}"
OUTPUT_PMTILES="basemap-germany-${BASEMAP_TAG}.pmtiles"
OUTPUT_META="basemap-germany-${BASEMAP_TAG}.meta.json"

# Planetiler 0.8.2 (linux/amd64) pinned by digest for a truly deterministic toolchain
PLANETILER_IMAGE="ghcr.io/onthegomap/planetiler@sha256:10e4d6850664bd2ad7a223623383c48281e7d87fb427360838b13342cac012bb"

echo "=== Weltgewebe Basemap Builder ==="
echo "Target:  Germany"
echo "Version: ${BASEMAP_VERSION} (Tag: ${BASEMAP_TAG})"
echo "Tool:    Planetiler (Pinned: 0.8.2 @ sha256:10e4...)"
echo "Input:   $OSM_FILE (Pinned & Hash-Verified)"
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

# 5. Fetch and verify input data
if [ ! -f "$OSM_FILE" ]; then
  echo "=> Downloading OSM data for Germany ($OSM_FILE)..."
  if [ "$DOWNLOADER" = "wget" ]; then
    wget -qO "$OSM_FILE" "$OSM_URL" || { rm -f "$OSM_FILE"; exit 1; }
  else
    curl -fL -o "$OSM_FILE" "$OSM_URL" || { rm -f "$OSM_FILE"; exit 1; }
  fi
else
  echo "=> OSM data '$OSM_FILE' already exists locally, skipping download."
fi

echo "=> Verifying integrity of $OSM_FILE..."
if command -v sha256sum >/dev/null 2>&1; then
  SHA256_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  SHA256_CMD=(shasum -a 256)
else
  echo "Error: 'sha256sum' or 'shasum' is required for artifact verification but not installed." >&2
  exit 1
fi

ACTUAL_SHA256="$("${SHA256_CMD[@]}" "$OSM_FILE" | awk '{print $1}')"
if [ "$ACTUAL_SHA256" != "$OSM_SHA256" ]; then
  echo "Error: Checksum mismatch for $OSM_FILE!" >&2
  echo "Expected: $OSM_SHA256" >&2
  echo "Actual:   $ACTUAL_SHA256" >&2
  echo "The file may be corrupted or modified. Aborting to preserve reproducibility." >&2
  exit 1
fi
echo "   [✓] Integrity verified (SHA256 match)."

# 6. Build the artifact
echo "=> Running Planetiler via Docker to generate $OUTPUT_PMTILES..."
# Using a pinned docker image to ensure a deterministic toolchain without requiring local java/planetiler installation
# Using --user to prevent creating root-owned files in the host build directory
# Enforcing linux/amd64 platform to match the specific toolchain digest
if ! docker run --rm   --platform linux/amd64   --user "$(id -u):$(id -g)"   -v "$BASEMAP_DIR":/data   "$PLANETILER_IMAGE"   --osm-path="/data/$OSM_FILE"   --output="/data/$OUTPUT_PMTILES"; then

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

echo "=> Calculating size and SHA256 of $OUTPUT_PMTILES..."
if command -v sha256sum >/dev/null 2>&1; then
  SHA256_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  SHA256_CMD=(shasum -a 256)
else
  echo "Error: 'sha256sum' or 'shasum' is required for artifact verification but not installed." >&2
  exit 1
fi

if [ ! -f "$BASEMAP_DIR/$OUTPUT_PMTILES" ]; then
  echo "Error: Artifact $OUTPUT_PMTILES not found. Cannot generate ready status." >&2
  exit 1
fi

PMTILES_SIZE=$(wc -c < "$BASEMAP_DIR/$OUTPUT_PMTILES" | tr -d '[:space:]')
PMTILES_SHA256="$("${SHA256_CMD[@]}" "$BASEMAP_DIR/$OUTPUT_PMTILES" | awk '{print $1}')"

if [ -z "$PMTILES_SHA256" ] || [ "$PMTILES_SIZE" -eq 0 ]; then
  echo "Error: Failed to determine valid size or hash for $OUTPUT_PMTILES." >&2
  exit 1
fi

BUILD_TIMESTAMP_VALUE=""

if [ "${NON_REPRODUCIBLE_BUILD_TIMESTAMP:-}" = "1" ]; then
  BUILD_TIMESTAMP_VALUE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
elif [ -n "${SOURCE_DATE_EPOCH:-}" ]; then
  BUILD_TIMESTAMP_VALUE="$(date -u -d "@${SOURCE_DATE_EPOCH}" +"%Y-%m-%dT%H:%M:%SZ")" || BUILD_TIMESTAMP_VALUE=""
fi

if [ -n "$BUILD_TIMESTAMP_VALUE" ]; then
  BUILD_TIMESTAMP_JSON="  "build_timestamp": "${BUILD_TIMESTAMP_VALUE}","
else
  BUILD_TIMESTAMP_JSON=""
fi

cat <<MANIFEST > "$BASEMAP_DIR/$OUTPUT_META"
{
  "version": "${BASEMAP_VERSION}",
  "region": "germany",
${BUILD_TIMESTAMP_JSON}
  "toolchain": {
    "generator": "planetiler",
    "image": "${PLANETILER_IMAGE}"
  },
  "input": {
    "url": "${OSM_URL}",
    "md5": "${OSM_MD5}",
    "note": "Pinned historical snapshot with verified SHA256 integrity"
  },
  "artifact_name": "${OUTPUT_PMTILES}",
  "sha256": "${PMTILES_SHA256}",
  "size_bytes": ${PMTILES_SIZE},
  "status": "ready"
}
MANIFEST

# 8. Create stable aliases
echo "=> Creating stable aliases for deployment..."
ALIAS_PMTILES="basemap-germany.pmtiles"
ALIAS_META="basemap-germany.meta.json"

TMP_ALIAS_PMTILES="${BASEMAP_DIR}/${ALIAS_PMTILES}.tmp.$$"
TMP_ALIAS_META="${BASEMAP_DIR}/${ALIAS_META}.tmp.$$"

# Clean up temporary files on exit
trap 'rm -f "$TMP_ALIAS_PMTILES" "$TMP_ALIAS_META"' EXIT

# We use robust file copying (cp) instead of symlinks.
# This ensures maximum cross-platform portability and prevents issues
# with static file servers that might not follow symlinks by default or
# where symlinks are not permitted outside specific directories.
# To avoid clients observing partially written files, we copy to a temporary
# file in the same directory and atomically rename it.
cp -f "$BASEMAP_DIR/$OUTPUT_PMTILES" "$TMP_ALIAS_PMTILES"
cp -f "$BASEMAP_DIR/$OUTPUT_META" "$TMP_ALIAS_META"

# Atomic rename
mv -f "$TMP_ALIAS_PMTILES" "$BASEMAP_DIR/$ALIAS_PMTILES"
mv -f "$TMP_ALIAS_META" "$BASEMAP_DIR/$ALIAS_META"

# Remove trap now that files have been successfully moved
trap - EXIT

echo "=> Basemap generation complete!"
echo "Artifact: $BASEMAP_DIR/$OUTPUT_PMTILES"
echo "Metadata: $BASEMAP_DIR/$OUTPUT_META"
echo "Alias (PMTiles): $BASEMAP_DIR/$ALIAS_PMTILES"
echo "Alias (Meta): $BASEMAP_DIR/$ALIAS_META"
