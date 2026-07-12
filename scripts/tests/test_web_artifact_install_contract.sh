#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" > /dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
INSTALL_SCRIPT="$REPO_ROOT/scripts/ops/install-web-artifact.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

artifact_src="$TEMP_DIR/artifact"
mkdir -p "$artifact_src/_app"
cat > "$artifact_src/index.html" << 'HTML'
<!doctype html><html><body><script type="module" src="/_app/app.js"></script></body></html>
HTML
cat > "$artifact_src/_app/version.json" << 'JSON'
{"version":"abc1234","build_id":"abc1234-build","commit":"abc1234"}
JSON

archive="$TEMP_DIR/web.tar.gz"
tar -C "$artifact_src" -czf "$archive" .
sha="$(sha256sum "$archive" | awk '{print $1}')"

MOCK_BIN="$TEMP_DIR/bin"
mkdir -p "$MOCK_BIN"
curl_counter="$TEMP_DIR/curl-count"
curl_args_log="$TEMP_DIR/curl-args"
cat > "$MOCK_BIN/curl" << CURLMOCK
#!/usr/bin/env bash
set -euo pipefail
printf '%q ' "\$@" >> "$curl_args_log"
printf '\n' >> "$curl_args_log"
headers=""
out=""
while [ "\$#" -gt 0 ]; do
  case "\$1" in
    -D)
      headers="\$2"
      shift 2
      ;;
    -o)
      out="\$2"
      shift 2
      ;;
    --connect-timeout | --max-time)
      shift 2
      ;;
    -*)
      shift
      ;;
    *)
      shift
      ;;
  esac
done
count=0
if [[ -f "$curl_counter" ]]; then read -r count < "$curl_counter"; fi
count=\$((count + 1))
printf '%s\n' "\$count" > "$curl_counter"
if [[ "\$count" -eq 1 ]]; then
  printf 'HTTP/2 200\r\ncache-control: no-store\r\nx-weltgewebe-build: old-build\r\n\r\n' > "\$headers"
  printf '{"version":"old-build","commit":"old-build"}\n' > "\$out"
else
  # Deliberate trailing horizontal whitespace before CR proves robust trimming.
  printf 'HTTP/2 200\r\ncache-control: no-store\r\nx-weltgewebe-build: abc1234 \t\r\n\r\n' > "\$headers"
  cat "$artifact_src/_app/version.json" > "\$out"
fi
CURLMOCK
chmod +x "$MOCK_BIN/curl"

reload_counter="$TEMP_DIR/reload-count"
cat > "$MOCK_BIN/reload" << RELOADMOCK
#!/usr/bin/env bash
set -euo pipefail
count=0
if [[ -f "$reload_counter" ]]; then read -r count < "$reload_counter"; fi
printf '%s\n' "\$((count + 1))" > "$reload_counter"
RELOADMOCK
chmod +x "$MOCK_BIN/reload"

release_dir="$TEMP_DIR/releases"
web_root="$TEMP_DIR/current"
common_env=(
  REPO_DIR="$REPO_ROOT"
  WEB_ARTIFACT_ARCHIVE="$archive"
  WEB_ARTIFACT_SHA256="$sha"
  WEB_ARTIFACT_VERSION=abc1234
  WEB_ARTIFACT_COMMIT=abc1234
  WEB_ROOT="$web_root"
  WEB_RELEASES_DIR="$release_dir"
  PUBLIC_VERSION_URL=https://example.invalid/_app/version.json
  CADDY_VALIDATE_CMD=true
  CADDY_RELOAD_CMD="$MOCK_BIN/reload"
  PUBLIC_READBACK_ATTEMPTS=3
  PUBLIC_READBACK_TOTAL_SECONDS=5
  PUBLIC_READBACK_INTERVAL_SECONDS=0
  PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS=2
  PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS=3
)

first_output="$TEMP_DIR/first-output"
first_error="$TEMP_DIR/first-error"
env PATH="$MOCK_BIN:$PATH" "${common_env[@]}" bash "$INSTALL_SCRIPT" > "$first_output" 2> "$first_error"

