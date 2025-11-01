#!/usr/bin/env bash
set -euo pipefail

# Minimaler Installer/Pinner für mikefarah/yq v4.x
# Usage: scripts/tools/yq-pin.sh ensure [<version>]
# Default: 4.47.2

CMD="${1:-ensure}"
REQ_VER="${2:-${YQ_VERSION:-4.47.2}}"
BIN_DIR="${HOME}/.local/bin"
BIN="${BIN_DIR}/yq"

ensure_path() {
  mkdir -p "${BIN_DIR}"
  case ":$PATH:" in
    *":${BIN_DIR}:"*) ;;
    *)
      if [[ -n "${GITHUB_PATH:-}" ]]; then
        echo "${BIN_DIR}" >> "${GITHUB_PATH}" 2>/dev/null || true
      fi
      ;;
  esac
}

parse_version() {
  local out ver
  if ! out="$("$@" --version 2>/dev/null)"; then
    echo ""
    return
  fi
  if ! ver="$(printf '%s\n' "${out}" | grep -Eo '[0-9]+(\.[0-9]+){1,3}' | head -n1)"; then
    ver=""
  fi
  printf '%s\n' "${ver}"
}

current_version() {
  if command -v yq >/dev/null 2>&1; then
    parse_version yq || true
  elif [[ -x "${BIN}" ]]; then
    parse_version "${BIN}" || true
  else
    echo ""
  fi
}

