#!/usr/bin/env bash
set -euo pipefail

# Guard: Basemap Runtime Proof — Caddy PMTiles HTTP Range delivery
#
# Proves that a live Caddy instance delivers a PMTiles artefact via HTTP Range
# requests (HTTP 206 Partial Content), with Accept-Ranges/Content-Range headers.
#
# This is DISTINCT from:
#   - apps/web/tests/basemap-client-integration.spec.ts  (mocked client test;
#       validates MapLibre protocol handling without a real HTTP backend)
#   - scripts/guard/caddy-basemap-route-guard.sh          (static config check;
#       validates route definitions in Caddyfiles, not live delivery)
#
# Neither of the above constitutes a real runtime proof.
# This script is the only current guard that exercises the actual delivery chain:
#   Browser / curl → HTTP → Caddy → PMTiles artefact → 206 Partial Content
#
# Usage:
#   scripts/guard/basemap-runtime-proof.sh
#
# Environment variables (all optional):
#   BASEMAP_CADDY_URL      Base URL of the running Caddy instance
#                          (default: http://localhost:8081)
#   BASEMAP_ENDPOINT_PATH  Explicit HTTP path to the PMTiles artefact on Caddy
#                          (overrides auto-detection; e.g. /local-basemap/basemap-v0.1.0.pmtiles)
#   BASEMAP_ARTIFACT_DIR   Local directory to scan for .pmtiles files
#                          (default: <repo-root>/build/basemap)
#   BASEMAP_PROOF_MODE     "require" — fail with exit 1 when artefact is absent (default)
#                          "skip"    — exit 0 with NOT_PROVEN note when artefact is absent
#
# Exit codes:
#   0 — HTTP 206 confirmed, Accept-Ranges or Content-Range header present (PROVEN)
#   0 — Artefact absent and BASEMAP_PROOF_MODE=skip (NOT_PROVEN, explicitly skipped)
#   1 — Proof failed: wrong HTTP status, missing range headers, connectivity error,
#         or artefact absent in "require" mode

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." >/dev/null 2>&1 && pwd)}"

BASEMAP_CADDY_URL="${BASEMAP_CADDY_URL:-http://localhost:8081}"
BASEMAP_ARTIFACT_DIR="${BASEMAP_ARTIFACT_DIR:-${REPO_ROOT}/build/basemap}"
BASEMAP_PROOF_MODE="${BASEMAP_PROOF_MODE:-require}"

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
# Step 2: Check Caddy reachability
# ---------------------------------------------------------------------------

printf 'Checking Caddy reachability at %s ...\n' "${BASEMAP_CADDY_URL}"
if ! curl --silent --fail --max-time 5 --output /dev/null --head "${BASEMAP_CADDY_URL}" 2>/dev/null; then
  printf 'ERROR: Caddy endpoint %s is not reachable\n' "${BASEMAP_CADDY_URL}" >&2
  printf 'Ensure Caddy is running before invoking this guard.\n' >&2
  exit 1
fi
printf 'Caddy is reachable at %s\n' "${BASEMAP_CADDY_URL}"

# ---------------------------------------------------------------------------
# Step 3: Issue GET Range request — capture HTTP status code and response headers
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
# Step 4: Validate HTTP 206 — reject silent 200 OK on Range requests
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
# Step 5: Verify Accept-Ranges or Content-Range header is present
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
