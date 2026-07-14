#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERIFY="$REPO_ROOT/scripts/ops/verify-api-release-identity.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"

cat > "$TMP/bin/curl" << 'MOCK'
#!/usr/bin/env bash
set -euo pipefail
headers=""
body=""
while (($#)); do
  case "$1" in
    -D)
      headers="$2"
      shift 2
      ;;
    -o)
      body="$2"
      shift 2
      ;;
    --connect-timeout | --max-time | -w)
      shift 2
      ;;
    -sS)
      shift
      ;;
    *)
      shift
      ;;
  esac
done
printf 'called\n' >> "${MOCK_CALL_LOG:?}"
cp "${MOCK_HEADERS:?}" "$headers"
cp "${MOCK_BODY:?}" "$body"
printf '%s' "${MOCK_STATUS:-200}"
MOCK
chmod +x "$TMP/bin/curl"

commit="0123456789abcdef0123456789abcdef01234567"
web_build="old-web-build"
timestamp="2026-07-12T19:57:15+00:00"

write_good() {
  printf 'HTTP/2 200\r\nX-Weltgewebe-Build: %s\r\nX-Weltgewebe-API-Build: %s \t\r\n\r\n' \
    "$web_build" "$commit" > "$TMP/headers"
  printf '{"version":"0.1.0","commit":"%s","build_timestamp":"%s"}\n' "$commit" "$timestamp" > "$TMP/body"
  : > "$TMP/calls"
}

run_verify() {
  env \
    PATH="$TMP/bin:/usr/bin:/bin" \
    MOCK_HEADERS="$TMP/headers" \
    MOCK_BODY="$TMP/body" \
    MOCK_CALL_LOG="$TMP/calls" \
    MOCK_STATUS="${MOCK_STATUS:-200}" \
    API_VERSION_URL=https://example.invalid/api/version \
    EXPECTED_COMMIT="$commit" \
    EXPECTED_BUILD_TIMESTAMP="$timestamp" \
    bash "$VERIFY"
}

write_good
out="$(run_verify)"
grep -Fq 'api_release_identity=ok' <<< "$out"
[[ "$(wc -l < "$TMP/calls")" -eq 1 ]]
echo "PASS: exact body and header identity accepted"

write_good
sed -i 's/0123456789abcdef0123456789abcdef01234567/unknown/' "$TMP/body"
if run_verify > /dev/null 2>&1; then
  echo "unknown commit should fail" >&2
  exit 1
fi
echo "PASS: unknown API commit rejected"

write_good
sed -i 's/2026-07-12T19:57:15+00:00/2026-07-12T20:00:00+00:00/' "$TMP/body"
if run_verify > /dev/null 2>&1; then
  echo "timestamp mismatch should fail" >&2
  exit 1
fi
echo "PASS: timestamp mismatch rejected"

write_good
sed -i 's/0123456789abcdef0123456789abcdef01234567/89abcdef89abcdef89abcdef89abcdef89abcdef/' "$TMP/headers"
if run_verify > /dev/null 2>&1; then
  echo "header mismatch should fail" >&2
  exit 1
fi
echo "PASS: API build header mismatch rejected while web header stays independent"

write_good
printf '{not-json}\n' > "$TMP/body"
if run_verify > /dev/null 2>&1; then
  echo "invalid JSON should fail" >&2
  exit 1
fi
echo "PASS: invalid API version JSON rejected"

write_good
MOCK_STATUS=503
export MOCK_STATUS
if run_verify > /dev/null 2>&1; then
  echo "HTTP 503 should fail" >&2
  exit 1
fi
unset MOCK_STATUS
echo "PASS: non-200 readback rejected"

write_good
if env \
  PATH="$TMP/bin:/usr/bin:/bin" \
  MOCK_HEADERS="$TMP/headers" \
  MOCK_BODY="$TMP/body" \
  MOCK_CALL_LOG="$TMP/calls" \
  API_VERSION_URL=https://example.invalid/api/version \
  EXPECTED_COMMIT=short \
  EXPECTED_BUILD_TIMESTAMP="$timestamp" \
  bash "$VERIFY" > /dev/null 2>&1; then
  echo "invalid expected commit should fail" >&2
  exit 1
fi
[[ ! -s "$TMP/calls" ]]
echo "PASS: invalid expectations fail before network access"

echo "test_api_release_identity_contract: OK"
