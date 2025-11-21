#!/usr/bin/env bash
set -euo pipefail

# Installer/Pinner for astral-sh/uv releases
# Usage: scripts/tools/uv-pin.sh ensure [<version>]
# Default version: 0.9.11 (matches toolchain.versions.yml)

CMD="${1:-ensure}"
REQ_VER="${2:-${UV_VERSION:-0.9.11}}"
BIN_DIR="${HOME}/.local/bin"
BIN="${BIN_DIR}/uv"

ensure_path() {
    mkdir -p "${BIN_DIR}"
    case ":$PATH:" in
    *":${BIN_DIR}:"*) ;;
    *)
        export PATH="${BIN_DIR}:${PATH}"
        echo "${BIN_DIR}" >>"${GITHUB_PATH:-/dev/null}" 2>/dev/null || true
        ;;
    esac
}

# NOTE on version probing strategy (why -V / --help / --version):
# - Different uv releases and distro builds expose different flags:
#   * Newer uv supports `-V` (short) while some older/help-wrapped builds
#     only show the version on the first line of `--help`.
#   * A few package variants still respond to `--version`.
# - Some CI images wrap commands (e.g. via shims) that hide `-V`, but print a
#   canonical banner on `--help`.
# - We keep probing in the order: `-V` → `--help | head -n1` → `--version`.
#   Together with `LC_ALL=C` and a robust regex extraction this makes parsing
#   locale- and wrapper-safe without depending on a specific uv build flavor.
# - If all probes fail, the caller handles an empty string as “not installed”.
#
extract_uv_version() {
    local binary="$1"
    local output=""

    # Try short form first (preferred on modern uv).
    if output="$(LC_ALL=C "${binary}" -V 2>/dev/null)"; then
        :
    # Some packaged builds only expose the version in the first --help line.
    elif output="$(LC_ALL=C "${binary}" --help 2>/dev/null | head -n1)"; then
        :
    # Legacy/alternative flag still present in a few environments.
    elif output="$(LC_ALL=C "${binary}" --version 2>/dev/null)"; then
        :
    else
        return 1
    fi

    local version=""

    # First, try to extract the version as the second field of the output.
    # This works if the output is like: "uv X.Y.Z" or similar, where the version is the second word.
    version="$(LC_ALL=C awk '{print $2}' <<<"${output}" | LC_ALL=C grep -Eo '^[0-9]+(\.[0-9]+)*' || true)"
    if [[ -z "${version}" ]]; then
        # Fallback: search for a version-like pattern anywhere in the output.
        # This handles cases where the output format is unexpected or contains extra text before the version.
        version="$(LC_ALL=C grep -Eo '[0-9]+(\.[0-9]+)*' <<<"${output}" | head -n1 || true)"
    fi
    if [[ -z "${version}" ]]; then
        return 1
    fi

    printf '%s\n' "${version}"
}

current_version() {
    local v=""

    if command -v uv >/dev/null 2>&1; then
        v="$(extract_uv_version uv || true)"
    elif [[ -x "${BIN}" ]]; then
        v="$(extract_uv_version "${BIN}" || true)"
    fi

    [[ -n "${v}" ]] || {
        if [[ "${DEBUG:-0}" = 1 ]]; then
            echo "uv version not detected" >&2
        fi
    }

    printf '%s\n' "${v}"
}

detect_target() {
    local uname_s uname_m triple
    uname_s="$(uname -s)"
    uname_m="$(uname -m)"

    case "${uname_s}" in
    Linux)
        case "${uname_m}" in
        x86_64) triple="x86_64-unknown-linux-gnu" ;;
        aarch64 | arm64) triple="aarch64-unknown-linux-gnu" ;;
        *)
            echo "unsupported architecture for uv on Linux: ${uname_m}" >&2
            exit 1
            ;;
        esac
        ;;
    Darwin)
        case "${uname_m}" in
        x86_64) triple="x86_64-apple-darwin" ;;
        arm64) triple="aarch64-apple-darwin" ;;
        *)
            echo "unsupported architecture for uv on macOS: ${uname_m}" >&2
            exit 1
            ;;
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
    local triple asset url tmpdir="" tarball checksum_file extracted checksum_url

    triple="$(detect_target)"
    asset="uv-${triple}.tar.gz"
    # Note: uv >= 0.9.0 release URLs do not use the 'v' prefix in the path.
    url="https://github.com/astral-sh/uv/releases/download/${ver}/${asset}"

    # Try individual checksum file first (newer releases), then fallback to SHA256SUMS
    checksum_url="https://github.com/astral-sh/uv/releases/download/${ver}/${asset}.sha256"

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
    checksum_file="${tmpdir}/CHECKSUM"

    echo "Downloading uv v${ver} (${asset})"
    curl_fetch "${url}" -L -o "${tarball}"

    # Try to download individual checksum file
    if curl_fetch "${checksum_url}" -L -o "${checksum_file}" 2>/dev/null; then
         echo "Verifying with individual checksum file..."
         # The .sha256 file format for uv is "HASH  FILENAME"
         # But sometimes it is just the hash.
         # Let's check if sha256sum -c works (it expects 2 columns).
         if ! sha256sum -c "${checksum_file}" 2>/dev/null; then
            # Fallback if the file only contains the hash or formatting issues
            local hash
            hash="$(awk '{print $1}' "${checksum_file}")"
            # Check if the hash matches the file
            echo "${hash}  ${tarball}" | sha256sum -c -
         fi
    else
         # Fallback to SHA256SUMS (older releases or if individual fails)
         # This path might fail for new releases that don't have SHA256SUMS, but that is expected fallback behavior.
         echo "Individual checksum not found, trying SHA256SUMS..."
         local checksum_sums_url="https://github.com/astral-sh/uv/releases/download/${ver}/SHA256SUMS"

         curl_fetch "${checksum_sums_url}" -L -o "${checksum_file}"

         if ! grep " ${asset}" "${checksum_file}" | sha256sum -c -; then
             echo "uv checksum verification failed for ${asset}" >&2
             exit 1
         fi
    fi

    # The tarball usually contains a directory like uv-x86_64-unknown-linux-gnu/uv
    # We want to extract just the 'uv' binary.
    # Using --strip-components=1 is risky if structure changes, but standard for these artifacts.
    # Let's try finding it.
    tar -xzf "${tarball}" -C "${tmpdir}"

    # Find the uv binary in the extracted directory (it might be in a subdir)
    extracted="$(find "${tmpdir}" -type f -name uv | head -n 1)"
    if [[ -z "${extracted}" ]]; then
        echo "Could not find 'uv' binary in downloaded archive" >&2
        exit 1
    fi

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