test -L "$web_root"
test -f "$(readlink "$web_root")/index.html"
test "$(cat "$reload_counter")" -eq 1
test "$(cat "$curl_counter")" -eq 2
grep -q -- '--connect-timeout 2' "$curl_args_log"
grep -q -- '--max-time 3' "$curl_args_log"
grep -q 'version-mismatch' "$first_error"
grep -q 'converged after 2 attempt(s)' "$first_output"

# Reinstalling the exact active artifact is idempotent and does not recreate Caddy.
idempotent_output="$TEMP_DIR/idempotent-output"
env PATH="$MOCK_BIN:$PATH" "${common_env[@]}" bash "$INSTALL_SCRIPT" > "$idempotent_output"
test "$(cat "$reload_counter")" -eq 1
grep -q 'verified idempotently' "$idempotent_output"

BAD_BIN="$TEMP_DIR/bad-bin"
mkdir -p "$BAD_BIN"
cat > "$BAD_BIN/curl" << 'BADCURL'
#!/usr/bin/env bash
set -euo pipefail
headers=""
out=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -D) headers="$2"; shift 2 ;;
    -o) out="$2"; shift 2 ;;
    --connect-timeout | --max-time) shift 2 ;;
    -*) shift ;;
    *) shift ;;
  esac
done
printf 'HTTP/1.1 200 OK\r\nCache-Control: no-store\r\nX-Weltgewebe-Build: wrong\r\n\r\n' > "$headers"
printf '{"version":"wrong","commit":"wrong"}\n' > "$out"
BADCURL
chmod +x "$BAD_BIN/curl"

# A failed verification of an already active, reused release must preserve it.
if env PATH="$BAD_BIN:$PATH" "${common_env[@]}" \
  PUBLIC_READBACK_ATTEMPTS=2 PUBLIC_READBACK_TOTAL_SECONDS=2 \
  PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS=1 PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS=1 \
  bash "$INSTALL_SCRIPT" > /dev/null 2>&1; then
  echo "active reused release verification should fail on a wrong public readback" >&2
  exit 1
fi
test -L "$web_root"
test -d "$release_dir/abc1234-abc1234-build"
test "$(cat "$reload_counter")" -eq 1

# A pre-existing real build directory must be preserved as the rollback source.
rollback_root="$TEMP_DIR/rollback-current"
rollback_releases="$TEMP_DIR/rollback-releases"
mkdir -p "$rollback_root"
printf 'old production build\n' > "$rollback_root/old-sentinel"
if env PATH="$BAD_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256="$sha" \
  WEB_ARTIFACT_VERSION=abc1234 \
  WEB_ARTIFACT_COMMIT=abc1234 \
  WEB_ROOT="$rollback_root" \
  WEB_RELEASES_DIR="$rollback_releases" \
  PUBLIC_VERSION_URL=https://example.invalid/_app/version.json \
  CADDY_VALIDATE_CMD=true \
  CADDY_RELOAD_CMD=true \
  PUBLIC_READBACK_ATTEMPTS=2 \
  PUBLIC_READBACK_TOTAL_SECONDS=2 \
  PUBLIC_READBACK_INTERVAL_SECONDS=0 \
  PUBLIC_READBACK_CONNECT_TIMEOUT_SECONDS=1 \
  PUBLIC_READBACK_REQUEST_TIMEOUT_SECONDS=1 \
  bash "$INSTALL_SCRIPT" > /dev/null 2>&1; then
  echo "installer should fail on public readback mismatch" >&2
  exit 1
fi
test -d "$rollback_root"
test ! -L "$rollback_root"
test -f "$rollback_root/old-sentinel"
test ! -d "$rollback_releases/abc1234-abc1234-build"