download_yq() {
  local ver="$1"
  local os arch sys
  sys="$(uname | tr '[:upper:]' '[:lower:]')"
  case "${sys}" in
    linux|darwin) os="${sys}" ;;
    *) echo "unsupported operating system for yq: ${sys}" >&2; exit 1 ;;
  esac

  arch="$(uname -m)"
  case "${arch}" in
    x86_64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) echo "unsupported architecture for yq: ${arch}" >&2; exit 1 ;;
  esac

  local base="yq_${os}_${arch}"
  local url_base="https://github.com/mikefarah/yq/releases/download/v${ver}"
  local asset="" tmp_dir=""

  echo "Target platform: ${os}/${arch}; requested yq v${ver}" >&2
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir:-}"' EXIT INT TERM

  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install yq" >&2
    exit 1
  fi

  local -a SHA256_CMD
  if command -v sha256sum >/dev/null 2>&1; then
    SHA256_CMD=(sha256sum)
  elif command -v shasum >/dev/null 2>&1; then
    SHA256_CMD=(shasum -a 256)
  else
    echo "no SHA256 tool found (need sha256sum or shasum)" >&2
    exit 1
  fi

  # Compose curl option groups mit Kompatibilitäts-Fallbacks
  local -a CURL_COMMON CURL_RETRY CURL_DOWNLOAD CURL_FAIL CURL_HEAD CURL_RANGE
  local curl_help=""
  CURL_COMMON=(-fsS --proto '=https' --tlsv1.2)
  CURL_COMMON+=(-A "heimgewebe-yq-pin/1.0")
  CURL_RETRY=(--retry 3 --retry-delay 2)
  CURL_DOWNLOAD=(-L --connect-timeout 10 --max-time 90)
  CURL_HEAD=(-I --connect-timeout 3 --max-time 10)
  CURL_RANGE=(--connect-timeout 5 --max-time 10 -H 'Range: bytes=0-0')

  if ! curl_help="$(curl --help all 2>/dev/null)"; then
    curl_help="$(curl --help 2>/dev/null || true)"
  fi
  if [[ -n "${curl_help}" ]]; then
    if grep -q -- '--retry-all-errors' <<<"${curl_help}"; then
      CURL_RETRY+=(--retry-all-errors)
    fi
    if grep -q -- '--retry-connrefused' <<<"${curl_help}"; then
      CURL_RETRY+=(--retry-connrefused)
    fi
  fi

  CURL_FAIL=(--fail)

  echo "Probing available yq assets at ${url_base}..." >&2
  if curl "${CURL_COMMON[@]}" "${CURL_RETRY[@]}" "${CURL_FAIL[@]}" "${CURL_HEAD[@]}" "${url_base}/${base}" >/dev/null; then
    asset="${base}"
  elif curl "${CURL_COMMON[@]}" "${CURL_RETRY[@]}" "${CURL_FAIL[@]}" "${CURL_HEAD[@]}" "${url_base}/${base}.tar.gz" >/dev/null; then
    asset="${base}.tar.gz"
  else
    echo "HEAD probe failed, retrying with Range 0-0…" >&2
    # Fallback für Server, die HEAD-Anfragen blockieren (Range 0-0 vermeidet vollen Download)
    if curl "${CURL_COMMON[@]}" "${CURL_RETRY[@]}" "${CURL_FAIL[@]}" "${CURL_RANGE[@]}" "${url_base}/${base}" >/dev/null; then
      asset="${base}"
    elif curl "${CURL_COMMON[@]}" "${CURL_RETRY[@]}" "${CURL_FAIL[@]}" "${CURL_RANGE[@]}" "${url_base}/${base}.tar.gz" >/dev/null; then
      asset="${base}.tar.gz"
    else
      echo "no yq asset for ${os}/${arch} v${ver} at ${url_base}" >&2
      exit 1
    fi
  fi

  if [[ "${asset}" == *.tar.gz ]]; then
    echo "Found yq archive asset: ${asset}"
  else
    echo "Found yq binary asset: ${asset}"
  fi

  if [[ "${asset}" == *.tar.gz ]] && ! command -v tar >/dev/null 2>&1; then
    echo "tar is required to extract yq archives" >&2
    exit 1
  fi

  local asset_path="${tmp_dir}/${asset##*/}"
  local sha_path="${asset_path}.sha256"

  echo "Downloading yq v${ver} from ${url_base}/${asset}"
  curl "${CURL_COMMON[@]}" "${CURL_RETRY[@]}" "${CURL_DOWNLOAD[@]}" "${CURL_FAIL[@]}" "${url_base}/${asset}" -o "${asset_path}"
  curl "${CURL_COMMON[@]}" "${CURL_RETRY[@]}" "${CURL_DOWNLOAD[@]}" "${CURL_FAIL[@]}" "${url_base}/${asset}.sha256" -o "${sha_path}"

  if [[ ! -s "${sha_path}" ]]; then
    echo "missing yq sha256 file at ${sha_path}" >&2
    exit 1
  fi

  local expected actual asset_name expected_line line
  asset_name="${asset##*/}"
  expected_line=""

  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ -z "${line}" ]] && continue
    [[ -z "${expected_line}" ]] && expected_line="${line}"
    case "${line}" in
      *" ${asset_name}"|*"*${asset_name}") expected_line="${line}"; break ;;
    esac
  done < "${sha_path}"

  if [[ -z "${expected_line}" ]]; then
    echo "no checksum entry found for ${asset_name} in ${sha_path}" >&2
    exit 1
  fi

  if command -v awk >/dev/null 2>&1; then
    expected="$(printf '%s\n' "${expected_line}" | awk '{print $1}')"
    actual="$(${SHA256_CMD[@]} "${asset_path}" | awk '{print $1}')"
  else
    expected="$(printf '%s\n' "${expected_line}" | cut -d' ' -f1)"
    actual="$(${SHA256_CMD[@]} "${asset_path}" | cut -d' ' -f1)"
  fi

  if [[ "${expected}" != "${actual}" ]]; then
    echo "yq checksum mismatch: expected ${expected}, got ${actual}" >&2
    exit 1
  fi

  local extracted="${tmp_dir}/${base}"
  if [[ "${asset}" == *.tar.gz ]]; then
    tar -xzf "${asset_path}" -C "${tmp_dir}" || { echo "failed to extract yq archive" >&2; exit 1; }
  else
    [[ "${asset_path}" != "${extracted}" ]] && cp -f "${asset_path}" "${extracted}"
  fi
  [[ -f "${extracted}" ]] || { echo "yq binary not found after extraction" >&2; exit 1; }

  if ! command -v install >/dev/null 2>&1; then
    echo "install not found; falling back to mv" >&2
  fi

  install -m 0755 "${extracted}" "${BIN}" 2>/dev/null || {
    chmod 0755 "${extracted}"
    mv -f "${extracted}" "${BIN}"
  }

  hash -r 2>/dev/null || true
  local installed_ver
  installed_ver="$(parse_version "${BIN}")"
  if [[ -z "${installed_ver}" ]]; then
    echo "failed to detect installed yq version" >&2
    exit 1
  fi
  if [[ "${installed_ver}" != "${ver}" ]]; then
    echo "installed yq version ${installed_ver} does not match requested ${ver}" >&2
    exit 1
  fi

  echo "✅ yq v${installed_ver} downloaded & verified"

  if [[ "${os}" == "darwin" ]] && [[ ":$PATH:" != *":${BIN_DIR}:"* ]]; then
    cat >&2 <<EOF
Note: ${BIN_DIR} is not currently in your PATH on macOS.
Add the following to your shell profile:
  export PATH="${BIN_DIR}:\$PATH"
EOF
  fi

  rm -rf "${tmp_dir}" 2>/dev/null || true
  trap - EXIT INT TERM
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
