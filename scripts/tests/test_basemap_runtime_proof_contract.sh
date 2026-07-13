#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." > /dev/null 2>&1 && pwd)"
GUARD="${REPO_ROOT}/scripts/guard/basemap-runtime-proof.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

mkdir -p "${TMP_DIR}/bin"
printf 'PMTiles' > "${TMP_DIR}/fixture.pmtiles"
EXPECTED_SHA256="$(sha256sum "${TMP_DIR}/fixture.pmtiles" | awk '{print $1}')"

cat > "${TMP_DIR}/bin/curl" <<'PY'
#!/usr/bin/python3
import os
import pathlib
import sys

args = sys.argv[1:]

def value_after(flag: str) -> str | None:
    try:
        return args[args.index(flag) + 1]
    except (ValueError, IndexError):
        return None

output = value_after("--output")
dump_header = value_after("--dump-header")
is_head = "--head" in args
range_value = value_after("--range")
header_value = value_after("--header")
omit_content_type = os.environ.get("FAKE_CURL_OMIT_CONTENT_TYPE") == "1"

if range_value == "0-6":
    if output:
        pathlib.Path(output).write_bytes(b"PMTiles")
    sys.stdout.write("206")
    raise SystemExit(0)

if is_head:
    lines = ["HTTP/1.1 200 OK"]
    if not omit_content_type:
        lines.append("Content-Type: application/octet-stream")
    lines.extend(["Accept-Ranges: bytes", "Content-Length: 7", ""])
    if dump_header:
        pathlib.Path(dump_header).write_text("\r\n".join(lines) + "\r\n")
    sys.stdout.write("200")
    raise SystemExit(0)

if header_value == "Range: bytes=0-511":
    lines = ["HTTP/1.1 206 Partial Content"]
    if not omit_content_type:
        lines.append("Content-Type: application/octet-stream")
    lines.extend(
        [
            "Accept-Ranges: bytes",
            "Content-Range: bytes 0-511/1024",
            "Content-Length: 512",
            "",
        ]
    )
    if dump_header:
        pathlib.Path(dump_header).write_text("\r\n".join(lines) + "\r\n")
    if output and output != "/dev/null":
        pathlib.Path(output).write_bytes(b"\0" * 512)
    sys.stdout.write("206")
    raise SystemExit(0)

raise SystemExit("unexpected fake curl arguments: " + repr(args))
PY
chmod +x "${TMP_DIR}/bin/curl"

COMMON_ENV=(
  "PATH=${TMP_DIR}/bin:${PATH}"
  "BASEMAP_PROOF_MODE=require"
  "BASEMAP_PROOF_SCOPE=pmtiles-content"
  "BASEMAP_CADDY_URL=http://proof.invalid"
  "BASEMAP_ENDPOINT_PATH=/local-basemap/fixture.pmtiles"
  "BASEMAP_PMTILES_PATH=${TMP_DIR}/fixture.pmtiles"
  "BASEMAP_EXPECTED_SHA256=${EXPECTED_SHA256}"
)

env "${COMMON_ENV[@]}" "${GUARD}" > "${TMP_DIR}/success.out" 2>&1
grep -Fq "Content-Type: application/octet-stream (full and Range confirmed)" "${TMP_DIR}/success.out"
grep -Fq "PROVEN: Caddy PMTiles content verified" "${TMP_DIR}/success.out"

if env "${COMMON_ENV[@]}" FAKE_CURL_OMIT_CONTENT_TYPE=1 "${GUARD}" \
  > "${TMP_DIR}/missing.out" 2>&1; then
  printf 'expected missing Content-Type to fail\n' >&2
  exit 1
fi
grep -Fq "PMTiles HEAD Content-Type is <missing>" "${TMP_DIR}/missing.out"

printf 'basemap runtime proof representation contract tests passed\n'
