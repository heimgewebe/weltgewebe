#!/usr/bin/env bash
set -euo pipefail

# Minimaler Installer/Pinner für mikefarah/yq v4.x
# Usage: scripts/tools/yq-pin.sh ensure [<version>]
# Default: 4.44.1

CMD="${1:-ensure}"
REQ_VER="${2:-4.44.1}"
BIN_DIR="${HOME}/.local/bin"
BIN="${BIN_DIR}/yq"

ensure_path() {
  mkdir -p "${BIN_DIR}"
  case ":$PATH:" in
    *":${BIN_DIR}:"*) ;;
    *) echo "${BIN_DIR}" >> "${GITHUB_PATH:-/dev/null}" 2>/dev/null || true ;;
  esac
}

current_version() {
  if command -v yq >/dev/null 2>&1; then
    yq --version | awk '{print $3}' || true
  elif [[ -x "${BIN}" ]]; then
    "${BIN}" --version | awk '{print $3}' || true
  else
    echo ""
  fi
}

download_yq() {
  local ver="$1"
  local os="linux"
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
  esac
  echo "yq-pin: detected architecture '${arch}'"
  local url="https://github.com/mikefarah/yq/releases/download/v${ver}/yq_${os}_${arch}"
  local tmp_bin
  local tmp_sha
  tmp_bin="$(mktemp)"
  tmp_sha="${tmp_bin}.sha256"
  echo "Downloading yq v${ver} from: ${url}"
  curl -fsSL "${url}" -o "${tmp_bin}"
  curl -fsSL "${url}.sha256" -o "${tmp_sha}"
  local expected
  local actual
  expected="$(awk '{print $1}' "${tmp_sha}")"
  actual="$(sha256sum "${tmp_bin}" | awk '{print $1}')"
  if [[ "${expected}" != "${actual}" ]]; then
    echo "yq checksum mismatch: expected ${expected}, got ${actual}" >&2
    rm -f "${tmp_bin}" "${tmp_sha}"
    exit 1
  fi
  chmod +x "${tmp_bin}"
  mv "${tmp_bin}" "${BIN}"
  rm -f "${tmp_sha}"
}

case "${CMD}" in
  ensure)
    ensure_path
    CUR="$(current_version)"
    if [[ "${CUR}" != "${REQ_VER}" ]]; then
      echo "yq: want v${REQ_VER}, have '${CUR:-none}'. Installing…"
      download_yq "${REQ_VER}"
    else
      echo "yq v${CUR} already present."
    fi
    ;;
  version)
    ensure_path
    current_version
    ;;
  *)
    echo "Usage: $0 ensure [<version>] | version" >&2
    exit 1
    ;;
esac
