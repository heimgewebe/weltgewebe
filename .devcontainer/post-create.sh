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
RAW_VER=$(yq -r '.uv' toolchain.versions.yml)
if [ -z "${RAW_VER:-}" ] || [ "${RAW_VER}" = "null" ]; then
  echo "failed to parse uv version from toolchain.versions.yml" >&2
  exit 1
fi
# Ensure clean version number (strip potential 'v' prefix if present in yaml, though usually it's 0.8.0)
CLEAN_VER="${RAW_VER#v}"
# GitHub Release URL uses tags without "v" prefix (e.g. "0.9.8")
URL="https://github.com/astral-sh/uv/releases/download/${CLEAN_VER}/uv-x86_64-unknown-linux-gnu.tar.gz"

echo "Installing uv version ${CLEAN_VER} from ${URL}..."

tmpfile=$(mktemp) || {
    echo "Failed to create temp file" >&2
    exit 1
}

curl -LsSf "$URL" -o "$tmpfile" || {
    echo "Failed to download uv tarball" >&2
    rm -f "$tmpfile"
    exit 1
}

# Extract to /tmp. The tarball usually contains a directory `uv-x86_64-unknown-linux-gnu/`
tar -xzf "$tmpfile" -C /tmp

# Move binaries. Use wildcard or explicit path.
# The folder name inside tarball matches the arch string.
# We move it to /usr/local/bin.
sudo mv /tmp/uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/uv
# uvx might be present
if [ -f /tmp/uv-x86_64-unknown-linux-gnu/uvx ]; then
    sudo mv /tmp/uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/uvx
fi

sudo chmod +x /usr/local/bin/uv
[ -f /usr/local/bin/uvx ] && sudo chmod +x /usr/local/bin/uvx

rm -f "$tmpfile"
rm -rf /tmp/uv-x86_64-unknown-linux-gnu

# Version anzeigen, damit man im Devcontainer-Log sieht, dass es geklappt hat
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH after installation" >&2
  exit 1
fi
uv --version

# NOTE: Dieses Setup muss identisch bleiben mit .github/workflows/ci.yml

echo "uv installed and ready"

# Rust warm-up (optional)
if [ -f "Cargo.toml" ]; then
    cargo fetch || true
fi
