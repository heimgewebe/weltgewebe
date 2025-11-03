#!/usr/bin/env bash
set -euo pipefail

# Installer/Pinner for astral-sh/uv releases
# Usage: scripts/tools/uv-pin.sh ensure [<version>]
# Default version: 0.8.0 (matches toolchain.versions.yml)

CMD="${1:-ensure}"
REQ_VER="${2:-${UV_VERSION:-0.8.0}}"
BIN_DIR="${HOME}/.local/bin"
BIN="${BIN_DIR}/uv"

ensure_path() {
  mkdir -p "${BIN_DIR}"
  case ":$PATH:" in
    *":${BIN_DIR}:"*) ;;
    *)
      export PATH="${BIN_DIR}:${PATH}"
      echo "${BIN_DIR}" >> "${GITHUB_PATH:-/dev/null}" 2>/dev/null || true
      ;;
  esac
}

extract_uv_version() {
  local binary="$1"
  local output=""

  if output="$(LC_ALL=C "${binary}" -V 2>/dev/null)"; then
    :
  elif output="$(LC_ALL=C "${binary}" --help 2>/dev/null | head -n1)"; then
    :
  elif output="$(LC_ALL=C "${binary}" --version 2>/dev/null)"; then
    :
  else
    return 1
  fi

  local version=""

  version="$(LC_ALL=C awk '{print $2}' <<<"${output}" | LC_ALL=C grep -Eo '^[0-9]+(\.[0-9]+)*' || true)"
  if [[ -z "${version}" ]]; then
    version="$(LC_ALL=C grep -Eo '[0-9]+(\.[0-9]+)*' <<<"${output}" | head -n1 || true)"
  fi
  if [[ -z "${version}" ]]; then
    return 1
  fi

  printf '%s\n' "${version}"
}

current_version() {
  if command -v uv >/dev/null 2>&1; then
    if extract_uv_version "uv"; then
      return 0
    fi
  elif [[ -x "${BIN}" ]]; then
    if extract_uv_version "${BIN}"; then
      return 0
    fi
  fi

  echo ""
}

detect_target() {
  local uname_s uname_m triple
  uname_s="$(uname -s)"
  uname_m="$(uname -m)"

  case "${uname_s}" in
    Linux)
      case "${uname_m}" in
        x86_64) triple="x86_64-unknown-linux-gnu" ;;
        aarch64|arm64) triple="aarch64-unknown-linux-gnu" ;;
        *) echo "unsupported architecture for uv on Linux: ${uname_m}" >&2; exit 1 ;;
      esac
      ;;
    Darwin)
      case "${uname_m}" in
        x86_64) triple="x86_64-apple-darwin" ;;
        arm64) triple="aarch64-apple-darwin" ;;
        *) echo "unsupported architecture for uv on macOS: ${uname_m}" >&2; exit 1 ;;
      esac
      ;;
    *)
      echo "unsupported operating system for uv: ${uname_s}" >&2
      exit 1
      ;;
  esac

  printf '%s' "${triple}"
}

curl_has_retry_all_errors() {
  local help
  if help="$(curl --help all 2>/dev/null)"; then
    :
  else
    help="$(curl --help 2>/dev/null || true)"
  fi
  [[ -n "${help}" ]] && grep -q -- '--retry-all-errors' <<<"${help}"
}

curl_fetch() {
  local url="$1"
  shift
  local -a curl_common curl_retry
  curl_common=(-fsS --proto '=https' --tlsv1.2)
  curl_retry=(--retry 3 --retry-delay 2)
  if curl_has_retry_all_errors; then
    curl_retry+=(--retry-all-errors)
  fi
  curl "${curl_common[@]}" "${curl_retry[@]}" "$@" "${url}"
}

download_uv() {
  local ver="$1"
  local triple asset url tmpdir="" tarball checksum_file extracted

  triple="$(detect_target)"
  asset="uv-${triple}.tar.gz"
  url="https://github.com/astral-sh/uv/releases/download/v${ver}/${asset}"

  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install uv" >&2
    exit 1
  fi
  if ! command -v tar >/dev/null 2>&1; then
    echo "tar is required to extract uv" >&2
    exit 1
  fi
  if ! command -v sha256sum >/dev/null 2>&1; then
    echo "sha256sum is required to verify uv downloads" >&2
    exit 1
  fi

  tmpdir="$(mktemp -d)"
  trap 'rm -rf "${tmpdir:-}"' EXIT INT TERM

  tarball="${tmpdir}/${asset}"
  checksum_file="${tmpdir}/SHA256SUMS"

  echo "Downloading uv v${ver} (${asset})"
  curl_fetch "${url}" -L -o "${tarball}"
  curl_fetch "https://github.com/astral-sh/uv/releases/download/v${ver}/SHA256SUMS" -L -o "${checksum_file}"

  if ! grep " ${asset}" "${checksum_file}" | sha256sum -c -; then
    echo "uv checksum verification failed for ${asset}" >&2
    exit 1
  fi

  extracted="${tmpdir}/uv"
  tar -xzf "${tarball}" -C "${tmpdir}" uv

  if command -v install >/dev/null 2>&1; then
    install -m 0755 "${extracted}" "${BIN}"
  else
    chmod 0755 "${extracted}"
    mv "${extracted}" "${BIN}"
  fi

  echo "✓ Installed uv v${ver} → ${BIN}" >&2
  rm -rf "${tmpdir:-}" || true
  trap - EXIT INT TERM
}

case "${CMD}" in
  ensure)
    ensure_path
    CUR="$(current_version)"
    if [[ "${CUR}" != "${REQ_VER}" ]]; then
      echo "uv: want v${REQ_VER}, have '${CUR:-none}'. Installing…"
      download_uv "${REQ_VER}"
    else
      echo "uv: found desired version v${CUR}"
    fi
    ;;
  *)
    echo "unknown command: ${CMD}" >&2
    echo "usage: $0 ensure [<version>]" >&2
    exit 1
    ;;
esac
