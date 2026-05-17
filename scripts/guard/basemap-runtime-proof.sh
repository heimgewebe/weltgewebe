#!/usr/bin/env bash
set -euo pipefail

# Guard: Basemap Runtime Proof — PMTiles content and Caddy HTTP Range delivery
#
# Supports two proof scopes, selected via BASEMAP_PROOF_SCOPE:
#
#   range-delivery   (default)
#     Proves that a live Caddy instance delivers a PMTiles artefact via HTTP
#     Range requests (HTTP 206 Partial Content), with Accept-Ranges/Content-Range
#     headers present.  Does NOT validate the artefact content itself.
#
#   pmtiles-content
#     Proves that the local artefact exists, is non-empty, and carries the exact
#     PMTiles magic header at byte offset 0 ("PMTiles", 7 bytes).
#     Optionally verifies SHA256 when BASEMAP_EXPECTED_SHA256 is set.
#     Explicitly NOT a deep PMTiles structure validation.
#
# This is DISTINCT from:
#   - apps/web/tests/basemap-client-integration.spec.ts  (mocked client test;
#       validates MapLibre protocol handling without a real HTTP backend)
#   - scripts/guard/caddy-basemap-route-guard.sh          (static config check;
#       validates route definitions in Caddyfiles, not live delivery)
#
# Neither of the above constitutes a real runtime proof.
#
# Usage:
#   scripts/guard/basemap-runtime-proof.sh
#
# Environment variables (all optional):
#   BASEMAP_PROOF_SCOPE    Proof scope to execute:
#                          "range-delivery" (default) — HTTP Range proof via Caddy
#                          "pmtiles-content"          — Magic/Header/Hash proof on local file
#   BASEMAP_PROOF_MODE     "require" — fail with exit 1 when artefact is absent (default)
#                          "skip"    — exit 0 with NOT_PROVEN note when artefact is absent
#
#   For range-delivery scope:
#   BASEMAP_CADDY_URL      Base URL of the running Caddy instance
#                          (default: http://localhost:8081)
#   BASEMAP_ENDPOINT_PATH  Explicit HTTP path to the PMTiles artefact on Caddy
#                          (overrides auto-detection)
#   BASEMAP_ARTIFACT_DIR   Local directory to scan for .pmtiles files
#                          (default: <repo-root>/build/basemap)
#
#   For pmtiles-content scope:
#   BASEMAP_PMTILES_PATH   Explicit path to the local .pmtiles file to inspect
#                          (overrides auto-detection from BASEMAP_ARTIFACT_DIR)
#   BASEMAP_EXPECTED_SHA256  Expected SHA256 hex digest; when set, hash is verified
#
# Exit codes:
#   0 — Proof succeeded (PROVEN)
#   0 — Artefact absent and BASEMAP_PROOF_MODE=skip (NOT_PROVEN, explicitly skipped)
#   1 — Proof failed or artefact absent in "require" mode

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)}"

BASEMAP_PROOF_SCOPE="${BASEMAP_PROOF_SCOPE:-range-delivery}"
BASEMAP_PROOF_MODE="${BASEMAP_PROOF_MODE:-require}"

# Validate BASEMAP_PROOF_SCOPE
if [[ "${BASEMAP_PROOF_SCOPE}" != "range-delivery" && "${BASEMAP_PROOF_SCOPE}" != "pmtiles-content" ]]; then
  printf 'ERROR: BASEMAP_PROOF_SCOPE must be "range-delivery" or "pmtiles-content", got: %s\n' "${BASEMAP_PROOF_SCOPE}" >&2
  exit 1
fi

# Validate BASEMAP_PROOF_MODE
if [[ "${BASEMAP_PROOF_MODE}" != "require" && "${BASEMAP_PROOF_MODE}" != "skip" ]]; then
  printf 'ERROR: BASEMAP_PROOF_MODE must be "require" or "skip", got: %s\n' "${BASEMAP_PROOF_MODE}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Scope: pmtiles-content
# Proves: local file exists, non-empty, PMTiles magic header at offset 0,
#         optional SHA256 checksum.
# Explicitly NOT: deep PMTiles structure validation.
# ---------------------------------------------------------------------------

