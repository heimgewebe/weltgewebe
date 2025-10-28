#!/usr/bin/env bash
set -euo pipefail

# Minimaler Installer/Pinner für mikefarah/yq v4.x
# Usage: scripts/tools/yq-pin.sh ensure [<version>]
# Default: 4.44.0

CMD="${1:-ensure}"
REQ_VER="${2:-${YQ_VERSION:-4.44.0}}"
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
  local os
  local arch
  local sys

  sys="$(uname | tr '[:upper:]' '[:lower:]')"
  case "${sys}" in
    linux|darwin)
      os="${sys}"
      ;;
    *)
      echo "unsupported operating system for yq: ${sys}" >&2
      exit 1
      ;;
  esac

  arch="$(uname -m)"
  case "${arch}" in
    x86_64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)
      echo "unsupported architecture for yq: ${arch}" >&2
      exit 1
      ;;
  esac

  local base="yq_${os}_${arch}"
  local url_base="https://github.com/mikefarah/yq/releases/download/v${ver}"
  local asset=""
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' EXIT INT TERM

  # tool prerequisites
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl is required to install yq" >&2
    exit 1
  fi
  if ! command -v sha256sum >/dev/null 2>&1; then
    echo "sha256sum is required to verify yq downloads" >&2
    exit 1
  fi

  # pick asset (plain binary or tarball)
  local -a curl_common curl_retry
  local curl_help=""
  curl_common=(-fsS --proto '=https' --tlsv1.2)
  curl_retry=(--retry 3 --retry-delay 2)
  if ! curl_help="$(curl --help all 2>/dev/null)"; then
    curl_help="$(curl --help 2>/dev/null || true)"
  fi
  if [[ -n "${curl_help}" ]] && grep -q -- '--retry-all-errors' <<<"${curl_help}"; then
    curl_retry+=(--retry-all-errors)
  fi

  if curl "${curl_common[@]}" "${curl_retry[@]}" -I "${url_base}/${base}" >/dev/null; then
    asset="${base}"
  elif curl "${curl_common[@]}" "${curl_retry[@]}" -I "${url_base}/${base}.tar.gz" >/dev/null; then
    asset="${base}.tar.gz"
  else
    echo "yq asset not found at ${url_base}/${base}{,.tar.gz}" >&2
    exit 1
  fi

  if [[ "${asset}" == *.tar.gz ]] && ! command -v tar >/dev/null 2>&1; then
    echo "tar is required to extract yq archives" >&2
    exit 1
  fi

  local asset_path="${tmp_dir}/${asset##*/}"
  local sha_path="${asset_path}.sha256"

  echo "Downloading yq v${ver} from: ${url_base}/${asset}"
  curl "${curl_common[@]}" "${curl_retry[@]}" -L "${url_base}/${asset}" -o "${asset_path}"
  curl "${curl_common[@]}" "${curl_retry[@]}" -L "${url_base}/${asset}.sha256" -o "${sha_path}"

  local expected actual
  expected="$(awk '{print $1}' "${sha_path}")"
  if [[ -z "${expected}" ]]; then
    echo "empty checksum file: ${sha_path}" >&2
    exit 1
  fi
  actual="$(sha256sum "${asset_path}" | awk '{print $1}')"
  if [[ "${expected}" != "${actual}" ]]; then
    echo "yq checksum mismatch: expected ${expected}, got ${actual}" >&2
    exit 1
  fi

  # Zielpfad der extrahierten/geladenen Binary im Tmp-Verzeichnis
  local extracted="${tmp_dir}/${base}"
  if [[ "${asset}" == *.tar.gz ]]; then
    # Archivfall: entpacken erzeugt ${base}
    tar -xzf "${asset_path}" -C "${tmp_dir}"
  else
    # Standalone-Binary: vermeide mv auf sich selbst unter set -euo pipefail
    if [[ "${asset_path}" != "${extracted}" ]]; then
      # in seltenen Fällen, falls die Namen differieren, kopieren wir explizit
      cp -f "${asset_path}" "${extracted}"
    else
      # identischer Pfad – wir verwenden den bereits geladenen Pfad direkt
      extracted="${asset_path}"
    fi
  fi

  if [[ ! -f "${extracted}" ]]; then
    echo "yq binary not found after extracting ${asset}" >&2
    exit 1
  fi

  # install atomically if possible
  if command -v install >/dev/null 2>&1; then
    install -m 0755 "${extracted}" "${BIN}"
  else
    chmod 0755 "${extracted}"
    mv "${extracted}" "${BIN}"
  fi

  echo "✓ Installed yq v${ver} → ${BIN}" >&2
  rm -rf "${tmp_dir}"
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
