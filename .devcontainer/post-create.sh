#!/usr/bin/env bash
set -euxo pipefail

# bestehendes Setup
sudo apt-get update
sudo apt-get install -y jq ripgrep vale shfmt hadolint just httpie

# yq installieren (wird gebraucht um toolchain.versions.yml zu lesen)
# Wir verwenden die offizielle Binary-Installation, da kein apt-Paket oder zu alt.
YQ_VERSION="v4.40.5"
YQ_BINARY="yq_linux_amd64"
wget https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/${YQ_BINARY} -O /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq

# Node/PNPM vorbereiten
corepack enable || true
# Wir richten pnpm ein - Version wird im nächsten Schritt ggf. angepasst, hier erstmal default
corepack prepare pnpm@latest --activate || true

# Frontend-Install, wenn apps/web existiert
if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then
    (cd apps/web && pnpm install)
fi

# --- uv installieren (Version aus toolchain.versions.yml) ---
UV_VERSION=$(yq '.uv' toolchain.versions.yml | tr -d '"')

# Download the installer script
tmpfile=$(mktemp) || {
    echo "Failed to create temp file" >&2
    exit 1
}

# Wir nutzen direkt curl auf den Release-Tarball für die spezifische Version,
# ähnlich wie im CI-Workflow, um exakt die Version zu bekommen.
# Der Installer script supported auch version constraints, aber wir machen es hier manuell für volle Kontrolle
# oder nutzen uv's installer feature 'curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh | sh'

echo "Installing uv version ${UV_VERSION}..."
curl -LsSf https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz -o "$tmpfile" || {
    echo "Failed to download uv tarball" >&2
    rm -f "$tmpfile"
    exit 1
}

tar -xzf "$tmpfile" -C /tmp
sudo mv /tmp/uv-x86_64-unknown-linux-gnu/uv /usr/local/bin/uv
sudo mv /tmp/uv-x86_64-unknown-linux-gnu/uvx /usr/local/bin/uvx || true
rm -f "$tmpfile"
rm -rf /tmp/uv-x86_64-unknown-linux-gnu

# Version anzeigen, damit man im Devcontainer-Log sieht, dass es geklappt hat
uv --version

# NOTE: Dieses Setup muss identisch bleiben mit .github/workflows/ci.yml

echo "uv installed and ready"

# Rust warm-up (optional)
if [ -f "Cargo.toml" ]; then
    cargo fetch || true
fi
