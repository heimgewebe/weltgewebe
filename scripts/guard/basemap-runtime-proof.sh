#!/usr/bin/env bash
set -euo pipefail

# Guard: Basemap Runtime Proof — PMTiles content and Caddy HTTP Range delivery
#
# Supports two proof scopes, selected via BASEMAP_PROOF_SCOPE:
#
#   range-delivery   (default)
#     Proves that a live Caddy instance delivers a PMTiles artefact via HTTP
#     full (HTTP 200) and Range (HTTP 206) representation contract with
#     application/octet-stream, Accept-Ranges and Content-Range. Does NOT
#     validate the artefact content itself.
#
#   pmtiles-content
#     Proves that the local artefact exists, is non-empty, carries the exact
#     PMTiles magic header at byte offset 0 ("PMTiles", 7 bytes), and that
#     Caddy delivers the same magic bytes 0-6 via HTTP Range request.
#     Optionally verifies SHA256 when BASEMAP_EXPECTED_SHA256 is set.
#     Deep structure is verified by apps/web/scripts/validate-pmtiles.mjs.
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

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd -- "${SCRIPT_DIR}/../.." > /dev/null 2>&1 && pwd)}"

BASEMAP_PROOF_SCOPE="${BASEMAP_PROOF_SCOPE:-range-delivery}"
BASEMAP_PROOF_MODE="${BASEMAP_PROOF_MODE:-require}"

read_header_value() {
  local header_name="${1,,}"
  local header_file="$2"

  awk -v target="${header_name}:" '
    tolower($1) == target {
      sub(/^[^:]*:[[:space:]]*/, "")
      sub(/\r$/, "")
      print
      exit
    }
  ' "${header_file}"
}