if [[ "${BASEMAP_PROOF_SCOPE}" == "pmtiles-content" ]]; then
  printf 'Proof scope: pmtiles-content (Magic/Header/Hash — not deep structure)\n'

  BASEMAP_ARTIFACT_DIR="${BASEMAP_ARTIFACT_DIR:-${REPO_ROOT}/build/basemap}"
  BASEMAP_PMTILES_PATH="${BASEMAP_PMTILES_PATH:-}"
  BASEMAP_EXPECTED_SHA256="${BASEMAP_EXPECTED_SHA256:-}"

  # Resolve file path
  PMTILES_FILE=""
  if [[ -n "${BASEMAP_PMTILES_PATH}" ]]; then
    PMTILES_FILE="${BASEMAP_PMTILES_PATH}"
    printf 'Using explicit PMTiles path: %s\n' "${PMTILES_FILE}"
  elif [[ -d "${BASEMAP_ARTIFACT_DIR}" ]]; then
    while IFS= read -r -d '' f; do
      PMTILES_FILE="${f}"
      break
    done < <(find "${BASEMAP_ARTIFACT_DIR}" -maxdepth 1 -name '*.pmtiles' -print0 2>/dev/null)
    if [[ -n "${PMTILES_FILE}" ]]; then
      printf 'Auto-detected PMTiles file: %s\n' "${PMTILES_FILE}"
    fi
  fi

  # Handle missing file
  if [[ -z "${PMTILES_FILE}" || ! -f "${PMTILES_FILE}" ]]; then
    if [[ "${BASEMAP_PROOF_MODE}" == "skip" ]]; then
      printf 'NOT_PROVEN: PMTiles file not found — content proof skipped\n'
      printf 'Set BASEMAP_PMTILES_PATH or place a .pmtiles file in %s to enable this proof.\n' "${BASEMAP_ARTIFACT_DIR}"
      exit 0
    else
      printf 'ERROR: PMTiles file not found: %s\n' "${PMTILES_FILE:-<none resolved>}" >&2
      printf 'Set BASEMAP_PMTILES_PATH to the artefact path, or use BASEMAP_PROOF_MODE=skip to skip.\n' >&2
      exit 1
    fi
  fi

  # Check non-empty
  FILE_SIZE="$(stat -c '%s' "${PMTILES_FILE}" 2>/dev/null || echo 0)"
  if [[ "${FILE_SIZE}" -eq 0 ]]; then
    printf 'ERROR: PMTiles file is empty: %s\n' "${PMTILES_FILE}" >&2
    exit 1
  fi
  printf 'File size: %s bytes\n' "${FILE_SIZE}"

  # Verify PMTiles magic header (bytes 0-6 must be ASCII "PMTiles")
  MAGIC_EXPECTED="PMTiles"
  MAGIC_ACTUAL="$(dd if="${PMTILES_FILE}" bs=1 count=7 skip=0 2>/dev/null | tr -d '\0')"
  if [[ "${MAGIC_ACTUAL}" != "${MAGIC_EXPECTED}" ]]; then
    printf 'ERROR: Magic header mismatch in %s\n' "${PMTILES_FILE}" >&2
    printf '  Expected: %s\n' "${MAGIC_EXPECTED}" >&2
    printf '  Actual:   %s\n' "${MAGIC_ACTUAL}" >&2
    printf '  File does not appear to be a valid PMTiles archive.\n' >&2
    exit 1
  fi
  printf 'Magic header: "%s" (PMTiles format confirmed at offset 0)\n' "${MAGIC_ACTUAL}"

  # Optional SHA256 check
  SHA256_STATUS="not checked"
  if [[ -n "${BASEMAP_EXPECTED_SHA256}" ]]; then
    ACTUAL_SHA256="$(sha256sum "${PMTILES_FILE}" | awk '{print $1}')"
    if [[ "${ACTUAL_SHA256}" != "${BASEMAP_EXPECTED_SHA256}" ]]; then
      printf 'ERROR: SHA256 mismatch for %s\n' "${PMTILES_FILE}" >&2
      printf '  Expected: %s\n' "${BASEMAP_EXPECTED_SHA256}" >&2
      printf '  Actual:   %s\n' "${ACTUAL_SHA256}" >&2
      exit 1
    fi
    printf 'SHA256: %s (matches expected)\n' "${ACTUAL_SHA256}"
    SHA256_STATUS="PROVEN"
  fi

  printf '\n'
  printf 'PROVEN: PMTiles Magic/Header verified\n'
  printf '  File:         %s\n' "${PMTILES_FILE}"
  printf '  Size:         %s bytes\n' "${FILE_SIZE}"
  printf '  Magic header: "%s" at offset 0\n' "${MAGIC_ACTUAL}"
  printf '  SHA256 check: %s\n' "${SHA256_STATUS}"
  printf '\n'
  printf 'NOT_PROVEN: Deep PMTiles structure validation (tile index, directory, metadata integrity)\n'
  printf '  This scope validates magic/header/hash only — full structure proof not implemented.\n'
  exit 0
