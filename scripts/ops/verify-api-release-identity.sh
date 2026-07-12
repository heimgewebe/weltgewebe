#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

API_VERSION_URL="${API_VERSION_URL:-https://weltgewebe.net/api/version}"
EXPECTED_COMMIT="${EXPECTED_COMMIT:-}"
EXPECTED_BUILD_TIMESTAMP="${EXPECTED_BUILD_TIMESTAMP:-}"
CONNECT_TIMEOUT_SECONDS="${CONNECT_TIMEOUT_SECONDS:-5}"
REQUEST_TIMEOUT_SECONDS="${REQUEST_TIMEOUT_SECONDS:-15}"

command -v curl > /dev/null 2>&1 || fail "curl is required"
command -v python3 > /dev/null 2>&1 || fail "python3 is required"

[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || fail "EXPECTED_COMMIT must be a full lowercase Git SHA"
[[ "$EXPECTED_BUILD_TIMESTAMP" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})$ ]] || fail "EXPECTED_BUILD_TIMESTAMP must be RFC3339"
case "$CONNECT_TIMEOUT_SECONDS" in
  '' | *[!0-9]*) fail "CONNECT_TIMEOUT_SECONDS must be an integer" ;;
esac
case "$REQUEST_TIMEOUT_SECONDS" in
  '' | *[!0-9]*) fail "REQUEST_TIMEOUT_SECONDS must be an integer" ;;
esac
((CONNECT_TIMEOUT_SECONDS >= 1 && CONNECT_TIMEOUT_SECONDS <= 30)) || fail "CONNECT_TIMEOUT_SECONDS must be between 1 and 30"
((REQUEST_TIMEOUT_SECONDS >= 1 && REQUEST_TIMEOUT_SECONDS <= 120)) || fail "REQUEST_TIMEOUT_SECONDS must be between 1 and 120"

headers="$(mktemp)"
body="$(mktemp)"
trap 'rm -f "$headers" "$body"' EXIT

if ! status="$(curl -sS \
  --connect-timeout "$CONNECT_TIMEOUT_SECONDS" \
  --max-time "$REQUEST_TIMEOUT_SECONDS" \
  -D "$headers" \
  -o "$body" \
  -w '%{http_code}' \
  "$API_VERSION_URL")"; then
  fail "API version readback request failed"
fi
[[ "$status" == "200" ]] || fail "API version readback returned HTTP $status"

actual_header="$(awk '
  tolower($1) == "x-weltgewebe-api-build:" {
    sub(/^[^:]+:[[:space:]]*/, "")
    gsub(/[[:space:]]+$/, "")
    print
    exit
  }
' "$headers")"
[[ -n "$actual_header" ]] || fail "X-Weltgewebe-API-Build header is missing"
[[ "$actual_header" == "$EXPECTED_COMMIT" ]] || fail "API build header mismatch: expected $EXPECTED_COMMIT, got $actual_header"

python3 - "$body" "$EXPECTED_COMMIT" "$EXPECTED_BUILD_TIMESTAMP" << 'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected_commit = sys.argv[2]
expected_timestamp = sys.argv[3]
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    raise SystemExit(f"ERROR: API version body is not valid JSON: {exc}")
if not isinstance(payload, dict):
    raise SystemExit("ERROR: API version body must be a JSON object")
version = payload.get("version")
commit = payload.get("commit")
build_timestamp = payload.get("build_timestamp")
if not isinstance(version, str) or not version.strip():
    raise SystemExit("ERROR: API version body has no non-empty version")
if commit != expected_commit:
    raise SystemExit(
        f"ERROR: API commit mismatch: expected {expected_commit}, got {commit!r}"
    )
if build_timestamp != expected_timestamp:
    raise SystemExit(
        "ERROR: API build timestamp mismatch: "
        f"expected {expected_timestamp}, got {build_timestamp!r}"
    )
if commit == "unknown" or build_timestamp == "unknown":
    raise SystemExit("ERROR: API release identity must not contain unknown values")
PY

printf 'api_release_identity=ok commit=%s build_timestamp=%s header=%s\n' \
  "$EXPECTED_COMMIT" "$EXPECTED_BUILD_TIMESTAMP" "$actual_header"