# A validation failure occurs before the switch and must remove only the release
# created by that run so an exact retry remains possible.
validation_root="$TEMP_DIR/validation-current"
validation_releases="$TEMP_DIR/validation-releases"
mkdir -p "$validation_root"
printf 'old validation build\n' > "$validation_root/old-sentinel"
if env PATH="$MOCK_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256="$sha" \
  WEB_ARTIFACT_VERSION=abc1234 \
  WEB_ARTIFACT_COMMIT=abc1234 \
  WEB_ROOT="$validation_root" \
  WEB_RELEASES_DIR="$validation_releases" \
  PUBLIC_VERSION_URL=https://example.invalid/_app/version.json \
  CADDY_VALIDATE_CMD=false \
  CADDY_RELOAD_CMD=true \
  bash "$INSTALL_SCRIPT" > /dev/null 2>&1; then
  echo "installer should fail when Caddy validation fails" >&2
  exit 1
fi
test -d "$validation_root"
test -f "$validation_root/old-sentinel"
test ! -d "$validation_releases/abc1234-abc1234-build"

# A Caddy recreate failure occurs after the switch. It must restore the previous
# real directory and remove only the newly created release.
reload_fail_root="$TEMP_DIR/reload-fail-current"
reload_fail_releases="$TEMP_DIR/reload-fail-releases"
mkdir -p "$reload_fail_root"
printf 'old reload build\n' > "$reload_fail_root/old-sentinel"
if env PATH="$MOCK_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256="$sha" \
  WEB_ARTIFACT_VERSION=abc1234 \
  WEB_ARTIFACT_COMMIT=abc1234 \
  WEB_ROOT="$reload_fail_root" \
  WEB_RELEASES_DIR="$reload_fail_releases" \
  PUBLIC_VERSION_URL=https://example.invalid/_app/version.json \
  CADDY_VALIDATE_CMD=true \
  CADDY_RELOAD_CMD=false \
  bash "$INSTALL_SCRIPT" > /dev/null 2>&1; then
  echo "installer should fail when Caddy recreation fails" >&2
  exit 1
fi
test -d "$reload_fail_root"
test ! -L "$reload_fail_root"
test -f "$reload_fail_root/old-sentinel"
test ! -d "$reload_fail_releases/abc1234-abc1234-build"

# A held host-wide lock must reject a concurrent install before staging or switching.
lock_releases="$TEMP_DIR/lock-releases"
lock_root="$TEMP_DIR/lock-current"
mkdir -p "$lock_releases"
exec 8> "$lock_releases/.install.lock"
flock -n 8
if env PATH="$MOCK_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256="$sha" \
  WEB_ARTIFACT_VERSION=abc1234 \
  WEB_ARTIFACT_COMMIT=abc1234 \
  WEB_ROOT="$lock_root" \
  WEB_RELEASES_DIR="$lock_releases" \
  PUBLIC_VERSION_URL=https://example.invalid/_app/version.json \
  CADDY_VALIDATE_CMD=true \
  CADDY_RELOAD_CMD=true \
  WEB_INSTALL_LOCK_WAIT_SECONDS=0 \
  bash "$INSTALL_SCRIPT" > /dev/null 2>&1; then
  echo "concurrent installer should fail while the deployment lock is held" >&2
  exit 1
fi
flock -u 8
exec 8>&-
test ! -e "$lock_root"
test ! -L "$lock_root"
test -z "$(find "$lock_releases" -maxdepth 1 -type d -name '.stage.*' -print -quit)"

if env PATH="$MOCK_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256=bad \
  WEB_ARTIFACT_VERSION=abc1234 \
  WEB_ARTIFACT_COMMIT=abc1234 \
  WEB_ROOT="$TEMP_DIR/other-current" \
  WEB_RELEASES_DIR="$TEMP_DIR/other-releases" \
  PUBLIC_VERSION_URL=https://example.invalid/_app/version.json \
  CADDY_VALIDATE_CMD=true \
  CADDY_RELOAD_CMD=true \
  bash "$INSTALL_SCRIPT" > /dev/null 2>&1; then
  echo "installer should fail on sha mismatch" >&2
  exit 1
fi

git -C "$REPO_ROOT" check-ignore -q apps/web/releases/runtime-release

echo "PASS: web artifact install contract"