fi

# ---------------------------------------------------------------------------
# Scope: range-delivery (default)
# Proves: HTTP Range request to live Caddy returns 206, Accept-Ranges/Content-Range.
# Does NOT validate artefact content.
# ---------------------------------------------------------------------------

BASEMAP_CADDY_URL="${BASEMAP_CADDY_URL:-http://localhost:8081}"
BASEMAP_ARTIFACT_DIR="${BASEMAP_ARTIFACT_DIR:-${REPO_ROOT}/build/basemap}"

# Validate BASEMAP_ENDPOINT_PATH starts with "/" if explicitly set
if [[ -n "${BASEMAP_ENDPOINT_PATH:-}" && "${BASEMAP_ENDPOINT_PATH}" != /* ]]; then
  printf 'ERROR: BASEMAP_ENDPOINT_PATH must start with "/", got: %s\n' "${BASEMAP_ENDPOINT_PATH}" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

HEADER_TMP=""
cleanup() {
  if [[ -n "${HEADER_TMP}" && -f "${HEADER_TMP}" ]]; then
    rm -f "${HEADER_TMP}"
  fi
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 1: Locate PMTiles artefact
# ---------------------------------------------------------------------------

ENDPOINT_PATH=""

if [[ -n "${BASEMAP_ENDPOINT_PATH:-}" ]]; then
  ENDPOINT_PATH="${BASEMAP_ENDPOINT_PATH}"
  printf 'Using explicit endpoint path: %s\n' "${ENDPOINT_PATH}"
else
  PMTILES_FILE=""
  if [[ -d "${BASEMAP_ARTIFACT_DIR}" ]]; then
    while IFS= read -r -d '' f; do
      PMTILES_FILE="${f}"
      break
    done < <(find "${BASEMAP_ARTIFACT_DIR}" -maxdepth 1 -name '*.pmtiles' -print0 2>/dev/null)
  fi

  if [[ -z "${PMTILES_FILE}" ]]; then
    if [[ "${BASEMAP_PROOF_MODE}" == "skip" ]]; then
      printf 'NOT_PROVEN: No PMTiles artefact found in %s\n' "${BASEMAP_ARTIFACT_DIR}"
      printf 'Basemap runtime proof skipped — artefact not available in this environment.\n'
      printf 'The mocked client test (basemap-client-integration.spec.ts) does NOT substitute this proof.\n'
      printf 'To produce a real proof: build a PMTiles artefact and start Caddy, then re-run this guard.\n'
      exit 0
    else
      printf 'ERROR: No PMTiles artefact found in %s\n' "${BASEMAP_ARTIFACT_DIR}" >&2
      printf 'Expected at least one .pmtiles file in that directory.\n' >&2
      printf 'To skip when artefact is absent, set: BASEMAP_PROOF_MODE=skip\n' >&2
      exit 1
    fi
  fi

  ARTEFACT_NAME="$(basename "${PMTILES_FILE}")"
  ENDPOINT_PATH="/local-basemap/${ARTEFACT_NAME}"
  printf 'Auto-detected PMTiles artefact: %s\n' "${PMTILES_FILE}"
fi

FULL_URL="${BASEMAP_CADDY_URL}${ENDPOINT_PATH}"

# ---------------------------------------------------------------------------
# Step 2: Issue GET Range request — capture HTTP status code and response headers
# ---------------------------------------------------------------------------

printf 'Issuing Range GET request: %s (Range: bytes=0-511)\n' "${FULL_URL}"

HEADER_TMP="$(mktemp)"

HTTP_STATUS="$(
  curl --silent \
       --max-time 10 \
       --header 'Range: bytes=0-511' \
       --output /dev/null \
       --dump-header "${HEADER_TMP}" \
       --write-out '%{http_code}' \
       "${FULL_URL}" 2>/dev/null
)" || {
  printf 'ERROR: curl request to %s failed\n' "${FULL_URL}" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# Step 3: Validate HTTP 206 — reject silent 200 OK on Range requests
# ---------------------------------------------------------------------------

if [[ "${HTTP_STATUS}" == "200" ]]; then
  printf 'ERROR: Caddy returned HTTP 200 for a Range request — Range delivery is inactive\n' >&2
  printf '  URL:    %s\n' "${FULL_URL}" >&2
  printf '  Status: 200 OK (expected 206 Partial Content)\n' >&2
  printf '  A 200 response to a Range request means the server ignores Range headers.\n' >&2
  printf '  PMTiles clients rely on byte-range streaming; a 200 here breaks tile loading.\n' >&2
  exit 1
fi

if [[ "${HTTP_STATUS}" != "206" ]]; then
  printf 'ERROR: Unexpected HTTP status %s for Range request\n' "${HTTP_STATUS}" >&2
  printf '  URL:      %s\n' "${FULL_URL}" >&2
  printf '  Expected: 206 Partial Content\n' >&2
  exit 1
fi

printf 'HTTP status: %s (206 Partial Content confirmed)\n' "${HTTP_STATUS}"

# ---------------------------------------------------------------------------
# Step 4: Verify Accept-Ranges or Content-Range header is present
# ---------------------------------------------------------------------------

HAS_ACCEPT_RANGES=0
HAS_CONTENT_RANGE=0

if grep -qi '^accept-ranges:' "${HEADER_TMP}"; then
  HAS_ACCEPT_RANGES=1
fi
if grep -qi '^content-range:' "${HEADER_TMP}"; then
  HAS_CONTENT_RANGE=1
fi

if [[ "${HAS_ACCEPT_RANGES}" -eq 0 && "${HAS_CONTENT_RANGE}" -eq 0 ]]; then
  printf 'ERROR: Neither Accept-Ranges nor Content-Range header present in response\n' >&2
  printf '  URL: %s\n' "${FULL_URL}" >&2
  printf '  Without these headers PMTiles clients cannot reliably stream byte ranges.\n' >&2
  exit 1
fi

if [[ "${HAS_ACCEPT_RANGES}" -eq 1 ]]; then
  ACCEPT_RANGES_VAL="$(grep -i '^accept-ranges:' "${HEADER_TMP}" | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r')"
  printf 'Accept-Ranges: %s (confirmed)\n' "${ACCEPT_RANGES_VAL}"
fi
if [[ "${HAS_CONTENT_RANGE}" -eq 1 ]]; then
  CONTENT_RANGE_VAL="$(grep -i '^content-range:' "${HEADER_TMP}" | head -1 | sed 's/^[^:]*:[[:space:]]*//' | tr -d '\r')"
  printf 'Content-Range: %s (confirmed)\n' "${CONTENT_RANGE_VAL}"
fi

# ---------------------------------------------------------------------------
# Proof confirmed
# ---------------------------------------------------------------------------

printf '\nPROVEN: Caddy PMTiles Range delivery verified\n'
printf '  Endpoint:      %s\n' "${FULL_URL}"
printf '  HTTP status:   206 Partial Content\n'
printf '  Range headers: present\n'
printf 'This constitutes a real runtime proof — not a mocked client test.\n'
