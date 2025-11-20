#!/usr/bin/env bash
set -euxo pipefail

# bestehendes Setup
sudo apt-get update
sudo apt-get install -y jq ripgrep vale shfmt hadolint just httpie

# yq installieren (wird gebraucht um toolchain.versions.yml zu lesen)
# Wir verwenden die offizielle Binary-Installation, da kein apt-Paket oder zu alt.
YQ_VERSION="v4.48.1"
YQ_BINARY="yq_linux_amd64"
tmp_yq=$(mktemp)
wget "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/${YQ_BINARY}" -O "${tmp_yq}"
sudo mv "${tmp_yq}" /usr/local/bin/yq
sudo chmod +x /usr/local/bin/yq

# Node/PNPM vorbereiten
corepack enable || true
# Pinned version to match CI (9.11.0)
corepack prepare pnpm@9.11.0 --activate || true

# Frontend-Install, wenn apps/web existiert
if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then
    (cd apps/web && pnpm install)
fi

# --- uv installieren (Version aus toolchain.versions.yml) ---
UV_VERSION=$(yq -r '.uv' toolchain.versions.yml)
if [ -z "${UV_VERSION:-}" ] || [ "${UV_VERSION}" = "null" ]; then
  echo "failed to parse uv version from toolchain.versions.yml" >&2
  exit 1
fi

# NOTE: Dieses Setup muss identisch bleiben mit .github/workflows/ci.yml
echo "Installing uv version ${UV_VERSION}..."

# Clean version string (strip leading v if present)
CLEAN_VER="${UV_VERSION#v}"
URL="https://github.com/astral-sh/uv/releases/download/${CLEAN_VER}/uv-x86_64-unknown-linux-gnu.tar.gz"

tmpfile=$(mktemp) || { echo "Failed to create temp file" >&2; exit 1; }

# Robust download
curl -LsSf "$URL" -o "$tmpfile" || {
    echo "Failed to download uv tarball" >&2
    rm -f "$tmpfile"
    exit 1
}

# Extract to /tmp
tar -xzf "$tmpfile" -C /tmp

# Move binaries
sudo mv /tmp/uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/uv
if [ -f /tmp/uv-x86_64-unknown-linux-gnu/uvx ]; then
    sudo mv /tmp/uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/uvx
fi

sudo chmod +x /usr/local/bin/uv
[ -f /usr/local/bin/uvx ] && sudo chmod +x /usr/local/bin/uvx

rm -f "$tmpfile"
rm -rf /tmp/uv-x86_64-unknown-linux-gnu

# Verification
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH after installation" >&2
  exit 1
fi
uv --version
