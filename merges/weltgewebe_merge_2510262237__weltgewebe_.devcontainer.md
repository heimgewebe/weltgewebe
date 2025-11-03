### 📄 weltgewebe/.devcontainer/Dockerfile.extended

**Größe:** 3 KB | **md5:** `1cdeecaa6f634376a941103f27fbc67b`

```plaintext
# syntax=docker/dockerfile:1.4
ARG BASE_IMAGE=mcr.microsoft.com/devcontainers/javascript-node:22
FROM ${BASE_IMAGE}
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# --- Ensure expected devcontainer user exists (the CLI assumes "vscode") ---
# Idempotent: nur anlegen, wenn er fehlt (manche Base-Images liefern ihn nicht).
#
# Robustere Logik: vermeide feste UID/GID, wenn die gewünschte UID bereits belegt ist.
# Falls ${USERNAME} bereits existiert, passiert nichts. Falls die gewünschte UID
# frei ist, wird sie verwendet; sonst wird der User ohne feste UID angelegt, um
# "UID ... is not unique"-Fehler während des Image-Builds zu vermeiden.
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=${USER_UID}
RUN set -eux; \
    # ensure group exists (try with requested GID, fall back to name-only)
    if ! getent group "${USERNAME}" >/dev/null 2>&1; then \
      groupadd --gid "${USER_GID}" "${USERNAME}" || groupadd "${USERNAME}"; \
    fi; \
    # create user only if missing
    if ! getent passwd "${USERNAME}" >/dev/null 2>&1; then \
      # if the requested UID is free, create with that UID; otherwise create
      # the user without forcing UID to avoid conflicts with existing users
      if ! getent passwd "${USER_UID}" >/dev/null 2>&1; then \
        useradd --uid "${USER_UID}" --gid "${USERNAME}" -m -s /bin/bash "${USERNAME}"; \
      else \
        useradd -m -s /bin/bash -g "${USERNAME}" "${USERNAME}" || useradd -m -s /bin/bash "${USERNAME}"; \
      fi; \
    fi; \
    mkdir -p /home/"${USERNAME}"/.ssh && chown -R "${USERNAME}:${USERNAME}" /home/"${USERNAME}"

# Optional: Standard-Tools/Qualität der Life-in-Container-Experience
# + sudo installieren und passwortlosen sudo für die Gruppe sudo erlauben,
#   damit postCreate/postStart-Kommandos zuverlässig laufen.
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt \
    set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates curl git git-lfs less nano bash-completion sudo; \
    git config --system --add safe.directory /workspaces; \
    git config --system --add safe.directory /workspaces/*; \
    git config --system --add safe.directory /workspaces/weltgewebe; \
    # sudo-Gruppe sicherstellen (falls Base-Image sie nicht hat)
    if ! getent group sudo >/dev/null 2>&1; then groupadd sudo; fi; \
    usermod -aG sudo "${USERNAME}" || true; \
    # NOPASSWD Drop-In (spät einsortieren, damit es gewinnt)
    install -d -m 0755 /etc/sudoers.d; \
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/99-sudo-nopasswd; \
    chmod 0440 /etc/sudoers.d/99-sudo-nopasswd; \
    rm -rf /var/lib/apt/lists/*

# Features/weitere Layer folgen darunter wie gehabt…
```

### 📄 weltgewebe/.devcontainer/devcontainer.json

**Größe:** 2 KB | **md5:** `4e45909d098137e59ce2f52d3218b340`

```json
{
  "name": "weltgewebe-dev",
  "build": {
    "dockerfile": "Dockerfile.extended"
  },
  "features": {
    "ghcr.io/devcontainers/features/git:1": {},
    "ghcr.io/devcontainers/features/github-cli:1": {},
    "ghcr.io/devcontainers/features/rust:1": {},
    "ghcr.io/devcontainers/features/node:1": {
      "version": "22"
    }
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "rust-lang.rust-analyzer",
        "timonwong.shellcheck",
        "streetsidesoftware.code-spell-checker",
        "yzhang.markdown-all-in-one",
        "DavidAnson.vscode-markdownlint",
        "bierner.markdown-preview-github-styles"
      ]
    }
  },
  "forwardPorts": [5173, 3000],
  "portsAttributes": {
    "5173": {
      "label": "Vite Dev Server",
      "onAutoForward": "openBrowser"
    },
    "3000": {
      "label": "API / Preview",
      "onAutoForward": "notify"
    }
  },
  "containerEnv": {
    "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1",
    "PUPPETEER_SKIP_DOWNLOAD": "true"
  },
  // Wir benutzen bewusst den "vscode"-User. Der Dockerfile-Patch legt ihn an, falls fehlend.
  "remoteUser": "vscode",
  "updateRemoteUserUID": true,
  // Start an init process (tini) for better signal handling inside the container.
  "init": true,
  "postCreateCommand": "bash .devcontainer/post-create.sh",
  "postAttachCommand": "bash -lc 'corepack enable || true; cd apps/web && [ -d node_modules ] || (pnpm install || npm ci || npm install)'",
  "postStartCommand": "bash -lc 'set -euxo pipefail; echo Using compose as the single source of truth; just check || true'"
}
```

### 📄 weltgewebe/.devcontainer/post-create.sh

**Größe:** 1 KB | **md5:** `eb1cd691a17159ed4045d1e9ee376646`

```bash
#!/usr/bin/env bash
set -euxo pipefail

# bestehendes Setup
sudo apt-get update
sudo apt-get install -y jq ripgrep vale shfmt hadolint just httpie

# Node/PNPM vorbereiten
corepack enable || true
corepack prepare pnpm@latest --activate || true

# Frontend-Install, wenn apps/web existiert
if [ -d "apps/web" ] && [ -f "apps/web/package.json" ]; then
  (cd apps/web && (pnpm install || npm ci || npm install))
fi

# --- uv installieren (offizieller Installer von Astral) ---
# Quelle: Astral Docs – Standalone installer
# https://docs.astral.sh/uv/getting-started/installation/
# Download the installer script to a temporary file
tmpfile=$(mktemp) || { echo "Failed to create temp file" >&2; exit 1; }
curl -LsSf https://astral.sh/uv/install.sh -o "$tmpfile" || { echo "Failed to download uv installer" >&2; rm -f "$tmpfile"; exit 1; }
# (Optional) Here you could verify the checksum if Astral provides one
sh "$tmpfile" || { echo "uv install failed" >&2; rm -f "$tmpfile"; exit 1; }
rm -f "$tmpfile"

# uv in PATH für diese Session (Installer schreibt auch in Shell-Profile)
export PATH="$HOME/.local/bin:$PATH"

# Version anzeigen, damit man im Devcontainer-Log sieht, dass es geklappt hat
uv --version

echo "uv installed and ready"

# Rust warm-up (optional)
if [ -f "Cargo.toml" ]; then
  cargo fetch || true
fi
```

