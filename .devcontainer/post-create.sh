#!/usr/bin/env bash
set -euxo pipefail

CURL_COMMON=(-fsS --proto '=https' --tlsv1.2 --retry 3 --retry-delay 2)
if curl --help all 2>/dev/null | grep -q -- '--retry-all-errors'; then
  CURL_COMMON+=(--retry-all-errors)
elif curl --help 2>/dev/null | grep -q -- '--retry-all-errors'; then
  CURL_COMMON+=(--retry-all-errors)
fi

install_vale() {
  local vale_version="3.4.1"
  local vale_os
  local tarball
  local base_url
  local tmpdir

  case "$(uname -m)" in
    x86_64)
      vale_os="Linux_64-bit"
      ;;
    aarch64|arm64)
      vale_os="Linux_arm64"
      ;;
    *)
      printf 'Unsupported architecture for Vale: %s\n' "$(uname -m)" >&2
      return 1
      ;;
  esac

  tarball="vale_${vale_version}_${vale_os}.tar.gz"
  base_url="https://github.com/errata-ai/vale/releases/download/v${vale_version}"
  tmpdir=$(mktemp -d)

  curl "${CURL_COMMON[@]}" -L -o "$tmpdir/$tarball" "${base_url}/${tarball}"
  curl "${CURL_COMMON[@]}" -L -o "$tmpdir/checksums.txt" "${base_url}/vale_${vale_version}_checksums.txt"
  (
    cd "$tmpdir"
    grep "$tarball" checksums.txt | sha256sum -c -
    tar -xzf "$tarball"
    install -m 0755 vale "$HOME/.local/bin/vale"
  )
  rm -rf "$tmpdir"

  vale --version
}

install_hadolint() {
  local hadolint_version="2.12.0"
  local hadolint_arch
  local binary_name
  local base_url
  local tmpdir

  case "$(uname -m)" in
    x86_64)
      hadolint_arch="x86_64"
      ;;
    aarch64|arm64)
      hadolint_arch="arm64"
      ;;
    *)
      printf 'Unsupported architecture for hadolint: %s\n' "$(uname -m)" >&2
      return 1
      ;;
  esac

  binary_name="hadolint-linux-${hadolint_arch}"
  base_url="https://github.com/hadolint/hadolint/releases/download/v${hadolint_version}"
  tmpdir=$(mktemp -d)

  curl "${CURL_COMMON[@]}" -L -o "$tmpdir/$binary_name" "${base_url}/${binary_name}"
  install -m 0755 "$tmpdir/$binary_name" "$HOME/.local/bin/hadolint"
  rm -rf "$tmpdir"

  hadolint --version
}

ensure_user_can_write() {
  local target_dir="$1"

  if [ -w "$target_dir" ]; then
    return 0
  fi

  sudo chown -R "$(id -u):$(id -g)" "$target_dir"
}

# bestehendes Setup
sudo apt-get update
sudo apt-get install -y jq ripgrep shfmt just httpie

mkdir -p "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"

install_vale
install_hadolint

# Node/PNPM vorbereiten (Version aus package.json)
export COREPACK_ENABLE_DOWNLOAD_PROMPT=0
corepack enable || true

# Frontend-Install, wenn apps/web existiert
if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then
  ensure_user_can_write "apps/web"
  (cd apps/web && pnpm install)
fi

# --- uv installieren (offizieller Installer von Astral) ---
# Quelle: Astral Docs – Standalone installer
# https://docs.astral.sh/uv/getting-started/installation/
# Download the installer script to a temporary file
tmpfile=$(mktemp) || {
  echo "Failed to create temp file" >&2
  exit 1
}
curl -LsSf https://astral.sh/uv/install.sh -o "$tmpfile" || {
  echo "Failed to download uv installer" >&2
  rm -f "$tmpfile"
  exit 1
}
# (Optional) Here you could verify the checksum if Astral provides one
sh "$tmpfile" || {
  echo "uv install failed" >&2
  rm -f "$tmpfile"
  exit 1
}
rm -f "$tmpfile"

# Version anzeigen, damit man im Devcontainer-Log sieht, dass es geklappt hat
uv --version

echo "uv installed and ready"

# Rust warm-up (optional)
if [ -f "Cargo.toml" ]; then
  cargo fetch || true
fi
