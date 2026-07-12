#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
INSTALL_SCRIPT="$REPO_ROOT/scripts/ops/install-web-artifact.sh"

TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

artifact_src="$TEMP_DIR/artifact"
mkdir -p "$artifact_src/_app"
cat >"$artifact_src/index.html" <<'HTML'
<!doctype html><html><body><script type="module" src="/_app/app.js"></script></body></html>
HTML
cat >"$artifact_src/_app/version.json" <<'JSON'
{"version":"abc1234","build_id":"abc1234-build","commit":"abc1234"}
JSON

archive="$TEMP_DIR/web.tar.gz"
tar -C "$artifact_src" -czf "$archive" .
sha="$(sha256sum "$archive" | awk '{print $1}')"

MOCK_BIN="$TEMP_DIR/bin"
mkdir -p "$MOCK_BIN"
cat >"$MOCK_BIN/curl" <<SH
#!/usr/bin/env bash
set -euo pipefail
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
    -*)
      shift
      ;;
    *)
      shift
      ;;
  esac
done
printf 'HTTP/1.1 200 OK\r\nCache-Control: no-store\r\nX-Weltgewebe-Build: abc1234\r\n\r\n' > "\$headers"
cat "$artifact_src/_app/version.json" > "\$out"
SH
chmod +x "$MOCK_BIN/curl"

release_dir="$TEMP_DIR/releases"
web_root="$TEMP_DIR/current"
reload_marker="$TEMP_DIR/reloaded"

PATH="$MOCK_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256="$sha" \
  WEB_ARTIFACT_VERSION="abc1234" \
  WEB_ARTIFACT_COMMIT="abc1234" \
  WEB_ROOT="$web_root" \
  WEB_RELEASES_DIR="$release_dir" \
  PUBLIC_VERSION_URL="https://example.invalid/_app/version.json" \
  CADDY_VALIDATE_CMD="true" \
  CADDY_RELOAD_CMD="touch $reload_marker" \
  bash "$INSTALL_SCRIPT" >/dev/null

test -L "$web_root"
test -f "$(readlink "$web_root")/index.html"
test -f "$reload_marker"


# A pre-existing real build directory must be preserved as the rollback source.
rollback_root="$TEMP_DIR/rollback-current"
rollback_releases="$TEMP_DIR/rollback-releases"
mkdir -p "$rollback_root"
printf 'old production build\n' >"$rollback_root/old-sentinel"
BAD_BIN="$TEMP_DIR/bad-bin"
mkdir -p "$BAD_BIN"
cat >"$BAD_BIN/curl" <<SH
#!/usr/bin/env bash
set -euo pipefail
headers=""
out=""
while [ "\$#" -gt 0 ]; do
  case "\$1" in
    -D) headers="\$2"; shift 2 ;;
    -o) out="\$2"; shift 2 ;;
    -*) shift ;;
    *) shift ;;
  esac
done
printf 'HTTP/1.1 200 OK\r\nCache-Control: no-store\r\nX-Weltgewebe-Build: wrong\r\n\r\n' >"\$headers"
printf '{"version":"wrong","commit":"wrong"}\n' >"\$out"
SH
chmod +x "$BAD_BIN/curl"
if PATH="$BAD_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256="$sha" \
  WEB_ARTIFACT_VERSION="abc1234" \
  WEB_ARTIFACT_COMMIT="abc1234" \
  WEB_ROOT="$rollback_root" \
  WEB_RELEASES_DIR="$rollback_releases" \
  PUBLIC_VERSION_URL="https://example.invalid/_app/version.json" \
  CADDY_VALIDATE_CMD="true" \
  CADDY_RELOAD_CMD="true" \
  bash "$INSTALL_SCRIPT" >/dev/null 2>&1; then
  echo "installer should fail on public readback mismatch" >&2
  exit 1
fi
test -d "$rollback_root"
test ! -L "$rollback_root"
test -f "$rollback_root/old-sentinel"

if PATH="$MOCK_BIN:$PATH" \
  REPO_DIR="$REPO_ROOT" \
  WEB_ARTIFACT_ARCHIVE="$archive" \
  WEB_ARTIFACT_SHA256="bad" \
  WEB_ARTIFACT_VERSION="abc1234" \
  WEB_ARTIFACT_COMMIT="abc1234" \
  WEB_ROOT="$TEMP_DIR/other-current" \
  WEB_RELEASES_DIR="$TEMP_DIR/other-releases" \
  PUBLIC_VERSION_URL="https://example.invalid/_app/version.json" \
  CADDY_VALIDATE_CMD="true" \
  CADDY_RELOAD_CMD="true" \
  bash "$INSTALL_SCRIPT" >/dev/null 2>&1; then
  echo "installer should fail on sha mismatch" >&2
  exit 1
fi

echo "PASS: web artifact install contract"
