#!/usr/bin/env bash
set -euo pipefail

# Scripts for operational bootstrap of the sovereign visual assets (Glyphs).
# Phase 2: Local generation/hosting of PBF fonts.
#
# Determinism status:
# - Pinned release version of OpenMapTiles fonts (v2.0)
# - SHA256 integrity verification of the downloaded archive
# - Extracted assets placed in reproducible local paths

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"
GLYPHS_DIR="$REPO_ROOT/map-style/glyphs"
TARGET_FONT_DIR="$GLYPHS_DIR/Noto Sans Regular"

# Pin OpenMapTiles fonts v2.0 (Noto Sans)
ASSET_URL="https://github.com/openmaptiles/fonts/releases/download/v2.0/noto-sans.zip"
ASSET_SHA256="d117316544b43a5dde7ee761b36e17701e9f85574e181d76a74814240fdbaf34"
TMP_ARCHIVE="/tmp/noto-sans-$$.zip"
trap 'rm -f "$TMP_ARCHIVE"' EXIT

echo "=== Weltgewebe Basemap Builder ==="
echo "Target:  Glyphs (Fonts)"
echo "Input:   OpenMapTiles Fonts v2.0 (Noto Sans)"
echo "Format:  PBF (Protocol Buffers)"
echo "=================================="

# Tool checks
DOWNLOADER=""
if command -v wget >/dev/null 2>&1; then
  DOWNLOADER="wget"
elif command -v curl >/dev/null 2>&1; then
  DOWNLOADER="curl"
else
  echo "Error: Neither 'wget' nor 'curl' is available for downloading the assets." >&2
  exit 1
fi

if ! command -v unzip >/dev/null 2>&1; then
  echo "Error: 'unzip' is required to extract the font archive." >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  SHA256_CMD=(sha256sum)
elif command -v shasum >/dev/null 2>&1; then
  SHA256_CMD=(shasum -a 256)
else
  echo "Error: 'sha256sum' or 'shasum' is required for artifact verification but not installed." >&2
  exit 1
fi


echo "=> Preparing target directory ($TARGET_FONT_DIR)..."
mkdir -p "$TARGET_FONT_DIR"

echo "=> Checking if glyphs are already present..."
if [ -n "$(find "$TARGET_FONT_DIR" -maxdepth 1 -name '*.pbf' -print -quit 2>/dev/null)" ]; then
  echo "   [✓] Glyphs already found in target directory. Skipping download."
  exit 0
fi

echo "=> Downloading font archive from OpenMapTiles..."
if [ "$DOWNLOADER" = "wget" ]; then
  wget -qO "$TMP_ARCHIVE" "$ASSET_URL" || { exit 1; }
else
  curl -fL -s -o "$TMP_ARCHIVE" "$ASSET_URL" || { exit 1; }
fi

echo "=> Verifying integrity of downloaded archive..."
ACTUAL_SHA256="$("${SHA256_CMD[@]}" "$TMP_ARCHIVE" | awk '{print $1}')"
if [ "$ACTUAL_SHA256" != "$ASSET_SHA256" ]; then
  echo "Error: Checksum mismatch for downloaded archive!" >&2
  echo "Expected: $ASSET_SHA256" >&2
  echo "Actual:   $ACTUAL_SHA256" >&2
  exit 1
fi
echo "   [✓] Integrity verified (SHA256 match)."

echo "=> Extracting 'Noto Sans Regular' glyphs..."
# Extract only the "Noto Sans Regular" directory, and place its contents directly into the TARGET_FONT_DIR
unzip -o -q -j "$TMP_ARCHIVE" "Noto Sans Regular/*" -d "$TARGET_FONT_DIR" || {
  echo "Error: Failed to extract 'Noto Sans Regular' from archive." >&2
  exit 1
}


echo "=> Glyph fetching complete!"
echo "Artifacts are now available in: $TARGET_FONT_DIR"