require_http_range_proof() {
  local full_url="$1"
  local expected_type="${BASEMAP_EXPECTED_CONTENT_TYPE:-application/octet-stream}"
  local full_headers=""
  local range_headers=""
  local full_status=""
  local range_status=""
  local full_type=""
  local range_type=""
  local accept_ranges=""
  local content_range=""

  full_headers="$(mktemp)"
  range_headers="$(mktemp)"

  full_status="$({
    curl --silent \
      --head \
      --max-time 10 \
      --output /dev/null \
      --dump-header "${full_headers}" \
      --write-out '%{http_code}' \
      "${full_url}" 2> /dev/null
  })" || {
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: HEAD request to %s failed\n' "${full_url}" >&2
    return 1
  }

  if [[ "${full_status}" != "200" ]]; then
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: Expected HTTP 200 for PMTiles HEAD, got %s\n' "${full_status}" >&2
    return 1
  fi

  full_type="$(read_header_value content-type "${full_headers}" | cut -d';' -f1)"
  accept_ranges="$(read_header_value accept-ranges "${full_headers}")"
  if [[ "${full_type}" != "${expected_type}" ]]; then
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: PMTiles HEAD Content-Type is %s, expected %s\n' \
      "${full_type:-<missing>}" "${expected_type}" >&2
    return 1
  fi
  if [[ "${accept_ranges}" != "bytes" ]]; then
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: Accept-Ranges is %s, expected bytes\n' \
      "${accept_ranges:-<missing>}" >&2
    return 1
  fi

  range_status="$({
    curl --silent \
      --max-time 10 \
      --header 'Range: bytes=0-511' \
      --output /dev/null \
      --dump-header "${range_headers}" \
      --write-out '%{http_code}' \
      "${full_url}" 2> /dev/null
  })" || {
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: Range request to %s failed\n' "${full_url}" >&2
    return 1
  }

  if [[ "${range_status}" != "206" ]]; then
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: Expected HTTP 206 for PMTiles Range request, got %s\n' \
      "${range_status}" >&2
    return 1
  fi

  range_type="$(read_header_value content-type "${range_headers}" | cut -d';' -f1)"
  content_range="$(read_header_value content-range "${range_headers}")"
  if [[ "${range_type}" != "${expected_type}" ]]; then
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: PMTiles Range Content-Type is %s, expected %s\n' \
      "${range_type:-<missing>}" "${expected_type}" >&2
    return 1
  fi
  if [[ "${content_range}" != bytes\ 0-511/* ]]; then
    rm -f "${full_headers}" "${range_headers}"
    printf 'ERROR: Content-Range is %s, expected bytes 0-511/<size>\n' \
      "${content_range:-<missing>}" >&2
    return 1
  fi

  printf 'HTTP full status: 200 (confirmed)\n'
  printf 'HTTP range status: 206 (confirmed)\n'
  printf 'Content-Type: %s (full and Range confirmed)\n' "${expected_type}"
  printf 'Accept-Ranges: bytes (confirmed)\n'
  printf 'Content-Range: %s (confirmed)\n' "${content_range}"
  rm -f "${full_headers}" "${range_headers}"
}

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
#         optional SHA256 checksum, and Caddy delivers the same magic bytes
#         via HTTP Range request (bytes 0-6).
# Deep structure is proved by the separate bounded validator in the content jobs.
# ---------------------------------------------------------------------------

if [[ "${BASEMAP_PROOF_SCOPE}" == "pmtiles-content" ]]; then
  printf 'Proof scope: pmtiles-content (local Magic/SHA + Caddy HTTP 206 + HTTP-served Magic; not deep structure)\n'

  BASEMAP_ARTIFACT_DIR="${BASEMAP_ARTIFACT_DIR:-${REPO_ROOT}/build/basemap}"
  BASEMAP_CADDY_URL="${BASEMAP_CADDY_URL:-http://localhost:8081}"
  BASEMAP_PMTILES_PATH="${BASEMAP_PMTILES_PATH:-}"
  BASEMAP_ENDPOINT_PATH="${BASEMAP_ENDPOINT_PATH:-}"
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
    done < <(find "${BASEMAP_ARTIFACT_DIR}" -maxdepth 1 -name '*.pmtiles' -print0 2> /dev/null)
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
  FILE_SIZE="$(stat -c '%s' "${PMTILES_FILE}" 2> /dev/null || echo 0)"
  if [[ "${FILE_SIZE}" -eq 0 ]]; then
    printf 'ERROR: PMTiles file is empty: %s\n' "${PMTILES_FILE}" >&2
    exit 1
  fi
  printf 'File size: %s bytes\n' "${FILE_SIZE}"

  # Verify PMTiles magic header (bytes 0-6 must be ASCII "PMTiles")
  MAGIC_EXPECTED="PMTiles"
  MAGIC_ACTUAL="$(dd if="${PMTILES_FILE}" bs=1 count=7 skip=0 2> /dev/null | tr -d '\0')"
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

  if [[ -z "${BASEMAP_ENDPOINT_PATH}" ]]; then
    BASEMAP_ENDPOINT_PATH="/local-basemap/$(basename "${PMTILES_FILE}")"
  fi

  if [[ "${BASEMAP_ENDPOINT_PATH}" != /* ]]; then
    printf 'ERROR: BASEMAP_ENDPOINT_PATH must start with "/", got: %s\n' "${BASEMAP_ENDPOINT_PATH}" >&2
    exit 1
  fi

  FULL_URL="${BASEMAP_CADDY_URL}${BASEMAP_ENDPOINT_PATH}"
  printf 'Issuing HTTP Range requests to: %s\n' "${FULL_URL}"

  # Step 1: Verify HTTP-served PMTiles magic bytes (0-6)
  printf 'Step 1: Verifying HTTP magic bytes (Range: bytes=0-6)...\n'
  http_magic_tmp="$(mktemp)"
  http_magic_status="$({
    curl --silent \
      --max-time 10 \
      --range 0-6 \
      --output "${http_magic_tmp}" \
      --write-out '%{http_code}' \
      "${FULL_URL}" 2> /dev/null
  })"
  http_magic_exit=$?
  if [[ ${http_magic_exit} -ne 0 ]]; then
    rm -f "${http_magic_tmp}"
    printf 'ERROR: curl request to fetch HTTP magic bytes failed (exit: %d)\n' ${http_magic_exit} >&2
    printf '  URL: %s\n' "${FULL_URL}" >&2
    exit 1
  fi

  if [[ "${http_magic_status}" != "206" ]]; then
    rm -f "${http_magic_tmp}"
    printf 'ERROR: Expected HTTP 206 for PMTiles magic range, got %s\n' "${http_magic_status}" >&2
    printf '  URL:      %s\n' "${FULL_URL}" >&2
    printf '  Expected: 206 Partial Content\n' >&2
    exit 1
  fi

  http_magic="$(tr -d '\0' < "${http_magic_tmp}" 2> /dev/null)"
  rm -f "${http_magic_tmp}"

  if [[ "${http_magic}" != "PMTiles" ]]; then
    printf 'ERROR: HTTP-served PMTiles magic bytes mismatch\n' >&2
    printf '  Expected: PMTiles\n' >&2
    printf '  Got:      %s\n' "${http_magic}" >&2
    exit 1
  fi
  printf 'HTTP magic bytes (0-6): "%s" confirmed\n' "${http_magic}"

  # Step 2: Verify HTTP Range delivery (206 + headers for bytes 0-511)
  printf 'Step 2: Verifying HTTP Range delivery (Range: bytes=0-511)...\n'
  require_http_range_proof "${FULL_URL}"

  printf '\n'
  printf 'PROVEN: HTTP-served PMTiles Magic verified\n'
  printf 'PROVEN: Caddy PMTiles content verified (scope=pmtiles-content)\n'
  printf '  Local file:     %s\n' "${PMTILES_FILE}"
  printf '  File size:      %s bytes\n' "${FILE_SIZE}"
  printf '  Local magic:    "%s" at offset 0\n' "${MAGIC_ACTUAL}"
  printf '  HTTP endpoint:  %s\n' "${FULL_URL}"
  printf '  HTTP magic:     "%s" (bytes 0-6)\n' "${http_magic}"
  printf '  HTTP status:    206 Partial Content\n'
  printf '  SHA256 check:   %s\n' "${SHA256_STATUS}"
  printf '\n'
  printf 'SCOPE_LIMIT: Deep structure is verified by the separate bounded validator step.\n'
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
    done < <(find "${BASEMAP_ARTIFACT_DIR}" -maxdepth 1 -name '*.pmtiles' -print0 2> /dev/null)
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
require_http_range_proof "${FULL_URL}"

# ---------------------------------------------------------------------------
# Proof confirmed
# ---------------------------------------------------------------------------

printf '\nPROVEN: Caddy PMTiles Range delivery verified (scope=range-delivery)\n'
printf '  Endpoint:      %s\n' "${FULL_URL}"
printf '  HTTP status:   206 Partial Content\n'
printf '  Range headers: present\n'
printf 'This constitutes a real runtime proof — not a mocked client test.\n'
