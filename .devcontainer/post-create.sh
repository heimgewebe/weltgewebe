#!/usr/bin/env bash
set -euxo pipefail

# bestehendes Setup
sudo apt-get update
sudo apt-get install -y jq ripgrep vale shfmt hadolint just httpie

# --- uv installieren (offizieller Installer von Astral) ---
# Quelle: Astral Docs – Standalone installer
# https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh || { echo "uv install failed" >&2; exit 1; }

# uv in PATH für diese Session (Installer schreibt auch in Shell-Profile)
export PATH="$HOME/.local/bin:$PATH"

# Version anzeigen, damit man im Devcontainer-Log sieht, dass es geklappt hat
uv --version

echo "uv installed and ready"
