### 📄 merges/weltgewebe_merge_2510262237__.devcontainer.md

**Größe:** 6 KB | **md5:** `801272bc7990d8357c6b4af0396feff8`

```markdown
### 📄 .devcontainer/Dockerfile.extended

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

### 📄 .devcontainer/devcontainer.json

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

### 📄 .devcontainer/post-create.sh

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
```

### 📄 merges/weltgewebe_merge_2510262237__.gewebe_in.md

**Größe:** 630 B | **md5:** `63b80bfe042ce579fa0e50487130dff9`

```markdown
### 📄 .gewebe/in/demo.edges.jsonl

**Größe:** 187 B | **md5:** `a392f31657002ee3eec53f74ce4a3203`

```plaintext
{"src":"n1","dst":"n2","rel":"references","why":"Demo-Kante","updated_at":"2024-03-02T09:00:00Z"}
{"src":"n2","dst":"n1","rel":"related","weight":0.6,"updated_at":"2024-03-02T09:05:00Z"}
```

### 📄 .gewebe/in/demo.nodes.jsonl

**Größe:** 199 B | **md5:** `a383755d092f8a85b35de76c58bd9c1b`

```plaintext
{"id":"n1","type":"doc","title":"Demo Node","tags":["sample"],"source":"semantAH","updated_at":"2024-03-01T10:00:00Z"}
{"id":"n2","type":"term","title":"Begriff","updated_at":"2024-03-02T08:30:00Z"}
```
```

### 📄 merges/weltgewebe_merge_2510262237__.github_workflows.md

**Größe:** 40 KB | **md5:** `3a7ba71cc869c963aa6b0b07f7e2b6f0`

```markdown
### 📄 .github/workflows/api-smoke.yml

**Größe:** 5 KB | **md5:** `330784c355ef87762c6c07d3b1fcf417`

```yaml
name: api-smoke
on:
  pull_request:
    branches: [ main ]
    paths:
      - "apps/api/**"
      - "Cargo.toml"
      - "Cargo.lock"
      - ".github/workflows/api-smoke.yml"
  push:
    branches: [ main ]
    paths:
      - "apps/api/**"
      - "Cargo.toml"
      - "Cargo.lock"
      - ".github/workflows/api-smoke.yml"
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: api-smoke-${{ github.ref }}
  cancel-in-progress: true
jobs:
  ultra_light_health:
    name: API – ultra-light smoke (health endpoints)
    runs-on: ubuntu-latest
    timeout-minutes: 5
    env:
      CARGO_TARGET_DIR: ./target
    defaults:
      run:
        working-directory: apps/api
        shell: bash
    steps:
      - uses: actions/checkout@v4
      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y pkg-config libssl-dev libpq-dev
      - name: Inject build metadata (compile-time env)
        run: |
          echo "GIT_COMMIT_SHA=${GITHUB_SHA}" >> "$GITHUB_ENV"
          echo "BUILD_TIMESTAMP=${{ github.run_started_at }}" >> "$GITHUB_ENV"
      - uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: stable
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: |
            apps/api -> target
      - name: Build release (fast start)
        run: cargo build --locked --release --bin weltgewebe-api
      - name: Run API in background
        env:
          API_BIND: 127.0.0.1:8787
          RUST_LOG: info
          RUST_BACKTRACE: 1
          APP_CONFIG_PATH: ${{ github.workspace }}/configs/app.defaults.yml
        run: |
          if [ ! -x ./target/release/weltgewebe-api ]; then
            echo "compiled API binary missing"
            ls -al ./target/release || true
            exit 1
          fi
          nohup ./target/release/weltgewebe-api >/tmp/api.log 2>&1 &
          echo $! > /tmp/api.pid
          # Wait up to 5 seconds for the PID file to exist
          for i in {1..10}; do
            [ -f /tmp/api.pid ] && break
            sleep 0.5
          done
          if [ ! -f /tmp/api.pid ]; then
            echo "PID file not found after waiting"
            exit 1
          fi
          if ! kill -0 "$(cat /tmp/api.pid)" 2>/dev/null; then
            echo "API process failed to start"
            exit 1
          fi
      - name: Probe /version (startup)
        run: |
          set -euo pipefail
          body="$(curl --max-time 10 --fail-with-body http://127.0.0.1:8787/version)"
          if ! echo "$body" | jq empty >/dev/null 2>&1; then
            echo "API did not return valid JSON: $body"
            exit 1
          fi
          echo "::group::/version body"
          echo "$body"
          echo "::endgroup::"
          # Validate fields using jq (more robust than grep on strings)
          echo "$body" | jq -e 'type == "object" and has("version") and has("commit") and has("build_timestamp")' >/dev/null

          # Optional: also assert types (string/string/number) – harmless if types differ:
          # echo "$body" | jq -e '(.version|type=="string") and (.commit|type=="string") and (.build_timestamp|type=="number")' >/dev/null
      - name: Wait for API health endpoint
        run: |
          ok=0
          for i in {1..60}; do
            if curl -fsS http://127.0.0.1:8787/health/live; then ok=1; break; fi
            sleep 0.5
          done
          [ "$ok" -eq 1 ] || { echo "health/live not ready in time"; exit 1; }
      - name: Probe /health and /metrics
        run: |
          set -euxo pipefail
          curl -fsS http://127.0.0.1:8787/health/live
          curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/health/ready | grep -E '^(200|503)$'
          # /metrics darf 200 liefern, Inhalt ist optional; zeigen die ersten Zeilen, falls vorhanden:
          curl -fsS http://127.0.0.1:8787/metrics | head -n 5 || echo "no /metrics yet (ok)"
      - name: Probe /version (field presence)
        run: |
          set -euo pipefail
          curl -fsS http://127.0.0.1:8787/version | jq -e '.version and .commit and .build_timestamp' >/dev/null
      - name: Stop API
        if: always()
        run: |
          PID_FILE=/tmp/api.pid
          if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
              kill "$PID" 2>/dev/null || true
              wait "$PID" 2>/dev/null || true
            fi
          fi
      - name: Upload API log
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: api-log
          path: /tmp/api.log
```

### 📄 .github/workflows/api.yml

**Größe:** 3 KB | **md5:** `1f2985143701e991e78c2845149c83db`

```yaml
name: api

on:
  pull_request:
    branches: [main]
    paths:
      - "apps/api/**"
      - "Cargo.toml"
      - "Cargo.lock"
      - "configs/app.defaults.yml"
      - ".github/workflows/api.yml"
  push:
    branches: [main]
    paths:
      - "apps/api/**"
      - "configs/app.defaults.yml"
      - ".github/workflows/api.yml"
  workflow_dispatch: {}

permissions:
  contents: read

env:
  RUST_TOOLCHAIN: stable

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test-and-lint:
    name: test and lint (rust)
    runs-on: ubuntu-latest
    env:
      CARGO_TERM_COLOR: always  # keep cargo output colorized in CI logs
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      # Optional: Validates that a default app config is parseable (if present)
      - name: Install PyYAML for config validation
        if: hashFiles('configs/app.defaults.yml') != ''
        run: python3 -m pip install --disable-pip-version-check --no-cache-dir pyyaml

      - name: Validate app.defaults.yml (optional)
        if: hashFiles('configs/app.defaults.yml') != ''
        run: |
          python3 - <<'PY'
          import yaml
          from pathlib import Path

          p = Path("configs/app.defaults.yml")
          yaml.safe_load(p.read_text(encoding="utf-8"))
          print("configs/app.defaults.yml: OK")
          PY

      - name: Install rust toolchain
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: ${{ env.RUST_TOOLCHAIN }}

      - name: Add rust components
        run: rustup component add rustfmt clippy

      - name: Cache cargo
        uses: Swatinem/rust-cache@v2

      # fmt & clippy at repo root: covers all crates/workspaces
      - name: Format check (workspace)
        run: cargo fmt --all -- --check

      - name: Clippy (deny warnings, workspace)
        run: cargo clippy --all-targets --all-features -- -D warnings

      - name: Test (all features, verbose)
        working-directory: apps/api
        run: cargo test --all-features --verbose

  dependency-audit:
    name: dependency audit (on-demand)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    # By default not on every PR/push: only manually or via "security" label
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' && contains(github.event.pull_request.labels.*.name, 'security'))
    steps:
      - uses: actions/checkout@v4
      - name: Install rust toolchain
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: ${{ env.RUST_TOOLCHAIN }}
      - name: Install cargo-audit
        run: cargo install cargo-audit --force
      - name: cargo audit
        run: cargo audit
```

### 📄 .github/workflows/ci.yml

**Größe:** 7 KB | **md5:** `d91b48b739c4522a624066857496b40e`

```yaml
name: CI

permissions:
  contents: read

on:
  push:
    branches: [ main ]
  pull_request:
  workflow_dispatch:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

defaults:
  run:
    shell: bash --noprofile --norc -euo pipefail {0}

jobs:
  ci:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      NODE_OPTIONS: --max-old-space-size=4096
    steps:
      - uses: actions/checkout@v4

      - name: Install yq (for toolchain.versions.yml)
        run: |
          set -euo pipefail
          YQ_VERSION=4.44.1
          ARCH="$(uname -m)"
          case "${ARCH}" in
            x86_64)  BIN="yq_linux_amd64" ;;
            aarch64|arm64) BIN="yq_linux_arm64" ;;
            *) echo "Unsupported arch for yq: ${ARCH}" >&2; exit 1 ;;
          esac
          echo "yq installer: detected architecture '${ARCH}'"
          URL_BASE="https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}"
          BIN_URL="${URL_BASE}/${BIN}"
          TMP="$(mktemp)"
          TMP_SHA="${TMP}.sha256"
          trap 'rm -f "${TMP}" "${TMP_SHA}"' EXIT
          echo "Downloading ${BIN_URL}"
          curl -fsSL "${BIN_URL}" -o "${TMP}"
          # Verify against matching checksum for the exact binary
          curl -fsSL "${BIN_URL}.sha256" -o "${TMP_SHA}"
          EXPECTED="$(awk '{print $1}' "${TMP_SHA}")"
          ACTUAL="$(sha256sum "${TMP}" | awk '{print $1}')"
          if [ "${EXPECTED}" != "${ACTUAL}" ]; then
            echo "yq checksum mismatch: expected ${EXPECTED}, got ${ACTUAL}" >&2
            exit 1
          fi
          sudo install -m 0755 "${TMP}" /usr/local/bin/yq
          rm -f "${TMP}" "${TMP_SHA}"
          trap - EXIT
          yq --version

      - name: Read toolchain versions
        run: |
          test -f toolchain.versions.yml || { echo "toolchain.versions.yml not found"; exit 1; }
          RUST=$(yq -r '.rust' toolchain.versions.yml)
          echo "RUST_VERSION=${RUST}" >> "$GITHUB_ENV"
          PY=$(yq -r '.python' toolchain.versions.yml)
          echo "PYTHON_VERSION=${PY}" >> "$GITHUB_ENV"
          UV=$(yq -r '.uv' toolchain.versions.yml)
          echo "UV_VERSION=${UV}" >> "$GITHUB_ENV"

      - name: Setup Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: ${{ env.RUST_VERSION }}
          components: rustfmt, clippy

      - name: Cache Cargo artifacts
        uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            ~/.cargo/git
            target
          key: ${{ runner.os }}-cargo-${{ env.RUST_VERSION }}-${{ hashFiles('**/Cargo.lock') }}
          restore-keys: |
            ${{ runner.os }}-cargo-${{ env.RUST_VERSION }}-
            ${{ runner.os }}-cargo-

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20.19.0'
          check-latest: true
          cache: 'npm'
          cache-dependency-path: |
            package-lock.json
            apps/web/package-lock.json

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache uv artifacts
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ env.UV_VERSION }}-${{ hashFiles('**/pyproject.toml', 'toolchain.versions.yml') }}
          restore-keys: |
            ${{ runner.os }}-uv-

      - name: Install uv
        env:
          UV_VERSION: ${{ env.UV_VERSION }}
        run: |
          set -euo pipefail
          mkdir -p "$HOME/.local/bin"
          ARCH="$(uname -m)"
          case "${ARCH}" in
            x86_64)  TARBALL="uv-x86_64-unknown-linux-gnu.tar.gz" ;;
            aarch64) TARBALL="uv-aarch64-unknown-linux-gnu.tar.gz" ;;
            arm64)   TARBALL="uv-aarch64-unknown-linux-gnu.tar.gz" ;;
            *) echo "Unsupported arch: ${ARCH}" >&2; exit 1 ;;
          esac
          URL="https://github.com/astral-sh/uv/releases/download/v${UV_VERSION}/${TARBALL}"
          echo "Downloading ${URL}"
          TMP_TGZ="$(mktemp)"
          TMP_SHA="${TMP_TGZ}.sha256"
          trap 'rm -f "${TMP_TGZ}" "${TMP_SHA}"' EXIT
          curl -fL "$URL" -o "${TMP_TGZ}"
          if curl -fsL "https://github.com/astral-sh/uv/releases/download/v${UV_VERSION}/SHA256SUMS" -o "${TMP_SHA}"; then
            (cd "$(dirname "${TMP_TGZ}")" && grep " ${TARBALL}$" "${TMP_SHA}" | sha256sum -c -)
          fi
          tar xzf "${TMP_TGZ}" -C "$HOME/.local/bin" uv
          chmod +x "$HOME/.local/bin/uv"
          export PATH="$HOME/.local/bin:$PATH"
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"
          echo "$HOME/.cargo/bin" >> "$GITHUB_PATH"
          INSTALLED=$(uv --version | awk '{print $2}')
          if [[ "${INSTALLED}" != "${UV_VERSION}" ]]; then
            echo "Expected uv ${UV_VERSION}, got ${INSTALLED}" >&2
            exit 1
          fi
          trap - EXIT

      - name: Setup Just
        uses: extractions/setup-just@v2

      - name: Show tool versions
        run: |
          rustc --version
          python --version
          uv --version
          just --version

      - name: Validate project
        run: just ci


  lint-docs:
    name: Docs & Shell Hygiene
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Markdownlint
        uses: DavidAnson/markdownlint-cli2-action@v16
        with:
          globs: |
            **/*.md
            !**/node_modules/**
            !**/dist/**

      - name: Link check (lychee)
        uses: lycheeverse/lychee-action@v2
        with:
          args: >
            --no-progress
            --accept 200,206,301,302,429
            --timeout 15s
            --max-concurrency 3
            --retry-wait-time 3s
            --max-retries 3
            --exclude 'https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?(/.*)?'
            --exclude-path '**/node_modules/**'
            --exclude-path '**/dist/**'
            '**/*.md'
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      - name: YAML lint
        uses: ibiqlik/action-yamllint@v3
        with:
          file_or_dir: |
            .
          strict: true

      - name: Ensure jq is available
        run: |
          set -euo pipefail
          if ! command -v jq >/dev/null 2>&1; then
            sudo apt-get update
            sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends jq
          fi

      - name: JSON lint
        run: |
          set -euo pipefail
          mapfile -d '' files < <(git ls-files -z '*.json' ':!:**/package-lock.json' || true)
          if (( ${#files[@]} )); then
            jq -n 'inputs' "${files[@]}" >/dev/null
          else
            echo "No JSON files to lint"
          fi
```

### 📄 .github/workflows/compose-smoke.yml

**Größe:** 1 KB | **md5:** `698dbf8c2011a8869ef2b1985b6a157a`

```yaml
name: compose-smoke
permissions:
  contents: read
on:
  workflow_dispatch: {}
  push:
    branches: [main]
    paths:
      - "infra/compose/compose.core.yml"
      - "infra/caddy/Caddyfile"
      - ".github/workflows/compose-smoke.yml"
      - "apps/api/**"
      - "apps/web/**"

jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Compose up (detached)
        run: docker compose -f infra/compose/compose.core.yml --profile dev up -d --build
      - name: Wait for services (API & Web)
        run: |
          set -euo pipefail
          tries=60
          until curl -fsS http://localhost:8081/ >/dev/null; do
            ((tries--)) || (docker compose -f infra/compose/compose.core.yml --profile dev logs --no-color && exit 1)
            sleep 2
          done
          tries=60
          until curl -fsS http://localhost:8081/api/version >/dev/null || curl -fsS http://localhost:8081/api/health/ready >/dev/null; do
            ((tries--)) || (docker compose -f infra/compose/compose.core.yml --profile dev logs --no-color && exit 1)
            sleep 2
          done
      - name: Show brief logs
        if: always()
        run: docker compose -f infra/compose/compose.core.yml --profile dev logs --no-color --tail=200
      - name: Compose down
        if: always()
        run: docker compose -f infra/compose/compose.core.yml --profile dev down -v
```

### 📄 .github/workflows/cost-report.yml

**Größe:** 469 B | **md5:** `0f7ac5f72887b57eb1acb8f2b3c0ac2d`

```yaml
name: cost-report
permissions:
  contents: read
  actions: write
on:
  workflow_dispatch:
  schedule:
    - cron: "7 3 1 * *"
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python tools/py/cost/report.py
      - uses: actions/upload-artifact@v4
        with:
          name: cost-report
          path: docs/reports/cost-report.md
```

### 📄 .github/workflows/docs-style.yml

**Größe:** 3 KB | **md5:** `23da05da88ccf3b3c28476d5cbfffe5e`

```yaml
name: docs-style

on:
  pull_request:
    branches: [ main ]
    paths:
      - "docs/**"
      - ".vale/**"
      - ".vale.ini"
      - ".github/workflows/docs-style.yml"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: docs-style-${{ github.ref }}
  cancel-in-progress: true

jobs:
  vale:
    name: Vale prose lint
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - name: Install Vale (v3.4.1, checksum verified)
        run: |
          set -euo pipefail
          VALE_VERSION="3.4.1"
          VALE_OS="Linux_64-bit"
          TARBALL="vale_${VALE_VERSION}_${VALE_OS}.tar.gz"
          BASE_URL="https://github.com/errata-ai/vale/releases/download/v${VALE_VERSION}"
          curl -fsSL -o "$TARBALL" "${BASE_URL}/${TARBALL}"
          curl -fsSL -o checksums.txt "${BASE_URL}/vale_${VALE_VERSION}_checksums.txt"
          grep "$TARBALL" checksums.txt | sha256sum -c -
          mkdir -p bin
          tar -xzf "$TARBALL"
          mv vale bin/vale
          rm -f "$TARBALL" checksums.txt
          ./bin/vale --version

      - name: Determine changed docs
        id: changed
        run: |
          set -euo pipefail
          base="${{ github.base_ref || 'main' }}"
          # Ensure base is a remote-tracking branch (origin/branch)
          if [[ "$base" != origin/* ]]; then
            base="origin/$base"
          fi
          if ! git fetch origin "${base#origin/}" --depth=1; then
            echo "Warning: unable to fetch $base; continuing with available history" >&2
          fi
          files=$(git diff --name-only "$base...HEAD" | awk '/^docs\// {print}' || true)
          echo "files<<EOF" >> "$GITHUB_OUTPUT"
          echo "$files" >> "$GITHUB_OUTPUT"
          echo "EOF" >> "$GITHUB_OUTPUT"

      - name: Run Vale (soft; no fail)
        run: |
          set -euo pipefail
          if [ -n "${{ steps.changed.outputs.files }}" ]; then
            if ! ./bin/vale --minAlertLevel=suggestion ${{ steps.changed.outputs.files }}; then
              echo "Vale reported suggestions; continuing without failing the workflow."
            fi
          else
            echo "No changed docs/* files; skipping."
          fi

      - name: Full docs sweep on manual run (optional)
        if: ${{ github.event_name == 'workflow_dispatch' }}
        run: |
          if ! ./bin/vale --minAlertLevel=suggestion docs; then
            echo "Vale reported suggestions during full sweep; continuing without failing the workflow."
          fi
```

### 📄 .github/workflows/heavy.yml

**Größe:** 2 KB | **md5:** `8f6465dbb55ef4f12c1c5e6d9c5910e0`

```yaml
name: CI (heavy on demand)

on:
  workflow_dispatch: {}
  pull_request:
    types: [labeled, synchronize, reopened, ready_for_review]
    branches: [ main ]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  gate:
    runs-on: ubuntu-latest
    outputs:
      run_heavy: ${{ steps.flags.outputs.run_heavy }}
    steps:
      - id: flags
        shell: bash
        run: |
          labels="${{ join(github.event.pull_request.labels.*.name, ' ') }}"
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo "run_heavy=true" >> "$GITHUB_OUTPUT"
          elif echo "$labels" | grep -qiE '(^| )full-ci( |$)'; then
            echo "run_heavy=true" >> "$GITHUB_OUTPUT"
          else
            echo "run_heavy=false" >> "$GITHUB_OUTPUT"
          fi

  e2e:
    needs: gate
    if: needs.gate.outputs.run_heavy == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 45
    permissions:
      contents: read
    env:
      CI: true
      HEADLESS: "1"
      NPM_CONFIG_AUDIT: "false"
      NPM_CONFIG_FUND: "false"
    defaults: { run: { working-directory: apps/web, shell: bash } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22.x'
          cache: 'npm'
          cache-dependency-path: apps/web/package-lock.json
      - name: Enable Corepack (npm)
        run: corepack enable
      - name: npm ci
        run: npm ci
      - name: Install Playwright browsers
        run: npx playwright install --with-deps
      - name: Build (production)
        run: npm run build
      - name: Run Playwright tests
        run: npm run test
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: apps/web/playwright-report
          if-no-files-found: ignore
```

### 📄 .github/workflows/infra.yml

**Größe:** 582 B | **md5:** `48e1c97cab00973cdd1a87830a566e48`

```yaml
name: infra
on:
  pull_request:
    branches: [ main ]
    paths:
      - "infra/**"
      - ".github/workflows/infra.yml"
  push:
    branches: [ main ]
    paths:
      - "infra/**"
      - ".github/workflows/infra.yml"
  workflow_dispatch: {}

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  compose-core-smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - name: Core profile is present
        run: test -f infra/compose/compose.core.yml
```

### 📄 .github/workflows/links.yml

**Größe:** 506 B | **md5:** `502aa30330f0e971d64b4214b2e9875f`

```yaml
name: links
on:
  schedule:
    - cron: "0 4 * * *"
  workflow_dispatch:
    # Link checks on pull requests are handled in the central CI.
permissions:
  contents: read
concurrency:
  group: links-${{ github.ref }}
  cancel-in-progress: true
jobs:
  lychee:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: lycheeverse/lychee-action@v2
        with:
          args: --accept 200,429 --max-redirects 5 --exclude-mail --no-progress "docs/**/*.md"
```

### 📄 .github/workflows/policies.yml

**Größe:** 706 B | **md5:** `ce35f3bad715804b1c8b17ba3698fd02`

```yaml
name: policies
on:
  pull_request:
  push:
    branches:
      - main
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: policies-${{ github.ref }}
  cancel-in-progress: true
jobs:
  limits-file-and-yaml:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Ensure limits policy exists
        run: test -f policies/limits.yaml
      - name: Lint policies directory with yamllint
        run: |
          python -m pip install --upgrade pip
          python -m pip install yamllint
          if [ -f .yamllint.yml ]; then
            yamllint -c .yamllint.yml policies
          else
            yamllint policies

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__.vale_styles_Weltgewebe.md

**Größe:** 2 KB | **md5:** `bf6bcf72b22df25a35a7dd423afeb4c4`

```markdown
### 📄 .vale/styles/Weltgewebe/GermanComments.yml

**Größe:** 167 B | **md5:** `649b1c9d66791244009507d8cc6307ba`

```yaml
extends: existence
message: "TODO/FIXME gefunden: Ergänze Kontext oder verlinke ein Ticket."
level: suggestion
ignorecase: true
scope: raw
tokens:
  - TODO
  - FIXME
```

### 📄 .vale/styles/Weltgewebe/GermanProse.yml

**Größe:** 189 B | **md5:** `4767fb769bf96c61801a9496667b15f9`

```yaml
extends: substitution
level: suggestion
ignorecase: true
message: "Begriff prüfen: '%s' – konsistente Schreibweise wählen."
swap:
  "z.B.": "z. B."
  "bspw.": "z. B."
  "u.a.": "u. a."
```

### 📄 .vale/styles/Weltgewebe/WeltgewebeStyle.yml

**Größe:** 1 KB | **md5:** `e4ea56a6673b4c7536ea8fdadc31f264`

```yaml
extends: existence
level: warning
scope: text
ignorecase: false
description: "Weltgewebe-Redaktionsstil: neutrale Sprache, konsistente Begriffe und Zahlenschreibweisen."
tokens:
  - pattern: "\\b[\u00C0-\u024F\w]+(?:\\*|:|_)innen\\b"
    message: "Vermeide Gender-Stern/-Gap – wähle eine neutrale Formulierung."
  - pattern: "\\b[\u00C0-\u024F\w]+/[\u00C0-\u024F\w]+innen\\b"
    message: "Vermeide Slash-Genderformen – nutze eine neutrale Bezeichnung."
  - pattern: "\\bRolle[nr]?/(?:und|oder)?Funktion\\b"
    message: "Begriffe nicht vermischen: 'Rolle' und 'Funktion' haben unterschiedliche Bedeutungen."
  - pattern: "\\bFunktion(en)?\\b"
    message: "Prüfe den Begriff: Meinst du die Glossar-'Rolle'? Rolle ≠ Funktion."
  - pattern: "\\bThread(s)?\\b"
    message: "Glossarbegriff verwenden: Statt 'Thread' bitte 'Faden'."
  - pattern: "\\bNode(s)?\\b"
    message: "Glossarbegriff verwenden: Statt 'Node' bitte 'Knoten'."
  - pattern: "\\bYarn\\b"
    message: "Glossarbegriff verwenden: Statt 'Yarn' bitte 'Faden' oder 'Garn'."
  - pattern: "\\bGarn\\b"
    message: "Prüfe den Kontext: 'Faden' ist der Standardbegriff, 'Garn' nur bei Verzwirnung."
  - pattern: "\\bKnotenpunkt\\b"
    message: "Glossarbegriff verwenden: Statt 'Knotenpunkt' bitte 'Knoten'."
  - pattern: "\\b\\d{4,}\\b"
    message: "Zahlenschreibweise prüfen: Tausender trennen (z. B. 10 000) oder Zahl ausschreiben."
  - pattern: "\\b\\d+[kK]\\b"
    message: "Zahl abkürzungen vermeiden: Schreibe z. B. '1 000' statt '1k'."
```
```

### 📄 merges/weltgewebe_merge_2510262237__.wgx.md

**Größe:** 3 KB | **md5:** `a30d70ccddd87fe129fccc16a792b0b7`

```markdown
### 📄 .wgx/profile.yml

**Größe:** 3 KB | **md5:** `7dee77ac35f55224a527120cf3af71dc`

```yaml
version: 1
wgx:
  org: heimgewebe
repo:
  # Kurzname des Repos (wird automatisch aus git ableitbar sein – hier nur Doku)
  name: auto
  description: "WGX profile for unified tasks and env priorities"

env_priority:
  # Ordnungsprinzip laut Vorgabe
  - devcontainer
  - devbox
  - mise_direnv
  - termux

tooling:
  python:
    uv: true           # uv ist Standard-Layer für Python-Tools
    precommit: true    # falls .pre-commit-config.yaml vorhanden
  rust:
    cargo: auto        # wenn Cargo.toml vorhanden → Rust-Checks aktivieren
    clippy_strict: true
    fmt_check: true
    deny: optional     # cargo-deny, falls vorhanden

tasks:
  up:
    desc: "Dev-Umgebung hochfahren (Container/venv/tooling bootstrap)"
    sh:
      - |
        if command -v devcontainer >/dev/null 2>&1 || [ -f .devcontainer/devcontainer.json ]; then
          echo "[wgx.up] devcontainer context detected"
        fi
        if command -v uv >/dev/null 2>&1; then
          uv --version || true
          [ -f pyproject.toml ] && uv sync --frozen || true
        fi
        [ -f .pre-commit-config.yaml ] && command -v pre-commit >/dev/null 2>&1 && pre-commit install || true
  lint:
    desc: "Schnelle statische Checks (Rust/Python/Markdown/YAML)"
    sh:
      - |
        # Rust
        if [ -f Cargo.toml ]; then
          cargo fmt --all -- --check
          cargo clippy --all-targets --all-features -- -D warnings
        fi
        # Python
        if [ -f pyproject.toml ]; then
          if command -v uv >/dev/null 2>&1; then uv run ruff check . || true; fi
          if command -v uv >/dev/null 2>&1; then uv run ruff format --check . || true; fi
        fi
        # Docs
        command -v markdownlint >/dev/null 2>&1 && markdownlint "**/*.md" || true
        command -v yamllint    >/dev/null 2>&1 && yamllint . || true
  test:
    desc: "Testsuite"
    sh:
      - |
        [ -f Cargo.toml ] && cargo test --all --all-features || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv run pytest -q || true
        fi
  build:
    desc: "Build-Artefakte erstellen"
    sh:
      - |
        [ -f Cargo.toml ] && cargo build --release || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv build || true
        fi
  smoke:
    desc: "Schnelle Smoke-Checks (läuft <60s)"
    sh:
      - |
        echo "[wgx.smoke] repo=$(basename "$(git rev-parse --show-toplevel)")"
        [ -f Cargo.toml ] && cargo metadata --no-deps > /dev/null || true
        [ -f pyproject.toml ] && grep -q '\[project\]' pyproject.toml || true

wgx:
  org: "heimgewebe"

meta:
  owner: "heimgewebe"
  conventions:
    gewebedir: ".gewebe"
    version_endpoint: "/version"
    tasks_standardized: true
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_api.md

**Größe:** 2 KB | **md5:** `0d8273748958cd846590f1d95310d14c`

```markdown
### 📄 apps/api/Cargo.toml

**Größe:** 661 B | **md5:** `1e2e74243b53f7ab39631153465f3554`

```toml
[package]
name = "weltgewebe-api"
version = "0.1.0"
edition = "2021"
authors = ["Weltgewebe Team"]
license = "MIT"

[dependencies]
anyhow = "1"
axum = { version = "0.7", features = ["macros"] }
async-nats = "0.35"
dotenvy = "0.15"
prometheus = "0.14.0"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sqlx = { version = "0.8.1", default-features = false, features = ["runtime-tokio", "postgres"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
tower = "0.5"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "fmt"] }
serde_yaml = "0.9"

[dev-dependencies]
serial_test = "3"
tempfile = "3"
```

### 📄 apps/api/README.md

**Größe:** 2 KB | **md5:** `d4e26f6f719e408fcf849bfbf4c80f82`

```markdown
# Weltgewebe API

The Weltgewebe API is a Rust-based Axum service that powers the platform's backend capabilities.
This README provides a quick orientation for running and developing the service locally.

## Quickstart

1. **Install dependencies**
   - [Rust toolchain](https://www.rust-lang.org/tools/install) (stable)
   - A running PostgreSQL instance (or use `make up` / `just up` for the dev stack)
   - Optional: a running NATS server when developing features that need messaging

2. **Copy the environment template**

   ```bash
   cp ../../.env.example .env
   ```

3. **Adjust the required environment variables** (either in `.env` or the shell).
   Values defined in `.env` take precedence over the defaults from Docker Compose when you use the
   local development stack.
   Recommended settings:
   - `API_BIND` &mdash; socket address to bind the API (default `0.0.0.0:8080`)
   - `DATABASE_URL` &mdash; PostgreSQL connection string (e.g. `postgres://user:password@localhost:5432/weltgewebe`)
   - `NATS_URL` &mdash; URL of the NATS server (e.g. `nats://127.0.0.1:4222`) when messaging is enabled

4. **Run the API**

   ```bash
   cargo run
   ```

   By default the service listens on <http://localhost:8080>.

## Observability

- `GET /health/live` and `GET /health/ready` expose liveness and readiness information.
- `GET /metrics` renders Prometheus metrics including `http_requests_total{method,path}` and `build_info`.

## Development tasks

```bash
# Format the code
cargo fmt -- --check

# Lint
cargo clippy -- -D warnings

# Run tests
cargo test
```

All commands should be executed from the `apps/api` directory unless otherwise noted.
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_api_src.md

**Größe:** 10 KB | **md5:** `00bab7e8852c82731855dc14c52c6cff`

```markdown
### 📄 apps/api/src/config.rs

**Größe:** 4 KB | **md5:** `ee70ae7586941cbd2747fca6b264117b`

```rust
use std::{env, fs, path::Path};

use anyhow::{Context, Result};
use serde::Deserialize;

macro_rules! apply_env_override {
    ($self:ident, $field:ident, $env_var:literal) => {
        if let Ok(value) = env::var($env_var) {
            $self.$field = value
                .parse()
                .with_context(|| format!("failed to parse {} override: {value}", $env_var))?;
        }
    };
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct AppConfig {
    pub fade_days: u32,
    pub ron_days: u32,
    pub anonymize_opt_in: bool,
    pub delegation_expire_days: u32,
}

impl AppConfig {
    const DEFAULT_CONFIG: &'static str = include_str!("../../../configs/app.defaults.yml");

    pub fn load() -> Result<Self> {
        match env::var("APP_CONFIG_PATH") {
            Ok(path) => Self::load_from_path(path),
            Err(_) => {
                let config: Self = serde_yaml::from_str(Self::DEFAULT_CONFIG)
                    .context("failed to parse embedded default configuration")?;
                config.apply_env_overrides()
            }
        }
    }

    pub fn load_from_path(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let raw = fs::read_to_string(path)
            .with_context(|| format!("failed to read configuration file at {}", path.display()))?;
        let config: Self = serde_yaml::from_str(&raw)
            .with_context(|| format!("failed to parse configuration file at {}", path.display()))?;
        config.apply_env_overrides()
    }

    fn apply_env_overrides(mut self) -> Result<Self> {
        apply_env_override!(self, fade_days, "HA_FADE_DAYS");
        apply_env_override!(self, ron_days, "HA_RON_DAYS");
        apply_env_override!(self, anonymize_opt_in, "HA_ANONYMIZE_OPT_IN");
        apply_env_override!(self, delegation_expire_days, "HA_DELEGATION_EXPIRE_DAYS");

        Ok(self)
    }
}

#[cfg(test)]
mod tests {
    use super::AppConfig;
    use crate::test_helpers::{DirGuard, EnvGuard};
    use anyhow::Result;
    use serial_test::serial;
    use tempfile::{tempdir, NamedTempFile};

    const YAML: &str = r#"fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
"#;

    #[test]
    #[serial]
    fn load_from_path_reads_defaults() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::unset("HA_FADE_DAYS");
        let _ron = EnvGuard::unset("HA_RON_DAYS");
        let _anonymize = EnvGuard::unset("HA_ANONYMIZE_OPT_IN");
        let _delegation = EnvGuard::unset("HA_DELEGATION_EXPIRE_DAYS");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert_eq!(cfg.fade_days, 7);
        assert_eq!(cfg.ron_days, 84);
        assert!(cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 28);

        Ok(())
    }

    #[test]
    #[serial]
    fn load_from_path_applies_env_overrides() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::set("HA_FADE_DAYS", "10");
        let _ron = EnvGuard::set("HA_RON_DAYS", "90");
        let _anonymize = EnvGuard::set("HA_ANONYMIZE_OPT_IN", "false");
        let _delegation = EnvGuard::set("HA_DELEGATION_EXPIRE_DAYS", "14");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert_eq!(cfg.fade_days, 10);
        assert_eq!(cfg.ron_days, 90);
        assert!(!cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 14);

        Ok(())
    }

    #[test]
    #[serial]
    fn load_uses_embedded_defaults_when_config_file_missing() -> Result<()> {
        let temp_dir = tempdir()?;
        let _dir = DirGuard::change_to(temp_dir.path())?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::unset("HA_FADE_DAYS");
        let _ron = EnvGuard::unset("HA_RON_DAYS");
        let _anonymize = EnvGuard::unset("HA_ANONYMIZE_OPT_IN");
        let _delegation = EnvGuard::unset("HA_DELEGATION_EXPIRE_DAYS");

        let cfg = AppConfig::load()?;
        assert_eq!(cfg.fade_days, 7);
        assert_eq!(cfg.ron_days, 84);
        assert!(cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 28);

        Ok(())
    }
}
```

### 📄 apps/api/src/main.rs

**Größe:** 4 KB | **md5:** `dc30b3c8002563c00cfe2ad07f824889`

```rust
mod config;
mod routes;
mod state;
mod telemetry;

#[cfg(test)]
mod test_helpers;

use std::{env, io::ErrorKind, net::SocketAddr};

use anyhow::{anyhow, Context};
use async_nats::Client as NatsClient;
use axum::{routing::get, Router};
use config::AppConfig;
use routes::health::health_routes;
use routes::meta::meta_routes;
use sqlx::postgres::PgPoolOptions;
use state::ApiState;
use telemetry::{metrics_handler, BuildInfo, Metrics, MetricsLayer};
use tokio::net::TcpListener;
use tracing_subscriber::{fmt, EnvFilter};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let dotenv = dotenvy::dotenv();
    if let Ok(path) = &dotenv {
        tracing::debug!(?path, "loaded environment variables from .env file");
    }

    if let Err(error) = dotenv {
        match &error {
            dotenvy::Error::Io(io_error) if io_error.kind() == ErrorKind::NotFound => {}
            _ => tracing::warn!(%error, "failed to load environment from .env file"),
        }
    }
    init_tracing()?;

    let app_config = AppConfig::load().context("failed to load API configuration")?;
    let (db_pool, db_pool_configured) = initialise_database_pool().await;
    let (nats_client, nats_configured) = initialise_nats_client().await;

    let metrics = Metrics::try_new(BuildInfo::collect())?;
    let state = ApiState {
        db_pool,
        db_pool_configured,
        nats_client,
        nats_configured,
        config: app_config.clone(),
        metrics: metrics.clone(),
    };

    let app = Router::new()
        .merge(health_routes())
        .merge(meta_routes())
        .route("/metrics", get(metrics_handler))
        .layer(MetricsLayer::new(metrics))
        .with_state(state);

    let bind_addr: SocketAddr = env::var("API_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8080".to_string())
        .parse()
        .context("failed to parse API_BIND address")?;

    tracing::info!(%bind_addr, "starting API server");

    let listener = TcpListener::bind(bind_addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

fn init_tracing() -> anyhow::Result<()> {
    if tracing::dispatcher::has_been_set() {
        return Ok(());
    }

    let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    fmt()
        .with_env_filter(env_filter)
        .try_init()
        .map_err(|error| anyhow!(error))?;

    Ok(())
}

async fn initialise_database_pool() -> (Option<sqlx::PgPool>, bool) {
    let database_url = match env::var("DATABASE_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    let pool = match PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&database_url)
    {
        Ok(pool) => pool,
        Err(error) => {
            tracing::warn!(error = %error, "failed to configure database pool");
            return (None, true);
        }
    };

    match pool.acquire().await {
        Ok(connection) => drop(connection),
        Err(error) => {
            tracing::warn!(
                error = %error,
                "database connection unavailable at startup; readiness will keep retrying",
            );
        }
    }

    (Some(pool), true)
}

async fn initialise_nats_client() -> (Option<NatsClient>, bool) {
    let nats_url = match env::var("NATS_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    match async_nats::connect(&nats_url).await {
        Ok(client) => (Some(client), true),
        Err(error) => {
            tracing::warn!(error = %error, "failed to connect to NATS");
            (None, true)
        }
    }
}
```

### 📄 apps/api/src/state.rs

**Größe:** 615 B | **md5:** `a8b5db0d3a261fbc705eaf927aa0d82a`

```rust
use crate::{config::AppConfig, telemetry::Metrics};
use async_nats::Client as NatsClient;
use sqlx::PgPool;

// ApiState is constructed for future expansion of the API server state. It is
// currently unused by the binary, so we explicitly allow dead code here to keep
// the CI pipeline green while maintaining the transparent intent of the state
// container.
#[allow(dead_code)]
#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub db_pool_configured: bool,
    pub nats_client: Option<NatsClient>,
    pub nats_configured: bool,
    pub config: AppConfig,
    pub metrics: Metrics,
}
```

### 📄 apps/api/src/test_helpers.rs

**Größe:** 1 KB | **md5:** `d67155af27b660b18cae353260709fdc`

```rust
use std::{
    env,
    path::{Path, PathBuf},
};

pub struct EnvGuard {
    key: &'static str,
    original: Option<String>,
}

impl EnvGuard {
    pub fn set(key: &'static str, value: &str) -> Self {
        let original = env::var(key).ok();
        env::set_var(key, value);
        Self { key, original }
    }

    pub fn unset(key: &'static str) -> Self {
        let original = env::var(key).ok();
        env::remove_var(key);
        Self { key, original }
    }
}

impl Drop for EnvGuard {
    fn drop(&mut self) {
        if let Some(ref val) = self.original {
            env::set_var(self.key, val);
        } else {
            env::remove_var(self.key);
        }
    }
}

pub struct DirGuard {
    original: PathBuf,
}

impl DirGuard {
    pub fn change_to(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        let original = env::current_dir()?;
        env::set_current_dir(path.as_ref())?;
        Ok(Self { original })
    }
}

impl Drop for DirGuard {
    fn drop(&mut self) {
        let _ = env::set_current_dir(&self.original);
    }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_api_src_routes.md

**Größe:** 13 KB | **md5:** `ec9f11e56383730fabbc2d444fd9b088`

```markdown
### 📄 apps/api/src/routes/health.rs

**Größe:** 12 KB | **md5:** `0b41ba88dece85a8ee4d84a75b66a1e3`

```rust
use std::{
    env, fs,
    path::{Path, PathBuf},
};

use axum::{
    extract::State,
    http::{header, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde_json::{json, Map};
use sqlx::query_scalar;

use crate::{
    state::ApiState,
    telemetry::health::{readiness_check_failed, readiness_checks_succeeded},
};

pub fn health_routes() -> Router<ApiState> {
    Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
}

async fn live() -> Response {
    let body = Json(json!({ "status": "ok" }));
    let mut response = body.into_response();
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

#[derive(Debug, Default)]
struct CheckResult {
    ready: bool,
    errors: Vec<String>,
}

impl CheckResult {
    fn ready() -> Self {
        Self {
            ready: true,
            errors: Vec::new(),
        }
    }

    fn failure(errors: Vec<String>) -> Self {
        Self {
            ready: false,
            errors,
        }
    }

    fn failure_with_message(message: String) -> Self {
        Self::failure(vec![message])
    }
}

fn readiness_verbose() -> bool {
    env::var("READINESS_VERBOSE")
        .map(|value| {
            let trimmed = value.trim();
            trimmed == "1" || trimmed.eq_ignore_ascii_case("true")
        })
        .unwrap_or(false)
}

fn check_policy_file(path: &Path) -> Result<(), String> {
    fs::read_to_string(path).map(|_| ()).map_err(|error| {
        format!(
            "failed to read policy file at {}: {}",
            path.display(),
            error
        )
    })
}

fn check_policy_fallbacks(paths: &[PathBuf]) -> CheckResult {
    let mut errors = Vec::new();
    for path in paths {
        match check_policy_file(path) {
            Ok(()) => return CheckResult::ready(),
            Err(message) => errors.push(message),
        }
    }

    if !errors.is_empty() {
        for error in &errors {
            readiness_check_failed("policy", error);
        }

        let message = format!(
            "no policy file found in fallback locations: {}",
            paths
                .iter()
                .map(|path| path.display().to_string())
                .collect::<Vec<_>>()
                .join(", ")
        );
        readiness_check_failed("policy", &message);
        errors.push(message);
    }

    CheckResult::failure(errors)
}

async fn check_nats(state: &ApiState) -> CheckResult {
    if !state.nats_configured {
        return CheckResult::ready();
    }

    match state.nats_client.as_ref() {
        Some(client) => match client.flush().await {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("nats", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "client not initialised".to_string();
            readiness_check_failed("nats", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

async fn check_database(state: &ApiState) -> CheckResult {
    if !state.db_pool_configured {
        return CheckResult::ready();
    }

    match state.db_pool.as_ref() {
        Some(pool) => match query_scalar::<_, i32>("SELECT 1")
            .fetch_optional(pool)
            .await
        {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("database", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "connection pool not initialised".to_string();
            readiness_check_failed("database", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

fn check_policy() -> CheckResult {
    // Prefer an explicit configuration via env var to avoid hard-coded path assumptions.
    // Fallbacks stay for dev/CI convenience.
    let env_path = env::var_os("POLICY_LIMITS_PATH").map(PathBuf::from);
    let fallback_paths = [
        Path::new("policies/limits.yaml").to_path_buf(),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies/limits.yaml"),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../policies/limits.yaml"),
    ];

    if let Some(path) = env_path {
        match check_policy_file(&path) {
            Ok(()) => CheckResult::ready(),
            Err(message) => {
                readiness_check_failed("policy", &message);
                CheckResult::failure_with_message(message)
            }
        }
    } else {
        check_policy_fallbacks(&fallback_paths)
    }
}

async fn ready(State(state): State<ApiState>) -> Response {
    let nats = check_nats(&state).await;
    let database = check_database(&state).await;
    let policy = check_policy();

    let status = if database.ready && nats.ready && policy.ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };

    if status == StatusCode::OK {
        readiness_checks_succeeded();
    }

    let verbose = readiness_verbose();

    let body = Json(json!({
        "status": if status == StatusCode::OK { "ok" } else { "error" },
        "checks": {
            "database": database.ready,
            "nats": nats.ready,
            "policy": policy.ready,
        }
    }));

    let mut value = body.0;

    if verbose {
        let mut errors = Map::new();

        if !database.errors.is_empty() {
            errors.insert("database".to_string(), json!(database.errors));
        }

        if !nats.errors.is_empty() {
            errors.insert("nats".to_string(), json!(nats.errors));
        }

        if !policy.errors.is_empty() {
            errors.insert("policy".to_string(), json!(policy.errors));
        }

        if !errors.is_empty() {
            if let Some(object) = value.as_object_mut() {
                object.insert("errors".to_string(), json!(errors));
            }
        }
    }

    let mut response = Json(value).into_response();
    *response.status_mut() = status;
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        config::AppConfig,
        telemetry::{BuildInfo, Metrics},
        test_helpers::EnvGuard,
    };
    use anyhow::Result;
    use axum::{body, extract::State, http::header};
    use serde_json::Value;
    use serial_test::serial;

    fn test_state() -> Result<ApiState> {
        let metrics = Metrics::try_new(BuildInfo {
            version: "test",
            commit: "test",
            build_timestamp: "test",
        })?;

        Ok(ApiState {
            db_pool: None,
            db_pool_configured: false,
            nats_client: None,
            nats_configured: false,
            config: AppConfig {
                fade_days: 7,
                ron_days: 84,
                anonymize_opt_in: true,
                delegation_expire_days: 28,
            },
            metrics,
        })
    }

    #[tokio::test]
    #[serial]
    async fn live_returns_ok_status_and_no_store_header() -> Result<()> {
        let response = live().await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_succeeds_when_optional_dependencies_are_disabled() -> Result<()> {
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_policy_path_is_invalid() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "error");
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], false);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_database_pool_missing() -> Result<()> {
        let mut state = test_state()?;
        state.db_pool_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_nats_client_missing() -> Result<()> {
        let mut state = test_state()?;
        state.nats_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_includes_error_details_when_verbose_enabled() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let _verbose = EnvGuard::set("READINESS_VERBOSE", "1");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["policy"], false);

        let errors = body["errors"]["policy"].as_array().expect("policy errors");
        assert!(!errors.is_empty());
        assert!(errors
            .iter()
            .filter_map(|value| value.as_str())
            .any(|message| message.contains("failed to read policy file")));

        Ok(())
    }
}
```

### 📄 apps/api/src/routes/meta.rs

**Größe:** 443 B | **md5:** `d2117861c4720327645ebeaef03f827e`

```rust
use axum::{routing::get, Json, Router};
use serde_json::{json, Value};

use crate::state::ApiState;
use crate::telemetry::BuildInfo;

pub fn meta_routes() -> Router<ApiState> {
    Router::new().route("/version", get(version))
}

async fn version() -> Json<Value> {
    let info = BuildInfo::collect();
    Json(json!({
        "version": info.version,
        "commit": info.commit,
        "build_timestamp": info.build_timestamp,
    }))
}
```

### 📄 apps/api/src/routes/mod.rs

**Größe:** 30 B | **md5:** `f941dc892dbc498b8ad9b3365a37310b`

```rust
pub mod health;
pub mod meta;
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_api_src_telemetry.md

**Größe:** 5 KB | **md5:** `0747dcb4c4c03d28b9a2444a37ea0b9f`

```markdown
### 📄 apps/api/src/telemetry/health.rs

**Größe:** 279 B | **md5:** `aef976111f6a7ff08c5d92636375a2a2`

```rust
use std::fmt;

pub fn readiness_check_failed(component: &str, error: &(impl fmt::Display + ?Sized)) {
    tracing::warn!(error = %error, %component, "{component} health check failed");
}

pub fn readiness_checks_succeeded() {
    tracing::info!("all readiness checks passed");
}
```

### 📄 apps/api/src/telemetry/mod.rs

**Größe:** 5 KB | **md5:** `3af4a1952918d4b0ea3350147df2b1bf`

```rust
use std::{
    future::Future,
    pin::Pin,
    sync::Arc,
    task::{Context, Poll},
};

pub mod health;

use axum::{
    extract::{MatchedPath, State},
    http::{header, HeaderValue, Request, StatusCode},
    response::{IntoResponse, Response},
};
use prometheus::{Encoder, IntCounterVec, IntGaugeVec, Opts, Registry, TextEncoder};
use tower::{Layer, Service};

use crate::state::ApiState;

#[derive(Clone, Debug)]
pub struct BuildInfo {
    pub version: &'static str,
    pub commit: &'static str,
    pub build_timestamp: &'static str,
}

impl BuildInfo {
    pub fn collect() -> Self {
        Self {
            version: env!("CARGO_PKG_VERSION"),
            commit: option_env!("GIT_COMMIT_SHA").unwrap_or("unknown"),
            build_timestamp: option_env!("BUILD_TIMESTAMP").unwrap_or("unknown"),
        }
    }
}

#[derive(Clone)]
pub struct Metrics {
    inner: Arc<MetricsInner>,
}

struct MetricsInner {
    registry: Registry,
    pub http_requests_total: IntCounterVec,
}

impl Metrics {
    pub fn try_new(build_info: BuildInfo) -> Result<Self, prometheus::Error> {
        let http_opts = Opts::new("http_requests_total", "Total number of HTTP requests");
        let http_requests_total = IntCounterVec::new(http_opts, &["method", "path", "status"])?;

        let build_opts = Opts::new("build_info", "Build information for the API");
        let build_info_metric =
            IntGaugeVec::new(build_opts, &["version", "commit", "build_timestamp"])?;

        let registry = Registry::new();
        registry.register(Box::new(http_requests_total.clone()))?;
        registry.register(Box::new(build_info_metric.clone()))?;

        build_info_metric
            .with_label_values(&[
                build_info.version,
                build_info.commit,
                build_info.build_timestamp,
            ])
            .set(1);

        Ok(Self {
            inner: Arc::new(MetricsInner {
                registry,
                http_requests_total,
            }),
        })
    }

    pub fn http_requests_total(&self) -> &IntCounterVec {
        &self.inner.http_requests_total
    }

    pub fn render(&self) -> Result<Vec<u8>, prometheus::Error> {
        let metric_families = self.inner.registry.gather();
        let encoder = TextEncoder::new();
        let mut buffer = Vec::new();
        encoder.encode(&metric_families, &mut buffer)?;
        Ok(buffer)
    }
}

pub async fn metrics_handler(State(state): State<ApiState>) -> impl IntoResponse {
    let content_type = HeaderValue::from_static("text/plain; version=0.0.4; charset=utf-8");
    match state.metrics.render() {
        Ok(body) => (StatusCode::OK, [(header::CONTENT_TYPE, content_type)], body).into_response(),
        Err(error) => {
            tracing::error!(error = %error, "failed to encode metrics");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

#[derive(Clone)]
pub struct MetricsLayer {
    metrics: Metrics,
}

impl MetricsLayer {
    pub fn new(metrics: Metrics) -> Self {
        Self { metrics }
    }
}

impl<S> Layer<S> for MetricsLayer {
    type Service = MetricsService<S>;

    fn layer(&self, inner: S) -> Self::Service {
        MetricsService {
            inner,
            metrics: self.metrics.clone(),
        }
    }
}

#[derive(Clone)]
pub struct MetricsService<S> {
    inner: S,
    metrics: Metrics,
}

impl<S, B> Service<Request<B>> for MetricsService<S>
where
    S: Service<Request<B>>,
    S::Future: Send + 'static,
    S::Response: IntoResponse,
    B: Send + 'static,
{
    type Response = Response;
    type Error = S::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, request: Request<B>) -> Self::Future {
        let method = request.method().as_str().to_owned();
        let matched_path = request
            .extensions()
            .get::<MatchedPath>()
            .map(|p| p.as_str().to_owned());
        let path = matched_path.unwrap_or_else(|| request.uri().path().to_owned());
        let metrics = self.metrics.clone();
        let future = self.inner.call(request);

        Box::pin(async move {
            match future.await {
                Ok(response) => {
                    let response: Response = response.into_response();
                    let status = response.status().as_u16().to_string();
                    metrics
                        .http_requests_total()
                        .with_label_values(&[method.as_str(), path.as_str(), status.as_str()])
                        .inc();
                    Ok(response)
                }
                Err(error) => Err(error),
            }
        })
    }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_api_tests.md

**Größe:** 512 B | **md5:** `de5d49cb04b696985b495f4478c58e8b`

```markdown
### 📄 apps/api/tests/smoke_k6.js

**Größe:** 390 B | **md5:** `41514ea7ab2202df978f99fce53e76dd`

```javascript
import http from 'k6/http';
import { check } from 'k6';

export const options = { vus: 1, iterations: 3 };

export default function () {
  const res1 = http.get(`${__ENV.BASE_URL}/health/live`);
  check(res1, { 'live 200': r => r.status === 200 });

  const res2 = http.get(`${__ENV.BASE_URL}/health/ready`);
  check(res2, { 'ready 2xx/5xx': r => r.status === 200 || r.status === 503 });
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web.md

**Größe:** 33 KB | **md5:** `69da4795ea778e8bc0bc0f3b56d5953d`

```markdown
### 📄 apps/web/.gitignore

**Größe:** 154 B | **md5:** `54f7490e482e03a6a348adfd9aa787f6`

```plaintext
node_modules
.svelte-kit
build
.DS_Store
public/demo.png
.env
.env.local

# Playwright artifacts
playwright-report/
test-results/
blob-report/
trace.zip
```

### 📄 apps/web/.npmrc

**Größe:** 19 B | **md5:** `e780ac33d3d13827a73886735c3a368b`

```plaintext
engine-strict=true
```

### 📄 apps/web/README.md

**Größe:** 2 KB | **md5:** `3c3b18af589bba248f7f848f79e7776b`

```markdown
# weltgewebe-web (Gate A Click-Dummy)

Frontend-only Prototyp zur Diskussion von UX und Vokabular (Karte, Knoten, Fäden, Drawer, Zeitachse).

## Dev

```bash
cd apps/web
npm ci
npm run dev
```

Standardmäßig läuft der Dev-Server auf `http://localhost:5173/map`.
In Container- oder Codespaces-Umgebungen kannst du optional `npm run dev -- --host --port 5173`
verwenden.

> [!NOTE]
> **Node-Version:** Bitte Node.js ≥ 20.19 (oder ≥ 22.12) verwenden – darunter verweigern Vite und Freunde den Dienst.

### Polyfill-Debugging

Für ältere Safari-/iPadOS-Versionen wird automatisch ein `inert`-Polyfill aktiviert.
Falls du das native Verhalten prüfen möchtest, hänge `?noinert=1` an die URL
(oder setze `window.__NO_INERT__ = true` im DevTools-Console).

### Screenshot aufnehmen

In einem zweiten Terminal (während `npm run dev` läuft):

```bash
npm run screenshot
```

Legt `public/demo.png` an.

## Was kann das?

- Vollbild-Karte (MapLibre) mit 4 Strukturknoten (Platzhalter).
- Linker/rechter Drawer (UI-Stubs), Legende, Zeitachsen-Stub im Footer.
- Keine Persistenz, keine echten Filter/Abfragen (Ethik → UX → Gemeinschaft → Zukunft → Autonomie → Kosten).

## Nächste Schritte

- A-2: Klick auf Marker öffnet Panel mit „Was passiert hier später?“
- A-3: Dummy-Datenlayer (JSON) für 2–3 Knotentypen, 2 Fadenfarben
- A-4: Accessibility-Pass 1 (Fokus, Kontrast)
- A-5: Dev-Overlay: Bundle-Größe (Budget ≤ ~90KB Initial-JS)

## Tests

### Playwright (Drawer + Keyboard)

```bash
npx playwright install --with-deps  # einmalig
npx playwright test tests/drawers.spec.ts
```

Die Tests setzen in `beforeEach` das Flag `window.__E2E__ = true`, damit Maus-Drags die Swipe-Gesten simulieren können.
```

### 📄 apps/web/eslint.config.js

**Größe:** 964 B | **md5:** `07731461ec97002acab7a87a553106af`

```javascript
import js from "@eslint/js";
import globals from "globals";
import svelte from "eslint-plugin-svelte";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

const IGNORE = [
  ".svelte-kit/",
  "build/",
  "dist/",
  "node_modules/",
  "public/demo.png",
  "scripts/record-screenshot.mjs"
];

export default [
  {
    ignores: IGNORE
  },
  ...svelte.configs["flat/recommended"],
  {
    files: ["**/*.svelte"],
    rules: {
      "svelte/no-at-html-tags": "error"
    }
  },
  {
    files: ["**/*.ts", "**/*.js"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2023,
        sourceType: "module"
      },
      globals: globals.browser
    },
    plugins: {
      "@typescript-eslint": tsPlugin
    },
    rules: {
      ...js.configs.recommended.rules,
      ...tsPlugin.configs["recommended"].rules,
      "@typescript-eslint/no-explicit-any": "off"
    }
  }
];
```

### 📄 apps/web/package-lock.json

**Größe:** 63 KB | **md5:** `d306b5235616f5e9d79048e2ae6fbadc`

```json
{
  "name": "weltgewebe-web",
  "version": "0.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "weltgewebe-web",
      "version": "0.0.0",
      "hasInstallScript": true,
      "dependencies": {
        "maplibre-gl": "4.7.1"
      },
      "devDependencies": {
        "@playwright/test": "1.55.1",
        "@sveltejs/adapter-auto": "6.1.0",
        "@sveltejs/kit": "^2.47.2",
        "@typescript-eslint/eslint-plugin": "8.8.0",
        "@typescript-eslint/parser": "8.8.0",
        "eslint": "9.11.1",
        "eslint-plugin-svelte": "2.45.1",
        "globals": "15.9.0",
        "playwright": "1.55.1",
        "prettier": "3.3.3",
        "prettier-plugin-svelte": "3.2.6",
        "svelte": "5.39.6",
        "svelte-check": "^4.3.2",
        "typescript": "5.9.2",
        "vite": "^7.1.11"
      },
      "engines": {
        "node": ">=20.19.0"
      }
    },
    "node_modules/@esbuild/aix-ppc64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.25.10.tgz",
      "integrity": "sha512-0NFWnA+7l41irNuaSVlLfgNT12caWJVLzp5eAVhZ0z1qpxbockccEt3s+149rE64VUI3Ml2zt8Nv5JVc4QXTsw==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "aix"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.25.10.tgz",
      "integrity": "sha512-dQAxF1dW1C3zpeCDc5KqIYuZ1tgAdRXNoZP7vkBIRtKZPYe2xVr/d3SkirklCHudW1B45tGiUlz2pUWDfbDD4w==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.25.10.tgz",
      "integrity": "sha512-LSQa7eDahypv/VO6WKohZGPSJDq5OVOo3UoFR1E4t4Gj1W7zEQMUhI+lo81H+DtB+kP+tDgBp+M4oNCwp6kffg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.25.10.tgz",
      "integrity": "sha512-MiC9CWdPrfhibcXwr39p9ha1x0lZJ9KaVfvzA0Wxwz9ETX4v5CHfF09bx935nHlhi+MxhA63dKRRQLiVgSUtEg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.25.10.tgz",
      "integrity": "sha512-JC74bdXcQEpW9KkV326WpZZjLguSZ3DfS8wrrvPMHgQOIEIG/sPXEN/V8IssoJhbefLRcRqw6RQH2NnpdprtMA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.25.10.tgz",
      "integrity": "sha512-tguWg1olF6DGqzws97pKZ8G2L7Ig1vjDmGTwcTuYHbuU6TTjJe5FXbgs5C1BBzHbJ2bo1m3WkQDbWO2PvamRcg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.25.10.tgz",
      "integrity": "sha512-3ZioSQSg1HT2N05YxeJWYR+Libe3bREVSdWhEEgExWaDtyFbbXWb49QgPvFH8u03vUPX10JhJPcz7s9t9+boWg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.25.10.tgz",
      "integrity": "sha512-LLgJfHJk014Aa4anGDbh8bmI5Lk+QidDmGzuC2D+vP7mv/GeSN+H39zOf7pN5N8p059FcOfs2bVlrRr4SK9WxA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.25.10.tgz",
      "integrity": "sha512-oR31GtBTFYCqEBALI9r6WxoU/ZofZl962pouZRTEYECvNF/dtXKku8YXcJkhgK/beU+zedXfIzHijSRapJY3vg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.25.10.tgz",
      "integrity": "sha512-5luJWN6YKBsawd5f9i4+c+geYiVEw20FVW5x0v1kEMWNq8UctFjDiMATBxLvmmHA4bf7F6hTRaJgtghFr9iziQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ia32": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.25.10.tgz",
      "integrity": "sha512-NrSCx2Kim3EnnWgS4Txn0QGt0Xipoumb6z6sUtl5bOEZIVKhzfyp/Lyw4C1DIYvzeW/5mWYPBFJU3a/8Yr75DQ==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-loong64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.25.10.tgz",
      "integrity": "sha512-xoSphrd4AZda8+rUDDfD9J6FUMjrkTz8itpTITM4/xgerAZZcFW7Dv+sun7333IfKxGG8gAq+3NbfEMJfiY+Eg==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-mips64el": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.25.10.tgz",
      "integrity": "sha512-ab6eiuCwoMmYDyTnyptoKkVS3k8fy/1Uvq7Dj5czXI6DF2GqD2ToInBI0SHOp5/X1BdZ26RKc5+qjQNGRBelRA==",
      "cpu": [
        "mips64el"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ppc64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.25.10.tgz",
      "integrity": "sha512-NLinzzOgZQsGpsTkEbdJTCanwA5/wozN9dSgEl12haXJBzMTpssebuXR42bthOF3z7zXFWH1AmvWunUCkBE4EA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-riscv64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.25.10.tgz",
      "integrity": "sha512-FE557XdZDrtX8NMIeA8LBJX3dC2M8VGXwfrQWU7LB5SLOajfJIxmSdyL/gU1m64Zs9CBKvm4UAuBp5aJ8OgnrA==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-s390x": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.25.10.tgz",
      "integrity": "sha512-3BBSbgzuB9ajLoVZk0mGu+EHlBwkusRmeNYdqmznmMc9zGASFjSsxgkNsqmXugpPk00gJ0JNKh/97nxmjctdew==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.25.10.tgz",
      "integrity": "sha512-QSX81KhFoZGwenVyPoberggdW1nrQZSvfVDAIUXr3WqLRZGZqWk/P4T8p2SP+de2Sr5HPcvjhcJzEiulKgnxtA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.25.10.tgz",
      "integrity": "sha512-AKQM3gfYfSW8XRk8DdMCzaLUFB15dTrZfnX8WXQoOUpUBQ+NaAFCP1kPS/ykbbGYz7rxn0WS48/81l9hFl3u4A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.25.10.tgz",
      "integrity": "sha512-7RTytDPGU6fek/hWuN9qQpeGPBZFfB4zZgcz2VK2Z5VpdUxEI8JKYsg3JfO0n/Z1E/6l05n0unDCNc4HnhQGig==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.25.10.tgz",
      "integrity": "sha512-5Se0VM9Wtq797YFn+dLimf2Zx6McttsH2olUBsDml+lm0GOCRVebRWUvDtkY4BWYv/3NgzS8b/UM3jQNh5hYyw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.25.10.tgz",
      "integrity": "sha512-XkA4frq1TLj4bEMB+2HnI0+4RnjbuGZfet2gs/LNs5Hc7D89ZQBHQ0gL2ND6Lzu1+QVkjp3x1gIcPKzRNP8bXw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openharmony-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openharmony-arm64/-/openharmony-arm64-0.25.10.tgz",
      "integrity": "sha512-AVTSBhTX8Y/Fz6OmIVBip9tJzZEUcY8WLh7I59+upa5/GPhh2/aM6bvOMQySspnCCHvFi79kMtdJS1w0DXAeag==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openharmony"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/sunos-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.25.10.tgz",
      "integrity": "sha512-fswk3XT0Uf2pGJmOpDB7yknqhVkJQkAQOcW/ccVOtfx05LkbWOaRAtn5SaqXypeKQra1QaEa841PgrSL9ubSPQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "sunos"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.25.10.tgz",
      "integrity": "sha512-ah+9b59KDTSfpaCg6VdJoOQvKjI33nTaQr4UluQwW7aEwZQsbMCfTmfEO4VyewOxx4RaDT/xCy9ra2GPWmO7Kw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-ia32": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.25.10.tgz",
      "integrity": "sha512-QHPDbKkrGO8/cz9LKVnJU22HOi4pxZnZhhA2HYHez5Pz4JeffhDjf85E57Oyco163GnzNCVkZK0b/n4Y0UHcSw==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.25.10.tgz",
      "integrity": "sha512-9KpxSVFCu0iK1owoez6aC/s/EdUQLDN3adTxGCqxMVhrPDj6bt5dbrHDXUuq+Bs2vATFBBrQS5vdQ/Ed2P+nbw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmjs.org/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "dev": true,
      "dependencies": {
        "@jridgewell/sourcemap-codec": "1.5.5",
        "@jridgewell/trace-mapping": "0.3.31"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "dev": true,
      "dependencies": {
        "@jridgewell/gen-mapping": "0.3.13",
        "@jridgewell/trace-mapping": "0.3.31"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "dev": true,
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "dev": true
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmjs.org/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "dev": true,
      "dependencies": {
        "@jridgewell/resolve-uri": "3.1.2",
        "@jridgewell/sourcemap-codec": "1.5.5"
      }
    },
    "node_modules/@mapbox/geojson-rewind": {
      "version": "0.5.2",
      "resolved": "https://registry.npmjs.org/@mapbox/geojson-rewind/-/geojson-rewind-0.5.2.tgz",
      "integrity": "sha512-tJaT+RbYGJYStt7wI3cq4Nl4SXxG8W7JDG5DMJu97V25RnbNg3QtQtf+KD+VLjNpWKYsRvXDNmNrBgEETr1ifA==",
      "dependencies": {
        "get-stream": "6.0.1",
        "minimist": "1.2.8"
      }
    },
    "node_modules/@mapbox/jsonlint-lines-primitives": {
      "version": "2.0.2",
      "resolved": "https://registry.npmjs.org/@mapbox/jsonlint-lines-primitives/-/jsonlint-lines-primitives-2.0.2.tgz",
      "integrity": "sha512-rY0o9A5ECsTQRVhv7tL/OyDpGAoUB4tTvLiW1DSzQGq4bvTPhNw1VpSNjDJc5GFZ2XuyOtSWSVN05qOtcD71qQ==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/@mapbox/point-geometry": {
      "version": "0.1.0",
      "resolved": "https://registry.npmjs.org/@mapbox/point-geometry/-/point-geometry-0.1.0.tgz",
      "integrity": "sha512-6j56HdLTwWGO0fJPlrZtdU/B13q8Uwmo18Ck2GnGgN9PCFyKTZ3UbXeEdRFh18i9XQ92eH2VdtpJHpBD3aripQ=="
    },
    "node_modules/@mapbox/tiny-sdf": {
      "version": "2.0.7",
      "resolved": "https://registry.npmjs.org/@mapbox/tiny-sdf/-/tiny-sdf-2.0.7.tgz",
      "integrity": "sha512-25gQLQMcpivjOSA40g3gO6qgiFPDpWRoMfd+G/GoppPIeP6JDaMMkMrEJnMZhKyyS6iKwVt5YKu02vCUyJM3Ug=="
    },
    "node_modules/@mapbox/unitbezier": {
      "version": "0.0.1",
      "resolved": "https://registry.npmjs.org/@mapbox/unitbezier/-/unitbezier-0.0.1.tgz",
      "integrity": "sha512-nMkuDXFv60aBr9soUG5q+GvZYL+2KZHVvsqFCzqnkGEf46U2fvmytHaEVc1/YZbiLn8X+eR3QzX1+dwDO1lxlw=="
    },
    "node_modules/@mapbox/vector-tile": {
      "version": "1.3.1",
      "resolved": "https://registry.npmjs.org/@mapbox/vector-tile/-/vector-tile-1.3.1.tgz",
      "integrity": "sha512-MCEddb8u44/xfQ3oD+Srl/tNcQoqTw3goGk2oLsrFxOTc3dUp+kAnby3PvAeeBYSMSjSPD1nd1AJA6W49WnoUw==",
      "dependencies": {
        "@mapbox/point-geometry": "0.1.0"
      }
    },
    "node_modules/@mapbox/whoots-js": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/@mapbox/whoots-js/-/whoots-js-3.1.0.tgz",
      "integrity": "sha512-Es6WcD0nO5l+2BOQS4uLfNPYQaNDfbot3X1XUoloz+x0mPDS3eeORZJl06HXjwBG1fOGwCRnzK88LMdxKRrd6Q==",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@maplibre/maplibre-gl-style-spec": {
      "version": "20.4.0",
      "resolved": "https://registry.npmjs.org/@maplibre/maplibre-gl-style-spec/-/maplibre-gl-style-spec-20.4.0.tgz",
      "integrity": "sha512-AzBy3095fTFPjDjmWpR2w6HVRAZJ6hQZUCwk5Plz6EyfnfuQW1odeW5i2Ai47Y6TBA2hQnC+azscjBSALpaWgw==",
      "dependencies": {
        "@mapbox/jsonlint-lines-primitives": "2.0.2",
        "@mapbox/unitbezier": "0.0.1",
        "json-stringify-pretty-compact": "4.0.0",
        "minimist": "1.2.8",
        "quickselect": "2.0.0",
        "rw": "1.3.3",
        "tinyqueue": "3.0.0"
      }
    },
    "node_modules/@playwright/test": {
      "version": "1.55.1",
      "resolved": "https://registry.npmjs.org/@playwright/test/-/test-1.55.1.tgz",
      "integrity": "sha512-IVAh/nOJaw6W9g+RJVlIQJ6gSiER+ae6mKQ5CX1bERzQgbC1VSeBlwdvczT7pxb0GWiyrxH4TGKbMfDb4Sq/ig==",
      "dev": true,
      "dependencies": {
        "playwright": "1.55.1"
      },
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@polka/url": {
      "version": "1.0.0-next.29",
      "resolved": "https://registry.npmjs.org/@polka/url/-/url-1.0.0-next.29.tgz",
      "integrity": "sha512-wwQAWhWSuHaag8c4q/KN/vCoeOJYshAIvMQwD4GpSb3OiZklFfvAgmj0VCBBImRpuF/aFgIRzllXlVX93Jevww==",
      "dev": true
    },
    "node_modules/@rollup/rollup-android-arm-eabi": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.52.3.tgz",
      "integrity": "sha512-h6cqHGZ6VdnwliFG1NXvMPTy/9PS3h8oLh7ImwR+kl+oYnQizgjxsONmmPSb2C66RksfkfIxEVtDSEcJiO0tqw==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-android-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.52.3.tgz",
      "integrity": "sha512-wd+u7SLT/u6knklV/ifG7gr5Qy4GUbH2hMWcDauPFJzmCZUAJ8L2bTkVXC2niOIxp8lk3iH/QX8kSrUxVZrOVw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-darwin-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.52.3.tgz",
      "integrity": "sha512-lj9ViATR1SsqycwFkJCtYfQTheBdvlWJqzqxwc9f2qrcVrQaF/gCuBRTiTolkRWS6KvNxSk4KHZWG7tDktLgjg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-darwin-x64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.52.3.tgz",
      "integrity": "sha512-+Dyo7O1KUmIsbzx1l+4V4tvEVnVQqMOIYtrxK7ncLSknl1xnMHLgn7gddJVrYPNZfEB8CIi3hK8gq8bDhb3h5A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.52.3.tgz",
      "integrity": "sha512-u9Xg2FavYbD30g3DSfNhxgNrxhi6xVG4Y6i9Ur1C7xUuGDW3banRbXj+qgnIrwRN4KeJ396jchwy9bCIzbyBEQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-x64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.52.3.tgz",
      "integrity": "sha512-5M8kyi/OX96wtD5qJR89a/3x5x8x5inXBZO04JWhkQb2JWavOWfjgkdvUqibGJeNNaz1/Z1PPza5/tAPXICI6A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_public.md

**Größe:** 118 B | **md5:** `e65ac4b24765c66faa7a921b98910e58`

```markdown
### 📄 apps/web/public/.gitkeep

**Größe:** 0 B | **md5:** `d41d8cd98f00b204e9800998ecf8427e`

```plaintext

```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_scripts.md

**Größe:** 3 KB | **md5:** `411c67fbe576f1be225021b8ff009ab8`

```markdown
### 📄 apps/web/scripts/record-screenshot.mjs

**Größe:** 424 B | **md5:** `399bbca4f4d3a269a3a9abdde909f5f1`

```plaintext
// record-screenshot.mjs
import puppeteer from "puppeteer";

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto("http://localhost:5173/map");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "public/demo.png", fullPage: true });
  console.log("✅ Screenshot gespeichert: public/demo.png");
  await browser.close();
})();
```

### 📄 apps/web/scripts/verify-cookie-version.js

**Größe:** 2 KB | **md5:** `9ba39a27476a451a6f6634933ce66d4f`

```javascript
import { createRequire } from 'node:module';

// Fail fast in CI if the lockfile resolves to a vulnerable cookie version.
// Skip silently when cookie isn't present (e.g. npm ci --omit=dev / production).
// This guards against transitive downgrades or accidental removal of `overrides`.
const require = createRequire(import.meta.url);
// CI is truthy on most providers; treat explicit "false" as off.
const isCI = !!process.env.CI && process.env.CI !== 'false';

// Minimal semver check for our purposes: we just need to know if a version is
// less than the minimum safe version, using exact numeric components.
const semverLt = (a, b) => {
  const aParts = a.split('.').map(Number);
  const bParts = b.split('.').map(Number);
  for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
    const aVal = aParts[i] || 0;
    const bVal = bParts[i] || 0;
    if (aVal < bVal) return true;
    if (aVal > bVal) return false;
  }
  return false;
};

// Helper: detect common "module not found" shapes across Node/ESM.
const isModuleNotFound = (err) =>
  err?.code === 'MODULE_NOT_FOUND' ||
  err?.code === 'ERR_MODULE_NOT_FOUND' ||
  /Cannot find module/.test(String(err?.message || err));

try {
  const pkg = require('cookie/package.json');
  const installed = pkg?.version;
  const minSafe = '0.7.0';
  if (semverLt(installed, minSafe)) {
    const msg =
      `\n[security] cookie@${installed} detected (< ${minSafe}). ` +
      `The advisory requires ${minSafe}+ — check npm overrides and lockfile.\n`;
    if (isCI) {
      console.error(msg);
      process.exit(1);
    } else {
      console.warn(msg.trim(), '\n(continuing locally)');
      process.exit(0);
    }
  }
} catch (err) {
  // If cookie is not installed at all (e.g. prod install without dev deps),
  // skip the check so production installs still succeed.
  if (isModuleNotFound(err)) {
    // Quiet skip — production deploys often omit dev deps.
    process.exit(0);
  }
  // Other errors: strict in CI, lenient locally.
  const msg =
    `\n[security] Could not verify cookie version (unexpected error): ${err?.message || err}`;
  if (isCI) {
    console.error(msg);
    process.exit(1);
  }
  console.warn(msg, '\n(continuing locally)');
  process.exit(0);
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src.md

**Größe:** 2 KB | **md5:** `a19706ae1dfa55eea2022a2e4b634b1d`

```markdown
### 📄 apps/web/src/app.css

**Größe:** 1 KB | **md5:** `4471946c3c1af41300f0c6804b38f808`

```css
/* Minimal, utility-light Styles für Click-Dummy */
:root { --bg:#0b0e12; --fg:#e7ebee; --muted:#9aa3ad; --panel:#141a21; --accent:#7cc4ff; }
html,body,#app { height:100%; margin:0; }
body { background:var(--bg); color:var(--fg); font: 14px/1.4 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial; }
.row { display:flex; gap:.75rem; align-items:center; }
.col { display:flex; flex-direction:column; gap:.5rem; }
.panel { background:var(--panel); border:1px solid #1f2630; border-radius:12px; padding:.75rem; }
.badge { border:1px solid #223244; padding:.15rem .45rem; border-radius:999px; color:var(--muted); }
.ghost { opacity:.7 }
.divider { height:1px; background:#1f2630; margin:.5rem 0; }
.btn { padding:.4rem .6rem; border:1px solid #263240; background:#101821; color:var(--fg); border-radius:8px; cursor:pointer }
.btn:disabled { opacity:.5; cursor:not-allowed }
.legend-dot { width:.8rem; height:.8rem; border-radius:999px; display:inline-block; margin-right:.4rem; vertical-align:middle }
.dot-blue{background:#4ea1ff}.dot-gray{background:#9aa3ad}.dot-yellow{background:#ffd65a}.dot-red{background:#ff6b6b}.dot-green{background:#54e1a6}.dot-violet{background:#b392f0}
```

### 📄 apps/web/src/app.d.ts

**Größe:** 112 B | **md5:** `c20a78b8e768a570c00cb0fd7e016b4e`

```typescript
// See https://kit.svelte.dev/docs/types
// for information about these interfaces
declare global {}
export {};
```

### 📄 apps/web/src/app.html

**Größe:** 286 B | **md5:** `e8f20d9bbdd6b5d1b19d651a703e0d1a`

```html
<!doctype html>
<html lang="en">
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		%sveltekit.head%
	</head>
	<body data-sveltekit-preload-data="hover">
		<div style="display: contents">%sveltekit.body%</div>
	</body>
</html>
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_lib.md

**Größe:** 195 B | **md5:** `0a51e2135e41895e4f62908a655b009c`

```markdown
### 📄 apps/web/src/lib/index.ts

**Größe:** 75 B | **md5:** `ffcb0e97b69eb555d5739e9efe961ca0`

```typescript
// place files you want to import through the `$lib` alias in this folder.
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_lib_assets.md

**Größe:** 2 KB | **md5:** `432eaee4a1fd1dcb37397beeb3dc3ea0`

```markdown
### 📄 apps/web/src/lib/assets/favicon.svg

**Größe:** 2 KB | **md5:** `a0d1b540c1b9a2a920d5f6cae983118a`

```plaintext
<svg xmlns="http://www.w3.org/2000/svg" width="107" height="128" viewBox="0 0 107 128"><title>svelte-logo</title><path d="M94.157 22.819c-10.4-14.885-30.94-19.297-45.792-9.835L22.282 29.608A29.92 29.92 0 0 0 8.764 49.65a31.5 31.5 0 0 0 3.108 20.231 30 30 0 0 0-4.477 11.183 31.9 31.9 0 0 0 5.448 24.116c10.402 14.887 30.942 19.297 45.791 9.835l26.083-16.624A29.92 29.92 0 0 0 98.235 78.35a31.53 31.53 0 0 0-3.105-20.232 30 30 0 0 0 4.474-11.182 31.88 31.88 0 0 0-5.447-24.116" style="fill:#ff3e00"/><path d="M45.817 106.582a20.72 20.72 0 0 1-22.237-8.243 19.17 19.17 0 0 1-3.277-14.503 18 18 0 0 1 .624-2.435l.49-1.498 1.337.981a33.6 33.6 0 0 0 10.203 5.098l.97.294-.09.968a5.85 5.85 0 0 0 1.052 3.878 6.24 6.24 0 0 0 6.695 2.485 5.8 5.8 0 0 0 1.603-.704L69.27 76.28a5.43 5.43 0 0 0 2.45-3.631 5.8 5.8 0 0 0-.987-4.371 6.24 6.24 0 0 0-6.698-2.487 5.7 5.7 0 0 0-1.6.704l-9.953 6.345a19 19 0 0 1-5.296 2.326 20.72 20.72 0 0 1-22.237-8.243 19.17 19.17 0 0 1-3.277-14.502 17.99 17.99 0 0 1 8.13-12.052l26.081-16.623a19 19 0 0 1 5.3-2.329 20.72 20.72 0 0 1 22.237 8.243 19.17 19.17 0 0 1 3.277 14.503 18 18 0 0 1-.624 2.435l-.49 1.498-1.337-.98a33.6 33.6 0 0 0-10.203-5.1l-.97-.294.09-.968a5.86 5.86 0 0 0-1.052-3.878 6.24 6.24 0 0 0-6.696-2.485 5.8 5.8 0 0 0-1.602.704L37.73 51.72a5.42 5.42 0 0 0-2.449 3.63 5.79 5.79 0 0 0 .986 4.372 6.24 6.24 0 0 0 6.698 2.486 5.8 5.8 0 0 0 1.602-.704l9.952-6.342a19 19 0 0 1 5.295-2.328 20.72 20.72 0 0 1 22.237 8.242 19.17 19.17 0 0 1 3.277 14.503 18 18 0 0 1-8.13 12.053l-26.081 16.622a19 19 0 0 1-5.3 2.328" style="fill:#fff"/></svg>
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_lib_components.md

**Größe:** 19 KB | **md5:** `ffb6ea33e76fdfbd421ffaafd1e28600`

```markdown
### 📄 apps/web/src/lib/components/AppShell.svelte

**Größe:** 2 KB | **md5:** `e14cf8f1ddf8c953d273dc988768a07e`

```svelte
<script lang="ts">
  export let title = "Weltgewebe – Click-Dummy";
  export let timeCursor: string = "T-0";
</script>

<div class="app-shell">
  <header class="app-bar panel" aria-label="Navigation und Status">
    <div class="brand">
      <div class="brand-main">
        <strong>{title}</strong>
        <span class="badge">Gate A</span>
      </div>
      <p class="brand-sub ghost">Frontend-only Prototype · UX vor Code</p>
    </div>
    <div class="header-actions">
      <slot name="gewebekonto" />
      <slot name="topright" />
    </div>
  </header>
  <main class="app-main">
    <slot />
  </main>
  <footer class="app-footer panel" aria-label="Zeitachse (Attrappe)">
    <div>Zeitachse: Cursor <span class="badge">{timeCursor}</span></div>
    <div class="ghost">Replay deaktiviert · Gate B/C folgen</div>
  </footer>
</div>

<style>
  .app-shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 0.75rem;
    padding: 0.75rem;
    box-sizing: border-box;
  }

  .app-bar {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .brand {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .brand-main {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .brand-sub {
    margin: 0;
  }

  .header-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .header-actions :global(.btn:focus-visible),
  .header-actions :global(button:focus-visible),
  .header-actions :global(a:focus-visible) {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
    border-radius: 0.5rem;
  }

  .app-main {
    position: relative;
    overflow: hidden;
    border-radius: 18px;
  }

  .app-footer {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  @media (min-width: 42rem) {
    .app-bar {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }

    .header-actions {
      flex-direction: row;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .app-footer {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/Drawer.svelte

**Größe:** 3 KB | **md5:** `8f7f125feb0ee4383ac90c07627d16f5`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';

  export let title = '';
  export let open = false;
  export let side: 'left' | 'right' | 'top' = 'left';
  export let id: string | undefined;

  const dispatch = createEventDispatcher<{ open: void; close: void }>();

  let headingId: string | undefined;
  let drawerId: string;
  $: drawerId = id ?? `${side}-drawer`;
  $: headingId = title ? `${drawerId}-title` : undefined;

  let rootEl: HTMLDivElement | null = null;
  let openerEl: HTMLElement | null = null;
  export function setOpener(el: HTMLElement | null) {
    openerEl = el;
  }

  function focusFirstInside() {
    if (!rootEl) return;
    const focusables = Array.from(
      rootEl.querySelectorAll<HTMLElement>(
        'button:not([tabindex="-1"]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => !element.hasAttribute('disabled'));

    (focusables[0] ?? rootEl).focus();
  }

  async function handleOpen() {
    await tick();
    focusFirstInside();
    dispatch('open');
  }

  async function handleClose() {
    await tick();
    openerEl?.focus();
    dispatch('close');
  }

  let hasMounted = false;
  onMount(() => {
    hasMounted = true;
  });

  let previousOpen = open;
  $: if (hasMounted && open !== previousOpen) {
    if (open) {
      handleOpen();
    } else {
      handleClose();
    }
    previousOpen = open;
  }
</script>

<style>
  .drawer{
    position:absolute; z-index:26; padding:var(--drawer-gap); color:var(--text);
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow);
    transform: translateY(calc(-1 * var(--drawer-slide-offset)));
    opacity:0;
    pointer-events:none;
    transition:.18s ease;
    overscroll-behavior: contain;
  }
  .drawer.open{ transform:none; opacity:1; pointer-events:auto; }
  .left{
    left:var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
    border-radius: var(--radius);
  }
  .right{
    right:var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
  }
  .top{
    left:50%;
    transform:translate(-50%, calc(-1 * var(--drawer-slide-offset)));
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    width:min(860px, calc(100vw - (2 * var(--drawer-gap))));
  }
  .top.open{ transform:translate(-50%,0); }
  h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .section{ margin-bottom:12px; padding:10px; border:1px solid var(--panel-border); border-radius:10px; background:rgba(255,255,255,0.02); }
  @media (prefers-reduced-motion: reduce){
    .drawer{ transition:none; }
  }
</style>

<div
  bind:this={rootEl}
  id={drawerId}
  class="drawer"
  class:open={open}
  class:left={side === 'left'}
  class:right={side === 'right'}
  class:top={side === 'top'}
  aria-hidden={!open}
  aria-labelledby={headingId}
  tabindex="-1"
  role="complementary"
  inert={!open ? true : undefined}
  {...$$restProps}
>
  {#if title}<h3 id={headingId}>{title}</h3>{/if}
  <slot />
  <slot name="footer" />
  <slot name="overlays" />
</div>
```

### 📄 apps/web/src/lib/components/DrawerLeft.svelte

**Größe:** 3 KB | **md5:** `6ae20720a86d772bc2ad352b6e991833`

```svelte
<script lang="ts">
  type TabId = 'webrat' | 'naehstuebchen';

  export let open = true;
  let tab: TabId = 'webrat';
  let webratButton: HTMLButtonElement | null = null;
  let naehstuebchenButton: HTMLButtonElement | null = null;

  const orderedTabs: TabId[] = ['webrat', 'naehstuebchen'];

  function select(next: TabId, focus = false) {
    tab = next;
    if (focus) {
      (next === 'webrat' ? webratButton : naehstuebchenButton)?.focus();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    const { key } = event;
    if (key === 'ArrowLeft' || key === 'ArrowRight' || key === 'Home' || key === 'End') {
      event.preventDefault();
      const currentIndex = orderedTabs.indexOf(tab);
      if (key === 'Home') {
        select(orderedTabs[0], true);
        return;
      }

      if (key === 'End') {
        select(orderedTabs[orderedTabs.length - 1], true);
        return;
      }

      const delta = key === 'ArrowRight' ? 1 : -1;
      const nextIndex = (currentIndex + delta + orderedTabs.length) % orderedTabs.length;
      select(orderedTabs[nextIndex], true);
    }
  }
</script>

{#if open}
<aside class="panel drawer drawer-left" aria-label="Primärer Bereichs-Drawer">
  <div
    class="row"
    style="gap:.5rem"
    role="tablist"
    aria-label="Bereich auswählen"
    aria-orientation="horizontal"
    on:keydown={handleKeydown}
  >
    <button
      class="btn"
      id="drawer-tab-webrat"
      role="tab"
      aria-selected={tab === 'webrat'}
      aria-controls="drawer-panel-webrat"
      type="button"
      tabindex={tab === 'webrat' ? 0 : -1}
      bind:this={webratButton}
      on:click={() => select('webrat')}
    >
      Webrat
    </button>
    <button
      class="btn"
      id="drawer-tab-naehstuebchen"
      role="tab"
      aria-selected={tab === 'naehstuebchen'}
      aria-controls="drawer-panel-naehstuebchen"
      type="button"
      tabindex={tab === 'naehstuebchen' ? 0 : -1}
      bind:this={naehstuebchenButton}
      on:click={() => select('naehstuebchen')}
    >
      Nähstübchen
    </button>
  </div>
  <div class="divider"></div>
  {#if tab === 'webrat'}
    <div id="drawer-panel-webrat" role="tabpanel" aria-labelledby="drawer-tab-webrat">
      <p>Platzhalter – „coming soon“ (Diskussionen/Abstimmungen)</p>
    </div>
  {:else}
    <div id="drawer-panel-naehstuebchen" role="tabpanel" aria-labelledby="drawer-tab-naehstuebchen">
      <p>Platzhalter – „coming soon“ (Community-Werkzeuge)</p>
    </div>
  {/if}
</aside>
{/if}

<style>
  .drawer {
    position: absolute;
    z-index: 2;
    left: 50%;
    transform: translateX(-50%);
    bottom: 12rem;
    width: min(22rem, calc(100% - 1.5rem));
    max-height: min(45vh, 22rem);
    overflow: auto;
  }

  .drawer :global(p) {
    margin: 0;
  }

  .drawer [role="tab"] {
    outline: none;
  }

  .drawer [role="tab"]:focus-visible {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
  }

  @media (min-width: 48rem) {
    .drawer {
      top: clamp(0.75rem, 2vw, 1.5rem);
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      left: clamp(0.75rem, 2vw, 1.5rem);
      transform: none;
      width: min(20rem, 28vw);
      max-height: none;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/DrawerRight.svelte

**Größe:** 3 KB | **md5:** `c2df462c5482b6b2bf4769f21b32a08f`

```svelte
<script lang="ts">
  export let open = true;
  // UI-State nur im Frontend; keine Persistenz
  let distance = 3;
  const filters = {
    knotentypen: {
      strukturknoten: true,
      faeden: false
    },
    bedarf: {
      bohrmaschine: false,
      schlafplatz: false,
      kinderspass: false,
      essen: false
    }
  };
</script>

{#if open}
<aside
  class="panel drawer drawer-right"
  aria-label="Filter- und Such-Drawer (inaktiv)"
  aria-describedby="filters-disabled-note"
>
  <strong>Suche</strong>
  <label class="col">
    <span class="ghost">Stichwort oder Adresse</span>
    <input type="search" placeholder="z. B. Reparatur" disabled />
  </label>
  <div class="divider"></div>
  <strong>Filter (stummgeschaltet)</strong>
  <div class="divider"></div>
  <div class="col">
    <label class="row"><input type="checkbox" bind:checked={filters.knotentypen.strukturknoten} disabled> Strukturknoten</label>
    <label class="row"><input type="checkbox" bind:checked={filters.knotentypen.faeden} disabled> Fäden</label>
  </div>
  <div class="divider"></div>
  <strong>Bedarf</strong>
  <div class="col">
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.bohrmaschine} disabled> Bohrmaschine</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.schlafplatz} disabled> Schlafplatz</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.kinderspass} disabled> Kinderspaß</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.essen} disabled> Essen</label>
  </div>
  <div class="divider"></div>
  <label class="col">
    <span>Distanz (km) – UI only</span>
    <input type="range" min="1" max="15" bind:value={distance} disabled />
    <span class="ghost">{distance} km</span>
  </label>
  <p class="ghost" id="filters-disabled-note">Filter sind im Click-Dummy deaktiviert.</p>
</aside>
{/if}

<style>
  .drawer {
    position: absolute;
    z-index: 2;
    left: 50%;
    transform: translateX(-50%);
    bottom: 1rem;
    width: min(22rem, calc(100% - 1.5rem));
    max-height: min(50vh, 24rem);
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .drawer :global(label) {
    gap: 0.5rem;
  }

  .drawer input[type="search"],
  .drawer input[type="range"] {
    width: 100%;
    background: #101821;
    border: 1px solid #263240;
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    color: var(--fg);
  }

  .drawer input[disabled] {
    opacity: 0.6;
  }

  @media (min-width: 48rem) {
    .drawer {
      top: clamp(0.75rem, 2vw, 1.5rem);
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      right: clamp(0.75rem, 2vw, 1.5rem);
      left: auto;
      transform: none;
      width: min(20rem, 28vw);
      max-height: none;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/Garnrolle.svelte

**Größe:** 1 KB | **md5:** `598a242724e118a4888305dc6a49eeed`

```svelte
<script lang="ts">
  export let label = 'Mein Konto';
  export let tooltip = 'Garnrolle – Konto';
</script>

<style>
  .wrap{ position:relative; }
  .roll{
    width:34px; height:34px; border-radius:50%;
    background: radial-gradient(circle at 30% 30%, #6aa6ff 0%, #2c6de0 60%, #1b3f7a 100%);
    border:1px solid rgba(255,255,255,0.12);
    box-shadow: var(--shadow);
    display:grid; place-items:center; cursor:pointer;
  }
  .hole{ width:10px; height:10px; border-radius:50%; background:#0f1a2f; box-shadow: inset 0 0 8px rgba(0,0,0,.6); }
  .tip{
    position:absolute; right:0; transform:translateY(calc(-100% - 8px));
    background:var(--panel); border:1px solid var(--panel-border); color:var(--text);
    padding:6px 8px; font-size:12px; border-radius:8px; white-space:nowrap;
    opacity:0; pointer-events:none; transition:.15s ease;
  }
  .wrap:hover .tip{ opacity:1; }
</style>

<div class="wrap" aria-label={label}>
  <div class="roll" title={tooltip}><div class="hole" /></div>
  <div class="tip">{tooltip}</div>
</div>
```

### 📄 apps/web/src/lib/components/GewebekontoWidget.svelte

**Größe:** 1 KB | **md5:** `30e5f7dbd97602fdd51c419f768a06bb`

```svelte
<script lang="ts">
  export let balance = "1 250 WE";
  export let trend: 'stable' | 'up' | 'down' = 'stable';
  export let note = "Attrappe · UX-Test";

  const trendLabels = {
    stable: 'gleichbleibend',
    up: 'steigend',
    down: 'sinkend'
  } as const;
</script>

<div class="gewebekonto panel" role="group" aria-label="Gewebekonto-Widget (Attrappe)">
  <div class="meta row">
    <span class="badge">Gewebekonto</span>
    <span class="ghost">Status: {trendLabels[trend]}</span>
  </div>
  <div class="balance" aria-live="polite">
    <strong>{balance}</strong>
  </div>
  <p class="note ghost">{note}</p>
  <div class="actions row" aria-hidden="true">
    <button class="btn" type="button" disabled>Einzahlen</button>
    <button class="btn" type="button" disabled>Auszahlen</button>
  </div>
</div>

<style>
  .gewebekonto {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 14rem;
  }

  .meta {
    justify-content: space-between;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .balance {
    font-size: 1.25rem;
  }

  .note {
    margin: 0;
  }

  .actions {
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 40rem) {
    .gewebekonto {
      width: 100%;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/Legend.svelte

**Größe:** 2 KB | **md5:** `9cc8e254463f5321fb576725d548c346`

```svelte
<script lang="ts">
  let open = false;
</script>

<div class="panel legend">
  <div class="legend-header row">
    <strong>Legende</strong>
    <button
      class="btn"
      on:click={() => (open = !open)}
      aria-expanded={open}
      aria-controls="legend-panel"
    >
      {open ? "Schließen" : "Öffnen"}
    </button>
  </div>
  {#if open}
    <div class="divider"></div>
    <div class="col" id="legend-panel">
      <div><span class="legend-dot dot-blue"></span>Blau = Zentrum/Meta</div>
      <div><span class="legend-dot dot-gray"></span>Grau = Grundlagen</div>
      <div><span class="legend-dot dot-yellow"></span>Gelb = Prozesse</div>
      <div><span class="legend-dot dot-red"></span>Rot = Hindernisse</div>
      <div><span class="legend-dot dot-green"></span>Grün = Ziele</div>
      <div><span class="legend-dot dot-violet"></span>Violett = Ebenen</div>
    </div>
    <div class="divider"></div>
    <em class="ghost">Essenz: „Karte sichtbar, aber dumm.“</em>
  {/if}
</div>

<style>
  .legend {
    position: absolute;
    z-index: 2;
    right: clamp(0.75rem, 3vw, 1.5rem);
    top: clamp(0.75rem, 3vw, 1.5rem);
    width: min(18rem, calc(100% - 1.5rem));
  }

  .legend-header {
    justify-content: space-between;
  }

  .legend :global(.col) {
    gap: 0.35rem;
  }

  @media (max-width: 40rem) {
    .legend {
      left: clamp(0.75rem, 3vw, 1.5rem);
      width: auto;
    }
  }

  @media (min-width: 48rem) {
    .legend {
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      top: auto;
    }
  }
</style>
```

### 📄 apps/web/src/lib/components/TimelineDock.svelte

**Größe:** 687 B | **md5:** `6cfaa4f9be468994236a0a6e14e629dd`

```svelte
<style>
  .dock{
    position:absolute; left:0; right:0; bottom:0; min-height:56px; z-index:28;
    display:flex; align-items:center; gap:12px;
    padding:0 12px calc(env(safe-area-inset-bottom)) 12px;
    backdrop-filter: blur(6px);
    background: linear-gradient(0deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
  }
  .badge{ border:1px solid var(--panel-border); background:var(--panel); padding:6px 10px; border-radius:10px; }
  .spacer{ flex:1; }
</style>

<div class="dock">
  <div class="badge">⏱️ Timeline (Stub)</div>
  <div class="spacer"></div>
  <div style="opacity:.72; font-size:12px;">Tipp: [ = links · ] = rechts · Alt+G = Gewebekonto</div>
</div>
```

### 📄 apps/web/src/lib/components/TopBar.svelte

**Größe:** 2 KB | **md5:** `6891014f2bb2c82ab7637bd0935b65ea`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import Garnrolle from './Garnrolle.svelte';
  export let onToggleLeft: () => void;
  export let onToggleRight: () => void;
  export let onToggleTop: () => void;
  export let leftOpen = false;
  export let rightOpen = false;
  export let topOpen = false;

  const dispatch = createEventDispatcher<{
    openers: {
      left: HTMLButtonElement | null;
      right: HTMLButtonElement | null;
      top: HTMLButtonElement | null;
    };
  }>();

  let btnLeft: HTMLButtonElement | null = null;
  let btnRight: HTMLButtonElement | null = null;
  let btnTop: HTMLButtonElement | null = null;

  onMount(() => {
    dispatch('openers', { left: btnLeft, right: btnRight, top: btnTop });
  });
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:30;
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:env(safe-area-inset-top) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
  }
  .btn{
    appearance:none; border:1px solid var(--panel-border); background:var(--panel); color:var(--text);
    height:34px; padding:0 12px; border-radius:10px; display:inline-flex; align-items:center; gap:8px;
    box-shadow: var(--shadow); cursor:pointer;
  }
  .btn:hover{ outline:1px solid var(--accent-soft); }
  .spacer{ flex:1; }
</style>

<div class="topbar" role="toolbar" aria-label="Navigation">
  <button
    class="btn"
    type="button"
    aria-pressed={leftOpen}
    aria-expanded={leftOpen}
    aria-controls="left-stack"
    bind:this={btnLeft}
    on:click={onToggleLeft}
  >
    ☰ Webrat/Nähstübchen
  </button>
  <button
    class="btn"
    type="button"
    aria-pressed={rightOpen}
    aria-expanded={rightOpen}
    aria-controls="filter-drawer"
    bind:this={btnRight}
    on:click={onToggleRight}
  >
    🔎 Filter
  </button>
  <button
    class="btn"
    type="button"
    aria-pressed={topOpen}
    aria-expanded={topOpen}
    aria-controls="account-drawer"
    bind:this={btnTop}
    on:click={onToggleTop}
  >
    🧶 Gewebekonto
  </button>
  <div class="spacer"></div>
  <Garnrolle />
</div>
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_lib_maplibre.md

**Größe:** 9 KB | **md5:** `6a52ceba51726268678e9d53d3d76cf3`

```markdown
### 📄 apps/web/src/lib/maplibre/MapLibre.svelte

**Größe:** 2 KB | **md5:** `c9b32f356f200f0927f72fa926e74c14`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";
  import "maplibre-gl/dist/maplibre-gl.css";
  import type { FitBoundsOptions, LngLatBoundsLike, LngLatLike, MapOptions } from "maplibre-gl";
  import { initMapContext } from "./context";

  const dispatch = createEventDispatcher();
  const context = initMapContext();

  export let style: string;
  export let center: LngLatLike | undefined;
  export let zoom: number | undefined;
  export let minZoom: number | undefined;
  export let maxZoom: number | undefined;
  export let bounds: LngLatBoundsLike | undefined;
  export let fitBoundsOptions: FitBoundsOptions | undefined;
  export let attributionControl = false;
  export let interactive: boolean | undefined;
  export let options: Partial<MapOptions> = {};

  let container: HTMLDivElement | undefined;
  let map: import("maplibre-gl").Map | null = null;
  let containerProps: Record<string, unknown> = {};

  $: ({ style: _omitStyle, ...containerProps } = $$restProps);

  onMount(async () => {
    const maplibreModule = await import("maplibre-gl");
    context.maplibre = maplibreModule;

    if (!container) {
      return;
    }

    const initialOptions: MapOptions = {
      container,
      style,
      attributionControl,
      ...options
    } as MapOptions;

    if (center) {
      initialOptions.center = normalizeLngLat(center);
    }

    if (zoom !== undefined) {
      initialOptions.zoom = zoom;
    }

    if (minZoom !== undefined) {
      initialOptions.minZoom = minZoom;
    }

    if (maxZoom !== undefined) {
      initialOptions.maxZoom = maxZoom;
    }

    if (interactive !== undefined) {
      initialOptions.interactive = interactive;
    }

    map = new maplibreModule.Map(initialOptions);
    context.map.set(map);

    map.on("load", () => dispatch("load", { map }));
    map.on("error", (event) => dispatch("error", event));

    if (bounds) {
      map.fitBounds(bounds, fitBoundsOptions);
    }

    return () => {
      map?.remove();
      map = null;
      context.map.set(null);
      context.maplibre = null;
    };
  });

  $: if (map && center) {
    map.setCenter(normalizeLngLat(center));
  }

  $: if (map && zoom !== undefined) {
    map.setZoom(zoom);
  }

  $: if (map && bounds) {
    map.fitBounds(bounds, fitBoundsOptions);
  }

  function normalizeLngLat(value: LngLatLike): LngLatLike {
    if (Array.isArray(value)) {
      return value;
    }

    return [value.lng, value.lat];
  }
</script>

<div bind:this={container} {...containerProps}>
  <slot />
</div>
```

### 📄 apps/web/src/lib/maplibre/Marker.svelte

**Größe:** 2 KB | **md5:** `68831b8c0a3634a486d5b537643f3517`

```svelte
<script lang="ts">
  import type { Anchor, LngLatLike, MarkerOptions, PointLike } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let lngLat: LngLatLike;
  export let anchor: Anchor = "center";
  export let draggable = false;
  export let offset: PointLike | undefined;

  const context = useMapContext();

  let element: HTMLDivElement | undefined;
  let marker: import("maplibre-gl").Marker | null = null;
  let markerProps: Record<string, unknown> = {};
  let currentAnchor: Anchor = anchor;

  $: markerProps = $$restProps;

  const unsubscribe = context.map.subscribe((map) => {
    recreateMarker(map);
  });

  $: if (marker && lngLat) {
    marker.setLngLat(lngLat);
  }

  $: if (marker) {
    marker.setDraggable(draggable);
  }

  $: if (marker && offset !== undefined) {
    marker.setOffset(offset);
  }

  $: if (marker && anchor !== currentAnchor) {
    recreateMarker(get(context.map));
  }

  function recreateMarker(map: import("maplibre-gl").Map | null) {
    if (marker) {
      marker.remove();
      marker = null;
    }

    if (!map || !context.maplibre || !element) {
      return;
    }

    const options: MarkerOptions = {
      element,
      anchor,
      draggable
    };

    if (offset !== undefined) {
      options.offset = offset;
    }

    marker = new context.maplibre.Marker(options).setLngLat(lngLat).addTo(map);
    currentAnchor = anchor;
  }

  onDestroy(() => {
    unsubscribe();

    if (marker) {
      marker.remove();
      marker = null;
    }
  });
</script>

<div bind:this={element} {...markerProps}>
  <slot />
</div>
```

### 📄 apps/web/src/lib/maplibre/NavigationControl.svelte

**Größe:** 2 KB | **md5:** `ddacf371d91ee0ea654400dfdc70dcc4`

```svelte
<script lang="ts">
  import type { ControlPosition } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let position: ControlPosition = "top-right";
  export let visualizePitch = true;
  export let showCompass = true;
  export let showZoom = true;

  const context = useMapContext();

  let control: import("maplibre-gl").NavigationControl | null = null;
  let signature: string | null = null;
  let lastMap: import("maplibre-gl").Map | null = null;

  const unsubscribe = context.map.subscribe((map) => {
    ensureControl(map);
  });

  $: ensureControl(get(context.map));

  function ensureControl(map: import("maplibre-gl").Map | null) {
    if (!map || !context.maplibre) {
      if (control && lastMap) {
        lastMap.removeControl(control);
        control = null;
      }
      signature = null;
      lastMap = map;
      return;
    }

    const nextSignature = JSON.stringify({ position, visualizePitch, showCompass, showZoom });
    if (control && signature === nextSignature && lastMap === map) {
      return;
    }

    if (control && lastMap) {
      lastMap.removeControl(control);
      control = null;
    }

    control = new context.maplibre.NavigationControl({ visualizePitch, showCompass, showZoom });
    map.addControl(control, position);
    signature = nextSignature;
    lastMap = map;
  }

  onDestroy(() => {
    unsubscribe();
    const map = get(context.map);
    if (control && map) {
      map.removeControl(control);
    } else if (control && lastMap) {
      lastMap.removeControl(control);
    }
    control = null;
    lastMap = null;
  });
</script>
```

### 📄 apps/web/src/lib/maplibre/ScaleControl.svelte

**Größe:** 2 KB | **md5:** `37e23429d60fa65d8c3c42b3ecb0a59d`

```svelte
<script lang="ts">
  import type { ControlPosition } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let position: ControlPosition = "bottom-left";
  export let maxWidth: number | undefined;
  export let unit: "imperial" | "metric" | "nautical" | undefined;

  const context = useMapContext();

  type ScaleControlOptions = ConstructorParameters<typeof import("maplibre-gl").ScaleControl>[0];

  let control: import("maplibre-gl").ScaleControl | null = null;
  let signature: string | null = null;
  let lastMap: import("maplibre-gl").Map | null = null;

  const unsubscribe = context.map.subscribe((map) => {
    ensureControl(map);
  });

  $: ensureControl(get(context.map));

  function ensureControl(map: import("maplibre-gl").Map | null) {
    if (control && lastMap && lastMap !== map) {
      lastMap.removeControl(control);
      control = null;
    }

    if (!map || !context.maplibre) {
      signature = null;
      lastMap = map;
      return;
    }

    const nextSignature = JSON.stringify({ position, maxWidth, unit });
    if (control && signature === nextSignature && lastMap === map) {
      return;
    }

    if (control && lastMap) {
      lastMap.removeControl(control);
      control = null;
    }

    const options: ScaleControlOptions = {};

    if (maxWidth !== undefined) {
      options.maxWidth = maxWidth;
    }

    if (unit) {
      options.unit = unit;
    }

    control = new context.maplibre.ScaleControl(options);
    map.addControl(control, position);

    signature = nextSignature;
    lastMap = map;
  }

  onDestroy(() => {
    unsubscribe();
    const map = get(context.map);
    if (control && map) {
      map.removeControl(control);
    } else if (control && lastMap) {
      lastMap.removeControl(control);
    }
    control = null;
    lastMap = null;
  });
</script>
```

### 📄 apps/web/src/lib/maplibre/context.ts

**Größe:** 815 B | **md5:** `8b578cf40bcb3da406f2f04ca730f297`

```typescript
import type * as maplibregl from "maplibre-gl";
import { getContext, setContext } from "svelte";
import { writable, type Writable } from "svelte/store";

export const MAP_CONTEXT_KEY = Symbol("maplibre-context");

export type MapContextValue = {
  map: Writable<maplibregl.Map | null>;
  maplibre: typeof import("maplibre-gl") | null;
};

export function initMapContext(): MapContextValue {
  const value: MapContextValue = {
    map: writable<maplibregl.Map | null>(null),
    maplibre: null
  };

  setContext(MAP_CONTEXT_KEY, value);
  return value;
}

export function useMapContext(): MapContextValue {
  const context = getContext<MapContextValue | undefined>(MAP_CONTEXT_KEY);

  if (!context) {
    throw new Error("MapLibre components must be used inside a <MapLibre> container.");
  }

  return context;
}
```

### 📄 apps/web/src/lib/maplibre/index.ts

**Größe:** 250 B | **md5:** `1d16218a92d62836dab4f0810c39f1cf`

```typescript
export { default as MapLibre } from "./MapLibre.svelte";
export { default as Marker } from "./Marker.svelte";
export { default as NavigationControl } from "./NavigationControl.svelte";
export { default as ScaleControl } from "./ScaleControl.svelte";
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_lib_stores.md

**Größe:** 2 KB | **md5:** `0708b93911a66cf14ab636a26f4f3579`

```markdown
### 📄 apps/web/src/lib/stores/governance.ts

**Größe:** 2 KB | **md5:** `2302c0165ea60ee88f6368d416add270`

```typescript
import { browser } from "$app/environment";
import { writable, type Subscriber, type Unsubscriber } from "svelte/store";

const TICK_MS = 1000;

/** Countdown-Store, der in festen Intervallen herunterzählt und nach Ablauf automatisch neu startet. */
export interface LoopingCountdown {
  subscribe: (run: Subscriber<number>) => Unsubscriber;
  /** Setzt den Countdown auf die Ausgangsdauer zurück und startet ihn erneut, falls er aktiv war. */
  reset: () => void;
}

/** Steuerungs-Store für einen booleschen Zustand mit sprechenden Convenience-Methoden. */
export interface BooleanToggle {
  subscribe: (run: Subscriber<boolean>) => Unsubscriber;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

export function createLoopingCountdown(durationMs: number): LoopingCountdown {
  const { subscribe: internalSubscribe, set, update } = writable(durationMs);

  let interval: ReturnType<typeof setInterval> | null = null;
  let activeSubscribers = 0;

  const start = () => {
    if (!browser || interval !== null) return;
    interval = setInterval(() => {
      update((previous) => (previous > TICK_MS ? previous - TICK_MS : durationMs));
    }, TICK_MS);
  };

  const stop = () => {
    if (interval !== null) {
      clearInterval(interval);
      interval = null;
    }
    set(durationMs);
  };

  return {
    subscribe(run) {
      activeSubscribers += 1;
      if (activeSubscribers === 1) start();
      const unsubscribe = internalSubscribe(run);
      return () => {
        unsubscribe();
        activeSubscribers -= 1;
        if (activeSubscribers === 0) {
          stop();
        }
      };
    },
    reset() {
      if (!browser) return;
      stop();
      if (activeSubscribers > 0) start();
    }
  };
}

export function createBooleanToggle(initial = false): BooleanToggle {
  const { subscribe, set, update } = writable(initial);
  return {
    subscribe,
    open: () => set(true),
    close: () => set(false),
    toggle: () => update((value) => !value)
  };
}
```

### 📄 apps/web/src/lib/stores/index.ts

**Größe:** 30 B | **md5:** `2578f505c899216949cce97e01d907b9`

```typescript
export * from "./governance";
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_lib_styles.md

**Größe:** 1 KB | **md5:** `9397e7ae1fdee5e2fab357e2205249f5`

```markdown
### 📄 apps/web/src/lib/styles/tokens.css

**Größe:** 923 B | **md5:** `3ffc03d6624bf43f77d5b0aa1a7603e8`

```css
:root{
  --bg: #0f1115;
  --panel: rgba(20,22,28,0.92);
  --panel-border: rgba(255,255,255,0.06);
  --text: #e9eef5;
  --muted: #9aa4b2;
  --accent: #6aa6ff;
  --accent-soft: rgba(106,166,255,0.18);
  --radius: 12px;
  --shadow: 0 6px 24px rgba(0,0,0,0.35);
  /* Layout- und Drawer-Defaults */
  --toolbar-offset: 52px;
  --drawer-gap: 12px;
  --drawer-width: 360px;
  --drawer-slide-offset: 20px;

  /* Swipe-Edge Defaults (innenliegende Greifzonen, kollisionsarm mit OS-Gesten) */
  --edge-inset-x: 24px;     /* Abstand von links/rechts */
  --edge-inset-top: 24px;   /* Abstand oben */
  --edge-top-height: 16px;  /* Höhe Top-Zone */
  --edge-left-width: 16px;  /* Breite linke Zone */
  --edge-right-width: 16px; /* Breite rechte Zone */
}

/* Android: Back-Swipe oft breiter → Zone schmaler & leicht weiter innen */
:root.ua-android{
  --edge-inset-x: 28px;
  --edge-left-width: 12px;
  --edge-right-width: 12px;
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_lib_utils.md

**Größe:** 2 KB | **md5:** `e53927c33dcb6be7989d4f3976228542`

```markdown
### 📄 apps/web/src/lib/utils/inert-polyfill.ts

**Größe:** 2 KB | **md5:** `7827c363e57b5dfc9af1dd8169d37ef4`

```typescript
// Minimaler inert-Polyfill:
// - blockiert Focus & Clicks in [inert]
// - setzt aria-hidden, solange inert aktiv ist
// Safari < 16.4 & ältere iPadOS-Versionen profitieren davon.

function applyAriaHidden(el: Element, on: boolean) {
  const prev = (el as HTMLElement).getAttribute('aria-hidden');
  if (on) {
    if (prev !== 'true') (el as HTMLElement).setAttribute('aria-hidden', 'true');
  } else {
    if (prev === 'true') (el as HTMLElement).removeAttribute('aria-hidden');
  }
}

export function ensureInertPolyfill() {
  // Moderne Browser haben bereits inert-Unterstützung.
  if ('inert' in HTMLElement.prototype) return;

  // Style-Schutz zusätzlich (Pointer & Selection aus).
  const style = document.createElement('style');
  style.textContent = `
    [inert] { pointer-events:none; user-select:none; -webkit-user-select:none; -webkit-tap-highlight-color: transparent; }
  `;
  document.head.appendChild(style);

  // Aria-Hidden initial anwenden
  const syncAll = () => {
    document.querySelectorAll<HTMLElement>('[inert]').forEach((el) => applyAriaHidden(el, true));
  };
  syncAll();

  // Fokus- & Click-Blocker
  document.addEventListener('focusin', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      (t as HTMLElement).blur?.();
      (document.activeElement as HTMLElement | null)?.blur?.();
    }
  }, true);
  document.addEventListener('click', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  // Reagiere auf spätere inert-Attribute
  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      if (!(m.target instanceof HTMLElement)) continue;
      if (m.type === 'attributes' && m.attributeName === 'inert') {
        const el = m.target as HTMLElement;
        const on = el.hasAttribute('inert');
        applyAriaHidden(el, on);
      }
    }
  });
  mo.observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['inert'] });
}
```

### 📄 apps/web/src/lib/utils/ua-flags.ts

**Größe:** 187 B | **md5:** `47cbc1d02f91baf7dfb2478070899b75`

```typescript
export function setUAClasses() {
  const ua = navigator.userAgent || '';
  const isAndroid = /Android/i.test(ua);
  if (isAndroid) document.documentElement.classList.add('ua-android');
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_routes.md

**Größe:** 2 KB | **md5:** `b61d0625ad7a187a9770fc72b55be0fa`

```markdown
### 📄 apps/web/src/routes/+layout.svelte

**Größe:** 805 B | **md5:** `4f9a070fe164fe56d1472deff592ba73`

```svelte
<script lang="ts">
  import '../app.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import '$lib/styles/tokens.css';
  import { onMount } from 'svelte';
  import { ensureInertPolyfill } from '$lib/utils/inert-polyfill';
  import { setUAClasses } from '$lib/utils/ua-flags';
  import { page } from '$app/stores';
  import { get } from 'svelte/store';

  export let data: any;

  onMount(() => {
    setUAClasses();
    // Toggle: ?noinert=1 schaltet Polyfill ab (Debug/Kompat)
    const q = new URLSearchParams(get(page).url.search);
    const disable = q.get('noinert') === '1' || (window as any).__NO_INERT__ === true;
    if (!disable) ensureInertPolyfill();
  });
</script>

<svelte:head>
  {#if data?.canonical}
    <link rel="canonical" href={data.canonical} />
  {/if}
</svelte:head>

<slot />
```

### 📄 apps/web/src/routes/+layout.ts

**Größe:** 192 B | **md5:** `9b63a9d01fca0cbe127d9a061b9f5d59`

```typescript
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, url.origin).toString();

  return {
    canonical
  };
};
```

### 📄 apps/web/src/routes/+page.server.ts

**Größe:** 101 B | **md5:** `f4319851426d4c10ea877e8e5de3f83d`

```typescript
import { redirect } from '@sveltejs/kit';

export function load() {
  throw redirect(307, '/map');
}
```

### 📄 apps/web/src/routes/+page.svelte

**Größe:** 232 B | **md5:** `904b1cf6094055486b945161db807a50`

```svelte
<!-- Platzhalter-Seite, damit die Route "/" existiert und
     der Redirect in +page.server.ts ausgeführt werden kann.
     (In CI/SSR wird sofort umgeleitet.) -->

<noscript>
  Weiterleitung… <a href="/map">/map</a>
</noscript>
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_routes_archive.md

**Größe:** 2 KB | **md5:** `97c022220f3d25e3d75acb779954b1ed`

```markdown
### 📄 apps/web/src/routes/archive/+page.svelte

**Größe:** 2 KB | **md5:** `a5c4de02e1586fe81976f4aabc4bbbcf`

```svelte
<script lang="ts">
  const archiveMonths = [
    { label: "Mai 2024", path: "/archive/2024/05" },
    { label: "April 2024", path: "/archive/2024/04" },
    { label: "März 2024", path: "/archive/2024/03" }
  ];
</script>

<svelte:head>
  <title>Archiv · Webrat</title>
  <meta
    name="description"
    content="Monatsarchiv der Webrat-Einträge mit einer Übersicht vergangener Beiträge."
  />
</svelte:head>

<main class="archive">
  <header>
    <h1>Archiv</h1>
    <p>
      Im Archiv findest du vergangene Monatsübersichten. Wähle einen Monat aus, um alle Einträge
      aus dieser Zeitspanne zu entdecken.
    </p>
  </header>

  <section aria-labelledby="archive-months">
    <h2 id="archive-months">Monate</h2>
    <ul>
      {#each archiveMonths as month}
        <li><a href={month.path}>{month.label}</a></li>
      {/each}
    </ul>
  </section>
</main>

<style>
  main.archive {
    max-width: 48rem;
    margin: 0 auto;
    padding: 2rem 1.5rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  header p {
    margin-top: 0.75rem;
    line-height: 1.6;
  }

  section ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.75rem;
  }

  section li {
    background: #f7f7f7;
    border-radius: 0.5rem;
    padding: 0.85rem 1rem;
    transition: background 0.2s ease-in-out, transform 0.2s ease-in-out;
  }

  section li:hover,
  section li:focus-within {
    background: #ececec;
    transform: translateY(-1px);
  }

  section a {
    color: inherit;
    text-decoration: none;
    font-weight: 600;
  }
</style>
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_src_routes_map.md

**Größe:** 12 KB | **md5:** `23a1d7c7ed1ee72194f5f00fdca6b921`

```markdown
### 📄 apps/web/src/routes/map/+page.svelte

**Größe:** 11 KB | **md5:** `0f7b4c6ce4041972ba19cf4b864d9e53`

```svelte
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap } from 'maplibre-gl';
  import TopBar from '$lib/components/TopBar.svelte';
  import Drawer from '$lib/components/Drawer.svelte';
  import TimelineDock from '$lib/components/TimelineDock.svelte';

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;

  let leftOpen = true;     // linke Spalte (Webrat/Nähstübchen)
  let rightOpen = false;   // Filter
  let topOpen = false;     // Gewebekonto

  type DrawerInstance = InstanceType<typeof Drawer> & {
    setOpener?: (el: HTMLElement | null) => void;
  };
  let rightDrawerRef: DrawerInstance | null = null;
  let topDrawerRef: DrawerInstance | null = null;
  let openerButtons: {
    left: HTMLButtonElement | null;
    right: HTMLButtonElement | null;
    top: HTMLButtonElement | null;
  } = { left: null, right: null, top: null };

  const defaultQueryState = { l: leftOpen, r: rightOpen, t: topOpen } as const;

  function setQuery(next: { l?: boolean; r?: boolean; t?: boolean }) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (next.l !== undefined) {
      if (next.l === defaultQueryState.l) {
        url.searchParams.delete('l');
      } else {
        url.searchParams.set('l', next.l ? '1' : '0');
      }
    }
    if (next.r !== undefined) {
      if (next.r === defaultQueryState.r) {
        url.searchParams.delete('r');
      } else {
        url.searchParams.set('r', next.r ? '1' : '0');
      }
    }
    if (next.t !== undefined) {
      if (next.t === defaultQueryState.t) {
        url.searchParams.delete('t');
      } else {
        url.searchParams.set('t', next.t ? '1' : '0');
      }
    }
    history.replaceState(history.state, '', url);
  }

  function syncFromLocation() {
    if (typeof window === 'undefined') return;
    const q = new URLSearchParams(window.location.search);
    leftOpen = q.has('l') ? q.get('l') === '1' : defaultQueryState.l;
    rightOpen = q.has('r') ? q.get('r') === '1' : defaultQueryState.r;
    topOpen = q.has('t') ? q.get('t') === '1' : defaultQueryState.t;
  }

  function toggleLeft(){ leftOpen = !leftOpen; setQuery({ l: leftOpen }); }
  function toggleRight(){ rightOpen = !rightOpen; setQuery({ r: rightOpen }); }
  function toggleTop(){ topOpen = !topOpen; setQuery({ t: topOpen }); }

  type SwipeIntent =
    | 'open-left'
    | 'close-left'
    | 'open-right'
    | 'close-right'
    | 'open-top'
    | 'close-top';

  type SwipeState = {
    pointerId: number;
    intent: SwipeIntent;
    startX: number;
    startY: number;
  } | null;

  let swipeState: SwipeState = null;

  function startSwipe(e: PointerEvent, intent: SwipeIntent) {
    const allowMouse = (window as any).__E2E__ === true;
    if (e.pointerType !== 'touch' && e.pointerType !== 'pen' && !allowMouse) return;

    if (
      (intent === 'open-left' && leftOpen) ||
      (intent === 'close-left' && !leftOpen) ||
      (intent === 'open-right' && rightOpen) ||
      (intent === 'close-right' && !rightOpen) ||
      (intent === 'open-top' && topOpen) ||
      (intent === 'close-top' && !topOpen)
    ) {
      return;
    }

    swipeState = {
      pointerId: e.pointerId,
      intent,
      startX: e.clientX,
      startY: e.clientY
    };
  }

  function finishSwipe(e: PointerEvent) {
    if (!swipeState || swipeState.pointerId !== e.pointerId) return;

    const dx = e.clientX - swipeState.startX;
    const dy = e.clientY - swipeState.startY;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    const threshold = 60;
    const { intent } = swipeState;
    swipeState = null;

    switch (intent) {
      case 'open-left':
        if (!leftOpen && dx > threshold && absX > absY) {
          leftOpen = true;
          setQuery({ l: true });
        }
        break;
      case 'close-left':
        if (leftOpen && -dx > threshold && absX > absY) {
          leftOpen = false;
          setQuery({ l: false });
        }
        break;
      case 'open-right':
        if (!rightOpen && -dx > threshold && absX > absY) {
          rightOpen = true;
          setQuery({ r: true });
        }
        break;
      case 'close-right':
        if (rightOpen && dx > threshold && absX > absY) {
          rightOpen = false;
          setQuery({ r: false });
        }
        break;
      case 'open-top':
        if (!topOpen && dy > threshold && absY > absX) {
          topOpen = true;
          setQuery({ t: true });
        }
        break;
      case 'close-top':
        if (topOpen && -dy > threshold && absY > absX) {
          topOpen = false;
          setQuery({ t: false });
        }
        break;
    }
  }

  function cancelSwipe(e: PointerEvent) {
    if (swipeState && swipeState.pointerId === e.pointerId) {
      swipeState = null;
    }
  }

  function handleOpeners(
    event: CustomEvent<{
      left: HTMLButtonElement | null;
      right: HTMLButtonElement | null;
      top: HTMLButtonElement | null;
    }>
  ) {
    openerButtons = event.detail;
  }

  $: if (rightDrawerRef) {
    rightDrawerRef.setOpener?.(openerButtons.right ?? null);
  }
  $: if (topDrawerRef) {
    topDrawerRef.setOpener?.(openerButtons.top ?? null);
  }

  let keyHandler: ((e: KeyboardEvent) => void) | null = null;
  let popHandler: ((event: PopStateEvent) => void) | null = null;
  onMount(() => {
    const pointerUp = (event: PointerEvent) => finishSwipe(event);
    const pointerCancel = (event: PointerEvent) => cancelSwipe(event);
    window.addEventListener('pointerup', pointerUp);
    window.addEventListener('pointercancel', pointerCancel);

    syncFromLocation();
    popHandler = () => syncFromLocation();
    window.addEventListener('popstate', popHandler);

    (async () => {
      const maplibregl = await import('maplibre-gl');
      const container = mapContainer;
      if (!container) {
        return;
      }
      // Hamburg-Hamm grob: 10.05, 53.55 — Zoom 13
      map = new maplibregl.Map({
        container,
        style: 'https://demotiles.maplibre.org/style.json',
        center: [10.05, 53.55],
        zoom: 13
      });
      map.addControl(new maplibregl.NavigationControl({ showZoom:true }), 'bottom-right');

      keyHandler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          if (topOpen) {
            topOpen = false;
            setQuery({ t: false });
            return;
          }
          if (rightOpen) {
            rightOpen = false;
            setQuery({ r: false });
            return;
          }
          if (leftOpen) {
            leftOpen = false;
            setQuery({ l: false });
            return;
          }
        }
        if (e.key === '[') toggleLeft();
        if (e.key === ']') toggleRight();
        if (e.altKey && (e.key === 'g' || e.key === 'G')) toggleTop();
      };
      window.addEventListener('keydown', keyHandler);
    })();

    return () => {
      window.removeEventListener('pointerup', pointerUp);
      window.removeEventListener('pointercancel', pointerCancel);
      if (popHandler) window.removeEventListener('popstate', popHandler);
    };
  });
  onDestroy(() => {
    if (keyHandler) window.removeEventListener('keydown', keyHandler);
    if (popHandler) window.removeEventListener('popstate', popHandler);
    if (map && typeof map.remove === 'function') map.remove();
  });
</script>

<style>
  .shell{
    position:relative;
    height:100dvh;
    /* keep the raw dynamic viewport height as a fallback for browsers missing safe-area support */
    height:calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom));
    width:100vw;
    overflow:hidden;
    background:var(--bg);
    color:var(--text);
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
  }
  #map{ position:absolute; inset:0; }
  #map :global(canvas){ filter: grayscale(0.2) saturate(0.75) brightness(1.03) contrast(0.95); }
  /* Swipe-Edge-Zonen über Tokens (OS-Gesten-freundlich) */
  .edge{ position:absolute; z-index:27; }
  .edge.left{ left:var(--edge-inset-x); top:80px; bottom:80px; width:var(--edge-left-width); touch-action: pan-y; }
  .edge.right{ right:var(--edge-inset-x); top:80px; bottom:80px; width:var(--edge-right-width); touch-action: pan-y; }
  .edge.top{ left:var(--edge-inset-x); right:var(--edge-inset-x); top:var(--edge-inset-top); height:var(--edge-top-height); touch-action: pan-x; }
  .edgeHit{ position:absolute; inset:0; }
  /* Linke Spalte: oben Webrat, unten Nähstübchen (hälftig) */
  .leftStack{
    position:absolute;
    left: var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
    z-index:26;
    display:grid; grid-template-rows: 1fr 1fr; gap:var(--drawer-gap);
    transform: translateX(calc(-1 * var(--drawer-width) - var(--drawer-slide-offset)));
    transition: transform .18s ease;
  }
  .leftStack.open{ transform:none; }
  .panel{
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow); color:var(--text); padding:var(--drawer-gap); overflow:auto;
  }
  .panel h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .muted{ color:var(--muted); font-size:13px; }
  @media (max-width: 900px){
    .leftStack{ --drawer-width: 320px; }
  }
  @media (max-width: 380px){
    .leftStack{ --drawer-width: 300px; }
  }
  @media (prefers-reduced-motion: reduce){
    .leftStack{ transition: none; }
  }
</style>

<div class="shell">
  <TopBar
    onToggleLeft={toggleLeft}
    onToggleRight={toggleRight}
    onToggleTop={toggleTop}
    {leftOpen}
    {rightOpen}
    {topOpen}
    on:openers={handleOpeners}
  />

  <!-- Linke Spalte: Webrat / Nähstübchen -->
  <div
    id="left-stack"
    class="leftStack"
    class:open={leftOpen}
    aria-hidden={!leftOpen}
    inert={!leftOpen ? true : undefined}
    on:pointerdown={(event) => startSwipe(event, 'close-left')}
  >
    <div class="panel">
      <h3>Webrat</h3>
      <div class="muted">Beratung, Anträge, Matrix (Stub)</div>
    </div>
    <div class="panel">
      <h3>Nähstübchen</h3>
      <div class="muted">Ideen, Entwürfe, Skizzen (Stub)</div>
    </div>
  </div>

  <!-- Rechter Drawer: Suche/Filter -->
  <Drawer
    bind:this={rightDrawerRef}
    id="filter-drawer"
    title="Suche & Filter"
    side="right"
    open={rightOpen}
    on:pointerdown={(event) => startSwipe(event, 'close-right')}
  >
    <div class="panel" style="padding:8px;">
      <div class="muted">Typ · Zeit · H3 · Delegation · Radius (Stub)</div>
    </div>
  </Drawer>

  <!-- Top Drawer: Gewebekonto -->
  <Drawer
    bind:this={topDrawerRef}
    id="account-drawer"
    title="Gewebekonto"
    side="top"
    open={topOpen}
    on:pointerdown={(event) => startSwipe(event, 'close-top')}
  >
    <div class="panel" style="padding:8px;">
      <div class="muted">Saldo / Delegationen / Verbindlichkeiten (Stub)</div>
    </div>
  </Drawer>

  <!-- Karte -->
  <div id="map" bind:this={mapContainer}></div>

  <div class="edge left" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-left')}>
    <div class="edgeHit"></div>
  </div>
  <div class="edge right" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-right')}>
    <div class="edgeHit"></div>
  </div>
  <div class="edge top" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-top')}>
    <div class="edgeHit"></div>
  </div>

  <!-- Zeitleiste -->
  <TimelineDock />
</div>
```
```

### 📄 merges/weltgewebe_merge_2510262237__apps_web_tests.md

**Größe:** 4 KB | **md5:** `5ac8314061608ffbd122c3d16eba1d1d`

```markdown
### 📄 apps/web/tests/drawers.spec.ts

**Größe:** 3 KB | **md5:** `ab97256041c7f0f44e14769a9bd338be`

```typescript
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Maus-Swipes in Tests erlauben
  await page.addInitScript(() => { (window as any).__E2E__ = true; });
  await page.goto('/map');
});

test('Esc schließt geöffnete Drawer (top → right → left)', async ({ page }) => {
  // Rechts öffnen
  await page.keyboard.press(']');
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeVisible();

  // Esc → schließt rechts
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeHidden();

  // Top öffnen
  await page.keyboard.press('Alt+g');
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeVisible();

  // Esc → schließt top
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeHidden();

  // Links öffnen
  await page.keyboard.press('[');
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();

  // Esc → schließt links (Stack)
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();
});

test('Swipe öffnet & schließt Drawer symmetrisch', async ({ page }) => {
  const map = page.locator('#map');

  // Linke Kante öffnen (drag→ rechts)
  const box = await map.boundingBox();
  if (!box) throw new Error('map not visible');
  const y = box.y + box.height * 0.5;

  // open left
  await page.mouse.move(box.x + 40, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 120, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();

  // close left (drag ←)
  await page.mouse.move(box.x + 140, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 30, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();

  // open right (drag ← an rechter Kante)
  const rx = box.x + box.width - 40;
  await page.mouse.move(rx, y);
  await page.mouse.down();
  await page.mouse.move(rx - 100, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeVisible();

  // close right (drag →)
  await page.mouse.move(rx - 120, y);
  await page.mouse.down();
  await page.mouse.move(rx + 20, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeHidden();

  // open top (drag ↓ nahe Top)
  const tx = box.x + box.width * 0.5;
  const ty = box.y + 40;
  await page.mouse.move(tx, ty);
  await page.mouse.down();
  await page.mouse.move(tx, ty + 120, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeVisible();

  // close top (drag ↑)
  await page.mouse.move(tx, ty + 140);
  await page.mouse.down();
  await page.mouse.move(tx, ty - 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeHidden();
});
```

### 📄 apps/web/tests/map-smoke.spec.ts

**Größe:** 570 B | **md5:** `79a75ef59118015fac2b3427e2fc9b88`

```typescript
import { expect, test } from "@playwright/test";

test.describe("map route", () => {
  test("shows structure layer controls", async ({ page }) => {
    await page.goto("/map");

    const strukturknotenButton = page.getByRole("button", { name: "Strukturknoten" });
    await expect(strukturknotenButton).toBeVisible();
    await expect(strukturknotenButton).toBeDisabled();

    await expect(page.getByRole("button", { name: "Fäden" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Archiv ansehen" })).toHaveAttribute("href", "/archive/");
  });
});
```
```

### 📄 merges/weltgewebe_merge_2510262237__ci.md

**Größe:** 533 B | **md5:** `85124bc9c01b7706110da5a726bdcea5`

```markdown
### 📄 ci/README.md

**Größe:** 200 B | **md5:** `d5d468659276cd627ef5d0055a942b75`

```markdown
# CI – Roadmap

- prose (vale)
- web (budgets)
- api (clippy/tests)
- security (trivy)

## CI (Platzhalter)

Diese Repo-Phase ist Docs-only. `ci/budget.json` dient als Referenz für spätere Gates.
```

### 📄 ci/budget.json

**Größe:** 123 B | **md5:** `d1377d85d1cc1645b5f2440bb0d08f25`

```json
{
  "budgets": {
    "web": {
      "js_kb_max": 60,
      "tti_ms_p95_max": 2000,
      "inp_ms_p75_max": 200
    }
  }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__ci_scripts.md

**Größe:** 4 KB | **md5:** `d6a26f2ce2a3dfb051103442cf7ab5fc`

```markdown
### 📄 ci/scripts/db-wait.sh

**Größe:** 498 B | **md5:** `4e3c7e73e15e8450e658938904534c12`

```bash
#!/usr/bin/env bash
set -euo pipefail

HOST=${PGHOST:-localhost}
PORT=${PGPORT:-5432}
TIMEOUT=${DB_WAIT_TIMEOUT:-60}
INTERVAL=${DB_WAIT_INTERVAL:-2}

declare -i end=$((SECONDS + TIMEOUT))

while (( SECONDS < end )); do
    if (echo >"/dev/tcp/${HOST}/${PORT}") >/dev/null 2>&1; then
        printf 'Postgres is available at %s:%s\n' "$HOST" "$PORT"
        exit 0
    fi
    sleep "$INTERVAL"
done

printf 'Timed out waiting for Postgres at %s:%s after %ss\n' "$HOST" "$PORT" "$TIMEOUT" >&2
exit 1
```

### 📄 ci/scripts/validate_wgx_profile.py

**Größe:** 4 KB | **md5:** `53f8d63e9450ddffc57ceff725f860ee`

```python
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-

"""Validate the minimal schema for ``.wgx/profile.yml``.

The wgx-guard workflow embeds this script and previously relied on an inline
Python snippet. A subtle indentation slip in that snippet caused
``IndentationError`` failures in CI.  To make the validation robust we keep the
logic in this dedicated module and ensure the implementation is intentionally
simple and well formatted.
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import sys
from types import ModuleType
from collections.abc import Iterable, Mapping


REQUIRED_TOP_LEVEL_KEYS = ("version", "env_priority", "tooling", "tasks", "wgx")
REQUIRED_WGX_KEYS = ("org",)
REQUIRED_TASKS = ("up", "lint", "test", "build", "smoke")


def _error(message: str) -> None:
    """Emit a GitHub Actions friendly error message."""

    print(f"::error::{message}")


def _missing_keys(data: Mapping[str, object], keys: Iterable[str]) -> list[str]:
    return [key for key in keys if key not in data]


def _load_yaml_module() -> ModuleType | None:
    existing = sys.modules.get("yaml")
    if isinstance(existing, ModuleType) and hasattr(existing, "safe_load"):
        return existing

    module = importlib.util.find_spec("yaml")
    if module is None:
        _error(
            "PyYAML not installed. Install it with 'python -m pip install pyyaml' before running this script."
        )
        return None

    return importlib.import_module("yaml")


def main() -> int:
    yaml = _load_yaml_module()
    if yaml is None:
        return 1

    profile_path = pathlib.Path(".wgx/profile.yml")

    try:
        contents = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _error(".wgx/profile.yml missing")
        return 1

    try:
        data = yaml.safe_load(contents) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - best effort logging
        _error(f"failed to parse YAML: {exc}")
        return 1

    if not isinstance(data, dict):
        _error("profile must be a mapping")
        return 1

    missing_top_level = _missing_keys(data, REQUIRED_TOP_LEVEL_KEYS)
    if missing_top_level:
        _error(f"missing keys: {missing_top_level}")
        return 1

    env_priority = data.get("env_priority")
    if not isinstance(env_priority, list) or not env_priority:
        _error("env_priority must be a non-empty list")
        return 1

    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        _error("tasks must be a mapping")
        return 1

    missing_tasks = _missing_keys(tasks, REQUIRED_TASKS)
    if missing_tasks:
        _error(f"missing tasks: {missing_tasks}")
        return 1

    wgx_block = data.get("wgx")
    if not isinstance(wgx_block, dict):
        _error("wgx must be a mapping")
        return 1

    missing_wgx = _missing_keys(wgx_block, REQUIRED_WGX_KEYS)
    if missing_wgx:
        _error(f"wgx missing keys: {missing_wgx}")
        return 1

    org = wgx_block.get("org")
    if not isinstance(org, str) or not org.strip():
        _error("wgx.org must be a non-empty string")
        return 1

    meta = data.get("meta")
    if isinstance(meta, dict) and "owner" in meta:
        owner = meta.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            _error("meta.owner must be a non-empty string when provided")
            return 1
        if owner != org:
            _error(f"meta.owner ({owner!r}) must match wgx.org ({org!r})")
            return 1

    print("wgx profile OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
```

### 📄 merges/weltgewebe_merge_2510262237__configs.md

**Größe:** 623 B | **md5:** `ea23496d6df706fc27c6f17f99e5bd8d`

```markdown
### 📄 configs/README.md

**Größe:** 323 B | **md5:** `5f291886a54691e71197bd288d398c5f`

```markdown
# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit `HA_*`-Variablen überschreiben (`HA_FADE_DAYS`, `HA_RON_DAYS`,
`HA_ANONYMIZE_OPT_IN`, `HA_DELEGATION_EXPIRE_DAYS`).
```

### 📄 configs/app.defaults.yml

**Größe:** 76 B | **md5:** `2e2703e5a92b04e9d68b1ab93b336039`

```yaml
fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
```
```

### 📄 merges/weltgewebe_merge_2510262237__contracts_semantics.md

**Größe:** 2 KB | **md5:** `a96e4e06a91191c1c8657bd20279a288`

```markdown
### 📄 contracts/semantics/.upstream

**Größe:** 54 B | **md5:** `5b69f8d0a21f4d7ad4719b99f0873d62`

```plaintext
repo: semantAH
path: contracts/semantics
mode: mirror
```

### 📄 contracts/semantics/README.md

**Größe:** 111 B | **md5:** `01d4ab919007afe03e6aa996c9b3b3ae`

```markdown
# Semantik-Verträge (Upstream: semantAH)

Quelle: externer Ableger `semantAH`. Nicht editieren, nur spiegeln.
```

### 📄 contracts/semantics/edge.schema.json

**Größe:** 302 B | **md5:** `8f92b25fdd52e7dc7a589f36c9ed0a3a`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemEdge","type":"object",
  "required":["src","dst","rel"],
  "properties":{"src":{"type":"string"},"dst":{"type":"string"},"rel":{"type":"string"},
    "weight":{"type":"number"},"why":{"type":"string"},"updated_at":{"type":"string"}}
}
```

### 📄 contracts/semantics/node.schema.json

**Größe:** 358 B | **md5:** `8a55023fb9d91f644833dbcd7243011b`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemNode","type":"object",
  "required":["id","type","title"],
  "properties":{"id":{"type":"string"},"type":{"type":"string"},
    "title":{"type":"string"},"tags":{"type":"array","items":{"type":"string"}},
    "source":{"type":"string"},"updated_at":{"type":"string","format":"date-time"}}
}
```

### 📄 contracts/semantics/report.schema.json

**Größe:** 311 B | **md5:** `66113d119045d16fdbfdba885d82fb73`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemReport","type":"object",
  "required":["kind","created_at"],
  "properties":{"kind":{"type":"string"},"created_at":{"type":"string","format":"date-time"},
    "notes":{"type":"array","items":{"type":"string"}},
    "stats":{"type":"object"}}
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs.md

**Größe:** 73 KB | **md5:** `39219d61c094f596aae2b204e3e050a7`

```markdown
### 📄 docs/README.md

**Größe:** 372 B | **md5:** `d97277ef89d096355ecc33689f5e89a9`

```markdown
# Weltgewebe – Doku-Index

– **Start:** architekturstruktur.md
– **Techstack:** techstack.md
– **Prozess & Fahrplan:** process/README.md
– **ADRs:** adr/
– **Runbooks:** runbooks/README.md
– **Glossar:** glossar.md
– **Inhalt/Story:** inhalt.md, zusammenstellung.md
– **X-Repo Learnings:** x-repo/peers-learnings.md
– **Beitragen:** ../CONTRIBUTING.md
```

### 📄 docs/architekturstruktur.md

**Größe:** 6 KB | **md5:** `b5ceafe29f2d968072fa413f468ba026`

```markdown
Weltgewebe – Repository-Struktur

Dieses Dokument beschreibt den Aufbau des Repositories.
Ziel: Übersicht für Entwickler und KI, damit alle Beiträge am richtigen Ort landen.

⸻

ASCII-Baum

weltgewebe/weltgewebe-repo/
├─ apps/                       # Anwendungen (Business-Code)
│  ├─ web/                      # SvelteKit-Frontend (PWA, MapLibre)
│  │  ├─ src/
│  │  │  ├─ routes/             # Seiten, Endpunkte (+page.svelte/+server.ts)
│  │  │  ├─ lib/                # UI-Komponenten, Stores, Utilities
│  │  │  ├─ hooks.client.ts     # RUM-Initialisierung (LongTasks)
│  │  │  └─ app.d.ts            # App-Typdefinitionen
│  │  ├─ static/                # Fonts, Icons, manifest.webmanifest
│  │  ├─ tests/                 # Frontend-Tests (Vitest, Playwright)
│  │  ├─ svelte.config.js
│  │  ├─ vite.config.ts
│  │  └─ README.md
│  │
│  ├─ api/                      # Rust (Axum) – REST + SSE
│  │  ├─ src/
│  │  │  ├─ main.rs             # Einstiegspunkt, Router
│  │  │  ├─ routes/             # HTTP- und SSE-Endpunkte
│  │  │  ├─ domain/             # Geschäftslogik, Services
│  │  │  ├─ repo/               # SQLx-Abfragen, Postgres-Anbindung
│  │  │  ├─ events/             # Outbox-Publisher, Eventtypen
│  │  │  └─ telemetry/          # Prometheus/OTel-Integration
│  │  ├─ migrations/            # Datenbankschemata, pg_partman
│  │  ├─ tests/                 # API-Tests (Rust)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
│  ├─ worker/                   # Projector/Indexer/Jobs
│  │  ├─ src/
│  │  │  ├─ projector_timeline.rs # Outbox→Timeline-Projektion
│  │  │  ├─ projector_search.rs   # Outbox→Search-Indizes
│  │  │  └─ replayer.rs           # Rebuilds (DSGVO/DR)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
│  └─ search/                   # (optional) Such-Adapter/SDKs
│     ├─ adapters/              # Typesense/Meili-Clients
│     └─ README.md
│
├─ packages/                    # (optional) Geteilte Libraries/SDKs
│  └─ README.md
│
├─ infra/                       # Betrieb/Deployment/Observability
│  ├─ compose/                  # Docker Compose Profile
│  │  ├─ compose.core.yml       # Basis-Stack: web, api, db, caddy
│  │  ├─ compose.observ.yml     # Monitoring: Prometheus, Grafana, Loki/Tempo
│  │  ├─ compose.stream.yml     # Event-Streaming: NATS/JetStream
│  │  └─ compose.search.yml     # Suche: Typesense/Meili, KeyDB
│  ├─ caddy/
│  │  ├─ Caddyfile              # Proxy, HTTP/3, CSP, TLS
│  │  └─ README.md
│  ├─ db/
│  │  ├─ init/                  # SQL-Init-Skripte, Extensions (postgis, h3)
│  │  ├─ partman/               # Partitionierung (pg_partman)
│  │  └─ README.md
│  ├─ monitoring/
│  │  ├─ prometheus.yml         # Prometheus-Konfiguration
│  │  ├─ grafana/
│  │  │  ├─ dashboards/         # Web-Vitals, JetStream, Edge-Kosten
│  │  │  └─ alerts/             # Alarme: Opex, Lag, LongTasks
│  │  └─ README.md
│  ├─ nomad/                    # (optional) Orchestrierungsspezifikationen
│  └─ k8s/                      # (optional) Kubernetes-Manifeste
│
├─ docs/                        # Dokumentation & Entscheidungen
│  ├─ adr/                      # Architecture Decision Records
│  ├─ techstack.md              # Techstack v3.2 (Referenz)
│  ├─ architektur.ascii         # Architektur-Poster/ASCII-Diagramme
│  ├─ datenmodell.md            # Datenbank- und Projektionstabellen
│  └─ runbook.md                # Woche-1/2 Setup, DR/DSGVO-Drills
│
├─ ci/                          # CI/CD & Qualitätsprüfungen
│  ├─ github/
│  │  └─ workflows/             # GitHub Actions für Build, Tests, Infra
│  │     ├─ web.yml
│  │     ├─ api.yml
│  │     └─ infra.yml
│  ├─ scripts/                  # Hilfsskripte (migrate, seed, db-wait)
│  └─ budget.json               # Performance-Budgets (≤60KB JS, ≤2s TTI)
│
├─ .env.example                 # Beispiel-Umgebungsvariablen
├─ .editorconfig                # Editor-Standards
├─ .gitignore                   # Ignorier-Regeln
├─ LICENSE                      # Lizenztext
└─ README.md                    # Projektüberblick, Quickstart

⸻

Erläuterungen zu den Hauptordnern

- **apps/**
  Enthält alle Anwendungen: Web-Frontend (SvelteKit), API (Rust/Axum), Worker (Eventprojektionen, Rebuilds) und
  optionale Search-Adapter. Jeder Unterordner ist eine eigenständige App mit eigenem README und Build-Konfig.
- **packages/**
  Platz für geteilte Libraries oder SDKs, die von mehreren Apps genutzt werden. Wird erst angelegt, wenn Bedarf an
  gemeinsamem Code entsteht.
- **infra/**
  Infrastruktur- und Deployment-Ebene. Compose-Profile für verschiedene Betriebsmodi, Caddy-Konfiguration,
  DB-Init, Monitoring-Setup. Optional Nomad- oder Kubernetes-Definitionen für spätere Skalierung.
- **docs/**
  Dokumentation und Architekturentscheidungen. Enthält ADRs, Techstack-Beschreibung, Diagramme,
  Datenmodellübersicht und Runbooks.
- **ci/**
  Alles rund um Continuous Integration/Deployment: Workflows für GitHub Actions, Skripte für Tests/DB-Handling,
  sowie zentrale Performance-Budgets (Lighthouse).
- **Root**
  Repository-Metadaten: .env.example (Vorlage), Editor- und Git-Configs, Lizenz und README mit Projektüberblick.

⸻

Zusammenfassung

Diese Struktur spiegelt den aktuellen Techstack (v3.2) wider:

- Mobil-first via PWA (SvelteKit).
- Rust/Axum API mit Outbox/JetStream-Eventing.
- Compose-first Infrastruktur mit klar getrennten Profilen.
- Observability und Compliance fest verankert.
- Erweiterbar durch optionale packages/, nomad/, k8s/.

Dies dient als Referenzrahmen für alle weiteren Arbeiten am Weltgewebe-Repository.
```

### 📄 docs/datenmodell.md

**Größe:** 4 KB | **md5:** `40e5e1201281b9d2cf8e6928c999fffb`

```markdown
# Datenmodell

Dieses Dokument beschreibt das Datenmodell der Weltgewebe-Anwendung, das auf PostgreSQL aufbaut.
Es dient als Referenz für Entwickler, um die Kernentitäten, ihre Beziehungen und die daraus
abgeleiteten Lese-Modelle zu verstehen.

## Grundprinzipien

- **Source of Truth:** PostgreSQL ist die alleinige Quelle der Wahrheit.
- **Transaktionaler Outbox:** Alle Zustandsänderungen werden transaktional in die `outbox`-Tabelle
  geschrieben, um eine konsistente Event-Verteilung an nachgelagerte Systeme (z.B. via NATS
  JetStream) zu garantieren.
- **Normalisierung:** Das Schreib-Modell ist normalisiert, um Datenintegrität zu gewährleisten.
  Lese-Modelle (Projektionen/Views) sind für spezifische Anwendungsfälle denormalisiert und
  optimiert.
- **UUIDs:** Alle Primärschlüssel sind UUIDs (`v4`), um eine verteilte Generierung zu
  ermöglichen und Abhängigkeiten von sequenziellen IDs zu vermeiden.

---

## Tabellen (Schreib-Modell)

### `nodes`

Speichert geografische oder logische Knotenpunkte, die als Anker für Threads dienen.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Knotens. |
| `location` | `geography(Point, 4326)` | Geografischer Standort (Längen- und Breitengrad). |
| `h3_index`| `bigint` | H3-Index für schnelle geografische Abfragen. |
| `name` | `text` | Anzeigename des Knotens. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `roles`

Verwaltet Benutzer- oder Systemrollen, die Berechtigungen steuern.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator der Rolle. |
| `user_id` | `uuid` (FK) | Referenz zum Benutzer (externes System). |
| `permissions` | `jsonb` | Berechtigungen der Rolle als JSON-Objekt. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

### `threads`

Repräsentiert die Konversationen oder "Fäden", die an Knoten gebunden sind.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Threads. |
| `node_id` | `uuid` (FK, `nodes.id`) | Zugehöriger Knoten. |
| `author_role_id` | `uuid` (FK, `roles.id`) | Ersteller des Threads. |
| `title` | `text` | Titel des Threads. |
| `content` | `text` | Inhalt des Threads (z.B. erster Beitrag). |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `outbox`

Implementiert das Transactional Outbox Pattern für zuverlässige Event-Publikation.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Events. |
| `aggregate_type` | `text` | Typ des Aggregats (z.B. "thread"). |
| `aggregate_id` | `uuid` | ID des betroffenen Aggregats. |
| `event_type` | `text` | Typ des Events (z.B. "thread.created"). |
| `payload` | `jsonb` | Event-Daten. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

---

## Projektionen (Lese-Modelle)

Diese Views sind für die Lese-Performance optimiert und fassen Daten aus mehreren Tabellen zusammen.
Sie werden von den Workern (Projektoren) asynchron aktualisiert.

### `public_role_view`

Eine denormalisierte Sicht auf Rollen, die nur öffentlich sichtbare Informationen enthält.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `role_id` | `uuid` | Identifikator der Rolle. |
| `display_name` | `text` | Öffentlich sichtbarer Name (ggf. aus einem externen User-Service). |
| `avatar_url` | `text` | URL zu einem Avatar-Bild. |

### `faden_view`

Eine zusammengefasste Ansicht von Threads für die schnelle Darstellung in der Benutzeroberfläche.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `thread_id` | `uuid` | Identifikator des Threads. |
| `node_id` | `uuid` | Zugehöriger Knoten. |
| `node_name` | `text` | Name des zugehörigen Knotens. |
| `author_display_name` | `text` | Anzeigename des Autors. |
| `title` | `text` | Titel des Threads. |
| `comment_count` | `integer` | Anzahl der Kommentare (wird vom Projektor berechnet). |
| `last_activity_at` | `timestamptz` | Zeitstempel der letzten Aktivität. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
```

### 📄 docs/geist-und-plan.md

**Größe:** 13 KB | **md5:** `613cb35836928aecb308cbf11be60475`

```markdown
Hier ist eine (meinerseits strukturierte) Analyse und Extraktion des „Geistes und Plans“ der
Weltweberei basierend auf der Website weltweberei.org.
Ich ziehe aus den öffentlich verfügbaren Texten, sortiere nach Themen und ziehe Schlussfolgerungen —
du kannst damit weiterarbeiten oder ich helfe dir beim Verdichten / Operationalisieren.

⸻

## 1. Einleitende, normative Aussagen – der Geist

Diese Passagen geben dir Einsicht in die philosophische und normative Grundhaltung hinter dem Projekt:

- Der Name Weltweberei legt den Fokus auf Verflechtung, Weben und Verknüpfen („weben der welt, wie
  es jedem (!) gefällt“).
- Es handelt sich um ein Konzept eines „sichtbaren, gemeinschaftlich ausgehandelten Zusammenwirkens
  von Nachbarschaften, versammelt um ein gemeinsames Konto“.
- Die Teilhabe ist ausdrücklich offen und frei: „anschauen kostet nichts, beitreten … auch nichts,
  dabei sein auch nicht – nichts kostet irgendetwas.“
- Es besteht eine Intention zur freiwilligen Gegenseitigkeit: Man kann von Gemeinschaftsressourcen
  profitieren, aber auch zurückgeben, in welcher Form man will.
- Transparenz und Freiwilligkeit sind zentral, insbesondere in Bezug auf Daten: keine Datenerhebung
  ohne dein Einverständnis, kein Tracking, keine automatische Profilbildung. Nur das, was du
  freiwillig sichtbar machst, erscheint öffentlich.
- Die Struktur ist bewusst offen, flexibel und veränderbar: „alles ist jederzeit kollektiv
  aushandelbar – alles!“
- Der Weg ist offen beziehungsweise ergebnisoffen: „der Weg ist das Ziel!“
- Es gibt einen utopischen Horizont: ein global anschlussfähiges Netz von Ortszellen, überregionale
  Zusammenschlüsse ohne Entmachtung der lokalen Zellen und sogar die Vision eines Ausstiegs aus dem
  vorherrschenden Geldsystem als denkbare Zukunft.

Kurz gesagt: Der Geist ist partizipativ, dezentral, transparent, nicht-hierarchisch, offen
verhandelbar und zukunftsgerichtet.
Es geht um kollektive Selbstorganisation, Verantwortung und Autonomie in einem vernetzten Raum.

⸻

## 2. Funktionale und strukturelle Elemente – der Plan (in Ansätzen)

Neben dem Geist gibt es auf der Website Hinweise auf konkrete Strukturen und Konzepte,
wie man dieses Ideal operationalisieren möchte:

- **Weltgewebe / Karte**
  - Zweck / Idee: Die Plattform oder Leinwand, auf der Aktionen, Wünsche, Kommentare und
    Verantwortungsübernahmen visualisiert werden.
  - Bemerkungen & Herausforderungen: Hier liegt ein Kern bei dir: Wie visualisiert man Fäden, Knoten
    und Wechselwirkungen?
- **Ortsgewebekonto**
  - Zweck / Idee: Jedes „Ortsweberei“ hat ein gemeinsames Konto, auf das Spenden eingehen und von
    dem Auszahlungen per Antrag möglich sind – und das im Netz (Karte) sichtbar ist.
  - Bemerkungen & Herausforderungen: Governance von Konten, Transparenz, Zugriffssteuerung und
    Antragssysteme sind zu designen.
- **Partizipartei / Mandatssystem**
  - Zweck / Idee: Politischer Arm der Ortswebereien: „Fadenträger“ fungieren als Mandatsträger,
    „Fadenreicher“ als Vermittler oder Sekretäre.
    Ihre Arbeit wird öffentlich (gestreamt), Input kann live durch Community eingegeben werden
    (gefiltert via Up-/Down-Voting, Plattform-KI).
    Stimmen können delegiert (transitär) werden.
  - Bemerkungen & Herausforderungen: Das Mandats- und Delegationssystem muss wasserdicht und
    nachvollziehbar gestaltet sein (Spielregeln, Sicherheit, Sybil-Schutz etc.).
- **Skalierbarkeit und Föderation**
  - Zweck / Idee: Ortswebereien sind Zellen; überregionale Bündnisse könnten gemeinsame Konten
    bilden, aber ohne die Basis zu entmachten.
    Lokale Entscheidungen bleiben vorherrschend.
  - Bemerkungen & Herausforderungen: Die Herausforderung einer föderalen Architektur mit Rückbindung
    und Reversibilität ist zentral.
- **Offene Anpassbarkeit**
  - Zweck / Idee: Jedes Element (Funktionen, Posten, Regeln) kann per Antrag verändert werden — also
    ein Meta-System zur Änderung der Regeln selbst.
  - Bemerkungen & Herausforderungen: Du brauchst ein Metagovernance-Modul: Regeln über Regeln.
- **Technische Infrastruktur & Datenschutz**
  - Zweck / Idee: Minimale Datenerhebung, nur das, was Nutzer:innen freiwillig veröffentlichen;
    temporäres Speichern von Serverlogs; keine automatische Profilbildung.
  - Bemerkungen & Herausforderungen: Datenschutz-Design, Sicherheit, Datenportabilität und
    Löschbarkeit müssen von Anfang an eingebaut sein.
- **Visionärer Horizont**
  - Zweck / Idee: In größeren Skalen kann man über Ausstieg aus dem Geldsystem, Verfassungsfragen,
    kollektive Selbstbestimmung nachdenken.
  - Bemerkungen & Herausforderungen: Diese Visionen sind (im Moment) noch eher hypothetisch.
    Du musst definieren, wie man von der Basis dorthin gelangen könnte.

⸻

## 3. Risiken, Widersprüche und offene Fragen

Damit du beim Weiterentwickeln gewappnet bist, hier ein paar erkennbare Spannungen oder Herausforderungen:

1. Governance vs. Skalierung — je größer das Netzwerk, desto höher ist die Gefahr von
   Koordinationsproblemen, Trittbrettfahrern, Machtkonzentration.
2. Sicherheit und Identitätsprobleme — wie verhinderst du Sybil-Attacken (falsche
   Mehrfachidentitäten), wie verifizierst du Mitgliedschaften, wie schützt du sensible Daten?
3. Effizienz vs. Inklusivität — partizipative Prozesse sind oft langsamer; wie verhinderst du
   Blockaden?
4. Delegation von Stimmen — das Modell ist spannend (Liquid Democracy), aber praktisch schwierig:
   wie oft darf delegiert werden, wie lange, wie wird Transparenz gewährleistet?
5. Konten und Geldflüsse — wie schafft man Sicherheit, Vertrauen und Transparenz in
   Finanztransaktionen über dezentrale Komponenten?
6. Technische Komplexität — Visualisierung von Geweben, Echtzeit-Interaktion, Skalierung,
   Datenschutz: das sind keine einfachen Aufgaben.
7. Motivations- und Engagement-Problem — viele Projekte scheitern daran, dass die Community nicht
   dauerhaft aktiv bleibt.
8. Zwischen Vision und Implementierung — manche Visionen (z. B. Ausstieg aus dem Geldsystem) sind
   ambitioniert; der Übergang muss sorgfältig gestaltet werden.

⸻

## 4. Mein zusammengefasster „Geist & Plan“ (in deiner Sprache, für deine Nutzung)

Wenn ich das für dein Projekt (Weltgewebe) zusammenfasse, um es nutzbar zu machen:

- Geist: Freiheit, Gemeinschaft, Transparenz, Verantwortung, partizipative Autonomie.
  Ein Raum, in dem Menschen freiwillig ihre Intentionen einbringen, sich verflechten und
  zusammenwirken, ohne dominante Hierarchien, und in dem Veränderung offen verhandelbar ist.

- Plan (Architektur):

  1. Ein interaktives Karten- und Netzwerkinterface (Weltgewebe), das sichtbar macht, wie Menschen
  handeln, wünschen und Verantwortung übernehmen.
  2. Lokale Zellen („Ortswebereien“) mit eigenen Gemeinschaftskonten, Antragsprozessen und
  Governance.
  3. Ein Mandats- und Delegationssystem (Partizipartei), um kollektive Entscheidungen zu treffen,
  bei maximaler Transparenz (z. B. Streaming, Chat und Voting).
  4. Eine federative Struktur, die lokale Autonomie bewahrt, aber überregionale Kooperation erlaubt.
  5. Ein Metasystem zur Anpassung und Veränderung von Regeln („Regeln über Regeln“) durch die
  Gemeinschaft.
  6. Ein strenger Datenschutzansatz: nur selbsteingetragene Daten sichtbar, keine Profilbildung,
  Nutzerkontrolle über ihre Daten.
  7. Ein visionärer Horizont, in dem globale Skalierung, alternative Wirtschaftsformen oder
  Systemwechsel denkbar sind — freilich erst als langfristige Option.

⸻

Es geht vor allem um Koordination von Gemeinschaftsaktionen und -interessen: Jemand möchte etwas auf
die Beine stellen, knüpft auf der Karte am Ort des geplanten Handelns einen Knoten, Beispiel:
gemeinsam grillen im Park (Parkspeise) am Donnerstag um 17 Uhr.
Dieser von ihm geknüpfte Knoten wird automatisch per Faden mit seiner Rolle verknüpft (da er Urheber
ist), es entsteht dort neben den angelegten Informationen ein Gesprächsraum.
Andere, die durch diese visuelle Plandarstellung auf das Angebot aufmerksam geworden sind, können
sich nun am Gespräch darüber beteiligen oder zusagen etc.
Jede Aktion eines Webers (eingeloggter Nutzer) spinnt ebenso automatisch einen Faden von dessen
Rolle zum jeweiligen Knoten.
Kommt es nun zur Parkspeise, gibt es natürlich für jedermann die Möglichkeit, etwas in die
Gemeinschaftskasse (Gewebekonto) zu spenden – als eine Art Energieausgleich.
Möchte der Urheber nun etwas aus dem Gewebekonto erhalten (er hatte schließlich Ausgaben etc.), dann
muss er einen Antrag auf Auszahlung aus dem Konto stellen.
Dies wird visualisiert durch einen Antragsfaden auf das Konto (eigener Knoten auf der Karte)
inklusive Sieben-Tage-Timer.
Kein Einspruch eines anderen Webers innerhalb der Frist: Auszahlung wird autorisiert.
Bei Einspruch: Verlängerung der Entscheidung um weitere sieben Tage mit anschließender Abstimmung.

Anderes Praxisbeispiel: Jeder kann die Ressourcen, die er der Gemeinschaft zur Verfügung stellen
will, auf seiner Garnrolle oder auf entsprechend verorteten Knoten hinterlegen.
Sucht nun jemand nach beispielsweise einem Schlafplatz, dann werden ihm alle in der Umgebung
angezeigt.

Kontextuelle Einordnung

Du hast Dateien hochgeladen, die Philosophie, Struktur und Tech-Stack des Weltgewebes dokumentieren:

- inhalt.md: Konzept und Funktionsweise.
- zusammenstellung.md: Systematische Zusammenfassung (Grundprinzipien, Domänenmodell, Governance).
- architekturstruktur.md: Repo-Struktur für Entwickler:innen.
- techstack.md: Detaillierter Technologie-Stack.

Damit liegt so etwas wie die DNA der Weltweberei vor: Vision, Plan, Architektur und konkrete
technische Umsetzung.

⸻

Extraktion: Geist der Weltweberei

- Verflechtung als Leitmotiv: Alles wird als Knoten und Fäden sichtbar, von Menschen bis Ressourcen.
- Radikale Transparenz und Freiwilligkeit: Jede Handlung ein sichtbares Event, aber ohne verstecktes
  Tracking.
- Commons-Orientierung: Keine künstliche Währung; Engagement und eingebrachte Ressourcen sind die
  „Währung“.
- Vergänglichkeit und Verzwirnung: Fäden verblassen, nur verzwirnte Inhalte werden dauerhaft –
  Dynamik statt Archivlast.
- Demokratische Prozesse: 7+7-Tage-Modell für Anträge, Liquid Democracy mit temporären Delegationen,
  offene Abstimmungen.
- Freiheit plus Absicherung: Jeder kann Ressourcen freigeben oder Aktionen starten, Anträge werden
  nur blockiert, wenn Widerspruch entsteht.
- Datenschutz: Privacy by Design, RoN-System für Anonymisierung, Unschärferadien für Ortsdaten.

⸻

Extraktion: Plan der Weltweberei

1. Domänenmodell
   - Nutzer = Garnrollen (mit privatem und öffentlichem Bereich).
   - Inhalte = Knoten (Ereignisse, Ressourcen, Ideen).
   - Verbindungen = Fäden (Gespräch, Antrag, Delegation, Spende etc.).
2. Funktionale Module
   - Gewebekonto: Finanzverwaltung, sichtbar als Goldfäden.
   - Webrat: Governance-Ort für Anträge, Abstimmungen, Delegationen.
   - Nähstübchen: Allgemeine Kommunikation.
   - RoN-Platzhalter: Sammelstelle für anonymisierte Inhalte.
3. Zeitlichkeit und Prozesse
   - Sieben-Sekunden-Sichtbarkeit bei Aktionen.
   - Sieben-Tage-Timer für Fäden, Knoten, Anträge.
   - Verlängerung um sieben Tage bei Einspruch → Abstimmung.
4. Organisation
   - Lokale Ortswebereien mit eigenen Konten.
   - Föderation mehrerer Ortswebereien möglich.
5. Technik
   - Frontend: SvelteKit, MapLibre, PWA.
   - Backend: Rust (Axum), PostgreSQL + PostGIS + h3, Event-Outbox, NATS JetStream.
   - Suche: Typesense / MeiliSearch.
   - Infrastruktur: Nomad, Caddy (HTTP/3), PgBouncer.
   - Observability: Prometheus, Grafana, Loki, Tempo.
   - Security: SBOM, Signaturen, DSGVO-Forget-Pipeline, Key-Rotation.
   - Kostenkontrolle: FinOps-KPIs (€/Session, €/GB Traffic).

⸻

Essenz-Kristall

👉 Die Weltweberei ist eine kartenbasierte Demokratie-Engine: Jede Handlung wird als Faden sichtbar,
jeder Knoten ist Raum für Aktionen oder Ressourcen, alle Prozesse laufen transparent, freiwillig,
temporär und verhandelbar – technisch abgesichert durch Event-Sourcing, föderierbar in Ortsgeweben
und getragen von einem klaren DSGVO-Privacy-by-Design.

⸻

Ironische Auslassung

„Früher musste man Plakate drucken und Flugblätter verteilen, um Nachbarn zum Grillen oder
Couch-Sharing zu überreden – heute genügt ein Knoten auf der Karte.
Demokratie trifft Picknick, mit JetStream und PgBouncer als unsichtbare Grillanzünder.“

⸻

∴fores Ungewissheit

- Grad: niedrig–mittel (30–40 %).

- Ursachen:

  - Soziale Dynamik (wie dauerhaft beteiligen sich Leute?).
  - Governance im Konfliktfall (Abstimmungen bei Missbrauch, Streit über Ressourcen).
  - Technische Skalierung (Last > 100k Nutzer, Kostenpfad).
  - Meta-Reflexion: Viele Prinzipien sind definiert, aber die echte Bewährung liegt in der Praxis.

⸻

Kontrastvektor

Noch nicht thematisiert:

- Konfliktlösung jenseits Abstimmungen (z. B. Mediation).
- Schnittstellen zu externen Systemen (öffentliche Verwaltung, lokale Initiativen).
- Umgang mit kulturellen Unterschieden bei Föderation globaler Ortswebereien.

⸻
```

### 📄 docs/glossar.md

**Größe:** 335 B | **md5:** `e1e1c4e097e48c0046706204cbb58a0d`

```markdown
# Glossar

**Rolle** (Garnrolle): auf Wohnsitz verorteter Account.
**Knoten:** lokalisierte Informationsbündel (Idee, Termin, Ort, Werkzeug…).
**Faden/Garn:** temporäre/persistente Verbindung Rolle→Knoten (Verzwirnung = Garn).
**RoN:** Rolle ohne Namen (Anonymisierung).
**Unschärferadius:** Öffentliche Genauigkeit in Metern.
```

### 📄 docs/inhalt.md

**Größe:** 9 KB | **md5:** `aa4c1484b00984a155cf4eb98cdf4fb1`

```markdown
# Inhalt (MANDATORISCH)

## Was bedeutet Weltweberei?

welt = althochdeutsch weralt = menschenzeitalter
weben = germanisch webaną, indogermanisch webʰ- = flechten, verknüpfen, bewegen

Guten Tag,

schön, dass du hergefunden hast! Tritt gerne ein in unser Weltgewebe oder schau dir erstmal an, um was es
hier überhaupt geht.

Anschauen kostet nichts, beitreten (bald erst möglich) auch nicht, dabei sein auch nicht, nichts kostet
irgendetwas. Du kannst nach eigenem Ermessen und kollektiven Gutdünken von diesem Netzwerk an gemeinsamen
Ressourcen profitieren, bist gleichzeitig aber natürlich ebenso frei der Gemeinschaft etwas von dir
zurückzugeben – was auch immer, wie auch immer.

Weltweberei ist der Name dieses Konzeptes eines sichtbaren, gemeinschaftlich ausgehandelten Zusammenwirkens
von Nachbarschaften, versammelt um ein gemeinsames Konto. weltgewebe.net ist die Leinwand (Karte), auf der
die jeweiligen Aktionen, Wünsche, Kommentare und Verantwortungsübernahmen der Weltweber visualisiert werden
– als dynamisch sich veränderndes Geflecht von Fäden und Knoten.

## Wie funktioniert das Weltgewebe?

Jeder kann auf dem Weltgewebe (Online-Karte) alles einsehen. Wer sich mit Namen und Adresse registriert,
der bekommt eine Garnrolle auf seinen Wohnsitz gesteckt. Diese Rolle ermöglicht es einem Nutzer, sich aktiv
ins Weltgewebe einzuweben, solange er eingeloggt (sichtbar durch Drehung der Rolle) ist. Er kann nun also
neue Knoten (auf der Karte lokalisierte Informationsbündel, beispielsweise über geplante oder ständige
Ereignisse, Fragen, Ideen) knüpfen, sich mit bestehenden verbinden (Zustimmung, Interesse, Ablehnung,
Zusage, Verantwortungsübernahme, etc.), an Gesprächen (Threads auf einem Knoten) teilnehmen, oder Geld an
ein Ortsgewebekonto (Gemeinschaftskonto) spenden.

Jede dieser Aktionen erzeugt einen Faden, der von der Rolle zu dem jeweiligen Knoten führt. Jeder Faden
verblasst sukzessive binnen 7 Tagen. Auch Knoten lösen sich sukzessive binnen 7 Tagen auf, wenn es ein
datiertes Ereignis war und dieses vorbei ist, oder wenn seit 7 Tagen kein Faden (oder Garn) mehr zu diesem
Knoten geführt hat. Führt jedoch ein Garn zu einem Knoten (siehe unten), dann besteht dieser auch permanent,
bis das letzte zu ihm führende Garn entzwirnt ist. Kurzum: Knoten bestehen solange, wie noch etwas Garn oder
Faden zu ihm führt.

### Benutzeroberfläche und Navigation

Der linke Drawer enthält den Webrat und das Nähstübchen. Hier wird über alle ortsunabhängigen Themen
beraten (und abgestimmt. Generell kann jeder jederzeit Abstimmungen einleiten). Im Nähstübchen wird
einfach (orts-/kartenunabhängig) geplaudert. Das Ortsgewebekonto (oberer Slider) ist das
Gemeinschaftskonto. Hier gehen sowohl anonyme Spenden, als auch sichtbare Spenden (als Goldfäden von der
jeweiligen Rolle) ein. Hier, wie auch überall im Gewebe können Weber Anträge (auf Auszahlung, Anschaffung,
Veränderung, etc.) stellen.

Solch ein Antrag ist ebenso durch einen speziellen Antragsfaden mit der Rolle des Webers verbunden und
enthält sichtbar einen 7-Tage Timer. Nun haben alle Weber 7 Tage lang Zeit Einspruch einzulegen.
Geschieht dies nicht, dann geht der Antrag durch, bei Einspruch verlängert sich die Entscheidungszeit um
weitere 7 Tage bis schlussendlich abgestimmt wird. Jeder Antrag eröffnet automatisch einen Raum mitsamt
Thread und Informationen. Überhaupt entsteht mit jedem Knoten ein eigener Raum (Fenster), in dem man
Informationen, Threads, etc. nebeneinander gestalten kann. Alles, was man gestaltet, kann von allen anderen
verändert werden, es sei denn man verzwirnt es. Dies führt automatisch dazu, dass der Faden, der zu dem
Knoten führt und von der Rolle des Verzwirners ausgeht, zu einem Garn wird. Solange also eine Verzwirnung
besteht, solange kann ein Knoten sich nicht auflösen. Die Verzwirnung kann einzelne Elemente in einem
Knoten oder auch den gesamten Knoten betreffen.

Unten ist eine Zeitleiste. Man kann hier in Tagesschritten zurückspringen und vergangene Webungen sehen.
Auf der rechten Seite ist ein Slider mit den Filterkästchen für die toggelbaren Ebenen. Ecke oben rechts:
eigene Kontoeinstellung (nicht zu verwechseln mit Ortsgewebekontodarstellung oben). Man hat in seiner
eigenen Garnrolle einen privaten Bereich (Kontoeinstellungen, etc.) und einen öffentlich einsehbaren. In
dem öffentlich einsehbaren kann man unter anderem Güter und Kompetenzen, die man der Gesamtheit zur
Verfügung stellen möchte, angeben.

Über eine Suche im rechten Drawer kann man alle möglichen Aspekte suchen. Sie werden per Glow auf dem
verorteten Knoten oder Garnrolle und auf einer Liste dargestellt. Die Liste ist geordnet nach Entfernung
zur Bildmitte bei Suchbeginn. Von der Liste springt man zu dem verorteten Knoten oder Garnrolle, wenn man
den Treffer anklickt.

All diese Ebenen (links, oben, Ecke rechts oben, rechts) werden aus der jeweiligen Ecke oder Kante
herausgezogen. Die Standardansicht zeigt nur die Karte. Kleine Symbole zeigen die herausziehbaren Ebenen an.

### Fadenarten und Knotentypen

Es gibt unterschiedliche Fadenarten (in unterschiedlichen Farben):

- **Gesprächsfaden** - für Kommunikation und Diskussion
- **Gestaltungsfaden** - neue Knoten knüpfen, Räume gestalten (mit Informationen versehen, einrichten, etc.)
- **Veränderungsfaden** - wenn man bestehende Informationen verändert
- **Antragsfaden** - für offizielle Anträge im System
- **Abstimmungsfaden** - für Teilnahme an Abstimmungen
- **Goldfaden** - für Spenden und finanzielle Beiträge
- **Meldefaden** - für Meldungen problematischer Inhalte

Alle sind verzwirnbar, um aus den Fäden ein permanentes Garn zu zaubern.

Auch gibt es unterschiedliche Knotenarten:

- **Ideen** - Vorschläge und Konzepte
- **Veranstaltungen** (diversifizierbar) - Events und Termine
- **Einrichtungen** (diversifizierbar) - physische Orte und Gebäude
- **Werkzeuge** - Hilfsmittel und Geräte
- **Schlaf-/Stellplätze** - Übernachtungs- und Parkmöglichkeiten
- etc.

Diese Knotenarten sind auf der Karte filterbar (toggelbar).

## Organisation und Struktur

Weltweberei ist das Konzept. Realisiert wird es durch Ortswebereien, welche sich um ein gemeinsames
Gewebekonto versammeln. Jede Ortsweberei hat eine eigene Unterseite auf weltgewebe.net.

### Accounts und Nutzerkonten

Die Verifizierung übernimmt ein Verantwortlicher der Ortsweberei (per Identitätsprüfung etc.). Damit wird
dem Weber ein Account erstellt, den er beliebig gestalten kann. Es gibt einen öffentlich einsehbaren und
einen privaten Bereich. Der Account wird als Garnrolle auf seiner Wohnstätte visualisiert.

**Wichtige Unterscheidung:**

- Rolle ≠ Funktion im Gewebe
- Rolle = Kurzform für Garnrolle = auf Wohnsitz verorteter Account

Das System der Weltweberei kommt ohne Währungsalternativen oder Creditsysteme aus. Sichtbares Engagement und
eingebrachte bzw. einzubringende Ressourcen (also geleistete und potenzielle Webungen) sind die Währung!

### Ortsgewebekonto

Dies ist das Gemeinschaftskonto der jeweiligen Ortswebereien.

Per Visualisierung im Weltgewebe jederzeit einsehbar.

Hier gehen Spenden ein und werden Anträge auf Auszahlung gestellt, die – wie alles im Weltgewebe – dem
Gemeinschaftswillen zur Disposition stehen.

### Partizipartei

Der politische Arm der jeweiligen Ortswebereien. Der Clou: Alles politische geschieht unter
Live-Beobachtung und -Mitwirkung der Weber und anderer Interessierter (diese jedoch ohne
Mitwirkungsmöglichkeit).

Die Arbeit der Fadenträger (Mandatsträger) und dessen Fadenreicher (Sekretäre, die den Input aus dem
Gewebe aufbereiten und an den Fadenträger weiterreichen) wird während der gesamten Arbeitszeit gestreamt.
Weber können live im Stream-Gruppenchat ihre Ideen (gefiltert durch Aufwertung/Abwertung der Mitweber und
möglicherweise unterstützt / geordnet durch eine Plattform-Künstliche Intelligenz) und Unterstützungen
einbringen. Jeder Funktion, jeder Posten kann – wie alles in dem Weltgewebe – per Antrag umbesetzt oder
verändert werden. Jeder Weber (auch die kleinen) haben eine Stimme. Diese können sie temporär an andere
Weber übertragen. Das bedeutet, dass diejenigen, an die die Stimmen übertragen wurden, bei Abstimmungen
dementsprechend mehr Stimmmacht haben.

Auch übertragene Stimmen können weiterübertragen werden. Übertragungen enden 4 Wochen nach Inaktivität des
Stimmenverleihenden oder durch dessen Entscheidung.

## Kontakt / Impressum / Datenschutz

**E-Mail-Adresse:** <kontakt@weltweberei.org>
Schreib gerne, wenn du interessiert bist, Fragen, Anregungen oder Kritik hast. Oder willst du gar selber
eine Ortsweberei gründen oder dich anderweitig beteiligen?

**Telefon:** +4915563658682
Aktuell benutze ich WhatsApp und Signal

**Verantwortlicher:** Alexander Mohr, Huskoppelallee 13, 23795 Klein Rönnau

**Datenschutz:** Das Weltgewebe ist so konzipiert, dass keine Daten erhoben werden, ohne dass du sie selbst
einträgst. Es gibt kein Tracking, keine versteckten Cookies, keine automatische Profilbildung. Sichtbar
wird nur das, was du freiwillig sichtbar machst: Name, Wohnort, Verbindungen im Gewebe. Deine persönlichen
Daten kannst du jederzeit verändern oder zurückziehen. Die Verarbeitung deiner Daten erfolgt auf Grundlage
von Artikel 6 Absatz 1 lit. a und f der Datenschutzgrundverordnung – also: Einverständnis & legitimes
Interesse an sicherer Gemeinschaftsorganisation.

## Technische Umsetzung

Ich arbeite an einem iPad und an einem Desktop PC.

Die technische Umsetzung soll maximale Kontrolle, Skalierbarkeit und Freiheit berücksichtigen. Es soll
stets die perspektivisch maximalst sinnvolle Lösung umgesetzt werden.
```

### 📄 docs/quickstart-gate-c.md

**Größe:** 546 B | **md5:** `9ebd955eee6d22093d170300d2822f2a`

```markdown
# Quickstart · Gate C (Dev-Stack)

```bash
cp .env.example .env
make up
# Web:  http://localhost:5173
# Proxy: http://localhost:8081
# API:  http://localhost:8081/api/version  (-> /version via Caddy)
make logs
make down
```

## Hinweise

- Frontend nutzt `PUBLIC_API_BASE=/api` (siehe `apps/web/.env.development`).
- Compose-Profil `dev` schützt vor Verwechslungen mit späteren prod-Stacks.
- `make smoke` triggert den GitHub-Workflow `compose-smoke` für einen E2E-Boot-Test.
- CSP ist im Dev gelockert; für externe Tiles Domains ergänzen.
```

### 📄 docs/runbook.md

**Größe:** 6 KB | **md5:** `fc66e5bfbda72c7a2023f79e4ac17684`

```markdown
# Runbook

Dieses Dokument enthält praxisorientierte Anleitungen für den Betrieb, die Wartung und das Onboarding
im Weltgewebe-Projekt.

## 1. Onboarding (Woche 1-2)

Ziel dieses Runbooks ist es, neuen Teammitgliedern einen strukturierten und schnellen Einstieg zu ermöglichen.

### Woche 1: Systemüberblick & lokales Setup

- **Tag 1: Willkommen & Einführung**
  - **Kennenlernen:** Team und Ansprechpartner.
  - **Projekt-Kontext:** Lektüre von [README.md](../README.md),
    [docs/overview/inhalt.md](overview/inhalt.md) und
    [docs/geist-und-plan.md](geist-und-plan.md).
  - **Architektur:** `docs/architekturstruktur.md` und `docs/techstack.md` durcharbeiten, um die
    Komponenten und ihre Zusammenspiel zu verstehen.
  - **Zugänge:** Accounts für GitHub, Docker Hub, etc. beantragen.

- **Tag 2-3: Lokales Setup**
  - **Voraussetzungen:** Git, Docker, Docker Compose, `just` und Rust (stable) installieren.
  - **Codespaces (Zero-Install):** GitHub Codespaces öffnen, das Devcontainer-Setup starten und im
    Terminal `npm run dev -- --host` ausführen. So lassen sich Frontend und API ohne lokale
    Installation testen – ideal auch auf iPad.
  - **Repository klonen:** `git clone <repo-url>`
  - **`.env`-Datei erstellen:** `cp .env.example .env`.
  - **Core-Stack starten:** `just up` (bevorzugt) oder `make up` als Fallback. Überprüfen, ob alle
    Container (`web`, `api`, `db`, `caddy`) laufen: `docker ps`.
  - **Web-Frontend aufrufen:** `http://localhost:5173` (SvelteKit-Devserver) oder – falls der Caddy
    Reverse-Proxy aktiv ist – `http://localhost:3000` im Browser öffnen.
  - **API-Healthcheck:** API-Endpunkt `/health` aufrufen, um eine positive Antwort zu sehen.

- **Tag 4-5: Erster kleiner Beitrag**
  - **Hygiene-Checks:** `just check` ausführen und sicherstellen, dass alle Linter, Formatierer und
    Tests erfolgreich durchlaufen.
  - **"Good first issue" suchen:** Ein kleines, abgeschlossenes Ticket (z.B. eine Textänderung in der
    UI oder eine Doku-Ergänzung) auswählen.
  - **Workflow üben:** Branch erstellen, Änderung implementieren, Commit mit passendem Präfix (`docs:
    ...` oder `feat(web): ...`) erstellen und einen Pull Request zur Review stellen.

### Woche 2: Vertiefung & erste produktive Aufgaben

- **Monitoring & Observability:**
  - **Monitoring-Stack starten:** `docker compose -f infra/compose/compose.observ.yml up -d`.
  - **Dashboards erkunden:** Grafana (`http://localhost:3001`) öffnen und die Dashboards für
    Web-Vitals, API-Latenzen und Systemmetriken ansehen.
- **Datenbank & Events:**
  - **Event-Streaming-Stack starten:** `docker compose -f infra/compose/compose.stream.yml up -d`.
  - **Datenbank-Migrationen:** Verzeichnis `apps/api/migrations/` ansehen, um die
    Schema-Entwicklung nachzuvollziehen.
- **Produktiv werden:**
  - **Erstes Feature-Ticket:** Eine überschaubare User-Story oder einen Bug bearbeiten, der alle
    Schichten (Web, API) betrifft.
  - **Pair-Programming:** Eine Session mit einem erfahrenen Teammitglied planen, um komplexere Teile

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__docs_adr.md

**Größe:** 5 KB | **md5:** `fb6f4ce7ede3613c234531e89e0150a3`

```markdown
### 📄 docs/adr/0042-consume-semantah-contracts.md

**Größe:** 276 B | **md5:** `eebc6c89ed10ea1704ace598b0064f93`

```markdown
# ADR-0042: semantAH-Contracts konsumieren

Status: accepted

Beschluss:

- Weltgewebe liest JSONL-Dumps (Nodes/Edges) als Infoquelle (read-only).
- Kein Schreibpfad zurück. Eventuelle Events: getrennte Domain.

Konsequenzen:

- CI validiert nur Formate; Import-Job später.
```

### 📄 docs/adr/ADR-0001__clean-slate-docs-monorepo.md

**Größe:** 315 B | **md5:** `a9e740a160cba7d00fa8f071255af7b8`

```markdown
# ADR-0001 — Clean-Slate als Docs-Monorepo

Datum: 2025-09-12
Status: Accepted
Entscheidung: Rückbau auf Doku-only. Re-Entry nur über klar definierte Gates.
Alternativen: Sofortiger Code-Reentry ohne ADR; verworfen wegen Drift-Risiko.
Konsequenzen: Vor Code zuerst Ordnungsprinzipien, Budgets, SLOs festhalten.
```

### 📄 docs/adr/ADR-0002__reentry-kriterien.md

**Größe:** 354 B | **md5:** `5a6822d1f593300a94d57cc86d6dea1d`

```markdown
# ADR-0002 — Re-Entry-Kriterien (Gates)

Datum: 2025-09-12
Status: Accepted
Gate A (Web): SvelteKit-Skelett + Budgets (TTI ≤2s, INP ≤200ms, ≤60KB JS).
Gate B (API): Health/Version, Contracts, Migrations-Plan.
Gate C (Infra-light): Compose dev, Caddy/CSP-Basis, keine laufenden Kosten.
Gate D (Security-Basis): Secrets-Plan, Lizenz-/Datenhygiene.
```

### 📄 docs/adr/ADR-0003__privacy-unschaerferadius-ron.md

**Größe:** 3 KB | **md5:** `f864059948a3cbad3cd93757311430b4`

```markdown
# ADR-0003 — Privacy: Unschärferadius & RoN-Platzhalterrolle (v1)

Datum: 2025-09-13  
Status: Accepted

## Kontext

Die Garnrolle ist am Wohnsitz verortet (Residence-Lock). Die Karte und die Fäden sollen ortsbasierte
Sichtbarkeit ermöglichen, ohne den exakten Wohnsitz preiszugeben - sofern dies explizit vom Nutzer gewünscht
ist. Generell gilt: Transparenz ist Standard – Privacy-Optionen sind ein freiwilliges Zugeständnis für
Nutzer, die das wünschen.

## Entscheidung

1) **Unschärferadius r (Meter)**  
   Der Nutzer kann die öffentliche Genauigkeit seiner Garnrolle über einen **Unschärferadius** selbst
   einstellen. Die **öffentliche Anzeige** nutzt eine **ungenaue Position innerhalb dieses Radius**.
   Alle öffentlichen Darstellungen und Beziehungen (Fäden/Garn) beziehen sich auf diese angezeigte Position.

2) **RoN-Platzhalterrolle (Toggle)**  
   Optional kann sich ein Nutzer **als „RoN“** (Rolle ohne Namen) zeigen bzw. Beiträge **anonymisieren**.
   Anonymisierte Fäden verweisen nicht mehr auf die ursprüngliche Garnrolle, sondern auf den
   **RoN-Platzhalter**. Beim Ausstieg werden Beiträge gemäß RoN-Prozess überführt.

3) **Transparenz als Standard**  
   Standard ist **ohne Unschärfe und ohne RoN**. Die Optionen sind **Opt-in** und dienen der persönlichen
   Zurückhaltung, nicht der Norm.

## Alternativen

Weitere Modi (z. B. Kachel-Snapping, Stadt-Centroid) werden **nicht** eingeführt.

## Konsequenzen

- **Einfaches UI**: **Slider** (Meter) für den Unschärferadius, **Toggle** für RoN.  
- **Konsistente Darstellung**: Öffentliche Fäden starten an der öffentlich angezeigten Position der Garnrolle.  
- **Eigenverantwortung**: Nutzer wählen ihre gewünschte Sichtbarkeit bewusst.

## Schnittstellen

- **Events**  
  - `VisibilityPreferenceSet { radius_m }`  
  - `RonEnabled` / `RonDisabled`
- **Views**  
  - intern: `roles_view` (exakte Position, nicht öffentlich)  
  - öffentlich: `public_role_view (id, public_pos, ron_flag, radius_m)`  
  - `faden_view` nutzt `public_pos` als Startpunkt

## UI

**Einstellungen → Privatsphäre**: Unschärfe-Slider (Meter) + RoN-Toggle (inkl. Einstellbarkeit der Tage
(beginnend mit 0, ab der die RoN-Anonymisierung greifen soll). Vorschau der angezeigten Position.

## Telemetrie & Logging

Keine exakten Wohnsitz-Koordinaten in öffentlichen Daten oder Logs, sofern gewünscht; personenbezogene Daten
nur, wo nötig.

## Rollout

- **Web**: Slider + Toggle und Vorschau integrieren.  
- **API**: `/me/visibility {GET/PUT}`, `/me/roles` liefert `public_pos`, `ron_flag`, `radius_m`.  
- **Worker**: Privacy-Auflösung vor Projektionen (`public_role_view` vor `faden_view`).
```

### 📄 docs/adr/ADR-0004__fahrplan-verweis.md

**Größe:** 874 B | **md5:** `e704ae31604d2be399186837a67ca35b`

```markdown
# ADR-0004 — Fahrplan als kanonischer Verweis

Datum: 2025-02-14
Status: Accepted

## Kontext

Der Projektfahrplan wird bereits in `docs/process/fahrplan.md` gepflegt. Dieses ADR dient lediglich als
stabile, versionierte Referenz auf diesen kanonischen Speicherort und vermeidet inhaltliche Duplikate.

## Entscheidung

- Der Fahrplan bleibt **kanonisch** in `docs/process/fahrplan.md`.
- Dieses Dokument enthält **keine Kopie** des Fahrplans, sondern verweist ausschließlich darauf.

## Konsequenzen

- Anpassungen am Fahrplan erfolgen ausschließlich in der Prozessdokumentation.
- Architekturentscheidungen und weitere Dokumente verlinken auf den Fahrplan über dieses ADR.

## Link

- [Fahrplan in docs/process](../process/fahrplan.md)

## Siehe auch

- [ADR-0003 — Privacy: Unschärferadius & RoN-Platzhalterrolle (v1)](ADR-0003__privacy-unschaerferadius-ron.md)
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_dev.md

**Größe:** 564 B | **md5:** `61fa3ad75f49c3bd43e7ab63e3a60439`

```markdown
### 📄 docs/dev/codespaces.md

**Größe:** 448 B | **md5:** `539e936bc772bd3ec55d4aa23b73f07d`

```markdown
# Codespaces: Dev-Server schnell starten

Im Codespace werden die Web-Abhängigkeiten automatisch installiert.

**Start:**

```bash
cd apps/web
npm run dev -- --host
```

Codespaces öffnet automatisch den Port **5173** – Link anklicken, `/map` ansehen.

**Troubleshooting:**  

- „vite: not found“: `npm i -D vite` und erneut starten.  
- „leere Seite“: einmal im Kartenbereich klicken (Keyboard-Fokus), dann `[` / `]` / `Alt+G` testen.
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_edge_systemd.md

**Größe:** 966 B | **md5:** `cfa5c840dd66d28619ee8cbf4af92a41`

```markdown
### 📄 docs/edge/systemd/README.md

**Größe:** 214 B | **md5:** `cead3a78ff4ddffd156fd97cde9b4061`

```markdown
# Edge systemd units (optional)

This is **not** the primary orchestration path. Default remains **Docker Compose → Nomad**.
Use these units only for tiny single-node edge installs where Compose isn't available.
```

### 📄 docs/edge/systemd/weltgewebe-projector.service

**Größe:** 490 B | **md5:** `59549cecea7d486a5ea6ce8db0907aab`

```plaintext
[Unit]
Description=Weltgewebe Projector (timeline/search)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Environment=RUST_LOG=info
EnvironmentFile=/etc/weltgewebe/projector.env
ExecStart=/usr/local/bin/weltgewebe-projector
Restart=on-failure
RestartSec=3

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_overview.md

**Größe:** 4 KB | **md5:** `e1d1f96ed4b6ce3993b2472b2584fb69`

```markdown
### 📄 docs/overview/inhalt.md

**Größe:** 2 KB | **md5:** `6f065ff394abd87be4043025db5fc89b`

```markdown
# Einführung: Ethik- & UX-First-Startpunkt

Die Weltgewebe-Initiative stellt Menschen und ihre Lebensrealität in den Mittelpunkt.
Die technische Plattform – SvelteKit für das Web-Frontend, Axum als Rust-API sowie Postgres
und JetStream im Daten- und Event-Backbone – ist Mittel zum Zweck: Sie schafft Transparenz,
Handlungssicherheit und nachhaltige Teilhabe.
Dieses Dokument bietet Außenstehenden einen klaren Einstieg in die inhaltliche Stoßrichtung
des Projekts.

## Leitplanken & Prinzipien

- **Ethik vor Feature-Liste:** Entscheidungen werden entlang von Wirkungszielen und Schutzbedarfen
  priorisiert.
  UX-Entscheidungen orientieren sich an Barrierefreiheit, Datenschutz und erklärbaren Abläufen.
- **Partizipation sichern:** Stakeholder:innen aus Zivilgesellschaft, Verwaltung und Forschung
  erhalten früh Zugang zu Prototypen, um Risiken zu erkennen und gemeinsam zu mitigieren.
- **Transparenz herstellen:** Dokumentation, Policies und öffentlich nachvollziehbare
  Entscheidungen haben Vorrang vor reinem Feature-Output.

## Projektumfang (Docs-only, Gate-Strategie)

Das Repository befindet sich in Phase ADR-0001 „Docs-only“.
Technische Re-Entry-Pfade sind über Gates A–D definiert.
So bleiben Experimente nachvollziehbar und können schrittweise in den Produktionskontext
überführt werden.

## Weitere Orientierung

- **Systematik & Struktur:** Siehe `docs/overview/zusammenstellung.md`.
- **Architektur-Details:** `architekturstruktur.md` fasst Domänen, Boundaries und Kommunikationspfade zusammen.
- **Fahrplan & Prozesse:** `docs/process/fahrplan.md` beschreibt Freigaben, Gates und Quality-Gates.

> _Stand:_ Docs-only, Fokus auf Ethik, UX und transparente Entscheidungsprozesse.
> Mit dem Startpunkt hier und der Systematik im Schwesterdokument erhalten Außenstehende in
> zwei Klicks den vollständigen Projektkontext.
```

### 📄 docs/overview/zusammenstellung.md

**Größe:** 2 KB | **md5:** `ab6cbff930700676b08bb59271a33fbc`

```markdown
# Systematik & Strukturüberblick

Diese Zusammenstellung führt durch die zentralen Orientierungspunkte der Weltgewebe-Dokumentation.
Sie ergänzt die inhaltliche Einführung (`docs/overview/inhalt.md`) und macht deutlich,
wie Ethik & UX entlang des gesamten Vorhabens abgesichert werden.

## Kernartefakte

| Bereich | Zweck | Primäre Ressourcen |
| --- | --- | --- |
| **Ethik & Wirkung** | Leitplanken, Risiken, Schutzbedarfe | `policies/`, `docs/ethik/`, `docs/process/fahrplan.md` |
| **User Experience** | UX-Guidelines, Prototypen, Feedback-Loops | `apps/web/README.md`, `docs/ux/`, `docs/runbooks/` |
| **Architektur** | Technische Boundaries, Integrationen | `architekturstruktur.md`, `docs/architecture/` |
|                 | Datenflüsse                          | `contracts/` |
| **Betrieb & Qualität** | Gates, CI/CD, Observability, Budgets | `docs/process/`, `ci/`, `policies/limits.yaml` |

## Navigationspfad für Außenstehende

1. **Einführung lesen:** `docs/overview/inhalt.md` liefert Vision, Prinzipien und Scope.
2. **Systematik prüfen:** Dieses Dokument zeigt, wo welche Detailtiefe zu finden ist.
3. **Architektur & Fahrplan vertiefen:**
   - `architekturstruktur.md` für Domänen & Komponenten.
   - `docs/process/fahrplan.md` für Timeline, Gates und Verantwortlichkeiten.
4. **Ethik & UX-Vertiefung:**
   - `docs/ethik/` für Entscheidungskriterien und Risikokataloge.
   - `docs/ux/` und `apps/web/README.md` für Prototypen und Research-Ansätze.

## Rollen & Verantwortlichkeiten

- **Ethik/Governance:** Kuratiert Policies, überprüft Releases gegen Schutzbedarfe.
- **UX-Research & Design:** Verantwortet Tests, Insights und Accessibility-Guidelines.
- **Tech Leads:** Halten Architekturdokumentation und Verträge aktuell.
- **Ops & QA:** Betreiben Gates, Observability und Budget-Checks in CI.

## Verbindung zu den Gates

Jedes Gate (A–D) besitzt eine eigene Dokumentation in `docs/process/`.
Die Gates stellen sicher, dass neue Funktionen den Ethik- und UX-Anforderungen
entsprechen, bevor sie in den produktiven Stack überführt werden.
Die Zusammenstellung dient als Index, um die passenden Unterlagen pro Gate rasch
zu finden.

> _Hinweis:_ Ergänzende Artefakte (z. B. Workshops, Entscheidungen, ADRs)
> werden im jeweiligen Ordner verlinkt, sobald sie vorliegen. Diese Systematik
> wird fortlaufend gepflegt und bildet den verbindlichen Einstiegspunkt für neue
> Teammitglieder ebenso wie externe Auditor:innen.
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_policies.md

**Größe:** 6 KB | **md5:** `ead681e01723a843e8812af7f7ffe6ab`

```markdown
### 📄 docs/policies/orientierung.md

**Größe:** 5 KB | **md5:** `1f169aa5b19f0c555c669faaff7bf2d1`

```markdown
# Leitfaden · Ethik & Systemdesign (Weltgewebe)

**Stand:** 2025-10-06
**Quelle:**

- [inhalt.md](../overview/inhalt.md)
- [zusammenstellung.md](../overview/zusammenstellung.md)
- [geist-und-plan.md](../geist-und-plan.md)
- [fahrplan.md](../process/fahrplan.md)
- [techstack.md](../techstack.md)

---

## 1 · Zweck

Dieses Dokument verdichtet Geist, Plan und technische Architektur des Weltgewebes zu einer
verbindlichen Orientierung für
Entwicklung, Gestaltung und Governance.
Es beschreibt:

- **Was** ethisch gilt.
- **Wie** daraus technische und gestalterische Konsequenzen folgen.
- **Woran** sich Teams bei Entscheidungen künftig messen lassen.

---

## 2 · Philosophie („Geist“)

- **Freiwilligkeit**
  - Bedeutung: Keine Handlung ohne bewusste Zustimmung.
  - Operative Konsequenz: Opt-in-Mechanismen, keine versteckten Datenflüsse.
- **Transparenz**
  - Bedeutung: Alles Sichtbare ist verhandelbar; nichts Geschlossenes.
  - Operative Konsequenz: Offene APIs, nachvollziehbare Governance-Entscheide.
- **Vergänglichkeit**
  - Bedeutung: Informationen altern sichtbar; kein endloses Archiv.
  - Operative Konsequenz: Zeitliche Sichtbarkeit („Fade-out“), Lösch- und Verblassungsprozesse.
- **Commons-Orientierung**
  - Bedeutung: Engagement ≠ Geld; Beiträge = Währung.
  - Operative Konsequenz: Spenden (Goldfäden) optional, sonst Ressourcen-Teilung.
- **Föderation**
  - Bedeutung: Lokale Autonomie + globale Anschlussfähigkeit.
  - Operative Konsequenz: Ortswebereien mit eigenem Konto + föderalen Hooks.
- **Privacy by Design**
  - Bedeutung: Sichtbar nur freiwillig Eingetragenes.
  - Operative Konsequenz: Keine Cookies/Tracking; RoN-System für Anonymität.

---

## 3 · Systemlogik („Plan“)

### 3.1 Domänenmodell

- **Rolle / Garnrolle**
  - Beschreibung: Verifizierter Nutzer (Account) + Position + Privat-/Öffentlich-Bereich.
- **Knoten**
  - Beschreibung: Informations- oder Ereignis-Bündel (Idee, Ressource, Ort …).
- **Faden**
  - Beschreibung: Verbindung zwischen Rolle und Knoten (Handlung).
- **Garn**
  - Beschreibung: Dauerhafte, verzwirnte Verbindung = Bestandsschutz.

### 3.2 Zeit und Prozesse

- **7-Sekunden-Rotation** → sichtbares Feedback nach Aktion.
- **7-Tage-Verblassen** → nicht verzwirnte Fäden/Knoten lösen sich auf.
- **7 + 7-Tage-Modell** → Anträge: Einspruch → Abstimmung.
- **Delegation (Liquid Democracy)** → verfällt nach 4 Wochen Inaktivität.
- **RoN-System** → anonymisierte Beiträge nach gewählter Frist.

---

## 4 · Ethisch-technische Defaults

- Sichtbarkeit (`fade_days`)
  - Richtwert: 7 Tage laut zusammenstellung.md.
  - Herkunft: Funktionsbeschreibung, nicht Code.
- Identität (`ron_alias_valid_days`)
  - Richtwert: 28 Tage (Delegations-Analogon).
  - Herkunft: Geist & Plan-Ableitung.
- Anonymisierung (`default_anonymized`)
  - Richtwert: *nicht festgelegt*, nur „Opt-in möglich“.
  - Herkunft: zusammenstellung.md, Abschnitt III.
- Ortsdaten (`unschaerferadius_m`)
  - Richtwert: individuell einstellbar.
  - Herkunft: zusammenstellung.md, Abschnitt III.
- Delegation (`delegation_expire_days`)
  - Richtwert: 28 Tage (4 Wochen).
  - Herkunft: § IV Delegation.

> **Hinweis:** Die Werte 7/7/28 Tage sind aus der Beschreibung im Repo abgeleitet – nicht normativ festgelegt.
> Änderungen erfordern Governance-Beschluss + Changelog-Eintrag.

---

## 5 · Governance-Matrix

- Antrag
  - Dauer: 7 Tage + 7 Tage.
  - Sichtbarkeit: öffentlich.
  - Trigger: Timer oder Einspruch.
- Delegation
  - Dauer: 4 Wochen.
  - Sichtbarkeit: transparent (gestrichelte Linien).
  - Trigger: Inaktivität.
- Meldung / Freeze
  - Dauer: 24 h.
  - Sichtbarkeit: eingeklappt.
  - Trigger: Moderations-Vote.
- RoN-Anonymisierung
  - Dauer: variable x Tage.
  - Sichtbarkeit: „Rolle ohne Namen“.
  - Trigger: User-Opt-in.

---

## 6 · Technische Leitplanken (aus techstack.md)

- **Architektur:** Rust API (Axum) + SvelteKit Frontend + PostgreSQL / NATS JetStream
  (Event-Sourcing).
- **Monitoring:** Prometheus + Grafana + Loki + Tempo.
- **Security:** SBOM + cosign + Key-Rotation + DSGVO-Forget-Pipeline.
- **HA & Cost Control:** Nomad Cluster · PgBouncer · Opex-KPIs < €1 / Session.
- **Privacy UI (ADR-0003):** RoN-Toggle + Unschärferadius-Slider (ab Phase C).

---

## 7 · Design-Ethik → UX-Richtlinien

1. **Transparente Zeitlichkeit:** Fade-Animationen zeigen Vergänglichkeit, nicht Löschung.
2. **Partizipative Interface-Metaphern:** Rollen drehen, Fäden fließen – Verantwortung wird
   sichtbar.
3. **Reversible Aktionen:** Alles ist änder- oder verzwirnbar, aber nicht heimlich.
4. **Privacy Controls Front and Center:** Slider / Toggles direkt im Profil.
5. **Lokale Sichtbarkeit:** Zoom ≈ Vertraulichkeit; Unschärfe nimmt mit Distanz zu.
6. **Keine versteckte Gamification:** Engagement wird nicht bewertet, nur sichtbar gemacht.

---

## 8 · Weiterer Fahrplan (Querschnitt aus fahrplan.md)

- Phase A
  - Ziel: Minimal-Web (SvelteKit + Map).
  - Ethik-Bezug: Transparenz sichtbar machen – Karte hallo sagen.
- Phase B
  - Ziel: API + Health + Contracts.
  - Ethik-Bezug: Nachvollziehbarkeit von Aktionen.
- Phase C
  - Ziel: Privacy UI + 7-Tage-Verblassen.
  - Ethik-Bezug: Privacy by Design erlebbar machen.
- Phase D
  - Ziel: Persistenz + Outbox-Hook.
  - Ethik-Bezug: Integrität von Ereignissen.
- Phase …
  - Ziel: Langfristig Föderation + Delegations-Audits.
  - Ethik-Bezug: Verantwortung skaliert halten.


## 9 · Governance / Changelog-Pflicht

Alle Änderungen an:

- Datenschutz- oder Ethikparametern.
- Governance-Timern.
- Sichtbarkeits-Mechaniken.
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_process.md

**Größe:** 13 KB | **md5:** `bf680fbd9743cab2c71844c2180f0335`

```markdown
### 📄 docs/process/README.md

**Größe:** 350 B | **md5:** `a64145073affb3b77a3cdf93997e0251`

```markdown
# Prozess

Übersicht über Abläufe und Konventionen.

## Index

- [Fahrplan](fahrplan.md) – zeitlicher Ablauf und Meilensteine (**kanonisch**)
- [Sprache](sprache.md) – Leitfaden zur Projektsprache
- [Bash Tooling Guidelines](bash-tooling-guidelines.md) – Best Practices für zukünftige Shell-Skripte

[Zurück zum Doku-Index](../README.md)
```

### 📄 docs/process/bash-tooling-guidelines.md

**Größe:** 3 KB | **md5:** `ef60df9aa99bb48d8f5b68ea6e049bab`

```markdown
# Bash-Tooling-Richtlinien

Diese Richtlinien beschreiben, wie wir Shell-Skripte im Weltgewebe-Projekt entwickeln, prüfen und ausführen.  
Sie kombinieren generelle Best Practices (Formatierung, Checks) mit projektspezifischen Vorgaben
wie Devcontainer-Setup, CLI-Bootstrap und SemVer.

## Ziele

- Einheitliche Formatierung der Skripte.
- Automatisierte Qualitätssicherung mit statischer Analyse.
- Gute Developer Experience für wiederkehrende Aufgaben.
- Projektkontext: sauberes Devcontainer-Setup, klare CLI-Kommandos, reproduzierbare SemVer-Logik.

## Kernwerkzeuge

### shfmt

- Formatierung gemäß POSIX-kompatiblen Standards.
- Nutze `shfmt -w` für automatische Formatierung.
- Setze `shfmt -d` in CI-Checks ein, um Abweichungen aufzuzeigen.

### ShellCheck

- Analysiert Skripte auf Fehler, Portabilität und Stilfragen.
- Lokaler Aufruf: `shellcheck <skript>`.
- In CI-Pipelines verpflichtend.

### Bash Language Server (optional)

- Bietet Editor-Unterstützung (Autocompletion, Inlay-Hints).
- Installierbar via `npm install -g bash-language-server`.
- Im Editor als LSP aktivieren.

## Arbeitsweise

1. Skripte beginnen mit `#!/usr/bin/env bash` und enthalten `set -euo pipefail`.
2. Vor Commit: `shfmt` und `shellcheck` lokal ausführen.
3. Ergebnisse der Checks im Pull Request sichtbar machen.
4. Neue Tools → Dokumentation hier ergänzen.
5. CI-Checks sind verbindlich; Ausnahmen werden dokumentiert.

## Projektspezifische Ergänzungen

### Devcontainer-Setup

- **Bash-Version dokumentieren** (z. B. Hinweis auf `nameref` → Bash ≥4.3).
- **Paketsammlungen per Referenz (`local -n`)** statt Subshell-Kopien.
- **`check`-Ziel ignorieren**, falls versehentlich mitinstalliert.

### CLI-Bootstrap (`wgx`)

- Debug-Ausgabe optional via `WGX_DEBUG=1`.
- Dispatcher validiert Subcommands:  
  - Ohne Argument → Usage + `exit 1`.  
  - Unbekannte Befehle → Fehlermeldung auf Englisch (für CI-Logs).  
  - Usage-Hilfe auf `stderr`.

### SemVer-Caret-Ranges

- `^0.0.x` → nur Patch-Updates erlaubt.
- Major-Sprünge blockiert (`^1.2.3` darf nicht auf `2.0.0` gehen).  
- Automatisierte Bats-Tests dokumentieren dieses Verhalten.

## Troubleshooting

- Legacy-Skripte mit `# shellcheck disable=...` markieren und begründen.  
- Plattformunterschiede (Linux/macOS) im Skript kommentieren.  
- `shfmt`-Fehler → prüfen, ob Tabs statt Spaces verwendet wurden (wir nutzen nur Spaces).

---

Diese Leitlinien werden zum **Gate-C-Übergang** erneut evaluiert und ggf. in produktive Skripte überführt.  
Weitere Infos werden im Fahrplan dokumentiert.
```

### 📄 docs/process/fahrplan.md

**Größe:** 9 KB | **md5:** `f91c67532806d908e78f8f595aa60876`

```markdown
# Fahrplan

**Stand:** 2025-10-20

**Bezug:**

- ADR-0001 (Clean Slate & Monorepo)
- ADR-0002 (Re-Entry-Kriterien)
- ADR-0003 (Privacy: Unschärferadius & RoN)

## Prinzipien: mobile-first, audit-ready, klein schneiden, Metriken vor Features

## Inhalt

- [Kurzfahrplan (Gates A–D)](#kurzfahrplan-gates-ad)
- [Gate-Checkliste (A–D)](#gate-checkliste-ad)
  - [Gate A — Web (SvelteKit) *Minimal sichtbares Skelett*](#gate-a--web-sveltekit-minimal-sichtbares-skelett)
  - [Gate B — API (Axum) *Health & Kernverträge*](#gate-b--api-axum-health--kernverträge--phaseziele)
  - [Gate C — Infra-light (Compose, Caddy, PG)](#gate-c--infra-light-compose-caddy-pg--phaseziele)
  - [Gate D — Security-Basis](#gate-d--security-basis-grundlagen)
- [0) Vorbereitungen (sofort)](#0-vorbereitungen-sofort)
- [Gate A — Web (SvelteKit) *Minimal sichtbares Skelett* —
  Phaseziele](#gate-a--web-sveltekit-minimal-sichtbares-skelett--phaseziele)

---

## Kurzfahrplan (Gates A–D)

- **Gate A:** UX Click-Dummy (keine Backends)
- **Gate B:** API-Mock (lokal)
- **Gate C:** Infra-light (Compose, minimale Pfade)
- **Gate D:** Produktive Pfade (härten, Observability)

## Gate-Checkliste (A–D)

### Gate A — Web (SvelteKit) *Minimal sichtbares Skelett*

#### Checkliste „bereit für Gate B“

- [ ] Interaktiver UX-Click-Dummy ist verlinkt (README) und deckt Karte → Knoten → Zeit-UI ab.
- [ ] Contracts-Schemas (`contracts/`) für `node`, `role`, `thread` abgestimmt und dokumentiert.
- [ ] README-Landing beschreibt Click-Dummy, Contracts und verweist auf diesen Fahrplan.
- [ ] Vale-Regeln laufen gegen README/Fahrplan ohne Verstöße.
- [ ] PWA installierbar, Offline-Shell lädt Grundlayout.
- [ ] Dummy-Karte (MapLibre) sichtbar, Layout-Slots vorhanden; Budgets ≤ 60 KB / TTI ≤ 2 s
  dokumentiert.
- [ ] Minimal-Smoke-Test (Playwright) grün, Lighthouse Mobile ≥ 85.

### Gate B — API (Axum) *Health & Kernverträge*

#### Checkliste „bereit für Gate C“

- [ ] Axum-Service liefert `/health/live`, `/health/ready`, `/version`.
- [ ] OpenAPI-Stub (utoipa) generiert und CI veröffentlicht Artefakt.
- [ ] Kernverträge (`POST /nodes`, `GET /nodes/{id}`, `POST /roles`, `POST /threads`) als Stubs
  implementiert.
- [ ] `migrations/` vorbereitet (Basis-Tabellen) und CI führt `cargo fmt`, `clippy -D warnings`,
  `cargo test` aus.
- [ ] `docker compose` (nur API) startet fehlerfrei.
- [ ] Contract-Test gegen `POST /nodes` grün, OpenAPI JSON abrufbar.

### Gate C — Infra-light (Compose, Caddy, PG)

#### Checkliste „bereit für Gate D“

- [ ] `infra/compose/compose.core.yml` umfasst web, api, postgres, pgBouncer, caddy.
- [ ] `infra/caddy/Caddyfile` mit HTTP/3, strikter CSP, gzip/zstd vorhanden.
- [ ] `.env.example` komplettiert, Healthchecks für Dienste konfiguriert.
- [ ] `docker compose -f infra/compose/compose.core.yml up -d` läuft lokal ohne Fehler.
- [ ] Caddy terminiert TLS (self-signed) und proxyt Web+API korrekt.
- [ ] Web-Skelett lädt mit CSP ohne Console-Fehler.

### Gate D — Security-Basis

#### Checkliste „bereit für Re-Entry“

- [ ] Lizenz final (AGPL-3.0-or-later) bestätigt und dokumentiert.
- [ ] Secrets-Plan (sops/age) dokumentiert, keine Klartext-Secrets im Repo.
- [ ] SBOM/Scan (Trivy oder Syft) in CI aktiv, bricht bei kritischen CVEs ab.
- [ ] Runbook „Incident 0“ (Logs sammeln, Restart, Contact) verfügbar.
- [ ] CI schützt Budgets, Policies verlinkt; Observability-Basis beschrieben.

> Details, Akzeptanzkriterien, Budgets und Risiken folgen im Langteil unten.

---

## 0) Vorbereitungen (sofort)

- **Sprache & Vale:** Vale aktiv, Regeln aus `styles/Weltgewebe/*` verbindlich.
- **Lizenz gewählt:** `LICENSE` verwendet **AGPL-3.0-or-later**.
- **Issue-Backlog:** Mini-Issues je Punkt unten (30–90 Min pro Issue).

**Done-Kriterien:** Vale grün in PRs; Lizenz festgelegt; 10–20 Start-Issues.

---

## Gate A — Web (SvelteKit) *Minimal sichtbares Skelett* — Phaseziele

**Ziel:** „Karte hallo sagen“ – startfähiges Web, PWA-Shell, Basislayout, MapLibre-Stub.

### Gate A: Umfang

- PWA: `manifest.webmanifest`, Offline-Shell, App-Icon.
- Layout: Header-Slot, Drawer-Platzhalter (links: Webrat/Nähstübchen, rechts: Filter/Zeitleiste).
- Route `/`: Überschrift + Dummy-Karte (MapLibre einbinden, Tiles später).
- Budgets: **≤60 KB Initial-JS**, **TTI ≤2 s** (Mess-Skript + Budgetdatei).
- Telemetrie (Client): PerformanceObserver für Long-Tasks (nur Log/console bis Gate C).

### Gate A: Aufgabenblöcke

- **UX-Click-Dummy:** Interaktiver Ablauf für Karte → Knoten → Zeit-UI. Figma/Tool-Link im README
  vermerken.
- **Contracts-Schemas:** JSON-Schemas/OpenAPI für `node`, `role`, `thread`
  abstimmen (Basis für Gate B). Ablage unter `contracts/` und im README
  verlinken.
- **README-Landing:** Landing-Abschnitt aktualisieren (Screenshot/Diagramm +
  Hinweise zum Click-Dummy, Contracts, Fahrplan).
- **Vale-Regeln:** Vale-Regeln aus `styles/Weltgewebe/*` gegen README,
  Fahrplan und Gate-A-Dokumente prüfen, Verstöße beheben.

### Gate A: Done

- Lighthouse lokal ≥ 85 (Mobile), Budgets eingehalten.
- PWA installierbar, Offline-Shell lädt Grundlayout.
- Minimal-Smoke-Test (Playwright) läuft.

---

## Gate B — API (Axum) *Health & Kernverträge* — Phaseziele

**Ziel:** API lebt, dokumentiert und testet minimal **Kernobjekte**: Knoten, Rolle, Faden.

### Gate B: Umfang

- Axum-Service mit `/health/live`, `/health/ready`, `/version`.
- OpenAPI-Stub (utoipa) generiert.
- **Kernverträge:** `POST /nodes`, `GET /nodes/{id}`, `POST /roles`, `POST /threads`
  (Stub-Implementierung).
- `migrations/` vorbereitet (ohne Fachtabellen).
- CI: `cargo fmt`, `clippy -D warnings`, `cargo test`.

### Gate B: Done

- `docker compose` (nur API) startet grün.
- OpenAPI JSON auslieferbar, minimaler Contract-Test grün (inkl. `POST /nodes`).

---

## Gate C — Infra-light (Compose, Caddy, PG) — Phaseziele

**Ziel:** Dev-Stack per `compose.core.yml` startbar (web+api+pg+caddy).

### Gate C: Umfang

- `infra/compose/compose.core.yml`: web, api, postgres, pgBouncer, caddy.
- `infra/caddy/Caddyfile`: HTTP/3, strikte CSP (später lockern), gzip/zstd.
- `.env.example` vervollständigt; Healthchecks verdrahtet.

### Gate C: Done

- `docker compose -f infra/compose/compose.core.yml up -d` läuft lokal.
- Caddy terminiert TLS lokal (self-signed), Proxies funktionieren.
- Basic CSP ohne Console-Fehler im Web-Skelett.

---

## Gate D — Security-Basis (Grundlagen)

**Ziel:** Minimaler Schutz und Compliance-Leitplanken.

### Gate D: Umfang

- **Lizenz final** (AGPL-3.0-or-later empfohlen).
- Secrets-Plan (sops/age, kein Klartext im Repo).
- SBOM/Scan: Trivy oder Syft in CI (Fail bei kritischen CVEs).
- Doku-Pfad: Kurz-Runbook „Incident 0“ (Logs sammeln, Restart, Contact).

### Gate D: Done

- Lizenz im Repo, CI bricht bei kritischen CVEs.
- Runbook-Skelett vorhanden.

---

## Phase A (Woche 1–2): **Karten-Demo, Zeit-UI, Knoten-Placement**

- Karte sichtbar (MapLibre), Dummy-Layer, UI-Skeleton für Filter & Zeitleiste.
- Zeit-Slider (UI) ohne Datenwirkung, nur State/URL-Sync.
- **Knoten anlegen (UI)**: kleines Formular (Name), flüchtige Speicherung (Client/Mem), Marker
  erscheint.
- Mobile-Nav-Gesten (Drawer wischen).

**Akzeptanz:** Mobile Lighthouse ≥ 90; TTI ≤ 2 s; UI-Flows klickbar; Knoten-Form erzeugt Marker.

---

## Phase B (Woche 3–4): **Kernmodell — Knoten, Rolle, Faden**

- Domain-Events: `node.created`, `role.created`, `thread.created`.
- Tabellen (PG): `nodes`, `roles`, `threads` (nur ID/Meta), Outbox (leer, aber vorhanden).
- API: `POST /nodes`, `GET /nodes/{id}` echt (PG); `POST /roles`, `POST /threads` stub.
- Web: „Rolle drehen 7 Sekunden“ (UI-Effekt), Faden-Stub Linie Rolle→Knoten (Fake-Data).

**Akzeptanz:** Knoten persistiert in PG; Faden-Stub sichtbar; E2E-Flow „Knoten knüpfen“ klickbar.

---

## Phase C (Woche 5–6): **Privacy-UI (ADR-0003) & 7-Tage-Verblassen**

- UI: **Unschärferadius-Slider** + **RoN-Toggle** (Profil-State; Fake-Persist).
- Zeitleiste wirkt auf Sichtbarkeit (Fäden/Knoten blenden weich aus; Client-seitig).
- `public_pos` im View-Modell (Fake-Backend oder Local-Derivation).

**Akzeptanz:** Vorschau der öffentlichen Position reagiert; Zeitleiste verhält sich wie
spezifiziert.

---

## Phase D (Woche 7–8): **Persistenz komplett & Outbox-Hook**

- API: echte Writes für Rolle/Faden in PG; Outbox-Write (noch ohne NATS-Relay).
- Worker-Stub: CLI liest Outbox und füllt Read-Model `public_role_view`.
- Web: liest Read-Model, zeigt `public_pos`, respektiert RoN-Flag.

**Akzeptanz:** Neustart-fest; nach Write→Read-Model erscheint korrekte `public_pos`.

---

## Messpunkte & Budgets

- Web: Initial-JS ≤ 60 KB; p75 Long-Tasks ≤ 200 ms/Route.
- API: p95 Latenz ≤ 300 ms (lokal); Fehlerquote < 1 %.
- Compose-Start ≤ 30 s bis „grün“.

---

## Risiken (kurz)

- Überplanung bremst Tempo → **kleine Issues** erzwingen.
- Privacy-Erwartung vs. Transparenz-Standard → UI-Texte klar formulieren.
- Mobile-Leistung → Budgets als CI-Gate früh aktivieren.

---

## Nächste konkrete Schritte

1. Gate A-Issues anlegen, PWA/Map-Stub bauen.
2. Compose core vorbereiten (web+api+pg+caddy), Caddy mit CSP.
3. API Gate B: `POST /nodes` als erster echter Vertrag, einfache PG-Migration `nodes`.
4. Privacy-UI (Slider/Toggle) per Feature-Flag einhängen.
```

### 📄 docs/process/sprache.md

**Größe:** 826 B | **md5:** `4557cff8f801c413a82df07f72ad138c`

```markdown
# Sprache & Ton im Weltgewebe

## 1. Grundsatz

- Primärsprache Deutsch (Duden-nah), Du-Form, präzise, knapp.
- Keine Gender-Sonderzeichen (Stern, Doppelpunkt, Binnen-I, Mediopunkt, Slash).
- Anglizismen nur bei echten Fachbegriffen ohne gutes deutsches Pendant.

## 2. Formatkonventionen

- UI: 24-h-Zeit, TT.MM.JJJJ, Dezimalkomma.
- Code/Protokolle: ISO-8601, Dezimalpunkt, SI-Einheiten.

## 3. Artefakte

- Commits: Conventional Commits; Kurzbeschreibung deutsch.
- Code-Kommentare: Englisch (knapp); ADRs/Domäne: Deutsch.
- PRs: deutsch, mit Evidenz-Verweisen.

## 4. Verbote & Alternativen

- Verboten: Schüler:innen, Schüler*innen, SchülerInnen, Schüler/innen, Schüler·innen.
- Nutze Alternativen: Lernende, Team, Ansprechperson, Beteiligte.

## 5. Prüfung

- Vale als Prose-Linter; PR blockt bei Verstößen.
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_reports.md

**Größe:** 163 B | **md5:** `35436bc00d64b6c2b94ccd5000590b02`

```markdown
### 📄 docs/reports/cost-report.md

**Größe:** 43 B | **md5:** `aa21a19145a081b543bd3b7c24d8fa98`

```markdown
# Cost Report 2025-10

≈ 72.00 EUR/Monat
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_runbooks.md

**Größe:** 3 KB | **md5:** `269e5a2b943465e1262d8f2113bd4486`

```markdown
### 📄 docs/runbooks/README.md

**Größe:** 205 B | **md5:** `f3721cf652e50a843846daaaced3ed2f`

```markdown
# Runbooks

Anleitungen für wiederkehrende Aufgaben.

- [UV Tooling – Ist-Stand & Ausbauoptionen](uv-tooling.md)
- [Codespaces Recovery](codespaces-recovery.md)
- [Zurück zum Doku-Index](../README.md)
```

### 📄 docs/runbooks/codespaces-recovery.md

**Größe:** 173 B | **md5:** `4a21868f0d5ab097c1c5e387c812d4a7`

```markdown
# Codespaces Recovery

– Rebuild Container
– remoteUser temporär entfernen
– overrideCommand: true testen
– creation.log prüfen (Pfad siehe postStart.sh Hinweise)
```

### 📄 docs/runbooks/semantics-intake.md

**Größe:** 233 B | **md5:** `e1aaf4a53383d8fc78af5ff828f74a41`

```markdown

# Semantics Intake (manuell)

1) Von semantAH: `.gewebe/out/nodes.jsonl` und `edges.jsonl` ziehen.
2) In Weltgewebe ablegen unter `.gewebe/in/*.{nodes,edges}.jsonl`.
3) PR eröffnen → Workflow `semantics-intake` validiert Format.
```

### 📄 docs/runbooks/uv-tooling.md

**Größe:** 2 KB | **md5:** `e5aef3d92b551c437d85b82424d258f6`

```markdown
# UV Tooling – Ist-Stand & Ausbauoptionen

Dieser Runbook-Eintrag fasst zusammen, wie der Python-Paketmanager
[uv](https://docs.astral.sh/uv/) heute im Repo eingebunden ist und welche
Erweiterungen sich anbieten.

## Aktueller Stand

- **Installation im Devcontainer:** `.devcontainer/post-create.sh` installiert `uv`
  per offizieller Astral-Installroutine und macht das Binary direkt verfügbar.
- **Dokumentation im Root-README:** Das Getting-Started beschreibt, dass `uv`
  im Devcontainer bereitgestellt wird und dass Lockfiles (`uv.lock`) eingecheckt
  werden sollen.
- **Python-Tooling-Workspace:** Unter `tools/py` liegt ein `pyproject.toml` mit
  Basiskonfiguration für Python-Helfer; zusätzliche Dependencies würden hier via
  `uv add` gepflegt.

Damit ist `uv` bereits für Tooling-Aufgaben vorbereitet, benötigt aber aktuell
noch keine Abhängigkeiten.

## Potenzial für Verbesserungen

1. **Lockfile etablieren:** Sobald der erste Dependency-Eintrag erfolgt, sollte
   `uv lock` ausgeführt und das entstehende `uv.lock` versioniert werden. Ein
   leeres Lockfile kann auch jetzt schon erzeugt werden, um den Workflow zu
   testen und künftige Änderungen leichter reviewen zu können.
2. **Just-Integration:** Ein `just`-Target (z. B. `just uv-sync`) würde das
   Synchronisieren des Tooling-Environments standardisieren – sowohl lokal als
   auch in CI.
3. **CI-Checks:** Ein optionaler Workflow-Schritt könnte `uv sync --locked`
   ausführen, um zu prüfen, dass das Lockfile konsistent ist, sobald Python-Tasks
   relevant werden.
4. **Fallback für lokale Maschinen:** Außerhalb des Devcontainers sollte das
   README kurz beschreiben, wie `uv` manuell installiert wird (z. B. per
   Installscript oder Paketmanager), damit Contributor:innen ohne Devcontainer
   den gleichen Setup-Pfad nutzen.

Diese Punkte lassen sich unabhängig voneinander umsetzen und sorgen dafür, dass
`uv` vom vorbereiteten Tooling-Baustein zu einem reproduzierbaren Bestandteil
von lokalen und CI-Workflows wird.
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_specs.md

**Größe:** 3 KB | **md5:** `c9c26170b22424c9e7a8e0a4bdbce87d`

```markdown
### 📄 docs/specs/contract.md

**Größe:** 2 KB | **md5:** `11cb90fa2b4c503b431651ccfac6cdbb`

```markdown
# Weltgewebe Contract – Löschkonzept (Tombstone & Key-Erase)

**Status:** Draft v0.1 · **Scope:** Beiträge, Kommentare, Artefakte

## 1. Modell

- **Event-Sourcing:** Jede Änderung ist ein Event. Historie ist unveränderlich.
- **Inhalt:** Nutzinhalte werden _verschlüsselt_ gespeichert (objektbezogener Daten-Key).
- **Identität:** Nutzer signieren Events (Ed25519). Server versieht Batches mit Transparency-Log
  (Merkle-Hash + Timestamp).

## 2. Löschen („jederzeit möglich“)

- **Semantik:** _Logisch löschen_ durch `DeleteEvent` (Tombstone). Der zugehörige **Daten-Key wird verworfen**
  (Key-Erase).
- **Effekt:**
  - UI zeigt „Gelöscht durch Autor“ (Zeitstempel, optional Grund).
  - Inhaltstext/Binary ist selbst für Admins nicht mehr rekonstruierbar.
  - Event-Spur bleibt (Minimalmetadaten: Objekt-ID, Autor-ID Hash, Zeit, Typ).
- **Unwiderruflichkeit:** Key-Erase ist irreversibel. Wiederherstellung nur möglich, wenn der Autor
  einen **lokal gesicherten Key** besitzt und freiwillig re-upploadet.

## 3. Rechts-/Moderationsbezug

- **Rechtswidrige Inhalte:** Sofortiger **Takedown-Hold**: Inhalt unzugänglich; Forensik-Snapshot
  (Hash + Signatur) intern versiegelt. Öffentlich nur Meta-Ticket.
- **DSGVO:** „Löschen“ i. S. d. Betroffenenrechte = Tombstone + Key-Erase. Historische
  Minimaldaten werden als _technische Protokollierung_ mit berechtigtem Interesse (Art. 6 (1) f)
  geführt.

## 4. API-Verhalten

- `GET /items/{id}`:
  - bei Tombstone: `{ status:"deleted", deleted_at, deleted_by, reason? }`
  - kein Content-Payload, keine Wiederherstellungs-Links
- `DELETE /items/{id}`:
  - idempotent; erzeugt `DeleteEvent` + triggert Key-Erase.

## 5. Migrationshinweis

- Bis zur produktiven Verschlüsselung gilt: _Soft-Delete + Scrub_: Inhalt wird überschrieben (z. B.
  mit Zufallsbytes), Backups erhalten Löschmarker, Replikate werden re-keyed.

## 6. Telemetrie/Transparenz

- Wöchentliche Veröffentlichung eines **Transparency-Anchors** (Root-Hash der Woche).
- Öffentliche Statistik: Anzahl Tombstones, Takedown-Holds, mediane Löschzeit.

---

**Kurzfassung:** Löschen = _Tombstone_ (sichtbar) + _Key-Erase_ (Inhalt weg).
Historie bleibt integer, Privatsphäre bleibt gewahrt.
```

### 📄 docs/specs/privacy-api.md

**Größe:** 134 B | **md5:** `a5dda2dfc103475fba76f2023ed93589`

```markdown
# Privacy API (ADR-0003)

GET/PUT /me/visibility { radius_m, ron_flag }, View: public_role_view (id, public_pos, ron_flag, radius_m).
```

### 📄 docs/specs/privacy-ui.md

**Größe:** 107 B | **md5:** `435f90a22ac8fbb74cf057947198dac8`

```markdown
# Privacy UI (ADR-0003)

Slider (r Meter), RoN-Toggle, Vorschau public_pos. Texte: Transparenz = Standard.
```
```

### 📄 merges/weltgewebe_merge_2510262237__docs_x-repo.md

**Größe:** 3 KB | **md5:** `bc4b0f2a5b8bd5530a20537607998647`

```markdown
### 📄 docs/x-repo/peers-learnings.md

**Größe:** 3 KB | **md5:** `0aa0e6faf00f6d4eba55e8596e31e068`

```markdown

# Kurzfassung: Übertragbare Praktiken aus HausKI, semantAH und WGX-Profil

## X-Repo Learnings → sofort anwendbare Leitplanken für Konsistenz & Qualität

- **Semantische Artefakte versionieren:** Ein leichtgewichtiges Graph-Schema (z. B. `nodes.jsonl`/`edges.jsonl`)
  und eingebettete Cluster-Artefakte direkt im Repo halten, um Beziehungen, Themen und Backlinks
  portabel zu machen.
- **Terminologie & Synonyme pflegen:** Eine gepflegte Taxonomie (z. B. `synonyms.yml`, `entities.yml`)
  unterstützt Suche, Filter und konsistente Begriffsnutzung.
- **Governance-Logik messbar machen:** Domänenregeln (**7-Tage** Verblassen, **84-Tage** RoN-Anonymisierung,
  Delegationsabläufe) über konkrete Metriken, Dashboards und Alerts operationalisieren.
  → vgl. `docs/zusammenstellung.md`
- **WGX-Profil als Task-SSoT:** Ein zentrales Profil `.wgx/profile.yml` definiert Env-Prioritäten &
  Standard-Tasks (`up/lint/test/build/smoke`) und vermeidet Drift zwischen lokal & CI.
- **Health/Readiness mit Policies koppeln:** Die bestehenden `/health/live` und `/health/ready` um
  Policy-Signale (Rate-Limits, Retention, Governance-Timer) ergänzen und in Runbooks verankern.
- **UI/Produkt-Definition testbar machen:** UI-Spezifika (Map-UI, Drawer, Zeitleiste, Knotentypen) als
  Playwright-/Vitest-Szenarien automatisieren, um Regressionen früh zu erkennen.
- **Föderierung & Archiv-Strategie festigen:** Hybrid-Indexierung durch wiederkehrende Archiv-Validierung,
  URL-Kanonisierungstests und CI-Jobs absichern.
- **Delegation/Abstimmung operationalisieren:** Policy-Engines und Telemetrie-Events (z. B.
  `delegation_expired`, `proposal_auto_passed`) etablieren, um Governance-Wirkung zu messen.
- **Kosten-Szenarien als Code umsetzen:** Kostenmodelle (S1–S4) in Versionierung halten und regelmäßige
  `cost-report.md`-Artefakte in CI erzeugen.
- **Security als Release-Gate durchsetzen:** SBOM, Signaturen, Key-Rotation und CVE-Schwellen als harte
  CI-Gates etablieren, um Releases zu schützen.

## Nächste Schritte (knapp & machbar)

- [x] `docs/README.md`: Abschnitt **„X-Repo Learnings“** mit Link auf dieses Dokument ergänzen.
- [ ] `.wgx/profile.yml`: Standard-Tasks `up|lint|test|build|smoke` definieren (Repo-SSoT).
- [ ] `/health/ready`: Policy-Signal-Platzhalter ausgeben (z. B. als JSON-Objekt wie
  `{ "governance_timer_ok": true, "rate_limit_ok": true }`), um den Status relevanter Policies
  maschinenlesbar bereitzustellen.
- [ ] `ci/`: Playwright-Smoke für Map-UI (1–2 kritische Szenarien) hinzufügen.
- [ ] `ci/`: `cost-report.md` (S1–S4) als regelmäßiges Artefakt erzeugen.
- [ ] `ci/`: SBOM+Signatur+Audit als Gate in Release-Workflow aktivieren.
```

### 📄 docs/x-repo/semantAH.md

**Größe:** 125 B | **md5:** `6f438447ce4e4f73be3ce061c2584c0b`

```markdown
Weltgewebe konsumiert semantAH-Exports. Kein Schreibpfad zurück.
Import-Job und Event-Verdrahtung folgen in separaten ADRs.
```
```

### 📄 merges/weltgewebe_merge_2510262237__index.md

**Größe:** 325 KB | **md5:** `4f9483292deca965e69d34fa738265d7`

```markdown
# Ordner-Merge: weltgewebe

**Zeitpunkt:** 2025-10-26 22:37
**Quelle:** `/home/alex/repos/weltgewebe`
**Dateien (gefunden):** 344
**Gesamtgröße (roh):** 887 KB

**Exclude:** ['.gitignore']

## 📁 Struktur

- weltgewebe/
  - .dockerignore
  - .editorconfig
  - .env.example
  - .gitattributes
  - .gitignore
  - .hauski-reports
  - .lychee.toml
  - .markdownlint.jsonc
  - .markdownlint.yaml
  - .nvmrc
  - .vale.ini
  - .yamllint.yml
  - CONTRIBUTING.md
  - Cargo.lock
  - Cargo.toml
  - Justfile
  - LICENSE
  - Makefile
  - README.md
  - deny.toml
  - package-lock.json
  - toolchain.versions.yml
  - target/
    - .future-incompat-report.json
    - .rustc_info.json
    - CACHEDIR.TAG
    - debug/
      - .cargo-lock
      - incremental/
        - weltgewebe_api-2qolc8u8tkbko/
          - s-hbs7qwgcrw-02ki5gq.lock
          - s-hbs7qwgcrw-02ki5gq-dq6t0gapbu0tjj7w4u901ieik/
            - 01rtl281wqpvqtulvmxw45zdw.o
            - 03mrow47atphjuxfz2fiih9pj.o
            - 06yq4xllvqw0pa0hi7aj46ca9.o
            - 0aggijju4s667nxudps8juxiu.o
            - 0ay9muo009dbrso1kmhuld0q4.o
            - 0k8w3z5sjorbsagcaxpxhsl4o.o
            - 0keghvj2rpmx7cpyd41sm3i63.o
            - 0m69bg3jhr91g8ttmtk09un2r.o
            - 0m7qrwrkxjeclcjtg7ckte0q4.o
            - 0n5qa3yt8ylkxzoifoi7w5kgf.o
            - 0ncu888epz96tfhlk7fp7b8or.o
            - 0p8thfngmd93ogm3j8pi96l9s.o
            - 0pgk7oet697e1cpqlfzm4uyvy.o
            - 0rdol8t8j1j9j618nrsr1u4je.o
            - 12i30vig0q9kr5exlahj9zkwi.o
            - 164ivfwg1ctdrotqb2pj5o7si.o
            - 1dhrib63qjv32eusl0pvenf1u.o
            - 1dlm9t3w74mgz3zcazv1w8zv5.o
            - 1e1q8ey9adlxul6pgcy1ge7fe.o
            - 1g9a22bfac974dyakpcbqgu2j.o
            - 1jlpmfsalu6notj7n7z87wxab.o
            - 1qf6fh25da2nmgjgtizucg765.o
            - 1rmxtxzhkrk2di6jkjye6s38l.o
            - 1wry3hytenbrutlz5b4otuzhm.o
            - 1z3ximui8uqzkizk1uj877qac.o
            - 22qyynz7zkekb6ldmlvw1npt3.o
            - 2304voko8arjbz3kwrnxm3fjl.o
            - 24jrpc3lfzjj7a22y2kt6jq7o.o
            - 261ym7myz753id10ec0pk064i.o
            - 26jf1mr13tis0li4qse93odvr.o
            - 26nsqy45g823vuol3yo6mguoc.o
            - 275wkdgxcw7kbhi70jeqslah9.o
            - 27z0i727uli85e8msrpr4xgln.o
            - 2aefftxp7qi9b5pbshm6v5xlp.o
            - 2f5x8dpzovugeczvsad20gbla.o
            - 2fbsis8laars43l5mptmp3jop.o
            - 2h93gb498nktqfcexhdimptxc.o
            - 2iapy79mnei4qk3m1w3g13ci3.o
            - 2isu8566anqfdzdahiou037ok.o
            - 2lahwuhmumikcyoukrzsse1x6.o
            - 2lm7r9iz3ywfrpp1c1vdtkf39.o
            - 2mu7tzz8kmjiujgl59alw1xv7.o
            - 2p9skusfrogp5oqv04r4ka2ji.o
            - 2ta85q54qatr8hucgke9a4wae.o
            - 2uch1305gzsgfwdmko2m2inyy.o
            - 2un8ifoxh833fcuyed5813qt8.o
            - 2yky24j562h3w63fks1mmap2k.o
            - 389g07cquhkwsu2aejo4d8yvv.o
            - 3cdjra5l27njwq7pcz4pzh98n.o
            - 3e5ffpqsub88s59nog1f3slxk.o
            - 3ivlqts49jpqlm68kn32u7bpy.o
            - 3k725tsmyzzzrbf5iphxaox6f.o
            - 3mvxgocv9ge8ggidpxgc6l399.o
            - 3p395tfdw4a2zo2o23kbf7onw.o
            - 3u2y6jq3t7w5vnfpp8vgp4mfq.o
            - 3v6t8x6pjpd6vw6u8i2bin9h8.o
            - 3ynetqjdnm4jjhzi4q3iri0dd.o
            - 3zv81o6rstkme7dp3lsbj2ndp.o
            - 435ygcqnpjqdq6ph84wkvvd1j.o
            - 43bpua1llfdjxytfzhfu6t4jz.o
            - 46bsurvytsmulqcdss7lmh43s.o
            - 4dasbqz5wikujf4oz8jbgmqri.o
            - 4e2nlor27f4gw96njp6t3nwzg.o
            - 4fc8ocnlhxdml22ksen5jazwn.o
            - 4h8ui2yzb0q5py83zanpjq7fh.o
            - 4i6auqj6xyfvf8s93hme935ee.o
            - 4iqxthtbmhq845dx4x061dodn.o
            - 4k11b1d87mfu3fro19kbogcw6.o
            - 4mh7a3dt7gcq3wtj696bsmlcj.o
            - 4mvkivh89kojpjnwx95vmtng3.o
            - 4n1tbq2d1iv8gxwv13n0c1rfn.o
            - 4x8n4f1j5h33fqbcfgdl5pmms.o
            - 5044quidrjcs9t3kiujh47tz1.o
            - 505cly7zdc95arsu67qu17fmo.o
            - 52dzrqjrqyu43nfsmlezl0x30.o
            - 547yyywwoxu91lm1vtk025263.o
            - 54ckhvmrijqgxee0p99lxbbwo.o
            - 5dfhck7mr8r91qxsygeeowob3.o
            - 5k19sjlw9dddyo2l9kcrl1b1e.o
            - 5kt0lstgzlarax9yi83hn847x.o
            - 5mbk9tjxiwi3i91bde2tvptgu.o
            - 5rd7ltnr565vifkd9casnpfhz.o
            - 5ui0ceygd30unhkkrboblcn47.o
            - 5unwbozvod6rym9ar82pv9xvh.o
            - 61fgt5zm0zrmzyhl4x5y5hvci.o
            - 62hyg7bzj0sc6dnmreebv4404.o
            - 66n3tyeq1ivhflzvxdymje9cm.o
            - 6csq9o6pvlums0euj3ye6jttk.o
            - 6ix7gjjq3kpxrdnbqgk6pet8m.o
            - 6jewek5zpbfqclyykjqzcfiy7.o
            - 6mjqoklkdagbeytzl6fmmjglw.o
            - 6v2rd3cl1gm6ktw20ecvmoayc.o
            - 6vpw05qv0kigbmbytb5s72o7t.o
            - 6xgqwah0ljklsetsipi471zrg.o
            - 709jr0zv54vv29k13akk2sapj.o
            - 72v916xxnun87qp8itks1n0r4.o
            - 75kd7mm54wuauxee3b1t0uiz7.o
            - 76zslcyke524a88y8bqs36ehe.o
            - 7d19s3l1mirk6hwjp2mltqz9p.o
            - 7g0w2mo1bemovwmw0hr8xvspp.o
            - 7j879yhmkyper3xjst0wcr2qi.o
            - 7kyzqskjlfip02isk921e6w50.o
            - 7mqlds0oi9hvvb00z4pf9u5kt.o
            - 7o9ewz2bh5q0s7htkami9d7hn.o
            - 7omzty8asm80f8nqcs6seyyj4.o
            - 7pozkuturtvn4czdbb1g11sqx.o
            - 7t5ixof1kltg4rmvbrl3d2r8z.o
            - 7uksa749079bmyl8mtdzjl6qc.o
            - 8430r5e90de0wwbzwtstdrq9x.o
            - 85km2peh2zjcek5axb1kkgogb.o
            - 88d5zr14d6k93o1web9obumbf.o
            - 8ap2luv1sl35rqehxuoqn2b1o.o
            - 8bqjgx35j5v7fbi3xfye2vxym.o
            - 8g9vzw1yk10rngqfjvu341592.o
            - 8hk27i99353r8nxq6io1nywai.o
            - 8il4vccnhuhcylvr3dxm755a3.o
            - 8jqt533hcda4pa9q1z8gafsos.o
            - 8nj83eqlx678o2jdfmftc7bkg.o
            - 8qjumauhmkjbuke7b2zrdigj9.o
            - 8zk7b4yn2fuh1j1mwysc5r473.o
            - 91r2otp6sdgom5k48fuc9t7y4.o
            - 94gjav3r05in5prjj9yym9302.o
            - 96g5bxcojofjiv8cfrbwh5s0x.o
            - 9gfzbhg1e1y57qn06mxat1mou.o
            - 9je01k7d46dsflv6j1d4s2i3v.o
            - 9k0q94oqxcrpeb2en6551tynp.o
            - 9t7gwck0tjg4wqiy053k6ere1.o
            - 9vpquvuc1o3rr4ndcm1pk9lcs.o
            - 9xlez09jqepcfggwnpa0yi7qu.o
            - 9ylodjbrkmpgs37u33gc4uv35.o
            - 9z6ep50ig68z2xz2lewcvfcbo.o
            - a30wftwv0drs6tg01cxtj001r.o
            - a8w14dkr4zakwyazxqw3inylp.o
            - ad4all98o36hxmaehyhnpbf9z.o
            - adf5ljzn7gmkd0ysfllfkvxyu.o
            - aibc3dvx72h5ns1i9h43kkl14.o
            - amkjn1adauvfpy5odnkw4dh99.o
            - appso4njp3gdxgycfqvhc7ew9.o
            - aw6p3aohjfkvrv8odfh7k25sr.o
            - ba15lqyz3ugi31ywe7rt259b4.o
            - bg3ju42sp8amkljapmqeocx3t.o
            - bmxfqt256bhj3emm5rmkjetkh.o
            - bnm39wm3zp6pwxh5qnyyzvex2.o
            - bwxsx1afaof3ldtmqh9bwmu4r.o
            - bx03o8h3uul0ecpek51dpzxhe.o
            - c1pzfd0i8yvdeuxkznqpf4dyu.o
            - c2jypf8hrdr4piqqi3uworcsr.o
            - c51kilupab615qsgovt0tvde9.o
            - c5ffgt0g9xka2kgcs6qciapgd.o
            - c6q18apgine88iafri9dumd7x.o
            - cab7cv5un04xv2xhb3tryqqvr.o
            - cd52ks1jxu92q0p7b5daem5bv.o
            - ciz3n3wa4e6sga73o3zebt7fi.o
            - coi9qb21o98mjpmenez8na5x1.o
            - cpo1zyzrzy7g4t1t844a2wkev.o
            - cr0vdnxqu2vpxilsb4hrqahf6.o
            - d1bol6nhfbl4cl4i850y0cjax.o
            - d2gb52zqmv6oim5feurz2q4nq.o
            - d3fyiljbxqdngdxmdm9i2qai6.o
            - d3lg522qcuwvzaz9jcdputitp.o
            - d72m6b5tcl4cgnrtj3ym2x113.o
            - d9rbifangbtdvfgqgv7h7wsob.o
            - ddcdgkhqllreivv4pchb6x930.o
            - dep-graph.bin
            - dh4wyxqmotub96a2fqj0k0h2o.o
            - djsuzue35d3amkr7dgw8h4ib2.o
            - dknk5i1ev2kz0uhcxi8yqbjxp.o
            - dnsl5dhhbw03rap445l3lotp4.o
            - dsap318rg24az635ulcv3xjbg.o
            - dtoyuw3aaqs3mffto99sstcuk.o
            - dtz89xykky550fn45r5wp4kta.o
            - dv0k2fizt49t7zm308kne56wb.o
            - e8mpdbotngoidlhnnm0i29cdj.o
            - eagr2p42ckfbu5w0849ni1ol6.o
            - eb92uns94qux9u3xrskis82qz.o
            - ebx5ef4wlsg9lnulovuyxdhcc.o
            - ed9rshltrhyt83w5biuhpanie.o
            - ehq3ehbfoiz4llzyeazrgwddk.o
            - elinklick17eihg7o5z8hf4it.o
            - eqo5u1hh7caf8zzh30twd82v7.o
            - ert8phxhg5u7tvjh9kgfgli81.o
            - esrw9sknj8i1hdudqf5llbwhl.o
            - etsmmijbadqyzxawvvw043wce.o
            - f0rp3fyxtc6mbpmxujzyuj5bp.o
            - f230gyl4e4oaqgfrbyfm6kkc1.o
            - f2vyzrk8hlq7mfh1tw1l5chal.o
            - query-cache.bin
            - work-products.bin
        - weltgewebe_api-01ji3xj1osd96/
          - s-hbtflopupi-09xzxjw.lock
          - s-hbtflopupi-09xzxjw-8relw6f0sgjqyg8x79xx961pt/
            - dep-graph.bin
            - query-cache.bin
            - work-products.bin
      - .fingerprint/
        - tinyvec-e8120bfe2b1a4920/
          - dep-lib-tinyvec
          - invoked.timestamp
          - lib-tinyvec
          - lib-tinyvec.json
        - icu_normalizer_data-d2473f55c03a7556/
          - dep-lib-icu_normalizer_data
          - invoked.timestamp
          - lib-icu_normalizer_data
          - lib-icu_normalizer_data.json
        - bytes-65d073b3fdf9d153/
          - dep-lib-bytes
          - invoked.timestamp
          - lib-bytes
          - lib-bytes.json
        - atomic-waker-93d4097655d001c5/
          - dep-lib-atomic_waker
          - invoked.timestamp
          - lib-atomic_waker
          - lib-atomic_waker.json
        - parking_lot_core-4a690d57ca21107a/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - aho-corasick-549fb29f09559838/
          - dep-lib-aho_corasick
          - invoked.timestamp
          - lib-aho_corasick
          - lib-aho_corasick.json
        - cc-8f8413ca802e9b18/
          - dep-lib-cc
          - invoked.timestamp
          - lib-cc
          - lib-cc.json
        - equivalent-efa3f710fdf26075/
          - dep-lib-equivalent
          - invoked.timestamp
          - lib-equivalent
          - lib-equivalent.json
        - crossbeam-queue-70a1377cade8c4e8/
          - dep-lib-crossbeam_queue
          - invoked.timestamp
          - lib-crossbeam_queue
          - lib-crossbeam_queue.json
        - ryu-21bbdb07b7fa6bff/
          - dep-lib-ryu
          - invoked.timestamp
          - lib-ryu
          - lib-ryu.json
        - getrandom-2ce7e6772d0c2425/
          - dep-lib-getrandom
          - invoked.timestamp
          - lib-getrandom
          - lib-getrandom.json
        - rustix-a06eedffdfc4d77f/
          - run-build-script-build-script-build
          - run-build-script-build-script-build.json
        - either-22506875e7953617/
          - dep-lib-either
          - invoked.timestamp
          - lib-either
          - lib-either.json
        - zerovec-cd00395e6eaed681/
          - dep-lib-zerovec
          - invoked.timestamp
          - lib-zerovec
          - lib-zerovec.json
        - rustls-native-certs-c49f3ad285420a8a/
          - dep-lib-rustls_native_certs
          - invoked.timestamp
          - lib-rustls_native_certs
          - lib-rustls_native_certs.json
        - thiserror-14edc43edb1485d2/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - ed25519-edfd80ead955da20/
          - dep-lib-ed25519
          - invoked.timestamp
          - lib-ed25519
          - lib-ed25519.json
        - serde-4e8f4b65b2951e94/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - crypto-common-3c682194a09b7613/
          - dep-lib-crypto_common
          - invoked.timestamp
          - lib-crypto_common
          - lib-crypto_common.json
        - zerovec-597d45153ac865a7/
          - dep-lib-zerovec
          - invoked.timestamp
          - lib-zerovec
          - lib-zerovec.json
        - portable-atomic-9277b22120812e96/
          - run-build-script-build-script-build
          - run-build-script-build-script-build.json
        - prometheus-fb5211ca7b4c2300/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - pin-project-lite-c14b565038496e22/
          - dep-lib-pin_project_lite
          - invoked.timestamp
          - lib-pin_project_lite
          - lib-pin_project_lite.json
        - cfg-if-60f5305215eca12c/
          - dep-lib-cfg_if
          - invoked.timestamp
          - lib-cfg_if
          - lib-cfg_if.json
        - hex-fbbed2810870e39e/
          - dep-lib-hex
          - invoked.timestamp
          - lib-hex
          - lib-hex.json
        - time-8b48f3c6d61cef97/
          - dep-lib-time
          - invoked.timestamp
          - lib-time
          - lib-time.json
        - libc-542f1ead4d82bc85/
          - dep-lib-libc
          - invoked.timestamp
          - lib-libc
          - lib-libc.json
        - futures-io-8f0f9ff3812a0397/
          - dep-lib-futures_io
          - invoked.timestamp
          - lib-futures_io
          - lib-futures_io.json
        - const-oid-370fbf126c15b32d/
          - dep-lib-const_oid
          - invoked.timestamp
          - lib-const_oid
          - lib-const_oid.json
        - rustversion-1898eae5a255a4ec/
          - run-build-script-build-script-build
          - run-build-script-build-script-build.json
        - syn-f8783a30f2c4c479/
          - dep-lib-syn
          - invoked.timestamp
          - lib-syn
          - lib-syn.json
        - tokio-rustls-fd100dcc27e93a4c/
          - dep-lib-tokio_rustls
          - invoked.timestamp
          - lib-tokio_rustls
          - lib-tokio_rustls.json
        - futures-executor-4341468557886ab7/
          - dep-lib-futures_executor
          - invoked.timestamp
          - lib-futures_executor
          - lib-futures_executor.json
        - synstructure-f4b1fc400471b884/
          - dep-lib-synstructure
          - invoked.timestamp
          - lib-synstructure
          - lib-synstructure.json
        - memchr-ac8810823885e36e/
          - dep-lib-memchr
          - invoked.timestamp
          - lib-memchr
          - lib-memchr.json
        - pkcs8-b2f5e7c4554a364e/
          - dep-lib-pkcs8
          - invoked.timestamp
          - lib-pkcs8
          - lib-pkcs8.json
        - regex-syntax-6318a9bbcc70ced8/
          - dep-lib-regex_syntax
          - invoked.timestamp
          - lib-regex_syntax
          - lib-regex_syntax.json
        - httparse-a369f4806a928b1e/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - idna-ea8b8be7759ed93f/
          - dep-lib-idna
          - invoked.timestamp
          - lib-idna
          - lib-idna.json
        - tempfile-713581b437f54b64/
          - dep-lib-tempfile
          - invoked.timestamp
          - lib-tempfile
          - lib-tempfile.json
        - crossbeam-queue-d0646850354035db/
          - dep-lib-crossbeam_queue
          - invoked.timestamp
          - lib-crossbeam_queue
          - lib-crossbeam_queue.json
        - memchr-ccc31091145e243c/
          - dep-lib-memchr
          - invoked.timestamp
          - lib-memchr
          - lib-memchr.json
        - rustls-webpki-ad74e8bdf26a7c3c/
          - dep-lib-webpki
          - invoked.timestamp
          - lib-webpki
          - lib-webpki.json
        - crossbeam-utils-cf5cfa5d0e283ebe/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - litemap-bc100b32c3f97fac/
          - dep-lib-litemap
          - invoked.timestamp
          - lib-litemap
          - lib-litemap.json
        - scopeguard-eba723b2b8e43bcd/
          - dep-lib-scopeguard
          - invoked.timestamp
          - lib-scopeguard
          - lib-scopeguard.json
        - zerofrom-ac19be1ca0dfc650/
          - dep-lib-zerofrom
          - invoked.timestamp
          - lib-zerofrom
          - lib-zerofrom.json
        - nuid-e990e947e71df356/
          - dep-lib-nuid
          - invoked.timestamp
          - lib-nuid
          - lib-nuid.json
        - tower-54d7cfe106c05043/
          - dep-lib-tower
          - invoked.timestamp
          - lib-tower
          - lib-tower.json
        - zerotrie-bf2f3b5d1a5cdc18/
          - dep-lib-zerotrie
          - invoked.timestamp
          - lib-zerotrie
          - lib-zerotrie.json
        - signature-03a3abe8f93951f7/
          - dep-lib-signature
          - invoked.timestamp
          - lib-signature
          - lib-signature.json
        - futures-sink-24f14c895a97cd70/
          - dep-lib-futures_sink
          - invoked.timestamp
          - lib-futures_sink
          - lib-futures_sink.json
        - tower-service-68697946deac773c/
          - dep-lib-tower_service
          - invoked.timestamp
          - lib-tower_service
          - lib-tower_service.json
        - rustls-webpki-c30285880e543b41/
          - dep-lib-webpki
          - invoked.timestamp
          - lib-webpki
          - lib-webpki.json
        - quote-ddf20bb25101601c/
          - run-build-script-build-script-build
          - run-build-script-build-script-build.json
        - async-nats-d508618d1fab4164/
          - dep-lib-async_nats
          - invoked.timestamp
          - lib-async_nats
          - lib-async_nats.json
        - tracing-attributes-2de78feca8e752f8/
          - dep-lib-tracing_attributes
          - invoked.timestamp
          - lib-tracing_attributes
          - lib-tracing_attributes.json
        - itoa-40fdb2a09307e577/
          - dep-lib-itoa
          - invoked.timestamp
          - lib-itoa
          - lib-itoa.json
        - thiserror-e3b29a19691cddd9/
          - run-build-script-build-script-build
          - run-build-script-build-script-build.json
        - subtle-23bbe7a6e0b68b65/
          - dep-lib-subtle
          - invoked.timestamp
          - lib-subtle
          - lib-subtle.json
        - anyhow-e1f554b474e8a16f/
          - run-build-script-build-script-build
          - run-build-script-build-script-build.json
        - cpufeatures-69aa18d40df9d02d/
          - dep-lib-cpufeatures
          - invoked.timestamp
          - lib-cpufeatures
          - lib-cpufeatures.json
        - url-a3c3cf97f9d7d2a2/
          - dep-lib-url
          - invoked.timestamp
          - lib-url
          - lib-url.json
        - serde-c335cbbb665db8c7/
          - dep-lib-serde
          - invoked.timestamp
          - lib-serde
          - lib-serde.json
        - tower-layer-1b6d015ec69ffc49/
          - dep-lib-tower_layer
          - invoked.timestamp
          - lib-tower_layer
          - lib-tower_layer.json
        - socket2-4293b964e8c0a719/
          - dep-lib-socket2
          - invoked.timestamp
          - lib-socket2
          - lib-socket2.json
        - stringprep-7f1a902879b8a466/
          - dep-lib-stringprep
          - invoked.timestamp
          - lib-stringprep
          - lib-stringprep.json
        - slab-42e319f38072c981/
          - dep-lib-slab
          - invoked.timestamp
          - lib-slab
          - lib-slab.json
        - rustc_version-eade9007b0624268/
          - dep-lib-rustc_version
          - invoked.timestamp
          - lib-rustc_version
          - lib-rustc_version.json
        - idna_adapter-c84556af106f7258/
          - dep-lib-idna_adapter
          - invoked.timestamp
          - lib-idna_adapter
          - lib-idna_adapter.json
        - icu_properties_data-ef8f86fdfbcc0e0e/
          - dep-lib-icu_properties_data
          - invoked.timestamp
          - lib-icu_properties_data
          - lib-icu_properties_data.json
        - tokio-stream-ec4296e0c062c1ac/
          - dep-lib-tokio_stream
          - invoked.timestamp
          - lib-tokio_stream
          - lib-tokio_stream.json
        - mio-eb2cc0c0dbaf7d98/
          - dep-lib-mio
          - invoked.timestamp
          - lib-mio
          - lib-mio.json
        - icu_properties-dcf335287fb53c38/
          - dep-lib-icu_properties
          - invoked.timestamp
          - lib-icu_properties
          - lib-icu_properties.json
        - byteorder-96b77cf0a259533b/
          - dep-lib-byteorder
          - invoked.timestamp
          - lib-byteorder
          - lib-byteorder.json
        - axum-core-a4f09e485de83d4d/
          - dep-lib-axum_core
          - invoked.timestamp
          - lib-axum_core
          - lib-axum_core.json
        - icu_properties_data-e05272786a6e1307/
          - dep-lib-icu_properties_data
          - invoked.timestamp
          - lib-icu_properties_data
          - lib-icu_properties_data.json
        - httparse-2246c683a1e71a20/
          - run-build-script-build-script-build
          - run-build-script-build-script-build.json
        - event-listener-94f7cffd21c377e7/
          - dep-lib-event_listener
          - invoked.timestamp
          - lib-event_listener
          - lib-event_listener.json
        - signatory-ef4ba3136cc80ac9/
          - dep-lib-signatory
          - invoked.timestamp
          - lib-signatory
          - lib-signatory.json
        - unicode-properties-cc89bba20f77e0eb/
          - dep-lib-unicode_properties
          - invoked.timestamp
          - lib-unicode_properties
          - lib-unicode_properties.json
        - httparse-b652932b81b77c4c/
          - dep-lib-httparse
          - invoked.timestamp
          - lib-httparse
          - lib-httparse.json
        - http-f78b98de5b2cdeaa/
          - dep-lib-http
          - invoked.timestamp
          - lib-http
          - lib-http.json
        - hex-4ccaaced0dd5bf6b/
          - dep-lib-hex
          - invoked.timestamp
          - lib-hex
          - lib-hex.json
        - zerofrom-derive-700e2f5e6d726543/
          - dep-lib-zerofrom_derive
          - invoked.timestamp
          - lib-zerofrom_derive
          - lib-zerofrom_derive.json
        - generic-array-776ede053fb88fe3/
          - dep-lib-generic_array
          - invoked.timestamp
          - lib-generic_array
          - lib-generic_array.json
        - tower-service-d71afa1094c1aff5/
          - dep-lib-tower_service
          - invoked.timestamp
          - lib-tower_service
          - lib-tower_service.json
        - sync_wrapper-0ec2ddbd9f1c81b5/
          - dep-lib-sync_wrapper
          - invoked.timestamp
          - lib-sync_wrapper
          - lib-sync_wrapper.json
        - ring-c624e3c961e82076/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - sqlx-core-eb1f9bccef0429c1/
          - dep-lib-sqlx_core
          - invoked.timestamp
          - lib-sqlx_core
          - lib-sqlx_core.json
        - url-53c3b267439a5dac/
          - dep-lib-url
          - invoked.timestamp
          - lib-url
          - lib-url.json
        - thread_local-1c0d514c6266b2f7/
          - dep-lib-thread_local
          - invoked.timestamp
          - lib-thread_local
          - lib-thread_local.json
        - der-a5304dc7dc7731cf/
          - dep-lib-der
          - invoked.timestamp
          - lib-der
          - lib-der.json
        - typenum-dec8b39c592c3a7d/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - crc-catalog-cd091cd2dccb80c7/
          - dep-lib-crc_catalog
          - invoked.timestamp
          - lib-crc_catalog
          - lib-crc_catalog.json
        - time-5ee53ba36c51bce1/
          - dep-lib-time
          - invoked.timestamp
          - lib-time
          - lib-time.json
        - nkeys-f4d5b48c5a799c31/
          - dep-lib-nkeys
          - invoked.timestamp
          - lib-nkeys
          - lib-nkeys.json
        - rustversion-795721cbadc38550/
          - dep-lib-rustversion
          - invoked.timestamp
          - lib-rustversion
          - lib-rustversion.json
        - generic-array-f2f2607b090a65d5/
          - build-script-build-script-build
          - build-script-build-script-build.json
          - dep-build-script-build-script-build
          - invoked.timestamp
        - slab-95d912b52b35c49c/
          - dep-lib-slab
          - invoked.timestamp
          - lib-slab
          - lib-slab.json
        - sync_wrapper-3a06295a41254b79/
          - dep-lib-sync_wrapper
          - invoked.timestamp
          - lib-sync_wrapper
          - lib-sync_wrapper.json
        - nom-c671ab6a23bd3c40/
          - dep-lib-nom
          - invoked.timestamp
          - lib-nom
          - lib-nom.json
        - sqlx-postgres-2b61db20aadfc45d/
          - dep-lib-sqlx_postgres
          - invoked.timestamp
          - lib-sqlx_postgres
          - lib-sqlx_postgres.json
          - output-lib-sqlx_postgres
        - rand_core-02a165dcbc1b1c64/
          - dep-lib-rand_core
          - invoked.timestamp
          - lib-rand_core
          - lib-rand_core.json
        - rustls-pki-types-000239a88336954e/
          - dep-lib-rustls_pki_types
          - invoked.timestamp
          - lib-rustls_pki_types
          - lib-rustls_pki_types.json
        - tracing-log-aeae6eacf11ed394/
          - dep-lib-tracing_log
          - invoked.timestamp
          - lib-tracing_log
          - lib-tracing_log.json
        - utf8_iter-7af36920edb0fdad/
          - dep-lib-utf8_iter
          - invoked.timestamp
          - lib-utf8_iter
          - lib-utf8_iter.json
        - deranged-5f0e18b803f0e716/
          - dep-lib-deranged
          - invoked.timestamp
          - lib-deranged
          - lib-deranged.json
        - autocfg-e43f4f6a57543659/
          - dep-lib-autocfg
          - invoked.timestamp
          - lib-autocfg
          - lib-autocfg.json
        - prometheus-7614f4d1c4634256/
          - dep-lib-prometheus
          - invoked.timestamp
          - lib-prometheus
          - lib-prometheus.json
        - scopeguard-94e7e756cd69aad0/
          - dep-lib-scopeguard
          - invoked.timestamp
          - lib-scopeguard
          - lib-scopeguard.json
        - serde_json-4d4f99666e4e7df3/
          - dep-lib-serde_json
          - invoked.timestamp
          - lib-serde_json
          - lib-serde_json.json
        - digest-b151f2bf46425167/
          - dep-lib-digest
          - invoked.timestamp
          - lib-digest
          - lib-digest.json
        - icu_collections-9726213a4a5b49eb/
          - dep-lib-icu_collections
          - invoked.timestamp
          - lib-icu_collections
          - lib-icu_collections.json
        - getrandom-22261e00fde65095/
          - dep-lib-getrandom
          - invoked.timestamp
          - lib-getrandom

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__infra_caddy.md

**Größe:** 905 B | **md5:** `a9de1fd9470dd2c83ce15791b9db44e0`

```markdown
### 📄 infra/caddy/Caddyfile

**Größe:** 789 B | **md5:** `3bfda9b8da56d21a02514d98eb48fd0a`

```plaintext
{
  auto_https off
  servers :8081 {
    protocol {
      experimental_http3
    }
    logs {
      level INFO
    }
  }
}

:8081 {
  encode zstd gzip
  # Strippt /api Prefix, damit /api/health -> /health an der API ankommt
  handle_path /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
  header {
    # Dev-CSP: HMR/WebSocket & Dev-Assets erlauben; bei Bedarf später härten
    # Für externe Tiles ggf. ergänzen, z.B.:
    #   img-src 'self' data: blob: https://tile.openstreetmap.org https://*.tile.openstreetmap.org;
    Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; img-src 'self' data: blob:; object-src 'none';"
    X-Frame-Options "DENY"
    Referrer-Policy "no-referrer"
  }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__infra_compose.md

**Größe:** 3 KB | **md5:** `66eb977e3093e7996e7c27e64a989f81`

```markdown
### 📄 infra/compose/compose.core.yml

**Größe:** 3 KB | **md5:** `e123001a9bff5640f956ec4a03dfa58c`

```yaml
version: "3.9"

services:
  web:
    profiles: ["dev"]
    image: node:20-alpine
    working_dir: /workspace
    command:
      - sh
      - -c
      - |
        if [ ! -d node_modules ]; then
          npm ci;
        fi;
        exec npm run dev -- --host 0.0.0.0 --port 5173
    volumes:
      - ../../apps/web:/workspace
    ports:
      - "5173:5173"
    depends_on:
      api:
        condition: service_healthy
    environment:
      NODE_ENV: development
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:5173 >/dev/null"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  api:
    profiles: ["dev"]
    image: rust:1.83-bullseye
    working_dir: /workspace
    command: ["cargo", "run", "--manifest-path", "apps/api/Cargo.toml", "--bin", "api"]
    environment:
      API_BIND: ${API_BIND:-0.0.0.0:8080}
      DATABASE_URL: postgres://welt:gewebe@pgbouncer:6432/weltgewebe
      RUST_LOG: ${RUST_LOG:-info}
    depends_on:
      pgbouncer:
        condition: service_started
    ports:
      - "8080:8080"
    volumes:
      - ../..:/workspace
      - cargo_registry:/usr/local/cargo/registry
      - cargo_git:/usr/local/cargo/git
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8080/health/live >/dev/null || curl -fsS http://localhost:8080/health/ready >/dev/null || curl -fsS http://localhost:8080/version >/dev/null"]
      interval: 5s
      timeout: 3s
      retries: 30
    restart: unless-stopped

  db:
    profiles: ["dev"]
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-welt}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-gewebe}
      POSTGRES_DB: ${POSTGRES_DB:-weltgewebe}
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-welt}"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 20s

  pgbouncer:
    profiles: ["dev"]
    image: edoburu/pgbouncer:1.20
    environment:
      DATABASE_URL: postgres://welt:gewebe@db:5432/weltgewebe
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 200
      DEFAULT_POOL_SIZE: 10
      AUTH_TYPE: trust
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "6432:6432"

  caddy:
    profiles: ["dev"]
    image: caddy:2
    ports:
      - "8081:8081"
    volumes:
      - ../caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    depends_on:
      web:
        condition: service_healthy
      api:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pg_data:
  cargo_registry:
  cargo_git:
```

### 📄 infra/compose/compose.observ.yml

**Größe:** 482 B | **md5:** `ed2503dd1bc994acd9dc84efbfb815c6`

```yaml
version: "3.9"
services:
  prometheus:
    image: prom/prometheus:v2.54.1
    ports: ["9090:9090"]
    # volumes:
    #   - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  grafana:
    image: grafana/grafana:11.1.4
    ports: ["3001:3000"]
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
  loki:
    image: grafana/loki:3.2.1
    ports: ["3100:3100"]
  tempo:
    image: grafana/tempo:2.5.0
    ports: ["3200:3200"]
```
```

### 📄 merges/weltgewebe_merge_2510262237__infra_compose_grafana_provisioning_dashboards.md

**Größe:** 2 KB | **md5:** `6b4eb8d2ec3b40df05a2ac4bc0a70508`

```markdown
### 📄 infra/compose/grafana/provisioning/dashboards/weltgewebe.json

**Größe:** 2 KB | **md5:** `3e09136fc46baf5e4e9d62181c02d2c8`

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "iteration": 1,
  "links": [],
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "center",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "text": {}
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "up{job=\"api\"}",
          "legendFormat": "",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "API availability",
      "type": "stat"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": [
    "weltgewebe"
  ],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-15m",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Weltgewebe Starter",
  "uid": "weltgewebe-starter",
  "version": 1
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__infra_compose_monitoring.md

**Größe:** 320 B | **md5:** `1a2afb9ca52458249b0787121e5d7d50`

```markdown
### 📄 infra/compose/monitoring/prometheus.yml

**Größe:** 191 B | **md5:** `b120ae667279988bdc058618653cfcfc`

```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: api
    static_configs:
      - targets:
          - host.docker.internal:8080 # on Linux consider host networking or extra_hosts
```
```

### 📄 merges/weltgewebe_merge_2510262237__infra_compose_sql_init.md

**Größe:** 269 B | **md5:** `33aae921011b78273bcd5b3cd7efca85`

```markdown
### 📄 infra/compose/sql/init/00_extensions.sql

**Größe:** 140 B | **md5:** `2dcecbff232b900dacd96d7bb6fdb12d`

```sql
-- optional: hilfreiche Extensions als Ausgangspunkt
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```
```

### 📄 merges/weltgewebe_merge_2510262237__part001.md

**Größe:** 43 B | **md5:** `ad150e6cdda3920dbef4d54c92745d83`

```markdown
<!-- chunk:1 created:2025-10-26 22:37 -->
```

### 📄 merges/weltgewebe_merge_2510262237__policies.md

**Größe:** 3 KB | **md5:** `ee088ad860d8c4eb1810325a7a402ce3`

```markdown
### 📄 policies/limits.yaml

**Größe:** 1 KB | **md5:** `1dee2dc0df293c029b353894c90a3135`

```yaml
---
# Weltgewebe – Soft Limits (v1)
# Zweck: Leitplanken sichtbar machen. Zunächst nur dokumentarisch; keine harten Gates.
version: v1
updated: 2025-02-14
owner: platform

web:
  bundle:
    # Gesamtbudget für alle produktiven JS/CSS-Assets (komprimiert)
    total_kb: 350
    note: "Muss zum 'ci/budget.json' passen; später automatische Prüfung."
  build:
    max_minutes: 10
    note: "CI-Build der Web-App soll schnell bleiben; Ziel für Developer-Feedback."

api:
  latency:
    p95_ms: 300
    note: "Lokales/dev-nahes Ziel; Produktions-SLOs stehen in policies/slo.yaml."
  test:
    max_minutes: 10
    note: "Schnelle Rust-Tests, damit PR-Feedback nicht stockt."

ci:
  max_runtime_minutes:
    default: 20
    heavy: 45
    note: "Deckel pro Job; deckt sich mit aktuellen Timeouts in Workflows (Stand Februar 2025)."

observability:
  required:
    - "compose.core.yml"
    - "compose.observ.yml"
  note: "Sobald Observability-Compose landet, wird hier 'compose.observ.yml' Pflicht."

docs:
  runbooks_required:
    - "docs/runbooks/README.md"
    - "docs/runbooks/codespaces-recovery.md"
    - "docs/runbooks/observability.md"
  note: "observability.md folgt; zunächst nur als Reminder gelistet."

semantics:
  max_nodes_jsonl_mb: 50
  max_edges_jsonl_mb: 50
  note: "Nur Informationsaufnahme; Import-Job folgt separat."
```

### 📄 policies/perf.json

**Größe:** 421 B | **md5:** `ec77e50ece7ad6399752423748414e0f`

```json
{
  "frontend": {
    "js_budget_kb": 60,
    "tti_ms_p95": 2500,
    "lcp_ms_p75": 2500,
    "long_tasks_per_view_max": 10
  },
  "api": {
    "latency_ms_p95": 300,
    "db_query_ms_p95": 150,
    "latency_target_note": "API latency target and SLO policy latency target are both set to 300ms intentionally for consistency."
  },
  "edge": {
    "monthly_egress_gb_max": 200,
    "edge_cost_delta_30d_pct_max": 10
  }
}
```

### 📄 policies/retention.yml

**Größe:** 416 B | **md5:** `67096157882cd66d87f83024d4e5313e`

```yaml
data_lifecycle:
  fade_days: 7
  ron_days: 84
  delegation_expire_days: 28
  anonymize_opt_in_default: true
forget_pipeline:
  - name: primary_accounts
    actions:
      - type: anonymize
        deadline_days: 7
      - type: delete
        deadline_days: 84
  - name: delegation_tokens
    actions:
      - type: revoke
        deadline_days: 28
compliance:
  privacy_by_design: true
  ron_anonymization: enabled
```

### 📄 policies/security.yml

**Größe:** 371 B | **md5:** `6609aa917e7b36ec6d837afd9e342cb8`

```yaml
content_security_policy:
  default-src: "'self'"
  img-src: "'self' data:"
  script-src: "'self' 'unsafe-inline'"
  connect-src:
    - "'self'"
    - https://api.weltgewebe.internal
allowed_origins:
  - https://app.weltgewebe.example
  - https://console.weltgewebe.example
strict_transport_security:
  max_age_seconds: 63072000
  include_subdomains: true
  preload: true
```

### 📄 policies/slo.yaml

**Größe:** 437 B | **md5:** `406302df1aad0e217bf229bfeb9c5298`

```yaml
version: 1
services:
  web:
    # availability_target is a percentage (e.g., 99.9% uptime)
    availability_target: 99.9
    latency:
      p95_ms: 3000
      alert_threshold_pct_over_budget: 5
  api:
    # availability_target is a percentage (e.g., 99.95% uptime)
    availability_target: 99.95
    latency:
      p95_ms: 300
      alert_threshold_pct_over_budget: 5
error_budgets:
  window_days: 30
  warn_at_pct: 25
  page_at_pct: 50
```
```

### 📄 merges/weltgewebe_merge_2510262237__root.md

**Größe:** 70 KB | **md5:** `f4ba54e73602d73bb817b4afcae3df6c`

```markdown
### 📄 .dockerignore

**Größe:** 136 B | **md5:** `e1f0168eace98a0b6158666ab4df57ff`

```plaintext
/node_modules
**/node_modules
**/.svelte-kit
**/.vite
**/.next
**/dist
**/build
**/target
/.cargo
.git
.gitignore
.DS_Store
.env
.env.*
```

### 📄 .editorconfig

**Größe:** 195 B | **md5:** `c5c030dca5adf99ed51d20fb9dd88b35`

```plaintext
root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.rs]
indent_size = 4

[*.sh]
indent_size = 4
```

### 📄 .gitattributes

**Größe:** 17 B | **md5:** `71450edb9a4f8cf9d474fb0a1432a3d5`

```plaintext
*.sh text eol=lf
```

### 📄 .gitignore

**Größe:** 279 B | **md5:** `feff7a80ee0ac93560795b8818869afa`

```plaintext
# Weltgewebe repository ignores
# Prevent accidental check-in of local Git directories
/.git/

# Environment files
.env
.env.local
.env.*
!.env.example

# Node/NPM artifacts
node_modules/
npm-debug.log*

# Build outputs
build/
dist/
.tmp/
target/

# OS files
.DS_Store
Thumbs.db
```

### 📄 .lychee.toml

**Größe:** 287 B | **md5:** `ae4d79202645000d4956d73acb13c7d3`

```toml
# Retries & Timeouts
max_redirects = 5
timeout = 10
retry_wait_time = 2
retry_count = 2

# Private/temporäre Hosts ignorieren (Beispiele)
exclude = [
  "localhost",
  "127.0.0.1",
  "0.0.0.0"
]

# Pfade: node_modules & Git-Ordner ausnehmen
exclude_path = [
  "node_modules",
  ".git"
]
```

### 📄 .markdownlint.jsonc

**Größe:** 109 B | **md5:** `aa1753b57ccc3fb5b53d7370b9ae2f73`

```plaintext
{
  "default": true,
  "MD013": { "line_length": 120, "tables": false },
  "MD033": false,
  "MD041": false
}
```

### 📄 .markdownlint.yaml

**Größe:** 86 B | **md5:** `3800019826b32c0cd883553dfa5a4fab`

```yaml
---
default: true
MD013:
  line_length: 120
  tables: false
MD033: false
MD041: false
```

### 📄 .nvmrc

**Größe:** 4 B | **md5:** `54cd1eb655dd4f5ee6410c4fd4a9c53a`

```plaintext
v20
```

### 📄 .vale.ini

**Größe:** 94 B | **md5:** `4f2775559c47a6279a64d9ed0f1675b7`

```plaintext
StylesPath = .vale/styles
MinAlertLevel = suggestion

[*.md]
BasedOnStyles = Vale, Weltgewebe
```

### 📄 .yamllint.yml

**Größe:** 161 B | **md5:** `d826f0422646e4e79b47ac7b319fd52e`

```yaml
extends: default

rules:
  line-length:
    max: 120
    allow-non-breakable-words: true
  truthy:
    level: warning
  comments:
    min-spaces-from-content: 1
```

### 📄 CONTRIBUTING.md

**Größe:** 5 KB | **md5:** `bdff7cad9dc64f137f0e75a6df11f304`

```markdown
Hier ist das finale CONTRIBUTING.md – optimiert, konsistent mit docs/architekturstruktur.md, und so
geschrieben, dass Menschen
und KIs sofort wissen, was wohin gehört, warum, und wie gearbeitet wird.

⸻

# CONTRIBUTING.md

## Weltgewebe – Beiträge, Qualität, Wegeführung

Dieses Dokument erklärt, wie im Weltgewebe-Repository gearbeitet wird: Ordner-Orientierung,
Workflows, Qualitätsmaßstäbe und
Entscheidungswege.

Es baut auf folgenden Dateien auf:

- docs/architekturstruktur.md – verbindliche Repo-Struktur (Ordner, Inhalte, Zweck).
- docs/techstack.md – Stack-Referenz (SvelteKit, Rust/Axum, Postgres+Outbox, JetStream, Caddy,
  Observability).
- ci/budget.json – Performance-Budgets (Frontend).
- docs/runbook.md – Woche-1/2, DR/DSGVO-Drills.
- docs/datenmodell.md – Tabellen, Projektionen, Events.

Kurzprinzip: „Richtig routen, klein schneiden, sauber messen.“ Beiträge landen im richtigen Ordner,
klein und testbar, mit
Metriken und Budgets im Blick.

⸻

## 1. Repo-Topographie in 30 Sekunden

- apps/ – Business-Code (Web-Frontend, API, Worker, optionale Search-Adapter).
- packages/ – gemeinsame Libraries/SDKs (optional).
- infra/ – Compose-Profile, Proxy (Caddy), DB-Init, Monitoring, optional Nomad/K8s.
- docs/ – ADRs, Architektur-Poster, Datenmodell, Runbook.
- ci/ – GitHub-Workflows, Skripte, Performance-Budgets.
- Root – .env.example, Editor/Git-Konfig, Lizenz, README.

Details: siehe docs/architekturstruktur.md.

⸻

## 2. Routing-Matrix „Wohin gehört was?“

- Neue Seite oder Route im UI
  - Zielordner/Datei: apps/web/src/routes/...
  - Typisches Pattern: +page.svelte, +page.ts, +server.ts.
  - Grund: SvelteKit-Routing, SSR/Islands, nahe an UI.
- UI-Komponente, Store oder Util
  - Zielordner/Datei: apps/web/src/lib/...
  - Typisches Pattern: *.svelte, stores.ts, utils.ts.
  - Grund: Wiederverwendung, klare Trennung vom Routing.
- Statische Assets
  - Zielordner/Datei: apps/web/static/.
  - Typisches Pattern: manifest.webmanifest, Icons, Fonts.
  - Grund: Build-unabhängige Auslieferung.
- Neuer API-Endpoint
  - Zielordner/Datei: apps/api/src/routes/...
  - Typisches Pattern: mod.rs, Handler, Router.
  - Grund: HTTP/SSE-Schnittstelle gehört in routes.
- Geschäftslogik oder Service
  - Zielordner/Datei: apps/api/src/domain/...
  - Typisches Pattern: Use-Case-Funktionen.
  - Grund: Fachlogik von I/O trennen.
- DB-Zugriff (nur PostgreSQL)
  - Zielordner/Datei: apps/api/src/repo/...
  - Typisches Pattern: sqlx-Queries, Mappings.
  - Grund: Konsistente Datenzugriffe.
- Outbox-Publizierer oder Eventtypen
  - Zielordner/Datei: apps/api/src/events/...
  - Typisches Pattern: publish_*, Event-Schema.
  - Grund: Transaktionale Events am System of Truth.
- DB-Migrationen
  - Zielordner/Datei: apps/api/migrations/.
  - Typisches Pattern: YYYYMMDDHHMM__beschreibung.sql.
  - Grund: Änderungsverfolgung am Schema.
- Timeline-Projektor
  - Zielordner/Datei: apps/worker/src/projector_timeline.rs.
  - Typisches Pattern: Outbox → Timeline.
  - Grund: Read-Model separat, idempotent.
- Search-Projektor
  - Zielordner/Datei: apps/worker/src/projector_search.rs.
  - Typisches Pattern: Outbox → Typesense/Meili.
  - Grund: Indexing asynchron.
- DSGVO- oder DR-Rebuilder
  - Zielordner/Datei: apps/worker/src/replayer.rs.
  - Typisches Pattern: Replay/Shadow-Rebuild.
  - Grund: Audit- und Forget-Pfad.
- Search-Adapter oder SDK
  - Zielordner/Datei: apps/search/adapters/...
  - Typisches Pattern: typesense.ts, meili.ts.
  - Grund: Client-Adapter gekapselt.
- Compose-Profile
  - Zielordner/Datei: infra/compose/*.yml.
  - Typisches Pattern: compose.core.yml usw.
  - Grund: Start- und Betriebsprofile.
- Proxy, Headers, CSP
  - Zielordner/Datei: infra/caddy/Caddyfile.
  - Typisches Pattern: HTTP/3, TLS, CSP.
  - Grund: Auslieferung & Sicherheit.
- DB-Init und Partitionierung
  - Zielordner/Datei: infra/db/{init,partman}/.
  - Typisches Pattern: Extensions, Partman.
  - Grund: Basis-Setup für PostgreSQL.
- Monitoring
  - Zielordner/Datei: infra/monitoring/...
  - Typisches Pattern: prometheus.yml, Dashboards, Alerts.
  - Grund: Metriken, SLO-Wächter.
- Architektur-Entscheidung
  - Zielordner/Datei: docs/adr/ADR-xxx.md.
  - Typisches Pattern: Datum- oder Nummernschema.
  - Grund: Nachvollziehbarkeit.
- Runbook
  - Zielordner/Datei: docs/runbook.md.
  - Typisches Pattern: Woche-1/2, DR/DSGVO.
  - Grund: Betrieb in der Praxis.
- Datenmodell
  - Zielordner/Datei: docs/datenmodell.md.
  - Typisches Pattern: Tabellen/Projektionen.
  - Grund: Referenz für API/Worker.

⸻

## 3. Arbeitsweise / Workflow

Branch-Strategie: kurzes Feature-Branching gegen main.
Kleine, thematisch fokussierte Pull Requests.

Commit-Präfixe:

- feat(web): … | feat(api): … | feat(worker): … | feat(infra): …
- fix(...) | chore(...) | refactor(...) | docs(adr|runbook|...)

PR-Prozess:

1. Lokal: Lints, Tests und Budgets laufen lassen.
2. PR klein halten, Zweck und „Wie getestet“ kurz erläutern.
3. Bei Architektur- oder Sicherheitsauswirkungen: ADR oder Runbook-Update beilegen oder verlinken.

CI-Gates (brechen Builds):

- Frontend-Budget aus ci/budget.json (Initial-JS ≤ 60 KB, TTI ≤ 2000 ms).
- Lints/Formatter (Web: ESLint/Prettier; API/Worker: cargo fmt, cargo clippy -D).
- Tests (npm test, cargo test).
- Sicherheitschecks (cargo audit/deny), Konfiglint (Prometheus, Caddy).
```

### 📄 Cargo.lock

**Größe:** 63 KB | **md5:** `534509eff6be9f906bb07d41eda3bfe7`

```plaintext
# This file is automatically @generated by Cargo.
# It is not intended for manual editing.
version = 4

[[package]]
name = "aho-corasick"
version = "1.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "8e60d3430d3a69478ad0993f19238d2df97c507009a52b3c10addcd7f6bcb916"
dependencies = [
 "memchr",
]

[[package]]
name = "allocator-api2"
version = "0.2.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "683d7910e743518b0e34f1186f92494becacb047c7b6bf616c96772180fef923"

[[package]]
name = "anyhow"
version = "1.0.100"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a23eb6b1614318a8071c9b2521f36b424b2c83db5eb3a0fead4a6c0809af6e61"

[[package]]
name = "async-nats"
version = "0.35.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ab8df97cb8fc4a884af29ab383e9292ea0939cfcdd7d2a17179086dc6c427e7f"
dependencies = [
 "base64",
 "bytes",
 "futures",
 "memchr",
 "nkeys",
 "nuid",
 "once_cell",
 "portable-atomic",
 "rand",
 "regex",
 "ring",
 "rustls-native-certs",
 "rustls-pemfile",
 "rustls-webpki 0.102.8",
 "serde",
 "serde_json",
 "serde_nanos",
 "serde_repr",
 "thiserror 1.0.69",
 "time",
 "tokio",
 "tokio-rustls",
 "tracing",
 "tryhard",
 "url",
]

[[package]]
name = "async-trait"
version = "0.1.89"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9035ad2d096bed7955a320ee7e2230574d28fd3c3a0f186cbea1ff3c7eed5dbb"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "atoi"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f28d99ec8bfea296261ca1af174f24225171fea9664ba9003cbebee704810528"
dependencies = [
 "num-traits",
]

[[package]]
name = "atomic-waker"
version = "1.1.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1505bd5d3d116872e7271a6d4e16d81d0c8570876c8de68093a09ac269d8aac0"

[[package]]
name = "autocfg"
version = "1.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "c08606f8c3cbf4ce6ec8e28fb0014a2c086708fe954eaa885384a6165172e7e8"

[[package]]
name = "axum"
version = "0.7.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "edca88bc138befd0323b20752846e6587272d3b03b0343c8ea28a6f819e6e71f"
dependencies = [
 "async-trait",
 "axum-core",
 "axum-macros",
 "bytes",
 "futures-util",
 "http",
 "http-body",
 "http-body-util",
 "hyper",
 "hyper-util",
 "itoa",
 "matchit",
 "memchr",
 "mime",
 "percent-encoding",
 "pin-project-lite",
 "rustversion",
 "serde",
 "serde_json",
 "serde_path_to_error",
 "serde_urlencoded",
 "sync_wrapper",
 "tokio",
 "tower",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-core"
version = "0.4.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "09f2bd6146b97ae3359fa0cc6d6b376d9539582c7b4220f041a33ec24c226199"
dependencies = [
 "async-trait",
 "bytes",
 "futures-util",
 "http",
 "http-body",
 "http-body-util",
 "mime",
 "pin-project-lite",
 "rustversion",
 "sync_wrapper",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-macros"
version = "0.4.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "57d123550fa8d071b7255cb0cc04dc302baa6c8c4a79f55701552684d8399bce"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "base64"
version = "0.22.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "72b3254f16251a8381aa12e40e3c4d2f0199f8c6508fbecb9d91f575e0fbb8c6"

[[package]]
name = "base64ct"
version = "1.8.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "55248b47b0caf0546f7988906588779981c43bb1bc9d0c44087278f80cdb44ba"

[[package]]
name = "bitflags"
version = "2.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2261d10cca569e4643e526d8dc2e62e433cc8aba21ab764233731f8d369bf394"

[[package]]
name = "block-buffer"
version = "0.10.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3078c7629b62d3f0439517fa394996acacc5cbc91c5a20d8c658e77abd503a71"
dependencies = [
 "generic-array",
]

[[package]]
name = "byteorder"
version = "1.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1fd0f2584146f6f2ef48085050886acf353beff7305ebd1ae69500e27c67f64b"

[[package]]
name = "bytes"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d71b6127be86fdcfddb610f7182ac57211d4b18a3e9c82eb2d17662f2227ad6a"
dependencies = [
 "serde",
]

[[package]]
name = "cc"
version = "1.2.41"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ac9fe6cdbb24b6ade63616c0a0688e45bb56732262c158df3c0c4bea4ca47cb7"
dependencies = [
 "find-msvc-tools",
 "shlex",
]

[[package]]
name = "cfg-if"
version = "1.0.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9330f8b2ff13f34540b44e946ef35111825727b38d33286ef986142615121801"

[[package]]
name = "concurrent-queue"
version = "2.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "4ca0197aee26d1ae37445ee532fefce43251d24cc7c166799f4d46817f1d3973"
dependencies = [
 "crossbeam-utils",
]

[[package]]
name = "const-oid"
version = "0.9.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "c2459377285ad874054d797f3ccebf984978aa39129f6eafde5cdc8315b612f8"

[[package]]
name = "core-foundation"
version = "0.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "91e195e091a93c46f7102ec7818a2aa394e1e1771c3ab4825963fa03e45afb8f"
dependencies = [
 "core-foundation-sys",
 "libc",
]

[[package]]
name = "core-foundation-sys"
version = "0.8.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "773648b94d0e5d620f64f280777445740e61fe701025087ec8b57f45c791888b"

[[package]]
name = "cpufeatures"
version = "0.2.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "59ed5838eebb26a2bb2e58f6d5b5316989ae9d08bab10e0e6d103e656d1b0280"
dependencies = [
 "libc",
]

[[package]]
name = "crc"
version = "3.3.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9710d3b3739c2e349eb44fe848ad0b7c8cb1e42bd87ee49371df2f7acaf3e675"
dependencies = [
 "crc-catalog",
]

[[package]]
name = "crc-catalog"
version = "2.4.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "19d374276b40fb8bbdee95aef7c7fa6b5316ec764510eb64b8dd0e2ed0d7e7f5"

[[package]]
name = "crossbeam-queue"
version = "0.3.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0f58bbc28f91df819d0aa2a2c00cd19754769c2fad90579b3592b1c9ba7a3115"
dependencies = [
 "crossbeam-utils",
]

[[package]]
name = "crossbeam-utils"
version = "0.8.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d0a5c400df2834b80a4c3327b3aad3a4c4cd4de0629063962b03235697506a28"

[[package]]
name = "crypto-common"
version = "0.1.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1bfb12502f3fc46cca1bb51ac28df9d618d813cdc3d2f25b9fe775a34af26bb3"
dependencies = [
 "generic-array",
 "typenum",
]

[[package]]
name = "curve25519-dalek"
version = "4.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "97fb8b7c4503de7d6ae7b42ab72a5a59857b4c937ec27a3d4539dba95b5ab2be"
dependencies = [
 "cfg-if",
 "cpufeatures",
 "curve25519-dalek-derive",
 "digest",
 "fiat-crypto",
 "rustc_version",
 "subtle",
]

[[package]]
name = "curve25519-dalek-derive"
version = "0.1.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f46882e17999c6cc590af592290432be3bce0428cb0d5f8b6715e4dc7b383eb3"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "data-encoding"
version = "2.9.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2a2330da5de22e8a3cb63252ce2abb30116bf5265e89c0e01bc17015ce30a476"

[[package]]
name = "der"
version = "0.7.10"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e7c1832837b905bbfb5101e07cc24c8deddf52f93225eee6ead5f4d63d53ddcb"
dependencies = [
 "const-oid",
 "pem-rfc7468",
 "zeroize",
]

[[package]]
name = "deranged"
version = "0.5.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a41953f86f8a05768a6cda24def994fd2f424b04ec5c719cf89989779f199071"
dependencies = [
 "powerfmt",
 "serde_core",
]

[[package]]
name = "digest"
version = "0.10.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9ed9a281f7bc9b7576e61468ba615a66a5c8cfdff42420a70aa82701a3b1e292"
dependencies = [
 "block-buffer",
 "crypto-common",
 "subtle",
]

[[package]]
name = "displaydoc"
version = "0.2.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "97369cbbc041bc366949bc74d34658d6cda5621039731c6310521892a3a20ae0"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "dotenvy"
version = "0.15.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1aaf95b3e5c8f23aa320147307562d361db0ae0d51242340f558153b4eb2439b"

[[package]]
name = "ed25519"
version = "2.2.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "115531babc129696a58c64a4fef0a8bf9e9698629fb97e9e40767d235cfbcd53"
dependencies = [
 "signature",
]

[[package]]
name = "ed25519-dalek"
version = "2.2.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "70e796c081cee67dc755e1a36a0a172b897fab85fc3f6bc48307991f64e4eca9"
dependencies = [
 "curve25519-dalek",
 "ed25519",
 "sha2",
 "signature",
 "subtle",
]

[[package]]
name = "either"
version = "1.15.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "48c757948c5ede0e46177b7add2e67155f70e33c07fea8284df6576da70b3719"
dependencies = [
 "serde",
]

[[package]]
name = "equivalent"
version = "1.0.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "877a4ace8713b0bcf2a4e7eec82529c029f1d0619886d18145fea96c3ffe5c0f"

[[package]]
name = "errno"
version = "0.3.14"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "39cab71617ae0d63f51a36d69f866391735b51691dbda63cf6f96d042b63efeb"
dependencies = [
 "libc",
 "windows-sys 0.61.2",
]

[[package]]
name = "etcetera"
version = "0.8.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "136d1b5283a1ab77bd9257427ffd09d8667ced0570b6f938942bc7568ed5b943"
dependencies = [
 "cfg-if",
 "home",
 "windows-sys 0.48.0",
]

[[package]]
name = "event-listener"
version = "5.4.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e13b66accf52311f30a0db42147dadea9850cb48cd070028831ae5f5d4b856ab"
dependencies = [
 "concurrent-queue",
 "parking",
 "pin-project-lite",
]

[[package]]
name = "fastrand"
version = "2.3.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "37909eebbb50d72f9059c3b6d82c0463f2ff062c9e95845c43a6c9c0355411be"

[[package]]
name = "fiat-crypto"
version = "0.2.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "28dea519a9695b9977216879a3ebfddf92f1c08c05d984f8996aecd6ecdc811d"

[[package]]
name = "find-msvc-tools"
version = "0.1.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "52051878f80a721bb68ebfbc930e07b65ba72f2da88968ea5c06fd6ca3d3a127"

[[package]]
name = "fnv"
version = "1.0.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3f9eec918d3f24069decb9af1554cad7c880e2da24a9afd88aca000531ab82c1"

[[package]]
name = "foldhash"
version = "0.1.5"
source = "registry+https://github.com/rust-lang/crates.io-index"

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__scripts_tools.md

**Größe:** 5 KB | **md5:** `405645040e2a07409f705d44616fba38`

```markdown
### 📄 scripts/tools/yq-pin.sh

**Größe:** 5 KB | **md5:** `df60f78b96090262ef390f02c6982cc3`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Minimaler Installer/Pinner für mikefarah/yq v4.x
# Usage: scripts/tools/yq-pin.sh ensure [<version>]
# Default: 4.44.1

CMD="${1:-ensure}"
REQ_VER="${2:-${YQ_VERSION:-4.44.1}}"
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
```
```

### 📄 merges/weltgewebe_merge_2510262237__tools.md

**Größe:** 598 B | **md5:** `c2a3709780d5073ec64f585ca3753bd8`

```markdown
### 📄 tools/drill-smoke.sh

**Größe:** 488 B | **md5:** `ab47f66548de5afccc0688ba95c42ba3`

```bash
#!/usr/bin/env bash
set -euo pipefail

printf "[drill] Starting disaster recovery smoke sequence...\n"

# Placeholder: ensure core services are up
if ! docker compose -f infra/compose/compose.core.yml ps >/dev/null 2>&1; then
  printf "[drill] Hinweis: Compose-Stack scheint nicht zu laufen. Bitte zuerst 'just up' ausführen.\n"
  exit 1
fi

docker compose -f infra/compose/compose.core.yml ps

printf "[drill] TODO: Automatisierte Smoke-Tests (Login, Thread-Erstellung) integrieren.\n"
```
```

### 📄 merges/weltgewebe_merge_2510262237__tools_py.md

**Größe:** 2 KB | **md5:** `bb3894a590096a75403951a79594364e`

```markdown
### 📄 tools/py/README.md

**Größe:** 296 B | **md5:** `6a43f76336f99f1d2caf09c2b5ad8e7f`

```markdown
# Weltgewebe – Python Tools

## Schnellstart

```bash
cd tools/py
uv sync        # erstellt venv, installiert deps (aktuell leer)
uv run python -V
```

## Abhängigkeiten hinzufügen

```bash
uv add ruff black
```

Das erzeugt/aktualisiert `uv.lock` – damit sind Builds in CI reproduzierbar.
```

### 📄 tools/py/policycheck.py

**Größe:** 1 KB | **md5:** `1531eb55d304c38c6b8ceb91980e0a7c`

```python
#!/usr/bin/env python3
"""Basic policy consistency checks."""

from __future__ import annotations

import pathlib
import sys

import yaml


def main() -> int:
    policy_path = pathlib.Path("policies/retention.yml")
    if not policy_path.exists():
        print("::error::policies/retention.yml missing")
        return 1

    data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    lifecycle = data.get("data_lifecycle")
    if not isinstance(lifecycle, dict):
        print("::error::data_lifecycle section missing")
        return 1

    try:
        fade_days = int(lifecycle["fade_days"])
        ron_days = int(lifecycle["ron_days"])
    except (KeyError, TypeError, ValueError) as exc:
        print(f"::error::invalid lifecycle values: {exc}")
        return 1

    if fade_days <= 0:
        print("::error::fade_days must be > 0")
        return 1

    if ron_days < fade_days:
        print("::error::ron_days must be >= fade_days")
        return 1

    print("policy ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 📄 tools/py/pyproject.toml

**Größe:** 259 B | **md5:** `96b3e59f00667138a66ea5d634b58b6b`

```toml
[project]
name = "weltgewebe-tools"
version = "0.1.0"
description = "Python tooling for Weltgewebe (CLI, lint, ETL, experiments)"
requires-python = ">=3.11"
dependencies = []

[tool.uv]
# uv verwaltet Lockfile uv.lock im Projektroot oder hier im Unterordner.
```
```

### 📄 merges/weltgewebe_merge_2510262237__tools_py_cost.md

**Größe:** 2 KB | **md5:** `1b72238769fe6fc9cbcc04363ba68fd2`

```markdown
### 📄 tools/py/cost/model.csv

**Größe:** 98 B | **md5:** `98ff2a57322a28e11011e8132b3cba57`

```plaintext
metric,value,unit
request_cost_eur,0.0002,EUR
session_avg_requests,12,req
active_users,1000,users
```

### 📄 tools/py/cost/report.py

**Größe:** 1 KB | **md5:** `8312cd39317502c07772c03ff60f6d4e`

```python
#!/usr/bin/env python3
"""Generate a simple monthly cost report."""

from __future__ import annotations

import csv
import datetime as dt
import pathlib


MODEL_PATH = pathlib.Path("tools/py/cost/model.csv")
OUTPUT_PATH = pathlib.Path("docs/reports/cost-report.md")


def load_metric(rows: list[dict[str, str]], name: str) -> float:
    for row in rows:
        if row["metric"] == name:
            return float(row["value"])
    raise KeyError(name)


def main() -> int:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(MODEL_PATH)

    with MODEL_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    request_cost_eur = load_metric(rows, "request_cost_eur")
    avg_requests = load_metric(rows, "session_avg_requests")
    active_users = load_metric(rows, "active_users")

    monthly_cost = active_users * avg_requests * request_cost_eur * 30

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "# Cost Report {:%Y-%m}\n\n≈ {:.2f} EUR/Monat\n".format(
            dt.date.today(), monthly_cost
        ),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe.md

**Größe:** 75 KB | **md5:** `a313309389d39056b38dbaf9110c141b`

```markdown
### 📄 weltgewebe/.dockerignore

**Größe:** 136 B | **md5:** `e1f0168eace98a0b6158666ab4df57ff`

```plaintext
/node_modules
**/node_modules
**/.svelte-kit
**/.vite
**/.next
**/dist
**/build
**/target
/.cargo
.git
.gitignore
.DS_Store
.env
.env.*
```

### 📄 weltgewebe/.editorconfig

**Größe:** 195 B | **md5:** `c5c030dca5adf99ed51d20fb9dd88b35`

```plaintext
root = true

[*]
end_of_line = lf
insert_final_newline = true
charset = utf-8
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.rs]
indent_size = 4

[*.sh]
indent_size = 4
```

### 📄 weltgewebe/.gitattributes

**Größe:** 17 B | **md5:** `71450edb9a4f8cf9d474fb0a1432a3d5`

```plaintext
*.sh text eol=lf
```

### 📄 weltgewebe/.gitignore

**Größe:** 279 B | **md5:** `feff7a80ee0ac93560795b8818869afa`

```plaintext
# Weltgewebe repository ignores
# Prevent accidental check-in of local Git directories
/.git/

# Environment files
.env
.env.local
.env.*
!.env.example

# Node/NPM artifacts
node_modules/
npm-debug.log*

# Build outputs
build/
dist/
.tmp/
target/

# OS files
.DS_Store
Thumbs.db
```

### 📄 weltgewebe/.lychee.toml

**Größe:** 287 B | **md5:** `ae4d79202645000d4956d73acb13c7d3`

```toml
# Retries & Timeouts
max_redirects = 5
timeout = 10
retry_wait_time = 2
retry_count = 2

# Private/temporäre Hosts ignorieren (Beispiele)
exclude = [
  "localhost",
  "127.0.0.1",
  "0.0.0.0"
]

# Pfade: node_modules & Git-Ordner ausnehmen
exclude_path = [
  "node_modules",
  ".git"
]
```

### 📄 weltgewebe/.markdownlint.jsonc

**Größe:** 109 B | **md5:** `aa1753b57ccc3fb5b53d7370b9ae2f73`

```plaintext
{
  "default": true,
  "MD013": { "line_length": 120, "tables": false },
  "MD033": false,
  "MD041": false
}
```

### 📄 weltgewebe/.markdownlint.yaml

**Größe:** 86 B | **md5:** `3800019826b32c0cd883553dfa5a4fab`

```yaml
---
default: true
MD013:
  line_length: 120
  tables: false
MD033: false
MD041: false
```

### 📄 weltgewebe/.nvmrc

**Größe:** 4 B | **md5:** `54cd1eb655dd4f5ee6410c4fd4a9c53a`

```plaintext
v20
```

### 📄 weltgewebe/.vale.ini

**Größe:** 94 B | **md5:** `4f2775559c47a6279a64d9ed0f1675b7`

```plaintext
StylesPath = .vale/styles
MinAlertLevel = suggestion

[*.md]
BasedOnStyles = Vale, Weltgewebe
```

### 📄 weltgewebe/.yamllint.yml

**Größe:** 161 B | **md5:** `d826f0422646e4e79b47ac7b319fd52e`

```yaml
extends: default

rules:
  line-length:
    max: 120
    allow-non-breakable-words: true
  truthy:
    level: warning
  comments:
    min-spaces-from-content: 1
```

### 📄 weltgewebe/CONTRIBUTING.md

**Größe:** 10 KB | **md5:** `1208a91aa5a1334c32da04d6ffcd8bfa`

```markdown
Hier ist das finale CONTRIBUTING.md – optimiert, konsistent mit docs/architekturstruktur.md, und so
geschrieben, dass Menschen und KIs sofort wissen, was wohin gehört, warum, und wie gearbeitet wird.

⸻

CONTRIBUTING.md

Weltgewebe – Beiträge, Qualität, Wegeführung

Dieses Dokument erklärt, wie im Weltgewebe-Repository gearbeitet wird: Ordner-Orientierung,
Workflows, Qualitätsmaßstäbe und Entscheidungswege. Es baut auf folgenden Dateien auf:
  •  docs/architekturstruktur.md – verbindliche Repo-Struktur (Ordner, Inhalte, Zweck)
  •  docs/techstack.md – Stack-Referenz (SvelteKit, Rust/Axum, Postgres+Outbox, JetStream, Caddy, Observability)
  •  ci/budget.json – Performance-Budgets (Frontend)
  •  docs/runbook.md – Woche-1/2, DR/DSGVO-Drills
  •  docs/datenmodell.md – Tabellen, Projektionen, Events

Kurzprinzip: „Richtig routen, klein schneiden, sauber messen.“
Beiträge landen im richtigen Ordner, klein und testbar, mit Metriken und Budgets im Blick.

⸻

## 1. Repo-Topographie in 30 Sekunden

  •  apps/ – Business-Code (Web-Frontend, API, Worker, optionale Search-Adapter)
  •  packages/ – gemeinsame Libraries/SDKs (optional)
  •  infra/ – Compose-Profile, Proxy (Caddy), DB-Init, Monitoring, optional Nomad/K8s
  •  docs/ – ADRs, Architektur-Poster, Datenmodell, Runbook
  •  ci/ – GitHub-Workflows, Skripte, Performance-Budgets
  •  Root – .env.example, Editor/Git-Konfig, Lizenz, README

Details: siehe docs/architekturstruktur.md.

⸻

## 2. Routing-Matrix „Wohin gehört was?“

Beitragstyp  Zielordner/Datei  Typisches Pattern  Grund (warum dort)
Neue Seite/Route im UI  apps/web/src/routes/...  +page.svelte, +page.ts, +server.ts  SvelteKit-Routing, SSR/Islands,
      nahe an UI
UI-Komponente/Store/Util  apps/web/src/lib/...  *.svelte, stores.ts, utils.ts  Wiederverwendung, klare Trennung vom Routing
Statische Assets  apps/web/static/  manifest.webmanifest, Icons, Fonts  Build-unabhängige Auslieferung
Neuer API-Endpoint  apps/api/src/routes/...  mod.rs, Handler, Router  HTTP/SSE-Schnittstelle gehört in routes
Geschäftslogik/Service  apps/api/src/domain/...  Use-Case-Funktionen  Fachlogik von I/O trennen
DB-Zugriff (nur PG)  apps/api/src/repo/...  sqlx-Queries, Mappings  Konsistente Datenzugriffe
Outbox-Publizierer/Eventtypen  apps/api/src/events/...  publish_*, Event-Schema  Transaktionale Events am SoT
DB-Migrationen  apps/api/migrations/  YYYYMMDDHHMM__beschreibung.sql  Änderungsverfolgung am Schema
Timeline-Projektor  apps/worker/src/projector_timeline.rs  Outbox → Timeline  Read-Model separat, idempotent
Search-Projektor  apps/worker/src/projector_search.rs  Outbox → Typesense/Meili  Indexing asynchron
DSGVO/DR-Rebuilder  apps/worker/src/replayer.rs  Replay/Shadow-Rebuild  Audit-/Forget-Pfad
Search-Adapter/SDK  apps/search/adapters/...  typesense.ts, meili.ts  Client-Adapter gekapselt
Compose-Profile  infra/compose/*.yml  compose.core.yml usw.  Start-/Betriebsprofile
Proxy/Headers/CSP  infra/caddy/Caddyfile  HTTP/3, TLS, CSP  Auslieferung & Sicherheit
DB-Init/Partitionierung  infra/db/{init,partman}/  Extensions, Partman  Basis-Setup für PG
Monitoring  infra/monitoring/...  prometheus.yml, Dashboards, Alerts  Metriken, SLO-Wächter
Architektur-Entscheidung  docs/adr/ADR-xxx.md  Datum- oder Nummernschema  Nachvollziehbarkeit
Runbook  docs/runbook.md  Woche-1/2, DR/DSGVO  Betrieb in der Praxis
Datenmodell  docs/datenmodell.md  Tabellen/Projektionen  Referenz für API/Worker

⸻

## 3. Arbeitsweise / Workflow

Branch-Strategie: kurzes Feature-Branching gegen main. Kleine, thematisch fokussierte PRs.
Commit-Präfixe:
  •  feat(web): … | feat(api): … | feat(worker): … | feat(infra): …
  •  fix(...) | chore(...) | refactor(...) | docs(adr|runbook|...)

PR-Prozess:

1. Lokal: Lints/Tests/Budgets laufen lassen.
2. PR klein halten, Zweck und „Wie getestet“ kurz erläutern.
3. Bei Architektur- oder Sicherheitsauswirkungen: ADR oder Runbook-Update beilegen oder verlinken.

CI-Gates (brechen Builds):
  •  Frontend-Budget aus ci/budget.json (Initial-JS ≤ 60 KB, TTI ≤ 2000 ms).
  •  Lints/Formatter (Web: ESLint/Prettier; API/Worker: cargo fmt, cargo clippy -D).
  •  Tests (npm test, cargo test).
  •  Sicherheitschecks (cargo audit/deny), Konfiglint (Prometheus, Caddy).

⸻

## 4. Qualitätsmaßstäbe je Schicht

Frontend (SvelteKit):
  •  SSR/PWA-freundlich; Caching per Header (Caddy).
  •  Insel-Denken: nur nötiges JS auf die Route.
  •  Budget: ≤60 KB Initial-JS, TTI ≤2000 ms (3G).
  •  Routen unter src/routes, Bausteine unter src/lib.
  •  RUM/Long-Tasks optional via hooks.client.ts.

API (Rust/Axum):
  •  Layer: routes (I/O) → domain (Fachlogik) → repo (sqlx, PG).
  •  Postgres-only, Migrations in migrations/.
  •  Outbox-Write transaktional, Events minimal (IDs, wenige Felder).
  •  Telemetrie: strukturiertes Logging, /metrics für Prometheus.

Worker:
  •  Idempotente Projektoren (Event-Wiederholung vertragen).
  •  Lag/Throughput messen, Backoff/Retry setzen.
  •  Projektionen und Indizes schlank halten (nur benötigte Felder).
  •  Replayer für DSGVO/DR pflegen und regelmäßig testen (Runbook).

Search (Typesense/Meili):
  •  Delta-Indexierung ereignisbasiert, Dokumente minimal.
  •  Feldevolution über Versionierung (abwärtskompatibel halten).

GIS (falls genutzt):
  •  Geometrien in PostGIS (GiST), H3-Spalten für Nachbarschaften.
  •  BRIN/Partitionen für Event-/Timeline-Tabellen.

⸻

## 5. Daten & Events – Konsistenzpfad

Source of Truth: PostgreSQL + Outbox.
Event-Namen: <aggregate>.<verb> (z. B. post.created, comment.deleted).
Payload-Prinzip: IDs + minimal nötige Felder. Schema-Version bei Änderungen.

Minimal-Beispiel (Event-Payload):

{
  "schema": "post.created@1",
  "aggregate_id": "5cfe6f3e-…",
  "occurred_at": "2025-09-11T12:34:56Z",
  "by": "account:…",
  "data": {
    "thread_id": "…",
    "author_id": "…",
    "h3_9": 613566756…
  }
}

Projektionsfluss: Outbox → JetStream → Projector → Read-Model / Timeline / Search.
DSGVO/Forget: Redaktions-/Lösch-Events erzeugen; Rebuild (Shadow) und Nachweis im Runbook.

⸻

## 6. Performance & Observability

  •  Frontend: Budgets gemäß ci/budget.json. Regelmäßige Lighthouse-Checks.
  •  Server: Ziel-Latenzen p95 route-spezifisch definieren (API, SSE).
  •  JetStream: Topic/Consumer-Lag überwachen; Consumer-Namen stabil halten; Ack-Strategie dokumentieren.
  •  Edge/Cache: s-maxage für SSR-HTML, immutable Assets über Caddy, Tiles/Prebakes getrennt cachen.

⸻

## 7. Sicherheit & Compliance (Kurz)

  •  Secrets: niemals ins Repo; .env.example als Vorlage.
  •  PII: isolieren gemäß Datenmodell; keine PII in Logs/Events.
  •  CSP/CORS: per Caddyfile verwalten; restriktiv beginnen, bei Bedarf öffnen.
  •  Auditierbarkeit: sicherheitsrelevante Änderungen mit ADR begründen.

⸻

## 8. Lokaler Quickstart

### 1. .env anlegen

cp .env.example .env

### 2. Core-Profile hochfahren (API, Web, PG, PgBouncer, Caddy)

docker compose -f infra/compose/compose.core.yml up -d

### 3. DB-Migrationen

docker exec -it welt_api sqlx migrate run   # oder eigenes Migrations-Binary

### 4. Web-Dev

cd apps/web && npm install && npm run dev   # <http://localhost:3000>

### 5. Tests

cd apps/api && cargo test
cd ../web && npm test

### 6. Budgets lokal prüfen (falls Skript vorhanden)

node ci/scripts/lhci.mjs

Weitere Profile: compose.stream.yml (JetStream), compose.search.yml (Typesense/Meili),
compose.observ.yml (Prom/Grafana).

⸻

## 9. Doku & Entscheidungen

ADR-Pflicht bei:
  •  neuem Framework/Tool,
  •  Datenmodell-/Event-Änderungen mit Folgen,
  •  Sicherheits-/Compliance-Themen,
  •  SLO/Monitoring-Regeländerungen.

Schreibe docs/adr/ADR-<laufende_nummer>__<kurztitel>.md mit: Kontext → Entscheidung → Alternativen → Konsequenzen.
Aktualisiere Runbook (Betrieb/Drills) und Datenmodell (Tabellen/Projektionen) bei Bedarf.

⸻

## 10. Versionierung & Releases (Kurz)

  •  SemVer: MAJOR.MINOR.PATCH
  •  Breaking Changes → MAJOR erhöhen, ADR ergänzen.
  •  Tagging und Changelog optional; CI kann Release-Artefakte bauen.

⸻

## 11. Entscheidungsbaum „Wohin mit meinem Beitrag?“

Start
 ├─ Ist es UI (Seite/Komponente/Store)?
 │    └─ apps/web/src/(routes|lib)
 ├─ Ist es ein API-Endpunkt / Server-Use-Case?
 │    ├─ Handler → apps/api/src/routes
 │    ├─ Logik  → apps/api/src/domain
 │    └─ DB     → apps/api/src/repo (+ migrations/)
 ├─ Ist es ein Event-Projektor / Replayer?
 │    └─ apps/worker/src/(projector_*|replayer.rs)
 ├─ Geht es um Suche?
 │    ├─ Projektor → apps/worker/src/projector_search.rs
 │    └─ Adapter  → apps/search/adapters
 ├─ Infrastruktur / Deploy / Monitoring?
 │    └─ infra/(compose|caddy|db|monitoring|nomad|k8s)
 └─ Dokumentation / Entscheidung / Runbook?
      └─ docs/(adr|runbook|datenmodell|techstack)

PR-Checkliste (kurz):
  •  Lints/Formatter/Tests lokal grün
  •  Frontend-Budgets eingehalten (falls UI)
  •  Migrationen geprüft (falls DB) – mit Rollback-Gedanken
  •  Event-Schema minimal & versioniert (falls Events)
  •  Doku/ADR/Runbook aktualisiert (falls nötig)
  •  Zweck & „Wie getestet“ in der PR-Beschreibung

⸻

## 12. Anhänge (kleine Referenzen)

Namensregeln:
  •  Rust: snake_case; TypeScript: kebab-case; ENV: UPPER_SNAKE.
  •  Standard-Ordner: routes/, domain/, repo/, events/, migrations/, telemetry/.

Beispiel-Commit-Nachrichten:

feat(web): neue karte mit layer-toggle (pwa friendly)
fix(api): race-condition im timeline-endpunkt behoben
docs(adr): ADR-012 jetstream-lag-alarme ergänzt
infra(compose): search-profile (typesense+keydb) aktiviert

Beispiel-Migration (Kopfkommentar):

-- 2025-09-11 add_post_stats
-- Kontext: Zählerprojektion für Reaktions-/Kommentarzahl
-- Rollback: DROP TABLE post_stats;

CREATE TABLE post_stats (
  post_id uuid PRIMARY KEY REFERENCES post(id) ON DELETE CASCADE,
  reactions int NOT NULL DEFAULT 0,
  comments  int NOT NULL DEFAULT 0,
  last_activity_at timestamptz
);

⸻

Schlusswort

Dieses Dokument ist die Arbeitslandkarte.
Bei Unklarheiten: zuerst docs/architekturstruktur.md (Ordner), dann docs/ (Entscheidungen/Runbooks),
danach kleiner PR, sauber getestet.
So bleibt Weltgewebe mobil-first, messbar schnell und audit-fest.
```

### 📄 weltgewebe/Cargo.lock

**Größe:** 63 KB | **md5:** `534509eff6be9f906bb07d41eda3bfe7`

```plaintext
# This file is automatically @generated by Cargo.
# It is not intended for manual editing.
version = 4

[[package]]
name = "aho-corasick"
version = "1.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "8e60d3430d3a69478ad0993f19238d2df97c507009a52b3c10addcd7f6bcb916"
dependencies = [
 "memchr",
]

[[package]]
name = "allocator-api2"
version = "0.2.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "683d7910e743518b0e34f1186f92494becacb047c7b6bf616c96772180fef923"

[[package]]
name = "anyhow"
version = "1.0.100"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a23eb6b1614318a8071c9b2521f36b424b2c83db5eb3a0fead4a6c0809af6e61"

[[package]]
name = "async-nats"
version = "0.35.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ab8df97cb8fc4a884af29ab383e9292ea0939cfcdd7d2a17179086dc6c427e7f"
dependencies = [
 "base64",
 "bytes",
 "futures",
 "memchr",
 "nkeys",
 "nuid",
 "once_cell",
 "portable-atomic",
 "rand",
 "regex",
 "ring",
 "rustls-native-certs",
 "rustls-pemfile",
 "rustls-webpki 0.102.8",
 "serde",
 "serde_json",
 "serde_nanos",
 "serde_repr",
 "thiserror 1.0.69",
 "time",
 "tokio",
 "tokio-rustls",
 "tracing",
 "tryhard",
 "url",
]

[[package]]
name = "async-trait"
version = "0.1.89"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9035ad2d096bed7955a320ee7e2230574d28fd3c3a0f186cbea1ff3c7eed5dbb"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "atoi"
version = "2.0.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f28d99ec8bfea296261ca1af174f24225171fea9664ba9003cbebee704810528"
dependencies = [
 "num-traits",
]

[[package]]
name = "atomic-waker"
version = "1.1.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1505bd5d3d116872e7271a6d4e16d81d0c8570876c8de68093a09ac269d8aac0"

[[package]]
name = "autocfg"
version = "1.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "c08606f8c3cbf4ce6ec8e28fb0014a2c086708fe954eaa885384a6165172e7e8"

[[package]]
name = "axum"
version = "0.7.9"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "edca88bc138befd0323b20752846e6587272d3b03b0343c8ea28a6f819e6e71f"
dependencies = [
 "async-trait",
 "axum-core",
 "axum-macros",
 "bytes",
 "futures-util",
 "http",
 "http-body",
 "http-body-util",
 "hyper",
 "hyper-util",
 "itoa",
 "matchit",
 "memchr",
 "mime",
 "percent-encoding",
 "pin-project-lite",
 "rustversion",
 "serde",
 "serde_json",
 "serde_path_to_error",
 "serde_urlencoded",
 "sync_wrapper",
 "tokio",
 "tower",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-core"
version = "0.4.5"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "09f2bd6146b97ae3359fa0cc6d6b376d9539582c7b4220f041a33ec24c226199"
dependencies = [
 "async-trait",
 "bytes",
 "futures-util",
 "http",
 "http-body",
 "http-body-util",
 "mime",
 "pin-project-lite",
 "rustversion",
 "sync_wrapper",
 "tower-layer",
 "tower-service",
 "tracing",
]

[[package]]
name = "axum-macros"
version = "0.4.2"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "57d123550fa8d071b7255cb0cc04dc302baa6c8c4a79f55701552684d8399bce"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "base64"
version = "0.22.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "72b3254f16251a8381aa12e40e3c4d2f0199f8c6508fbecb9d91f575e0fbb8c6"

[[package]]
name = "base64ct"
version = "1.8.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "55248b47b0caf0546f7988906588779981c43bb1bc9d0c44087278f80cdb44ba"

[[package]]
name = "bitflags"
version = "2.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2261d10cca569e4643e526d8dc2e62e433cc8aba21ab764233731f8d369bf394"

[[package]]
name = "block-buffer"
version = "0.10.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3078c7629b62d3f0439517fa394996acacc5cbc91c5a20d8c658e77abd503a71"
dependencies = [
 "generic-array",
]

[[package]]
name = "byteorder"
version = "1.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1fd0f2584146f6f2ef48085050886acf353beff7305ebd1ae69500e27c67f64b"

[[package]]
name = "bytes"
version = "1.10.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d71b6127be86fdcfddb610f7182ac57211d4b18a3e9c82eb2d17662f2227ad6a"
dependencies = [
 "serde",
]

[[package]]
name = "cc"
version = "1.2.41"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "ac9fe6cdbb24b6ade63616c0a0688e45bb56732262c158df3c0c4bea4ca47cb7"
dependencies = [
 "find-msvc-tools",
 "shlex",
]

[[package]]
name = "cfg-if"
version = "1.0.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9330f8b2ff13f34540b44e946ef35111825727b38d33286ef986142615121801"

[[package]]
name = "concurrent-queue"
version = "2.5.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "4ca0197aee26d1ae37445ee532fefce43251d24cc7c166799f4d46817f1d3973"
dependencies = [
 "crossbeam-utils",
]

[[package]]
name = "const-oid"
version = "0.9.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "c2459377285ad874054d797f3ccebf984978aa39129f6eafde5cdc8315b612f8"

[[package]]
name = "core-foundation"
version = "0.9.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "91e195e091a93c46f7102ec7818a2aa394e1e1771c3ab4825963fa03e45afb8f"
dependencies = [
 "core-foundation-sys",
 "libc",
]

[[package]]
name = "core-foundation-sys"
version = "0.8.7"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "773648b94d0e5d620f64f280777445740e61fe701025087ec8b57f45c791888b"

[[package]]
name = "cpufeatures"
version = "0.2.17"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "59ed5838eebb26a2bb2e58f6d5b5316989ae9d08bab10e0e6d103e656d1b0280"
dependencies = [
 "libc",
]

[[package]]
name = "crc"
version = "3.3.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "9710d3b3739c2e349eb44fe848ad0b7c8cb1e42bd87ee49371df2f7acaf3e675"
dependencies = [
 "crc-catalog",
]

[[package]]
name = "crc-catalog"
version = "2.4.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "19d374276b40fb8bbdee95aef7c7fa6b5316ec764510eb64b8dd0e2ed0d7e7f5"

[[package]]
name = "crossbeam-queue"
version = "0.3.12"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "0f58bbc28f91df819d0aa2a2c00cd19754769c2fad90579b3592b1c9ba7a3115"
dependencies = [
 "crossbeam-utils",
]

[[package]]
name = "crossbeam-utils"
version = "0.8.21"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "d0a5c400df2834b80a4c3327b3aad3a4c4cd4de0629063962b03235697506a28"

[[package]]
name = "crypto-common"
version = "0.1.6"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1bfb12502f3fc46cca1bb51ac28df9d618d813cdc3d2f25b9fe775a34af26bb3"
dependencies = [
 "generic-array",
 "typenum",
]

[[package]]
name = "curve25519-dalek"
version = "4.1.3"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "97fb8b7c4503de7d6ae7b42ab72a5a59857b4c937ec27a3d4539dba95b5ab2be"
dependencies = [
 "cfg-if",
 "cpufeatures",
 "curve25519-dalek-derive",
 "digest",
 "fiat-crypto",
 "rustc_version",
 "subtle",
]

[[package]]
name = "curve25519-dalek-derive"
version = "0.1.1"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "f46882e17999c6cc590af592290432be3bce0428cb0d5f8b6715e4dc7b383eb3"
dependencies = [
 "proc-macro2",
 "quote",
 "syn",
]

[[package]]
name = "data-encoding"
version = "2.9.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "2a2330da5de22e8a3cb63252ce2abb30116bf5265e89c0e01bc17015ce30a476"

[[package]]
name = "der"
version = "0.7.10"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "e7c1832837b905bbfb5101e07cc24c8deddf52f93225eee6ead5f4d63d53ddcb"
dependencies = [
 "const-oid",
 "pem-rfc7468",
 "zeroize",
]

[[package]]
name = "deranged"
version = "0.5.4"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "a41953f86f8a05768a6cda24def994fd2f424b04ec5c719cf89989779f199071"
dependencies = [
 "powerfmt",
 "serde_core",

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_.devcontainer.md

**Größe:** 6 KB | **md5:** `0c90ea9498b1d97a6f01a82a01bc856f`

```markdown
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
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_.gewebe_in.md

**Größe:** 652 B | **md5:** `acc362cf044365ef884c377cada0fe93`

```markdown
### 📄 weltgewebe/.gewebe/in/demo.edges.jsonl

**Größe:** 187 B | **md5:** `a392f31657002ee3eec53f74ce4a3203`

```plaintext
{"src":"n1","dst":"n2","rel":"references","why":"Demo-Kante","updated_at":"2024-03-02T09:00:00Z"}
{"src":"n2","dst":"n1","rel":"related","weight":0.6,"updated_at":"2024-03-02T09:05:00Z"}
```

### 📄 weltgewebe/.gewebe/in/demo.nodes.jsonl

**Größe:** 199 B | **md5:** `a383755d092f8a85b35de76c58bd9c1b`

```plaintext
{"id":"n1","type":"doc","title":"Demo Node","tags":["sample"],"source":"semantAH","updated_at":"2024-03-01T10:00:00Z"}
{"id":"n2","type":"term","title":"Begriff","updated_at":"2024-03-02T08:30:00Z"}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_.github_workflows.md

**Größe:** 37 KB | **md5:** `9aa81ba99297946925817378ac514f9a`

```markdown
### 📄 weltgewebe/.github/workflows/api-smoke.yml

**Größe:** 5 KB | **md5:** `330784c355ef87762c6c07d3b1fcf417`

```yaml
name: api-smoke
on:
  pull_request:
    branches: [ main ]
    paths:
      - "apps/api/**"
      - "Cargo.toml"
      - "Cargo.lock"
      - ".github/workflows/api-smoke.yml"
  push:
    branches: [ main ]
    paths:
      - "apps/api/**"
      - "Cargo.toml"
      - "Cargo.lock"
      - ".github/workflows/api-smoke.yml"
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: api-smoke-${{ github.ref }}
  cancel-in-progress: true
jobs:
  ultra_light_health:
    name: API – ultra-light smoke (health endpoints)
    runs-on: ubuntu-latest
    timeout-minutes: 5
    env:
      CARGO_TARGET_DIR: ./target
    defaults:
      run:
        working-directory: apps/api
        shell: bash
    steps:
      - uses: actions/checkout@v4
      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y pkg-config libssl-dev libpq-dev
      - name: Inject build metadata (compile-time env)
        run: |
          echo "GIT_COMMIT_SHA=${GITHUB_SHA}" >> "$GITHUB_ENV"
          echo "BUILD_TIMESTAMP=${{ github.run_started_at }}" >> "$GITHUB_ENV"
      - uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: stable
      - uses: Swatinem/rust-cache@v2
        with:
          workspaces: |
            apps/api -> target
      - name: Build release (fast start)
        run: cargo build --locked --release --bin weltgewebe-api
      - name: Run API in background
        env:
          API_BIND: 127.0.0.1:8787
          RUST_LOG: info
          RUST_BACKTRACE: 1
          APP_CONFIG_PATH: ${{ github.workspace }}/configs/app.defaults.yml
        run: |
          if [ ! -x ./target/release/weltgewebe-api ]; then
            echo "compiled API binary missing"
            ls -al ./target/release || true
            exit 1
          fi
          nohup ./target/release/weltgewebe-api >/tmp/api.log 2>&1 &
          echo $! > /tmp/api.pid
          # Wait up to 5 seconds for the PID file to exist
          for i in {1..10}; do
            [ -f /tmp/api.pid ] && break
            sleep 0.5
          done
          if [ ! -f /tmp/api.pid ]; then
            echo "PID file not found after waiting"
            exit 1
          fi
          if ! kill -0 "$(cat /tmp/api.pid)" 2>/dev/null; then
            echo "API process failed to start"
            exit 1
          fi
      - name: Probe /version (startup)
        run: |
          set -euo pipefail
          body="$(curl --max-time 10 --fail-with-body http://127.0.0.1:8787/version)"
          if ! echo "$body" | jq empty >/dev/null 2>&1; then
            echo "API did not return valid JSON: $body"
            exit 1
          fi
          echo "::group::/version body"
          echo "$body"
          echo "::endgroup::"
          # Validate fields using jq (more robust than grep on strings)
          echo "$body" | jq -e 'type == "object" and has("version") and has("commit") and has("build_timestamp")' >/dev/null

          # Optional: also assert types (string/string/number) – harmless if types differ:
          # echo "$body" | jq -e '(.version|type=="string") and (.commit|type=="string") and (.build_timestamp|type=="number")' >/dev/null
      - name: Wait for API health endpoint
        run: |
          ok=0
          for i in {1..60}; do
            if curl -fsS http://127.0.0.1:8787/health/live; then ok=1; break; fi
            sleep 0.5
          done
          [ "$ok" -eq 1 ] || { echo "health/live not ready in time"; exit 1; }
      - name: Probe /health and /metrics
        run: |
          set -euxo pipefail
          curl -fsS http://127.0.0.1:8787/health/live
          curl -fsS -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8787/health/ready | grep -E '^(200|503)$'
          # /metrics darf 200 liefern, Inhalt ist optional; zeigen die ersten Zeilen, falls vorhanden:
          curl -fsS http://127.0.0.1:8787/metrics | head -n 5 || echo "no /metrics yet (ok)"
      - name: Probe /version (field presence)
        run: |
          set -euo pipefail
          curl -fsS http://127.0.0.1:8787/version | jq -e '.version and .commit and .build_timestamp' >/dev/null
      - name: Stop API
        if: always()
        run: |
          PID_FILE=/tmp/api.pid
          if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
              kill "$PID" 2>/dev/null || true
              wait "$PID" 2>/dev/null || true
            fi
          fi
      - name: Upload API log
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: api-log
          path: /tmp/api.log
```

### 📄 weltgewebe/.github/workflows/api.yml

**Größe:** 3 KB | **md5:** `1f2985143701e991e78c2845149c83db`

```yaml
name: api

on:
  pull_request:
    branches: [main]
    paths:
      - "apps/api/**"
      - "Cargo.toml"
      - "Cargo.lock"
      - "configs/app.defaults.yml"
      - ".github/workflows/api.yml"
  push:
    branches: [main]
    paths:
      - "apps/api/**"
      - "configs/app.defaults.yml"
      - ".github/workflows/api.yml"
  workflow_dispatch: {}

permissions:
  contents: read

env:
  RUST_TOOLCHAIN: stable

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test-and-lint:
    name: test and lint (rust)
    runs-on: ubuntu-latest
    env:
      CARGO_TERM_COLOR: always  # keep cargo output colorized in CI logs
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4

      # Optional: Validates that a default app config is parseable (if present)
      - name: Install PyYAML for config validation
        if: hashFiles('configs/app.defaults.yml') != ''
        run: python3 -m pip install --disable-pip-version-check --no-cache-dir pyyaml

      - name: Validate app.defaults.yml (optional)
        if: hashFiles('configs/app.defaults.yml') != ''
        run: |
          python3 - <<'PY'
          import yaml
          from pathlib import Path

          p = Path("configs/app.defaults.yml")
          yaml.safe_load(p.read_text(encoding="utf-8"))
          print("configs/app.defaults.yml: OK")
          PY

      - name: Install rust toolchain
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: ${{ env.RUST_TOOLCHAIN }}

      - name: Add rust components
        run: rustup component add rustfmt clippy

      - name: Cache cargo
        uses: Swatinem/rust-cache@v2

      # fmt & clippy at repo root: covers all crates/workspaces
      - name: Format check (workspace)
        run: cargo fmt --all -- --check

      - name: Clippy (deny warnings, workspace)
        run: cargo clippy --all-targets --all-features -- -D warnings

      - name: Test (all features, verbose)
        working-directory: apps/api
        run: cargo test --all-features --verbose

  dependency-audit:
    name: dependency audit (on-demand)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    # By default not on every PR/push: only manually or via "security" label
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' && contains(github.event.pull_request.labels.*.name, 'security'))
    steps:
      - uses: actions/checkout@v4
      - name: Install rust toolchain
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: ${{ env.RUST_TOOLCHAIN }}
      - name: Install cargo-audit
        run: cargo install cargo-audit --force
      - name: cargo audit
        run: cargo audit
```

### 📄 weltgewebe/.github/workflows/ci.yml

**Größe:** 3 KB | **md5:** `46b30c8c9c00bc56e6dd66307fbbe1a1`

```yaml
name: CI

permissions:
  contents: read

on:
  push:
    branches: [ main ]
  pull_request:
  workflow_dispatch:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

defaults:
  run:
    shell: bash --noprofile --norc -euo pipefail {0}

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Ensure yq is available
        run: |
          scripts/tools/yq-pin.sh ensure
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"

      - name: Read toolchain versions
        run: |
          test -f toolchain.versions.yml || { echo "toolchain.versions.yml not found"; exit 1; }
          RUST=$(yq -r '.rust' toolchain.versions.yml)
          echo "RUST_VERSION=${RUST}" >> "$GITHUB_ENV"
          PY=$(yq -r '.python' toolchain.versions.yml)
          echo "PYTHON_VERSION=${PY}" >> "$GITHUB_ENV"
          UV=$(yq -r '.uv' toolchain.versions.yml)
          echo "UV_VERSION=${UV}" >> "$GITHUB_ENV"

      - name: Setup Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: ${{ env.RUST_VERSION }}
          components: rustfmt, clippy

      - name: Cache Cargo artifacts
        uses: actions/cache@v4
        with:
          path: |
            ~/.cargo/registry
            ~/.cargo/git
            target
          key: ${{ runner.os }}-cargo-${{ hashFiles('**/Cargo.lock') }}

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20.19.0'
          cache: 'npm'
          cache-dependency-path: |
            package-lock.json
            apps/web/package-lock.json

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Cache uv artifacts
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: ${{ runner.os }}-uv-${{ env.UV_VERSION }}-${{ hashFiles('**/pyproject.toml') }}

      - name: Install uv
        env:
          UV_VERSION: ${{ env.UV_VERSION }}
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          export PATH="$HOME/.local/bin:$PATH"
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"
          echo "$HOME/.cargo/bin" >> "$GITHUB_PATH"
          INSTALLED=$(uv --version | awk '{print $2}')
          if [[ "${INSTALLED}" != "${UV_VERSION}" ]]; then
            echo "Expected uv ${UV_VERSION}, got ${INSTALLED}" >&2
            exit 1
          fi

      - name: Setup Just
        uses: extractions/setup-just@v2

      - name: Show tool versions
        run: |
          rustc --version
          python --version
          uv --version
          just --version

      - name: Validate project
        run: just ci


  lint-docs:
    name: Docs & Shell Hygiene
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Markdownlint
        run: |
          npm install -g markdownlint-cli@0.41.0
          git ls-files '*.md' | xargs -r markdownlint

      - name: ShellCheck
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y shellcheck
          git ls-files '*.sh' | xargs -r shellcheck -x

      - name: Broken-Link Check
        uses: lycheeverse/lychee-action@v2
        with:
          args: --config .lychee.toml .
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 📄 weltgewebe/.github/workflows/compose-smoke.yml

**Größe:** 1 KB | **md5:** `698dbf8c2011a8869ef2b1985b6a157a`

```yaml
name: compose-smoke
permissions:
  contents: read
on:
  workflow_dispatch: {}
  push:
    branches: [main]
    paths:
      - "infra/compose/compose.core.yml"
      - "infra/caddy/Caddyfile"
      - ".github/workflows/compose-smoke.yml"
      - "apps/api/**"
      - "apps/web/**"

jobs:
  smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      - name: Compose up (detached)
        run: docker compose -f infra/compose/compose.core.yml --profile dev up -d --build
      - name: Wait for services (API & Web)
        run: |
          set -euo pipefail
          tries=60
          until curl -fsS http://localhost:8081/ >/dev/null; do
            ((tries--)) || (docker compose -f infra/compose/compose.core.yml --profile dev logs --no-color && exit 1)
            sleep 2
          done
          tries=60
          until curl -fsS http://localhost:8081/api/version >/dev/null || curl -fsS http://localhost:8081/api/health/ready >/dev/null; do
            ((tries--)) || (docker compose -f infra/compose/compose.core.yml --profile dev logs --no-color && exit 1)
            sleep 2
          done
      - name: Show brief logs
        if: always()
        run: docker compose -f infra/compose/compose.core.yml --profile dev logs --no-color --tail=200
      - name: Compose down
        if: always()
        run: docker compose -f infra/compose/compose.core.yml --profile dev down -v
```

### 📄 weltgewebe/.github/workflows/cost-report.yml

**Größe:** 469 B | **md5:** `0f7ac5f72887b57eb1acb8f2b3c0ac2d`

```yaml
name: cost-report
permissions:
  contents: read
  actions: write
on:
  workflow_dispatch:
  schedule:
    - cron: "7 3 1 * *"
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python tools/py/cost/report.py
      - uses: actions/upload-artifact@v4
        with:
          name: cost-report
          path: docs/reports/cost-report.md
```

### 📄 weltgewebe/.github/workflows/docs-style.yml

**Größe:** 3 KB | **md5:** `23da05da88ccf3b3c28476d5cbfffe5e`

```yaml
name: docs-style

on:
  pull_request:
    branches: [ main ]
    paths:
      - "docs/**"
      - ".vale/**"
      - ".vale.ini"
      - ".github/workflows/docs-style.yml"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: docs-style-${{ github.ref }}
  cancel-in-progress: true

jobs:
  vale:
    name: Vale prose lint
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 2

      - name: Install Vale (v3.4.1, checksum verified)
        run: |
          set -euo pipefail
          VALE_VERSION="3.4.1"
          VALE_OS="Linux_64-bit"
          TARBALL="vale_${VALE_VERSION}_${VALE_OS}.tar.gz"
          BASE_URL="https://github.com/errata-ai/vale/releases/download/v${VALE_VERSION}"
          curl -fsSL -o "$TARBALL" "${BASE_URL}/${TARBALL}"
          curl -fsSL -o checksums.txt "${BASE_URL}/vale_${VALE_VERSION}_checksums.txt"
          grep "$TARBALL" checksums.txt | sha256sum -c -
          mkdir -p bin
          tar -xzf "$TARBALL"
          mv vale bin/vale
          rm -f "$TARBALL" checksums.txt
          ./bin/vale --version

      - name: Determine changed docs
        id: changed
        run: |
          set -euo pipefail
          base="${{ github.base_ref || 'main' }}"
          # Ensure base is a remote-tracking branch (origin/branch)
          if [[ "$base" != origin/* ]]; then
            base="origin/$base"
          fi
          if ! git fetch origin "${base#origin/}" --depth=1; then
            echo "Warning: unable to fetch $base; continuing with available history" >&2
          fi
          files=$(git diff --name-only "$base...HEAD" | awk '/^docs\// {print}' || true)
          echo "files<<EOF" >> "$GITHUB_OUTPUT"
          echo "$files" >> "$GITHUB_OUTPUT"
          echo "EOF" >> "$GITHUB_OUTPUT"

      - name: Run Vale (soft; no fail)
        run: |
          set -euo pipefail
          if [ -n "${{ steps.changed.outputs.files }}" ]; then
            if ! ./bin/vale --minAlertLevel=suggestion ${{ steps.changed.outputs.files }}; then
              echo "Vale reported suggestions; continuing without failing the workflow."
            fi
          else
            echo "No changed docs/* files; skipping."
          fi

      - name: Full docs sweep on manual run (optional)
        if: ${{ github.event_name == 'workflow_dispatch' }}
        run: |
          if ! ./bin/vale --minAlertLevel=suggestion docs; then
            echo "Vale reported suggestions during full sweep; continuing without failing the workflow."
          fi
```

### 📄 weltgewebe/.github/workflows/heavy.yml

**Größe:** 2 KB | **md5:** `8f6465dbb55ef4f12c1c5e6d9c5910e0`

```yaml
name: CI (heavy on demand)

on:
  workflow_dispatch: {}
  pull_request:
    types: [labeled, synchronize, reopened, ready_for_review]
    branches: [ main ]

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  gate:
    runs-on: ubuntu-latest
    outputs:
      run_heavy: ${{ steps.flags.outputs.run_heavy }}
    steps:
      - id: flags
        shell: bash
        run: |
          labels="${{ join(github.event.pull_request.labels.*.name, ' ') }}"
          if [[ "${{ github.event_name }}" == "workflow_dispatch" ]]; then
            echo "run_heavy=true" >> "$GITHUB_OUTPUT"
          elif echo "$labels" | grep -qiE '(^| )full-ci( |$)'; then
            echo "run_heavy=true" >> "$GITHUB_OUTPUT"
          else
            echo "run_heavy=false" >> "$GITHUB_OUTPUT"
          fi

  e2e:
    needs: gate
    if: needs.gate.outputs.run_heavy == 'true'
    runs-on: ubuntu-latest
    timeout-minutes: 45
    permissions:
      contents: read
    env:
      CI: true
      HEADLESS: "1"
      NPM_CONFIG_AUDIT: "false"
      NPM_CONFIG_FUND: "false"
    defaults: { run: { working-directory: apps/web, shell: bash } }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '22.x'
          cache: 'npm'
          cache-dependency-path: apps/web/package-lock.json
      - name: Enable Corepack (npm)
        run: corepack enable
      - name: npm ci
        run: npm ci
      - name: Install Playwright browsers
        run: npx playwright install --with-deps
      - name: Build (production)
        run: npm run build
      - name: Run Playwright tests
        run: npm run test
      - name: Upload Playwright report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: apps/web/playwright-report
          if-no-files-found: ignore
```

### 📄 weltgewebe/.github/workflows/infra.yml

**Größe:** 582 B | **md5:** `48e1c97cab00973cdd1a87830a566e48`

```yaml
name: infra
on:
  pull_request:
    branches: [ main ]
    paths:
      - "infra/**"
      - ".github/workflows/infra.yml"
  push:
    branches: [ main ]
    paths:
      - "infra/**"
      - ".github/workflows/infra.yml"
  workflow_dispatch: {}

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
jobs:
  compose-core-smoke:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - name: Core profile is present
        run: test -f infra/compose/compose.core.yml
```

### 📄 weltgewebe/.github/workflows/links.yml

**Größe:** 506 B | **md5:** `502aa30330f0e971d64b4214b2e9875f`

```yaml
name: links
on:
  schedule:
    - cron: "0 4 * * *"
  workflow_dispatch:
    # Link checks on pull requests are handled in the central CI.
permissions:
  contents: read
concurrency:
  group: links-${{ github.ref }}
  cancel-in-progress: true
jobs:
  lychee:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - uses: lycheeverse/lychee-action@v2
        with:
          args: --accept 200,429 --max-redirects 5 --exclude-mail --no-progress "docs/**/*.md"
```

### 📄 weltgewebe/.github/workflows/policies.yml

**Größe:** 706 B | **md5:** `ce35f3bad715804b1c8b17ba3698fd02`

```yaml
name: policies
on:
  pull_request:
  push:
    branches:
      - main
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: policies-${{ github.ref }}
  cancel-in-progress: true
jobs:
  limits-file-and-yaml:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - name: Ensure limits policy exists
        run: test -f policies/limits.yaml
      - name: Lint policies directory with yamllint
        run: |
          python -m pip install --upgrade pip
          python -m pip install yamllint
          if [ -f .yamllint.yml ]; then
            yamllint -c .yamllint.yml policies
          else
            yamllint policies
          fi
```

### 📄 weltgewebe/.github/workflows/policycheck.yml

**Größe:** 425 B | **md5:** `f1f56005cd2cd3dccaef672718434585`

```yaml
name: policycheck
permissions:
  contents: read
on:
  pull_request:
    paths:
      - "policies/**"
      - "tools/py/**"
      - ".github/workflows/policycheck.yml"
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install pyyaml
      - run: python tools/py/policycheck.py
```

### 📄 weltgewebe/.github/workflows/python-tooling.yml

**Größe:** 2 KB | **md5:** `ce4a20bf9ee24a99cd2fea3445b2400f`

```yaml
name: python-tooling

on:
  pull_request:
    branches: [ main ]
    paths:
      - "**/*.py"
      - "**/pyproject.toml"
      - "**/requirements*.txt"
      - "**/uv.lock"
      - ".github/workflows/python-tooling.yml"
  push:
    branches: [ main ]
    paths:
      - "**/*.py"
      - "**/pyproject.toml"
      - "**/requirements*.txt"
      - "**/uv.lock"
      - ".github/workflows/python-tooling.yml"
  workflow_dispatch: {}

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  tooling:
    name: Python tooling checks
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      # Official uv setup (adds `uv` to PATH)
      - uses: astral-sh/setup-uv@v1

      - name: Cache uv downloads
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: uv-${{ runner.os }}-${{ hashFiles('**/pyproject.toml', '**/requirements*.txt', '**/uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-

      - name: Show uv version
        run: uv --version

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_.vale_styles_Weltgewebe.md

**Größe:** 2 KB | **md5:** `e391fe9dbaeed7b38681a6889d283a04`

```markdown
### 📄 weltgewebe/.vale/styles/Weltgewebe/GermanComments.yml

**Größe:** 167 B | **md5:** `649b1c9d66791244009507d8cc6307ba`

```yaml
extends: existence
message: "TODO/FIXME gefunden: Ergänze Kontext oder verlinke ein Ticket."
level: suggestion
ignorecase: true
scope: raw
tokens:
  - TODO
  - FIXME
```

### 📄 weltgewebe/.vale/styles/Weltgewebe/GermanProse.yml

**Größe:** 189 B | **md5:** `4767fb769bf96c61801a9496667b15f9`

```yaml
extends: substitution
level: suggestion
ignorecase: true
message: "Begriff prüfen: '%s' – konsistente Schreibweise wählen."
swap:
  "z.B.": "z. B."
  "bspw.": "z. B."
  "u.a.": "u. a."
```

### 📄 weltgewebe/.vale/styles/Weltgewebe/WeltgewebeStyle.yml

**Größe:** 1 KB | **md5:** `e4ea56a6673b4c7536ea8fdadc31f264`

```yaml
extends: existence
level: warning
scope: text
ignorecase: false
description: "Weltgewebe-Redaktionsstil: neutrale Sprache, konsistente Begriffe und Zahlenschreibweisen."
tokens:
  - pattern: "\\b[\u00C0-\u024F\w]+(?:\\*|:|_)innen\\b"
    message: "Vermeide Gender-Stern/-Gap – wähle eine neutrale Formulierung."
  - pattern: "\\b[\u00C0-\u024F\w]+/[\u00C0-\u024F\w]+innen\\b"
    message: "Vermeide Slash-Genderformen – nutze eine neutrale Bezeichnung."
  - pattern: "\\bRolle[nr]?/(?:und|oder)?Funktion\\b"
    message: "Begriffe nicht vermischen: 'Rolle' und 'Funktion' haben unterschiedliche Bedeutungen."
  - pattern: "\\bFunktion(en)?\\b"
    message: "Prüfe den Begriff: Meinst du die Glossar-'Rolle'? Rolle ≠ Funktion."
  - pattern: "\\bThread(s)?\\b"
    message: "Glossarbegriff verwenden: Statt 'Thread' bitte 'Faden'."
  - pattern: "\\bNode(s)?\\b"
    message: "Glossarbegriff verwenden: Statt 'Node' bitte 'Knoten'."
  - pattern: "\\bYarn\\b"
    message: "Glossarbegriff verwenden: Statt 'Yarn' bitte 'Faden' oder 'Garn'."
  - pattern: "\\bGarn\\b"
    message: "Prüfe den Kontext: 'Faden' ist der Standardbegriff, 'Garn' nur bei Verzwirnung."
  - pattern: "\\bKnotenpunkt\\b"
    message: "Glossarbegriff verwenden: Statt 'Knotenpunkt' bitte 'Knoten'."
  - pattern: "\\b\\d{4,}\\b"
    message: "Zahlenschreibweise prüfen: Tausender trennen (z. B. 10 000) oder Zahl ausschreiben."
  - pattern: "\\b\\d+[kK]\\b"
    message: "Zahl abkürzungen vermeiden: Schreibe z. B. '1 000' statt '1k'."
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_.wgx.md

**Größe:** 3 KB | **md5:** `ac90fd669c31b5614d45370a6a864b8d`

```markdown
### 📄 weltgewebe/.wgx/profile.yml

**Größe:** 3 KB | **md5:** `7dee77ac35f55224a527120cf3af71dc`

```yaml
version: 1
wgx:
  org: heimgewebe
repo:
  # Kurzname des Repos (wird automatisch aus git ableitbar sein – hier nur Doku)
  name: auto
  description: "WGX profile for unified tasks and env priorities"

env_priority:
  # Ordnungsprinzip laut Vorgabe
  - devcontainer
  - devbox
  - mise_direnv
  - termux

tooling:
  python:
    uv: true           # uv ist Standard-Layer für Python-Tools
    precommit: true    # falls .pre-commit-config.yaml vorhanden
  rust:
    cargo: auto        # wenn Cargo.toml vorhanden → Rust-Checks aktivieren
    clippy_strict: true
    fmt_check: true
    deny: optional     # cargo-deny, falls vorhanden

tasks:
  up:
    desc: "Dev-Umgebung hochfahren (Container/venv/tooling bootstrap)"
    sh:
      - |
        if command -v devcontainer >/dev/null 2>&1 || [ -f .devcontainer/devcontainer.json ]; then
          echo "[wgx.up] devcontainer context detected"
        fi
        if command -v uv >/dev/null 2>&1; then
          uv --version || true
          [ -f pyproject.toml ] && uv sync --frozen || true
        fi
        [ -f .pre-commit-config.yaml ] && command -v pre-commit >/dev/null 2>&1 && pre-commit install || true
  lint:
    desc: "Schnelle statische Checks (Rust/Python/Markdown/YAML)"
    sh:
      - |
        # Rust
        if [ -f Cargo.toml ]; then
          cargo fmt --all -- --check
          cargo clippy --all-targets --all-features -- -D warnings
        fi
        # Python
        if [ -f pyproject.toml ]; then
          if command -v uv >/dev/null 2>&1; then uv run ruff check . || true; fi
          if command -v uv >/dev/null 2>&1; then uv run ruff format --check . || true; fi
        fi
        # Docs
        command -v markdownlint >/dev/null 2>&1 && markdownlint "**/*.md" || true
        command -v yamllint    >/dev/null 2>&1 && yamllint . || true
  test:
    desc: "Testsuite"
    sh:
      - |
        [ -f Cargo.toml ] && cargo test --all --all-features || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv run pytest -q || true
        fi
  build:
    desc: "Build-Artefakte erstellen"
    sh:
      - |
        [ -f Cargo.toml ] && cargo build --release || true
        if [ -f pyproject.toml ] && command -v uv >/dev/null 2>&1; then
          uv build || true
        fi
  smoke:
    desc: "Schnelle Smoke-Checks (läuft <60s)"
    sh:
      - |
        echo "[wgx.smoke] repo=$(basename "$(git rev-parse --show-toplevel)")"
        [ -f Cargo.toml ] && cargo metadata --no-deps > /dev/null || true
        [ -f pyproject.toml ] && grep -q '\[project\]' pyproject.toml || true

wgx:
  org: "heimgewebe"

meta:
  owner: "heimgewebe"
  conventions:
    gewebedir: ".gewebe"
    version_endpoint: "/version"
    tasks_standardized: true
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_api.md

**Größe:** 3 KB | **md5:** `6a1ba1d23679ff245421d6b25ae3f518`

```markdown
### 📄 weltgewebe/apps/api/Cargo.toml

**Größe:** 661 B | **md5:** `1e2e74243b53f7ab39631153465f3554`

```toml
[package]
name = "weltgewebe-api"
version = "0.1.0"
edition = "2021"
authors = ["Weltgewebe Team"]
license = "MIT"

[dependencies]
anyhow = "1"
axum = { version = "0.7", features = ["macros"] }
async-nats = "0.35"
dotenvy = "0.15"
prometheus = "0.14.0"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sqlx = { version = "0.8.1", default-features = false, features = ["runtime-tokio", "postgres"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
tower = "0.5"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "fmt"] }
serde_yaml = "0.9"

[dev-dependencies]
serial_test = "3"
tempfile = "3"
```

### 📄 weltgewebe/apps/api/README.md

**Größe:** 2 KB | **md5:** `d4e26f6f719e408fcf849bfbf4c80f82`

```markdown
# Weltgewebe API

The Weltgewebe API is a Rust-based Axum service that powers the platform's backend capabilities.
This README provides a quick orientation for running and developing the service locally.

## Quickstart

1. **Install dependencies**
   - [Rust toolchain](https://www.rust-lang.org/tools/install) (stable)
   - A running PostgreSQL instance (or use `make up` / `just up` for the dev stack)
   - Optional: a running NATS server when developing features that need messaging

2. **Copy the environment template**

   ```bash
   cp ../../.env.example .env
   ```

3. **Adjust the required environment variables** (either in `.env` or the shell).
   Values defined in `.env` take precedence over the defaults from Docker Compose when you use the
   local development stack.
   Recommended settings:
   - `API_BIND` &mdash; socket address to bind the API (default `0.0.0.0:8080`)
   - `DATABASE_URL` &mdash; PostgreSQL connection string (e.g. `postgres://user:password@localhost:5432/weltgewebe`)
   - `NATS_URL` &mdash; URL of the NATS server (e.g. `nats://127.0.0.1:4222`) when messaging is enabled

4. **Run the API**

   ```bash
   cargo run
   ```

   By default the service listens on <http://localhost:8080>.

## Observability

- `GET /health/live` and `GET /health/ready` expose liveness and readiness information.
- `GET /metrics` renders Prometheus metrics including `http_requests_total{method,path}` and `build_info`.

## Development tasks

```bash
# Format the code
cargo fmt -- --check

# Lint
cargo clippy -- -D warnings

# Run tests
cargo test
```

All commands should be executed from the `apps/api` directory unless otherwise noted.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_api_src.md

**Größe:** 10 KB | **md5:** `805dfba21dbcc65042dabf8dceb50df1`

```markdown
### 📄 weltgewebe/apps/api/src/config.rs

**Größe:** 4 KB | **md5:** `ee70ae7586941cbd2747fca6b264117b`

```rust
use std::{env, fs, path::Path};

use anyhow::{Context, Result};
use serde::Deserialize;

macro_rules! apply_env_override {
    ($self:ident, $field:ident, $env_var:literal) => {
        if let Ok(value) = env::var($env_var) {
            $self.$field = value
                .parse()
                .with_context(|| format!("failed to parse {} override: {value}", $env_var))?;
        }
    };
}

#[derive(Debug, Clone, Deserialize, PartialEq)]
pub struct AppConfig {
    pub fade_days: u32,
    pub ron_days: u32,
    pub anonymize_opt_in: bool,
    pub delegation_expire_days: u32,
}

impl AppConfig {
    const DEFAULT_CONFIG: &'static str = include_str!("../../../configs/app.defaults.yml");

    pub fn load() -> Result<Self> {
        match env::var("APP_CONFIG_PATH") {
            Ok(path) => Self::load_from_path(path),
            Err(_) => {
                let config: Self = serde_yaml::from_str(Self::DEFAULT_CONFIG)
                    .context("failed to parse embedded default configuration")?;
                config.apply_env_overrides()
            }
        }
    }

    pub fn load_from_path(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let raw = fs::read_to_string(path)
            .with_context(|| format!("failed to read configuration file at {}", path.display()))?;
        let config: Self = serde_yaml::from_str(&raw)
            .with_context(|| format!("failed to parse configuration file at {}", path.display()))?;
        config.apply_env_overrides()
    }

    fn apply_env_overrides(mut self) -> Result<Self> {
        apply_env_override!(self, fade_days, "HA_FADE_DAYS");
        apply_env_override!(self, ron_days, "HA_RON_DAYS");
        apply_env_override!(self, anonymize_opt_in, "HA_ANONYMIZE_OPT_IN");
        apply_env_override!(self, delegation_expire_days, "HA_DELEGATION_EXPIRE_DAYS");

        Ok(self)
    }
}

#[cfg(test)]
mod tests {
    use super::AppConfig;
    use crate::test_helpers::{DirGuard, EnvGuard};
    use anyhow::Result;
    use serial_test::serial;
    use tempfile::{tempdir, NamedTempFile};

    const YAML: &str = r#"fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
"#;

    #[test]
    #[serial]
    fn load_from_path_reads_defaults() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::unset("HA_FADE_DAYS");
        let _ron = EnvGuard::unset("HA_RON_DAYS");
        let _anonymize = EnvGuard::unset("HA_ANONYMIZE_OPT_IN");
        let _delegation = EnvGuard::unset("HA_DELEGATION_EXPIRE_DAYS");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert_eq!(cfg.fade_days, 7);
        assert_eq!(cfg.ron_days, 84);
        assert!(cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 28);

        Ok(())
    }

    #[test]
    #[serial]
    fn load_from_path_applies_env_overrides() -> Result<()> {
        let file = NamedTempFile::new()?;
        std::fs::write(file.path(), YAML)?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::set("HA_FADE_DAYS", "10");
        let _ron = EnvGuard::set("HA_RON_DAYS", "90");
        let _anonymize = EnvGuard::set("HA_ANONYMIZE_OPT_IN", "false");
        let _delegation = EnvGuard::set("HA_DELEGATION_EXPIRE_DAYS", "14");

        let cfg = AppConfig::load_from_path(file.path())?;
        assert_eq!(cfg.fade_days, 10);
        assert_eq!(cfg.ron_days, 90);
        assert!(!cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 14);

        Ok(())
    }

    #[test]
    #[serial]
    fn load_uses_embedded_defaults_when_config_file_missing() -> Result<()> {
        let temp_dir = tempdir()?;
        let _dir = DirGuard::change_to(temp_dir.path())?;

        let _config_path = EnvGuard::unset("APP_CONFIG_PATH");
        let _fade = EnvGuard::unset("HA_FADE_DAYS");
        let _ron = EnvGuard::unset("HA_RON_DAYS");
        let _anonymize = EnvGuard::unset("HA_ANONYMIZE_OPT_IN");
        let _delegation = EnvGuard::unset("HA_DELEGATION_EXPIRE_DAYS");

        let cfg = AppConfig::load()?;
        assert_eq!(cfg.fade_days, 7);
        assert_eq!(cfg.ron_days, 84);
        assert!(cfg.anonymize_opt_in);
        assert_eq!(cfg.delegation_expire_days, 28);

        Ok(())
    }
}
```

### 📄 weltgewebe/apps/api/src/main.rs

**Größe:** 4 KB | **md5:** `dc30b3c8002563c00cfe2ad07f824889`

```rust
mod config;
mod routes;
mod state;
mod telemetry;

#[cfg(test)]
mod test_helpers;

use std::{env, io::ErrorKind, net::SocketAddr};

use anyhow::{anyhow, Context};
use async_nats::Client as NatsClient;
use axum::{routing::get, Router};
use config::AppConfig;
use routes::health::health_routes;
use routes::meta::meta_routes;
use sqlx::postgres::PgPoolOptions;
use state::ApiState;
use telemetry::{metrics_handler, BuildInfo, Metrics, MetricsLayer};
use tokio::net::TcpListener;
use tracing_subscriber::{fmt, EnvFilter};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let dotenv = dotenvy::dotenv();
    if let Ok(path) = &dotenv {
        tracing::debug!(?path, "loaded environment variables from .env file");
    }

    if let Err(error) = dotenv {
        match &error {
            dotenvy::Error::Io(io_error) if io_error.kind() == ErrorKind::NotFound => {}
            _ => tracing::warn!(%error, "failed to load environment from .env file"),
        }
    }
    init_tracing()?;

    let app_config = AppConfig::load().context("failed to load API configuration")?;
    let (db_pool, db_pool_configured) = initialise_database_pool().await;
    let (nats_client, nats_configured) = initialise_nats_client().await;

    let metrics = Metrics::try_new(BuildInfo::collect())?;
    let state = ApiState {
        db_pool,
        db_pool_configured,
        nats_client,
        nats_configured,
        config: app_config.clone(),
        metrics: metrics.clone(),
    };

    let app = Router::new()
        .merge(health_routes())
        .merge(meta_routes())
        .route("/metrics", get(metrics_handler))
        .layer(MetricsLayer::new(metrics))
        .with_state(state);

    let bind_addr: SocketAddr = env::var("API_BIND")
        .unwrap_or_else(|_| "0.0.0.0:8080".to_string())
        .parse()
        .context("failed to parse API_BIND address")?;

    tracing::info!(%bind_addr, "starting API server");

    let listener = TcpListener::bind(bind_addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

fn init_tracing() -> anyhow::Result<()> {
    if tracing::dispatcher::has_been_set() {
        return Ok(());
    }

    let env_filter = EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info"));
    fmt()
        .with_env_filter(env_filter)
        .try_init()
        .map_err(|error| anyhow!(error))?;

    Ok(())
}

async fn initialise_database_pool() -> (Option<sqlx::PgPool>, bool) {
    let database_url = match env::var("DATABASE_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    let pool = match PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&database_url)
    {
        Ok(pool) => pool,
        Err(error) => {
            tracing::warn!(error = %error, "failed to configure database pool");
            return (None, true);
        }
    };

    match pool.acquire().await {
        Ok(connection) => drop(connection),
        Err(error) => {
            tracing::warn!(
                error = %error,
                "database connection unavailable at startup; readiness will keep retrying",
            );
        }
    }

    (Some(pool), true)
}

async fn initialise_nats_client() -> (Option<NatsClient>, bool) {
    let nats_url = match env::var("NATS_URL") {
        Ok(url) => url,
        Err(_) => return (None, false),
    };

    match async_nats::connect(&nats_url).await {
        Ok(client) => (Some(client), true),
        Err(error) => {
            tracing::warn!(error = %error, "failed to connect to NATS");
            (None, true)
        }
    }
}
```

### 📄 weltgewebe/apps/api/src/state.rs

**Größe:** 615 B | **md5:** `a8b5db0d3a261fbc705eaf927aa0d82a`

```rust
use crate::{config::AppConfig, telemetry::Metrics};
use async_nats::Client as NatsClient;
use sqlx::PgPool;

// ApiState is constructed for future expansion of the API server state. It is
// currently unused by the binary, so we explicitly allow dead code here to keep
// the CI pipeline green while maintaining the transparent intent of the state
// container.
#[allow(dead_code)]
#[derive(Clone)]
pub struct ApiState {
    pub db_pool: Option<PgPool>,
    pub db_pool_configured: bool,
    pub nats_client: Option<NatsClient>,
    pub nats_configured: bool,
    pub config: AppConfig,
    pub metrics: Metrics,
}
```

### 📄 weltgewebe/apps/api/src/test_helpers.rs

**Größe:** 1 KB | **md5:** `d67155af27b660b18cae353260709fdc`

```rust
use std::{
    env,
    path::{Path, PathBuf},
};

pub struct EnvGuard {
    key: &'static str,
    original: Option<String>,
}

impl EnvGuard {
    pub fn set(key: &'static str, value: &str) -> Self {
        let original = env::var(key).ok();
        env::set_var(key, value);
        Self { key, original }
    }

    pub fn unset(key: &'static str) -> Self {
        let original = env::var(key).ok();
        env::remove_var(key);
        Self { key, original }
    }
}

impl Drop for EnvGuard {
    fn drop(&mut self) {
        if let Some(ref val) = self.original {
            env::set_var(self.key, val);
        } else {
            env::remove_var(self.key);
        }
    }
}

pub struct DirGuard {
    original: PathBuf,
}

impl DirGuard {
    pub fn change_to(path: impl AsRef<Path>) -> anyhow::Result<Self> {
        let original = env::current_dir()?;
        env::set_current_dir(path.as_ref())?;
        Ok(Self { original })
    }
}

impl Drop for DirGuard {
    fn drop(&mut self) {
        let _ = env::set_current_dir(&self.original);
    }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_api_src_routes.md

**Größe:** 13 KB | **md5:** `949bf8c180f1e96bef9af4c3c17384f8`

```markdown
### 📄 weltgewebe/apps/api/src/routes/health.rs

**Größe:** 12 KB | **md5:** `0b41ba88dece85a8ee4d84a75b66a1e3`

```rust
use std::{
    env, fs,
    path::{Path, PathBuf},
};

use axum::{
    extract::State,
    http::{header, HeaderValue, StatusCode},
    response::{IntoResponse, Response},
    routing::get,
    Json, Router,
};
use serde_json::{json, Map};
use sqlx::query_scalar;

use crate::{
    state::ApiState,
    telemetry::health::{readiness_check_failed, readiness_checks_succeeded},
};

pub fn health_routes() -> Router<ApiState> {
    Router::new()
        .route("/health/live", get(live))
        .route("/health/ready", get(ready))
}

async fn live() -> Response {
    let body = Json(json!({ "status": "ok" }));
    let mut response = body.into_response();
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

#[derive(Debug, Default)]
struct CheckResult {
    ready: bool,
    errors: Vec<String>,
}

impl CheckResult {
    fn ready() -> Self {
        Self {
            ready: true,
            errors: Vec::new(),
        }
    }

    fn failure(errors: Vec<String>) -> Self {
        Self {
            ready: false,
            errors,
        }
    }

    fn failure_with_message(message: String) -> Self {
        Self::failure(vec![message])
    }
}

fn readiness_verbose() -> bool {
    env::var("READINESS_VERBOSE")
        .map(|value| {
            let trimmed = value.trim();
            trimmed == "1" || trimmed.eq_ignore_ascii_case("true")
        })
        .unwrap_or(false)
}

fn check_policy_file(path: &Path) -> Result<(), String> {
    fs::read_to_string(path).map(|_| ()).map_err(|error| {
        format!(
            "failed to read policy file at {}: {}",
            path.display(),
            error
        )
    })
}

fn check_policy_fallbacks(paths: &[PathBuf]) -> CheckResult {
    let mut errors = Vec::new();
    for path in paths {
        match check_policy_file(path) {
            Ok(()) => return CheckResult::ready(),
            Err(message) => errors.push(message),
        }
    }

    if !errors.is_empty() {
        for error in &errors {
            readiness_check_failed("policy", error);
        }

        let message = format!(
            "no policy file found in fallback locations: {}",
            paths
                .iter()
                .map(|path| path.display().to_string())
                .collect::<Vec<_>>()
                .join(", ")
        );
        readiness_check_failed("policy", &message);
        errors.push(message);
    }

    CheckResult::failure(errors)
}

async fn check_nats(state: &ApiState) -> CheckResult {
    if !state.nats_configured {
        return CheckResult::ready();
    }

    match state.nats_client.as_ref() {
        Some(client) => match client.flush().await {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("nats", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "client not initialised".to_string();
            readiness_check_failed("nats", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

async fn check_database(state: &ApiState) -> CheckResult {
    if !state.db_pool_configured {
        return CheckResult::ready();
    }

    match state.db_pool.as_ref() {
        Some(pool) => match query_scalar::<_, i32>("SELECT 1")
            .fetch_optional(pool)
            .await
        {
            Ok(_) => CheckResult::ready(),
            Err(error) => {
                let message = error.to_string();
                readiness_check_failed("database", &message);
                CheckResult::failure_with_message(message)
            }
        },
        None => {
            let message = "connection pool not initialised".to_string();
            readiness_check_failed("database", &message);
            CheckResult::failure_with_message(message)
        }
    }
}

fn check_policy() -> CheckResult {
    // Prefer an explicit configuration via env var to avoid hard-coded path assumptions.
    // Fallbacks stay for dev/CI convenience.
    let env_path = env::var_os("POLICY_LIMITS_PATH").map(PathBuf::from);
    let fallback_paths = [
        Path::new("policies/limits.yaml").to_path_buf(),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../policies/limits.yaml"),
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../policies/limits.yaml"),
    ];

    if let Some(path) = env_path {
        match check_policy_file(&path) {
            Ok(()) => CheckResult::ready(),
            Err(message) => {
                readiness_check_failed("policy", &message);
                CheckResult::failure_with_message(message)
            }
        }
    } else {
        check_policy_fallbacks(&fallback_paths)
    }
}

async fn ready(State(state): State<ApiState>) -> Response {
    let nats = check_nats(&state).await;
    let database = check_database(&state).await;
    let policy = check_policy();

    let status = if database.ready && nats.ready && policy.ready {
        StatusCode::OK
    } else {
        StatusCode::SERVICE_UNAVAILABLE
    };

    if status == StatusCode::OK {
        readiness_checks_succeeded();
    }

    let verbose = readiness_verbose();

    let body = Json(json!({
        "status": if status == StatusCode::OK { "ok" } else { "error" },
        "checks": {
            "database": database.ready,
            "nats": nats.ready,
            "policy": policy.ready,
        }
    }));

    let mut value = body.0;

    if verbose {
        let mut errors = Map::new();

        if !database.errors.is_empty() {
            errors.insert("database".to_string(), json!(database.errors));
        }

        if !nats.errors.is_empty() {
            errors.insert("nats".to_string(), json!(nats.errors));
        }

        if !policy.errors.is_empty() {
            errors.insert("policy".to_string(), json!(policy.errors));
        }

        if !errors.is_empty() {
            if let Some(object) = value.as_object_mut() {
                object.insert("errors".to_string(), json!(errors));
            }
        }
    }

    let mut response = Json(value).into_response();
    *response.status_mut() = status;
    response
        .headers_mut()
        .insert(header::CACHE_CONTROL, HeaderValue::from_static("no-store"));
    response
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{
        config::AppConfig,
        telemetry::{BuildInfo, Metrics},
        test_helpers::EnvGuard,
    };
    use anyhow::Result;
    use axum::{body, extract::State, http::header};
    use serde_json::Value;
    use serial_test::serial;

    fn test_state() -> Result<ApiState> {
        let metrics = Metrics::try_new(BuildInfo {
            version: "test",
            commit: "test",
            build_timestamp: "test",
        })?;

        Ok(ApiState {
            db_pool: None,
            db_pool_configured: false,
            nats_client: None,
            nats_configured: false,
            config: AppConfig {
                fade_days: 7,
                ron_days: 84,
                anonymize_opt_in: true,
                delegation_expire_days: 28,
            },
            metrics,
        })
    }

    #[tokio::test]
    #[serial]
    async fn live_returns_ok_status_and_no_store_header() -> Result<()> {
        let response = live().await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_succeeds_when_optional_dependencies_are_disabled() -> Result<()> {
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::OK);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "ok");
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_policy_path_is_invalid() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let cache_control = response.headers().get(header::CACHE_CONTROL).cloned();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(
            cache_control.as_ref().and_then(|value| value.to_str().ok()),
            Some("no-store")
        );
        assert_eq!(body["status"], "error");
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], false);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_database_pool_missing() -> Result<()> {
        let mut state = test_state()?;
        state.db_pool_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], false);
        assert_eq!(body["checks"]["nats"], true);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_fails_when_nats_client_missing() -> Result<()> {
        let mut state = test_state()?;
        state.nats_configured = true;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["database"], true);
        assert_eq!(body["checks"]["nats"], false);
        assert_eq!(body["checks"]["policy"], true);

        Ok(())
    }

    #[tokio::test]
    #[serial]
    async fn readiness_includes_error_details_when_verbose_enabled() -> Result<()> {
        let _policy = EnvGuard::set("POLICY_LIMITS_PATH", "/does/not/exist");
        let _verbose = EnvGuard::set("READINESS_VERBOSE", "1");
        let state = test_state()?;

        let response = ready(State(state)).await;
        let status = response.status();
        let body_bytes = body::to_bytes(response.into_body(), usize::MAX).await?;
        let body: Value = serde_json::from_slice(&body_bytes)?;

        assert_eq!(status, StatusCode::SERVICE_UNAVAILABLE);
        assert_eq!(body["checks"]["policy"], false);

        let errors = body["errors"]["policy"].as_array().expect("policy errors");
        assert!(!errors.is_empty());
        assert!(errors
            .iter()
            .filter_map(|value| value.as_str())
            .any(|message| message.contains("failed to read policy file")));

        Ok(())
    }
}
```

### 📄 weltgewebe/apps/api/src/routes/meta.rs

**Größe:** 443 B | **md5:** `d2117861c4720327645ebeaef03f827e`

```rust
use axum::{routing::get, Json, Router};
use serde_json::{json, Value};

use crate::state::ApiState;
use crate::telemetry::BuildInfo;

pub fn meta_routes() -> Router<ApiState> {
    Router::new().route("/version", get(version))
}

async fn version() -> Json<Value> {
    let info = BuildInfo::collect();
    Json(json!({
        "version": info.version,
        "commit": info.commit,
        "build_timestamp": info.build_timestamp,
    }))
}
```

### 📄 weltgewebe/apps/api/src/routes/mod.rs

**Größe:** 30 B | **md5:** `f941dc892dbc498b8ad9b3365a37310b`

```rust
pub mod health;
pub mod meta;
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_api_src_telemetry.md

**Größe:** 5 KB | **md5:** `637cd0e425393b36a144895318815267`

```markdown
### 📄 weltgewebe/apps/api/src/telemetry/health.rs

**Größe:** 279 B | **md5:** `aef976111f6a7ff08c5d92636375a2a2`

```rust
use std::fmt;

pub fn readiness_check_failed(component: &str, error: &(impl fmt::Display + ?Sized)) {
    tracing::warn!(error = %error, %component, "{component} health check failed");
}

pub fn readiness_checks_succeeded() {
    tracing::info!("all readiness checks passed");
}
```

### 📄 weltgewebe/apps/api/src/telemetry/mod.rs

**Größe:** 5 KB | **md5:** `3af4a1952918d4b0ea3350147df2b1bf`

```rust
use std::{
    future::Future,
    pin::Pin,
    sync::Arc,
    task::{Context, Poll},
};

pub mod health;

use axum::{
    extract::{MatchedPath, State},
    http::{header, HeaderValue, Request, StatusCode},
    response::{IntoResponse, Response},
};
use prometheus::{Encoder, IntCounterVec, IntGaugeVec, Opts, Registry, TextEncoder};
use tower::{Layer, Service};

use crate::state::ApiState;

#[derive(Clone, Debug)]
pub struct BuildInfo {
    pub version: &'static str,
    pub commit: &'static str,
    pub build_timestamp: &'static str,
}

impl BuildInfo {
    pub fn collect() -> Self {
        Self {
            version: env!("CARGO_PKG_VERSION"),
            commit: option_env!("GIT_COMMIT_SHA").unwrap_or("unknown"),
            build_timestamp: option_env!("BUILD_TIMESTAMP").unwrap_or("unknown"),
        }
    }
}

#[derive(Clone)]
pub struct Metrics {
    inner: Arc<MetricsInner>,
}

struct MetricsInner {
    registry: Registry,
    pub http_requests_total: IntCounterVec,
}

impl Metrics {
    pub fn try_new(build_info: BuildInfo) -> Result<Self, prometheus::Error> {
        let http_opts = Opts::new("http_requests_total", "Total number of HTTP requests");
        let http_requests_total = IntCounterVec::new(http_opts, &["method", "path", "status"])?;

        let build_opts = Opts::new("build_info", "Build information for the API");
        let build_info_metric =
            IntGaugeVec::new(build_opts, &["version", "commit", "build_timestamp"])?;

        let registry = Registry::new();
        registry.register(Box::new(http_requests_total.clone()))?;
        registry.register(Box::new(build_info_metric.clone()))?;

        build_info_metric
            .with_label_values(&[
                build_info.version,
                build_info.commit,
                build_info.build_timestamp,
            ])
            .set(1);

        Ok(Self {
            inner: Arc::new(MetricsInner {
                registry,
                http_requests_total,
            }),
        })
    }

    pub fn http_requests_total(&self) -> &IntCounterVec {
        &self.inner.http_requests_total
    }

    pub fn render(&self) -> Result<Vec<u8>, prometheus::Error> {
        let metric_families = self.inner.registry.gather();
        let encoder = TextEncoder::new();
        let mut buffer = Vec::new();
        encoder.encode(&metric_families, &mut buffer)?;
        Ok(buffer)
    }
}

pub async fn metrics_handler(State(state): State<ApiState>) -> impl IntoResponse {
    let content_type = HeaderValue::from_static("text/plain; version=0.0.4; charset=utf-8");
    match state.metrics.render() {
        Ok(body) => (StatusCode::OK, [(header::CONTENT_TYPE, content_type)], body).into_response(),
        Err(error) => {
            tracing::error!(error = %error, "failed to encode metrics");
            StatusCode::INTERNAL_SERVER_ERROR.into_response()
        }
    }
}

#[derive(Clone)]
pub struct MetricsLayer {
    metrics: Metrics,
}

impl MetricsLayer {
    pub fn new(metrics: Metrics) -> Self {
        Self { metrics }
    }
}

impl<S> Layer<S> for MetricsLayer {
    type Service = MetricsService<S>;

    fn layer(&self, inner: S) -> Self::Service {
        MetricsService {
            inner,
            metrics: self.metrics.clone(),
        }
    }
}

#[derive(Clone)]
pub struct MetricsService<S> {
    inner: S,
    metrics: Metrics,
}

impl<S, B> Service<Request<B>> for MetricsService<S>
where
    S: Service<Request<B>>,
    S::Future: Send + 'static,
    S::Response: IntoResponse,
    B: Send + 'static,
{
    type Response = Response;
    type Error = S::Error;
    type Future = Pin<Box<dyn Future<Output = Result<Self::Response, Self::Error>> + Send>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        self.inner.poll_ready(cx)
    }

    fn call(&mut self, request: Request<B>) -> Self::Future {
        let method = request.method().as_str().to_owned();
        let matched_path = request
            .extensions()
            .get::<MatchedPath>()
            .map(|p| p.as_str().to_owned());
        let path = matched_path.unwrap_or_else(|| request.uri().path().to_owned());
        let metrics = self.metrics.clone();
        let future = self.inner.call(request);

        Box::pin(async move {
            match future.await {
                Ok(response) => {
                    let response: Response = response.into_response();
                    let status = response.status().as_u16().to_string();
                    metrics
                        .http_requests_total()
                        .with_label_values(&[method.as_str(), path.as_str(), status.as_str()])
                        .inc();
                    Ok(response)
                }
                Err(error) => Err(error),
            }
        })
    }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_api_tests.md

**Größe:** 523 B | **md5:** `926b25e6d9ac090f67ac22867d0448f9`

```markdown
### 📄 weltgewebe/apps/api/tests/smoke_k6.js

**Größe:** 390 B | **md5:** `41514ea7ab2202df978f99fce53e76dd`

```javascript
import http from 'k6/http';
import { check } from 'k6';

export const options = { vus: 1, iterations: 3 };

export default function () {
  const res1 = http.get(`${__ENV.BASE_URL}/health/live`);
  check(res1, { 'live 200': r => r.status === 200 });

  const res2 = http.get(`${__ENV.BASE_URL}/health/ready`);
  check(res2, { 'ready 2xx/5xx': r => r.status === 200 || r.status === 503 });
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web.md

**Größe:** 33 KB | **md5:** `682a29d3a770463ecdf1e30cfef56c2e`

```markdown
### 📄 weltgewebe/apps/web/.gitignore

**Größe:** 154 B | **md5:** `54f7490e482e03a6a348adfd9aa787f6`

```plaintext
node_modules
.svelte-kit
build
.DS_Store
public/demo.png
.env
.env.local

# Playwright artifacts
playwright-report/
test-results/
blob-report/
trace.zip
```

### 📄 weltgewebe/apps/web/.npmrc

**Größe:** 19 B | **md5:** `e780ac33d3d13827a73886735c3a368b`

```plaintext
engine-strict=true
```

### 📄 weltgewebe/apps/web/README.md

**Größe:** 2 KB | **md5:** `3c3b18af589bba248f7f848f79e7776b`

```markdown
# weltgewebe-web (Gate A Click-Dummy)

Frontend-only Prototyp zur Diskussion von UX und Vokabular (Karte, Knoten, Fäden, Drawer, Zeitachse).

## Dev

```bash
cd apps/web
npm ci
npm run dev
```

Standardmäßig läuft der Dev-Server auf `http://localhost:5173/map`.
In Container- oder Codespaces-Umgebungen kannst du optional `npm run dev -- --host --port 5173`
verwenden.

> [!NOTE]
> **Node-Version:** Bitte Node.js ≥ 20.19 (oder ≥ 22.12) verwenden – darunter verweigern Vite und Freunde den Dienst.

### Polyfill-Debugging

Für ältere Safari-/iPadOS-Versionen wird automatisch ein `inert`-Polyfill aktiviert.
Falls du das native Verhalten prüfen möchtest, hänge `?noinert=1` an die URL
(oder setze `window.__NO_INERT__ = true` im DevTools-Console).

### Screenshot aufnehmen

In einem zweiten Terminal (während `npm run dev` läuft):

```bash
npm run screenshot
```

Legt `public/demo.png` an.

## Was kann das?

- Vollbild-Karte (MapLibre) mit 4 Strukturknoten (Platzhalter).
- Linker/rechter Drawer (UI-Stubs), Legende, Zeitachsen-Stub im Footer.
- Keine Persistenz, keine echten Filter/Abfragen (Ethik → UX → Gemeinschaft → Zukunft → Autonomie → Kosten).

## Nächste Schritte

- A-2: Klick auf Marker öffnet Panel mit „Was passiert hier später?“
- A-3: Dummy-Datenlayer (JSON) für 2–3 Knotentypen, 2 Fadenfarben
- A-4: Accessibility-Pass 1 (Fokus, Kontrast)
- A-5: Dev-Overlay: Bundle-Größe (Budget ≤ ~90KB Initial-JS)

## Tests

### Playwright (Drawer + Keyboard)

```bash
npx playwright install --with-deps  # einmalig
npx playwright test tests/drawers.spec.ts
```

Die Tests setzen in `beforeEach` das Flag `window.__E2E__ = true`, damit Maus-Drags die Swipe-Gesten simulieren können.
```

### 📄 weltgewebe/apps/web/eslint.config.js

**Größe:** 964 B | **md5:** `07731461ec97002acab7a87a553106af`

```javascript
import js from "@eslint/js";
import globals from "globals";
import svelte from "eslint-plugin-svelte";
import tsParser from "@typescript-eslint/parser";
import tsPlugin from "@typescript-eslint/eslint-plugin";

const IGNORE = [
  ".svelte-kit/",
  "build/",
  "dist/",
  "node_modules/",
  "public/demo.png",
  "scripts/record-screenshot.mjs"
];

export default [
  {
    ignores: IGNORE
  },
  ...svelte.configs["flat/recommended"],
  {
    files: ["**/*.svelte"],
    rules: {
      "svelte/no-at-html-tags": "error"
    }
  },
  {
    files: ["**/*.ts", "**/*.js"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2023,
        sourceType: "module"
      },
      globals: globals.browser
    },
    plugins: {
      "@typescript-eslint": tsPlugin
    },
    rules: {
      ...js.configs.recommended.rules,
      ...tsPlugin.configs["recommended"].rules,
      "@typescript-eslint/no-explicit-any": "off"
    }
  }
];
```

### 📄 weltgewebe/apps/web/package-lock.json

**Größe:** 63 KB | **md5:** `d306b5235616f5e9d79048e2ae6fbadc`

```json
{
  "name": "weltgewebe-web",
  "version": "0.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "weltgewebe-web",
      "version": "0.0.0",
      "hasInstallScript": true,
      "dependencies": {
        "maplibre-gl": "4.7.1"
      },
      "devDependencies": {
        "@playwright/test": "1.55.1",
        "@sveltejs/adapter-auto": "6.1.0",
        "@sveltejs/kit": "^2.47.2",
        "@typescript-eslint/eslint-plugin": "8.8.0",
        "@typescript-eslint/parser": "8.8.0",
        "eslint": "9.11.1",
        "eslint-plugin-svelte": "2.45.1",
        "globals": "15.9.0",
        "playwright": "1.55.1",
        "prettier": "3.3.3",
        "prettier-plugin-svelte": "3.2.6",
        "svelte": "5.39.6",
        "svelte-check": "^4.3.2",
        "typescript": "5.9.2",
        "vite": "^7.1.11"
      },
      "engines": {
        "node": ">=20.19.0"
      }
    },
    "node_modules/@esbuild/aix-ppc64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/aix-ppc64/-/aix-ppc64-0.25.10.tgz",
      "integrity": "sha512-0NFWnA+7l41irNuaSVlLfgNT12caWJVLzp5eAVhZ0z1qpxbockccEt3s+149rE64VUI3Ml2zt8Nv5JVc4QXTsw==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "aix"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm/-/android-arm-0.25.10.tgz",
      "integrity": "sha512-dQAxF1dW1C3zpeCDc5KqIYuZ1tgAdRXNoZP7vkBIRtKZPYe2xVr/d3SkirklCHudW1B45tGiUlz2pUWDfbDD4w==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-arm64/-/android-arm64-0.25.10.tgz",
      "integrity": "sha512-LSQa7eDahypv/VO6WKohZGPSJDq5OVOo3UoFR1E4t4Gj1W7zEQMUhI+lo81H+DtB+kP+tDgBp+M4oNCwp6kffg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/android-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/android-x64/-/android-x64-0.25.10.tgz",
      "integrity": "sha512-MiC9CWdPrfhibcXwr39p9ha1x0lZJ9KaVfvzA0Wxwz9ETX4v5CHfF09bx935nHlhi+MxhA63dKRRQLiVgSUtEg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-arm64/-/darwin-arm64-0.25.10.tgz",
      "integrity": "sha512-JC74bdXcQEpW9KkV326WpZZjLguSZ3DfS8wrrvPMHgQOIEIG/sPXEN/V8IssoJhbefLRcRqw6RQH2NnpdprtMA==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/darwin-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/darwin-x64/-/darwin-x64-0.25.10.tgz",
      "integrity": "sha512-tguWg1olF6DGqzws97pKZ8G2L7Ig1vjDmGTwcTuYHbuU6TTjJe5FXbgs5C1BBzHbJ2bo1m3WkQDbWO2PvamRcg==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-arm64/-/freebsd-arm64-0.25.10.tgz",
      "integrity": "sha512-3ZioSQSg1HT2N05YxeJWYR+Libe3bREVSdWhEEgExWaDtyFbbXWb49QgPvFH8u03vUPX10JhJPcz7s9t9+boWg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/freebsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/freebsd-x64/-/freebsd-x64-0.25.10.tgz",
      "integrity": "sha512-LLgJfHJk014Aa4anGDbh8bmI5Lk+QidDmGzuC2D+vP7mv/GeSN+H39zOf7pN5N8p059FcOfs2bVlrRr4SK9WxA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm/-/linux-arm-0.25.10.tgz",
      "integrity": "sha512-oR31GtBTFYCqEBALI9r6WxoU/ZofZl962pouZRTEYECvNF/dtXKku8YXcJkhgK/beU+zedXfIzHijSRapJY3vg==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-arm64/-/linux-arm64-0.25.10.tgz",
      "integrity": "sha512-5luJWN6YKBsawd5f9i4+c+geYiVEw20FVW5x0v1kEMWNq8UctFjDiMATBxLvmmHA4bf7F6hTRaJgtghFr9iziQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ia32": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ia32/-/linux-ia32-0.25.10.tgz",
      "integrity": "sha512-NrSCx2Kim3EnnWgS4Txn0QGt0Xipoumb6z6sUtl5bOEZIVKhzfyp/Lyw4C1DIYvzeW/5mWYPBFJU3a/8Yr75DQ==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-loong64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-loong64/-/linux-loong64-0.25.10.tgz",
      "integrity": "sha512-xoSphrd4AZda8+rUDDfD9J6FUMjrkTz8itpTITM4/xgerAZZcFW7Dv+sun7333IfKxGG8gAq+3NbfEMJfiY+Eg==",
      "cpu": [
        "loong64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-mips64el": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-mips64el/-/linux-mips64el-0.25.10.tgz",
      "integrity": "sha512-ab6eiuCwoMmYDyTnyptoKkVS3k8fy/1Uvq7Dj5czXI6DF2GqD2ToInBI0SHOp5/X1BdZ26RKc5+qjQNGRBelRA==",
      "cpu": [
        "mips64el"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-ppc64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-ppc64/-/linux-ppc64-0.25.10.tgz",
      "integrity": "sha512-NLinzzOgZQsGpsTkEbdJTCanwA5/wozN9dSgEl12haXJBzMTpssebuXR42bthOF3z7zXFWH1AmvWunUCkBE4EA==",
      "cpu": [
        "ppc64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-riscv64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-riscv64/-/linux-riscv64-0.25.10.tgz",
      "integrity": "sha512-FE557XdZDrtX8NMIeA8LBJX3dC2M8VGXwfrQWU7LB5SLOajfJIxmSdyL/gU1m64Zs9CBKvm4UAuBp5aJ8OgnrA==",
      "cpu": [
        "riscv64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-s390x": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-s390x/-/linux-s390x-0.25.10.tgz",
      "integrity": "sha512-3BBSbgzuB9ajLoVZk0mGu+EHlBwkusRmeNYdqmznmMc9zGASFjSsxgkNsqmXugpPk00gJ0JNKh/97nxmjctdew==",
      "cpu": [
        "s390x"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/linux-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/linux-x64/-/linux-x64-0.25.10.tgz",
      "integrity": "sha512-QSX81KhFoZGwenVyPoberggdW1nrQZSvfVDAIUXr3WqLRZGZqWk/P4T8p2SP+de2Sr5HPcvjhcJzEiulKgnxtA==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "linux"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-arm64/-/netbsd-arm64-0.25.10.tgz",
      "integrity": "sha512-AKQM3gfYfSW8XRk8DdMCzaLUFB15dTrZfnX8WXQoOUpUBQ+NaAFCP1kPS/ykbbGYz7rxn0WS48/81l9hFl3u4A==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/netbsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/netbsd-x64/-/netbsd-x64-0.25.10.tgz",
      "integrity": "sha512-7RTytDPGU6fek/hWuN9qQpeGPBZFfB4zZgcz2VK2Z5VpdUxEI8JKYsg3JfO0n/Z1E/6l05n0unDCNc4HnhQGig==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "netbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-arm64/-/openbsd-arm64-0.25.10.tgz",
      "integrity": "sha512-5Se0VM9Wtq797YFn+dLimf2Zx6McttsH2olUBsDml+lm0GOCRVebRWUvDtkY4BWYv/3NgzS8b/UM3jQNh5hYyw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openbsd-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openbsd-x64/-/openbsd-x64-0.25.10.tgz",
      "integrity": "sha512-XkA4frq1TLj4bEMB+2HnI0+4RnjbuGZfet2gs/LNs5Hc7D89ZQBHQ0gL2ND6Lzu1+QVkjp3x1gIcPKzRNP8bXw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openbsd"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/openharmony-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/openharmony-arm64/-/openharmony-arm64-0.25.10.tgz",
      "integrity": "sha512-AVTSBhTX8Y/Fz6OmIVBip9tJzZEUcY8WLh7I59+upa5/GPhh2/aM6bvOMQySspnCCHvFi79kMtdJS1w0DXAeag==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "openharmony"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/sunos-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/sunos-x64/-/sunos-x64-0.25.10.tgz",
      "integrity": "sha512-fswk3XT0Uf2pGJmOpDB7yknqhVkJQkAQOcW/ccVOtfx05LkbWOaRAtn5SaqXypeKQra1QaEa841PgrSL9ubSPQ==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "sunos"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-arm64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-arm64/-/win32-arm64-0.25.10.tgz",
      "integrity": "sha512-ah+9b59KDTSfpaCg6VdJoOQvKjI33nTaQr4UluQwW7aEwZQsbMCfTmfEO4VyewOxx4RaDT/xCy9ra2GPWmO7Kw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-ia32": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-ia32/-/win32-ia32-0.25.10.tgz",
      "integrity": "sha512-QHPDbKkrGO8/cz9LKVnJU22HOi4pxZnZhhA2HYHez5Pz4JeffhDjf85E57Oyco163GnzNCVkZK0b/n4Y0UHcSw==",
      "cpu": [
        "ia32"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@esbuild/win32-x64": {
      "version": "0.25.10",
      "resolved": "https://registry.npmjs.org/@esbuild/win32-x64/-/win32-x64-0.25.10.tgz",
      "integrity": "sha512-9KpxSVFCu0iK1owoez6aC/s/EdUQLDN3adTxGCqxMVhrPDj6bt5dbrHDXUuq+Bs2vATFBBrQS5vdQ/Ed2P+nbw==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "win32"
      ],
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@jridgewell/gen-mapping": {
      "version": "0.3.13",
      "resolved": "https://registry.npmjs.org/@jridgewell/gen-mapping/-/gen-mapping-0.3.13.tgz",
      "integrity": "sha512-2kkt/7niJ6MgEPxF0bYdQ6etZaA+fQvDcLKckhy1yIQOzaoKjBBjSj63/aLVjYE3qhRt5dvM+uUyfCg6UKCBbA==",
      "dev": true,
      "dependencies": {
        "@jridgewell/sourcemap-codec": "1.5.5",
        "@jridgewell/trace-mapping": "0.3.31"
      }
    },
    "node_modules/@jridgewell/remapping": {
      "version": "2.3.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/remapping/-/remapping-2.3.5.tgz",
      "integrity": "sha512-LI9u/+laYG4Ds1TDKSJW2YPrIlcVYOwi2fUC6xB43lueCjgxV4lffOCZCtYFiH6TNOX+tQKXx97T4IKHbhyHEQ==",
      "dev": true,
      "dependencies": {
        "@jridgewell/gen-mapping": "0.3.13",
        "@jridgewell/trace-mapping": "0.3.31"
      }
    },
    "node_modules/@jridgewell/resolve-uri": {
      "version": "3.1.2",
      "resolved": "https://registry.npmjs.org/@jridgewell/resolve-uri/-/resolve-uri-3.1.2.tgz",
      "integrity": "sha512-bRISgCIjP20/tbWSPWMEi54QVPRZExkuD9lJL+UIxUKtwVJA8wW1Trb1jMs1RFXo1CBTNZ/5hpC9QvmKWdopKw==",
      "dev": true,
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@jridgewell/sourcemap-codec": {
      "version": "1.5.5",
      "resolved": "https://registry.npmjs.org/@jridgewell/sourcemap-codec/-/sourcemap-codec-1.5.5.tgz",
      "integrity": "sha512-cYQ9310grqxueWbl+WuIUIaiUaDcj7WOq5fVhEljNVgRfOUhY9fy2zTvfoqWsnebh8Sl70VScFbICvJnLKB0Og==",
      "dev": true
    },
    "node_modules/@jridgewell/trace-mapping": {
      "version": "0.3.31",
      "resolved": "https://registry.npmjs.org/@jridgewell/trace-mapping/-/trace-mapping-0.3.31.tgz",
      "integrity": "sha512-zzNR+SdQSDJzc8joaeP8QQoCQr8NuYx2dIIytl1QeBEZHJ9uW6hebsrYgbz8hJwUQao3TWCMtmfV8Nu1twOLAw==",
      "dev": true,
      "dependencies": {
        "@jridgewell/resolve-uri": "3.1.2",
        "@jridgewell/sourcemap-codec": "1.5.5"
      }
    },
    "node_modules/@mapbox/geojson-rewind": {
      "version": "0.5.2",
      "resolved": "https://registry.npmjs.org/@mapbox/geojson-rewind/-/geojson-rewind-0.5.2.tgz",
      "integrity": "sha512-tJaT+RbYGJYStt7wI3cq4Nl4SXxG8W7JDG5DMJu97V25RnbNg3QtQtf+KD+VLjNpWKYsRvXDNmNrBgEETr1ifA==",
      "dependencies": {
        "get-stream": "6.0.1",
        "minimist": "1.2.8"
      }
    },
    "node_modules/@mapbox/jsonlint-lines-primitives": {
      "version": "2.0.2",
      "resolved": "https://registry.npmjs.org/@mapbox/jsonlint-lines-primitives/-/jsonlint-lines-primitives-2.0.2.tgz",
      "integrity": "sha512-rY0o9A5ECsTQRVhv7tL/OyDpGAoUB4tTvLiW1DSzQGq4bvTPhNw1VpSNjDJc5GFZ2XuyOtSWSVN05qOtcD71qQ==",
      "engines": {
        "node": ">= 0.6"
      }
    },
    "node_modules/@mapbox/point-geometry": {
      "version": "0.1.0",
      "resolved": "https://registry.npmjs.org/@mapbox/point-geometry/-/point-geometry-0.1.0.tgz",
      "integrity": "sha512-6j56HdLTwWGO0fJPlrZtdU/B13q8Uwmo18Ck2GnGgN9PCFyKTZ3UbXeEdRFh18i9XQ92eH2VdtpJHpBD3aripQ=="
    },
    "node_modules/@mapbox/tiny-sdf": {
      "version": "2.0.7",
      "resolved": "https://registry.npmjs.org/@mapbox/tiny-sdf/-/tiny-sdf-2.0.7.tgz",
      "integrity": "sha512-25gQLQMcpivjOSA40g3gO6qgiFPDpWRoMfd+G/GoppPIeP6JDaMMkMrEJnMZhKyyS6iKwVt5YKu02vCUyJM3Ug=="
    },
    "node_modules/@mapbox/unitbezier": {
      "version": "0.0.1",
      "resolved": "https://registry.npmjs.org/@mapbox/unitbezier/-/unitbezier-0.0.1.tgz",
      "integrity": "sha512-nMkuDXFv60aBr9soUG5q+GvZYL+2KZHVvsqFCzqnkGEf46U2fvmytHaEVc1/YZbiLn8X+eR3QzX1+dwDO1lxlw=="
    },
    "node_modules/@mapbox/vector-tile": {
      "version": "1.3.1",
      "resolved": "https://registry.npmjs.org/@mapbox/vector-tile/-/vector-tile-1.3.1.tgz",
      "integrity": "sha512-MCEddb8u44/xfQ3oD+Srl/tNcQoqTw3goGk2oLsrFxOTc3dUp+kAnby3PvAeeBYSMSjSPD1nd1AJA6W49WnoUw==",
      "dependencies": {
        "@mapbox/point-geometry": "0.1.0"
      }
    },
    "node_modules/@mapbox/whoots-js": {
      "version": "3.1.0",
      "resolved": "https://registry.npmjs.org/@mapbox/whoots-js/-/whoots-js-3.1.0.tgz",
      "integrity": "sha512-Es6WcD0nO5l+2BOQS4uLfNPYQaNDfbot3X1XUoloz+x0mPDS3eeORZJl06HXjwBG1fOGwCRnzK88LMdxKRrd6Q==",
      "engines": {
        "node": ">=6.0.0"
      }
    },
    "node_modules/@maplibre/maplibre-gl-style-spec": {
      "version": "20.4.0",
      "resolved": "https://registry.npmjs.org/@maplibre/maplibre-gl-style-spec/-/maplibre-gl-style-spec-20.4.0.tgz",
      "integrity": "sha512-AzBy3095fTFPjDjmWpR2w6HVRAZJ6hQZUCwk5Plz6EyfnfuQW1odeW5i2Ai47Y6TBA2hQnC+azscjBSALpaWgw==",
      "dependencies": {
        "@mapbox/jsonlint-lines-primitives": "2.0.2",
        "@mapbox/unitbezier": "0.0.1",
        "json-stringify-pretty-compact": "4.0.0",
        "minimist": "1.2.8",
        "quickselect": "2.0.0",
        "rw": "1.3.3",
        "tinyqueue": "3.0.0"
      }
    },
    "node_modules/@playwright/test": {
      "version": "1.55.1",
      "resolved": "https://registry.npmjs.org/@playwright/test/-/test-1.55.1.tgz",
      "integrity": "sha512-IVAh/nOJaw6W9g+RJVlIQJ6gSiER+ae6mKQ5CX1bERzQgbC1VSeBlwdvczT7pxb0GWiyrxH4TGKbMfDb4Sq/ig==",
      "dev": true,
      "dependencies": {
        "playwright": "1.55.1"
      },
      "engines": {
        "node": ">=18"
      }
    },
    "node_modules/@polka/url": {
      "version": "1.0.0-next.29",
      "resolved": "https://registry.npmjs.org/@polka/url/-/url-1.0.0-next.29.tgz",
      "integrity": "sha512-wwQAWhWSuHaag8c4q/KN/vCoeOJYshAIvMQwD4GpSb3OiZklFfvAgmj0VCBBImRpuF/aFgIRzllXlVX93Jevww==",
      "dev": true
    },
    "node_modules/@rollup/rollup-android-arm-eabi": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm-eabi/-/rollup-android-arm-eabi-4.52.3.tgz",
      "integrity": "sha512-h6cqHGZ6VdnwliFG1NXvMPTy/9PS3h8oLh7ImwR+kl+oYnQizgjxsONmmPSb2C66RksfkfIxEVtDSEcJiO0tqw==",
      "cpu": [
        "arm"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-android-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-android-arm64/-/rollup-android-arm64-4.52.3.tgz",
      "integrity": "sha512-wd+u7SLT/u6knklV/ifG7gr5Qy4GUbH2hMWcDauPFJzmCZUAJ8L2bTkVXC2niOIxp8lk3iH/QX8kSrUxVZrOVw==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "android"
      ]
    },
    "node_modules/@rollup/rollup-darwin-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-arm64/-/rollup-darwin-arm64-4.52.3.tgz",
      "integrity": "sha512-lj9ViATR1SsqycwFkJCtYfQTheBdvlWJqzqxwc9f2qrcVrQaF/gCuBRTiTolkRWS6KvNxSk4KHZWG7tDktLgjg==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-darwin-x64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-darwin-x64/-/rollup-darwin-x64-4.52.3.tgz",
      "integrity": "sha512-+Dyo7O1KUmIsbzx1l+4V4tvEVnVQqMOIYtrxK7ncLSknl1xnMHLgn7gddJVrYPNZfEB8CIi3hK8gq8bDhb3h5A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "darwin"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-arm64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-arm64/-/rollup-freebsd-arm64-4.52.3.tgz",
      "integrity": "sha512-u9Xg2FavYbD30g3DSfNhxgNrxhi6xVG4Y6i9Ur1C7xUuGDW3banRbXj+qgnIrwRN4KeJ396jchwy9bCIzbyBEQ==",
      "cpu": [
        "arm64"
      ],
      "dev": true,
      "optional": true,
      "os": [
        "freebsd"
      ]
    },
    "node_modules/@rollup/rollup-freebsd-x64": {
      "version": "4.52.3",
      "resolved": "https://registry.npmjs.org/@rollup/rollup-freebsd-x64/-/rollup-freebsd-x64-4.52.3.tgz",
      "integrity": "sha512-5M8kyi/OX96wtD5qJR89a/3x5x8x5inXBZO04JWhkQb2JWavOWfjgkdvUqibGJeNNaz1/Z1PPza5/tAPXICI6A==",
      "cpu": [
        "x64"
      ],
      "dev": true,
      "optional": true,

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_public.md

**Größe:** 129 B | **md5:** `fa5a9580eb2592a549fb1ece4a6b1ba0`

```markdown
### 📄 weltgewebe/apps/web/public/.gitkeep

**Größe:** 0 B | **md5:** `d41d8cd98f00b204e9800998ecf8427e`

```plaintext

```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_scripts.md

**Größe:** 3 KB | **md5:** `c92bc76e0da1dcc4a2be6df688440a7b`

```markdown
### 📄 weltgewebe/apps/web/scripts/record-screenshot.mjs

**Größe:** 424 B | **md5:** `399bbca4f4d3a269a3a9abdde909f5f1`

```plaintext
// record-screenshot.mjs
import puppeteer from "puppeteer";

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto("http://localhost:5173/map");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "public/demo.png", fullPage: true });
  console.log("✅ Screenshot gespeichert: public/demo.png");
  await browser.close();
})();
```

### 📄 weltgewebe/apps/web/scripts/verify-cookie-version.js

**Größe:** 2 KB | **md5:** `9ba39a27476a451a6f6634933ce66d4f`

```javascript
import { createRequire } from 'node:module';

// Fail fast in CI if the lockfile resolves to a vulnerable cookie version.
// Skip silently when cookie isn't present (e.g. npm ci --omit=dev / production).
// This guards against transitive downgrades or accidental removal of `overrides`.
const require = createRequire(import.meta.url);
// CI is truthy on most providers; treat explicit "false" as off.
const isCI = !!process.env.CI && process.env.CI !== 'false';

// Minimal semver check for our purposes: we just need to know if a version is
// less than the minimum safe version, using exact numeric components.
const semverLt = (a, b) => {
  const aParts = a.split('.').map(Number);
  const bParts = b.split('.').map(Number);
  for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
    const aVal = aParts[i] || 0;
    const bVal = bParts[i] || 0;
    if (aVal < bVal) return true;
    if (aVal > bVal) return false;
  }
  return false;
};

// Helper: detect common "module not found" shapes across Node/ESM.
const isModuleNotFound = (err) =>
  err?.code === 'MODULE_NOT_FOUND' ||
  err?.code === 'ERR_MODULE_NOT_FOUND' ||
  /Cannot find module/.test(String(err?.message || err));

try {
  const pkg = require('cookie/package.json');
  const installed = pkg?.version;
  const minSafe = '0.7.0';
  if (semverLt(installed, minSafe)) {
    const msg =
      `\n[security] cookie@${installed} detected (< ${minSafe}). ` +
      `The advisory requires ${minSafe}+ — check npm overrides and lockfile.\n`;
    if (isCI) {
      console.error(msg);
      process.exit(1);
    } else {
      console.warn(msg.trim(), '\n(continuing locally)');
      process.exit(0);
    }
  }
} catch (err) {
  // If cookie is not installed at all (e.g. prod install without dev deps),
  // skip the check so production installs still succeed.
  if (isModuleNotFound(err)) {
    // Quiet skip — production deploys often omit dev deps.
    process.exit(0);
  }
  // Other errors: strict in CI, lenient locally.
  const msg =
    `\n[security] Could not verify cookie version (unexpected error): ${err?.message || err}`;
  if (isCI) {
    console.error(msg);
    process.exit(1);
  }
  console.warn(msg, '\n(continuing locally)');
  process.exit(0);
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src.md

**Größe:** 2 KB | **md5:** `cadbf2f93c8aeb5c07f7edcd3eecf63d`

```markdown
### 📄 weltgewebe/apps/web/src/app.css

**Größe:** 1 KB | **md5:** `4471946c3c1af41300f0c6804b38f808`

```css
/* Minimal, utility-light Styles für Click-Dummy */
:root { --bg:#0b0e12; --fg:#e7ebee; --muted:#9aa3ad; --panel:#141a21; --accent:#7cc4ff; }
html,body,#app { height:100%; margin:0; }
body { background:var(--bg); color:var(--fg); font: 14px/1.4 ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, "Helvetica Neue", Arial; }
.row { display:flex; gap:.75rem; align-items:center; }
.col { display:flex; flex-direction:column; gap:.5rem; }
.panel { background:var(--panel); border:1px solid #1f2630; border-radius:12px; padding:.75rem; }
.badge { border:1px solid #223244; padding:.15rem .45rem; border-radius:999px; color:var(--muted); }
.ghost { opacity:.7 }
.divider { height:1px; background:#1f2630; margin:.5rem 0; }
.btn { padding:.4rem .6rem; border:1px solid #263240; background:#101821; color:var(--fg); border-radius:8px; cursor:pointer }
.btn:disabled { opacity:.5; cursor:not-allowed }
.legend-dot { width:.8rem; height:.8rem; border-radius:999px; display:inline-block; margin-right:.4rem; vertical-align:middle }
.dot-blue{background:#4ea1ff}.dot-gray{background:#9aa3ad}.dot-yellow{background:#ffd65a}.dot-red{background:#ff6b6b}.dot-green{background:#54e1a6}.dot-violet{background:#b392f0}
```

### 📄 weltgewebe/apps/web/src/app.d.ts

**Größe:** 112 B | **md5:** `c20a78b8e768a570c00cb0fd7e016b4e`

```typescript
// See https://kit.svelte.dev/docs/types
// for information about these interfaces
declare global {}
export {};
```

### 📄 weltgewebe/apps/web/src/app.html

**Größe:** 286 B | **md5:** `e8f20d9bbdd6b5d1b19d651a703e0d1a`

```html
<!doctype html>
<html lang="en">
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		%sveltekit.head%
	</head>
	<body data-sveltekit-preload-data="hover">
		<div style="display: contents">%sveltekit.body%</div>
	</body>
</html>
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_lib.md

**Größe:** 206 B | **md5:** `3e7b81bf7914a7d743bb1109fd1e3141`

```markdown
### 📄 weltgewebe/apps/web/src/lib/index.ts

**Größe:** 75 B | **md5:** `ffcb0e97b69eb555d5739e9efe961ca0`

```typescript
// place files you want to import through the `$lib` alias in this folder.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_lib_assets.md

**Größe:** 2 KB | **md5:** `2f599be89327c8348ed61aa30f8cf1fc`

```markdown
### 📄 weltgewebe/apps/web/src/lib/assets/favicon.svg

**Größe:** 2 KB | **md5:** `a0d1b540c1b9a2a920d5f6cae983118a`

```plaintext
<svg xmlns="http://www.w3.org/2000/svg" width="107" height="128" viewBox="0 0 107 128"><title>svelte-logo</title><path d="M94.157 22.819c-10.4-14.885-30.94-19.297-45.792-9.835L22.282 29.608A29.92 29.92 0 0 0 8.764 49.65a31.5 31.5 0 0 0 3.108 20.231 30 30 0 0 0-4.477 11.183 31.9 31.9 0 0 0 5.448 24.116c10.402 14.887 30.942 19.297 45.791 9.835l26.083-16.624A29.92 29.92 0 0 0 98.235 78.35a31.53 31.53 0 0 0-3.105-20.232 30 30 0 0 0 4.474-11.182 31.88 31.88 0 0 0-5.447-24.116" style="fill:#ff3e00"/><path d="M45.817 106.582a20.72 20.72 0 0 1-22.237-8.243 19.17 19.17 0 0 1-3.277-14.503 18 18 0 0 1 .624-2.435l.49-1.498 1.337.981a33.6 33.6 0 0 0 10.203 5.098l.97.294-.09.968a5.85 5.85 0 0 0 1.052 3.878 6.24 6.24 0 0 0 6.695 2.485 5.8 5.8 0 0 0 1.603-.704L69.27 76.28a5.43 5.43 0 0 0 2.45-3.631 5.8 5.8 0 0 0-.987-4.371 6.24 6.24 0 0 0-6.698-2.487 5.7 5.7 0 0 0-1.6.704l-9.953 6.345a19 19 0 0 1-5.296 2.326 20.72 20.72 0 0 1-22.237-8.243 19.17 19.17 0 0 1-3.277-14.502 17.99 17.99 0 0 1 8.13-12.052l26.081-16.623a19 19 0 0 1 5.3-2.329 20.72 20.72 0 0 1 22.237 8.243 19.17 19.17 0 0 1 3.277 14.503 18 18 0 0 1-.624 2.435l-.49 1.498-1.337-.98a33.6 33.6 0 0 0-10.203-5.1l-.97-.294.09-.968a5.86 5.86 0 0 0-1.052-3.878 6.24 6.24 0 0 0-6.696-2.485 5.8 5.8 0 0 0-1.602.704L37.73 51.72a5.42 5.42 0 0 0-2.449 3.63 5.79 5.79 0 0 0 .986 4.372 6.24 6.24 0 0 0 6.698 2.486 5.8 5.8 0 0 0 1.602-.704l9.952-6.342a19 19 0 0 1 5.295-2.328 20.72 20.72 0 0 1 22.237 8.242 19.17 19.17 0 0 1 3.277 14.503 18 18 0 0 1-8.13 12.053l-26.081 16.622a19 19 0 0 1-5.3 2.328" style="fill:#fff"/></svg>
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_lib_components.md

**Größe:** 19 KB | **md5:** `0aea83aefeea439f82cd6e5d0fdafb34`

```markdown
### 📄 weltgewebe/apps/web/src/lib/components/AppShell.svelte

**Größe:** 2 KB | **md5:** `e14cf8f1ddf8c953d273dc988768a07e`

```svelte
<script lang="ts">
  export let title = "Weltgewebe – Click-Dummy";
  export let timeCursor: string = "T-0";
</script>

<div class="app-shell">
  <header class="app-bar panel" aria-label="Navigation und Status">
    <div class="brand">
      <div class="brand-main">
        <strong>{title}</strong>
        <span class="badge">Gate A</span>
      </div>
      <p class="brand-sub ghost">Frontend-only Prototype · UX vor Code</p>
    </div>
    <div class="header-actions">
      <slot name="gewebekonto" />
      <slot name="topright" />
    </div>
  </header>
  <main class="app-main">
    <slot />
  </main>
  <footer class="app-footer panel" aria-label="Zeitachse (Attrappe)">
    <div>Zeitachse: Cursor <span class="badge">{timeCursor}</span></div>
    <div class="ghost">Replay deaktiviert · Gate B/C folgen</div>
  </footer>
</div>

<style>
  .app-shell {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto 1fr auto;
    gap: 0.75rem;
    padding: 0.75rem;
    box-sizing: border-box;
  }

  .app-bar {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .brand {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .brand-main {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .brand-sub {
    margin: 0;
  }

  .header-actions {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .header-actions :global(.btn:focus-visible),
  .header-actions :global(button:focus-visible),
  .header-actions :global(a:focus-visible) {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
    border-radius: 0.5rem;
  }

  .app-main {
    position: relative;
    overflow: hidden;
    border-radius: 18px;
  }

  .app-footer {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  @media (min-width: 42rem) {
    .app-bar {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }

    .header-actions {
      flex-direction: row;
      align-items: center;
      justify-content: flex-end;
      flex-wrap: wrap;
    }

    .app-footer {
      flex-direction: row;
      align-items: center;
      justify-content: space-between;
    }
  }
</style>
```

### 📄 weltgewebe/apps/web/src/lib/components/Drawer.svelte

**Größe:** 3 KB | **md5:** `8f7f125feb0ee4383ac90c07627d16f5`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount, tick } from 'svelte';

  export let title = '';
  export let open = false;
  export let side: 'left' | 'right' | 'top' = 'left';
  export let id: string | undefined;

  const dispatch = createEventDispatcher<{ open: void; close: void }>();

  let headingId: string | undefined;
  let drawerId: string;
  $: drawerId = id ?? `${side}-drawer`;
  $: headingId = title ? `${drawerId}-title` : undefined;

  let rootEl: HTMLDivElement | null = null;
  let openerEl: HTMLElement | null = null;
  export function setOpener(el: HTMLElement | null) {
    openerEl = el;
  }

  function focusFirstInside() {
    if (!rootEl) return;
    const focusables = Array.from(
      rootEl.querySelectorAll<HTMLElement>(
        'button:not([tabindex="-1"]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => !element.hasAttribute('disabled'));

    (focusables[0] ?? rootEl).focus();
  }

  async function handleOpen() {
    await tick();
    focusFirstInside();
    dispatch('open');
  }

  async function handleClose() {
    await tick();
    openerEl?.focus();
    dispatch('close');
  }

  let hasMounted = false;
  onMount(() => {
    hasMounted = true;
  });

  let previousOpen = open;
  $: if (hasMounted && open !== previousOpen) {
    if (open) {
      handleOpen();
    } else {
      handleClose();
    }
    previousOpen = open;
  }
</script>

<style>
  .drawer{
    position:absolute; z-index:26; padding:var(--drawer-gap); color:var(--text);
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow);
    transform: translateY(calc(-1 * var(--drawer-slide-offset)));
    opacity:0;
    pointer-events:none;
    transition:.18s ease;
    overscroll-behavior: contain;
  }
  .drawer.open{ transform:none; opacity:1; pointer-events:auto; }
  .left{
    left:var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
    border-radius: var(--radius);
  }
  .right{
    right:var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
  }
  .top{
    left:50%;
    transform:translate(-50%, calc(-1 * var(--drawer-slide-offset)));
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    width:min(860px, calc(100vw - (2 * var(--drawer-gap))));
  }
  .top.open{ transform:translate(-50%,0); }
  h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .section{ margin-bottom:12px; padding:10px; border:1px solid var(--panel-border); border-radius:10px; background:rgba(255,255,255,0.02); }
  @media (prefers-reduced-motion: reduce){
    .drawer{ transition:none; }
  }
</style>

<div
  bind:this={rootEl}
  id={drawerId}
  class="drawer"
  class:open={open}
  class:left={side === 'left'}
  class:right={side === 'right'}
  class:top={side === 'top'}
  aria-hidden={!open}
  aria-labelledby={headingId}
  tabindex="-1"
  role="complementary"
  inert={!open ? true : undefined}
  {...$$restProps}
>
  {#if title}<h3 id={headingId}>{title}</h3>{/if}
  <slot />
  <slot name="footer" />
  <slot name="overlays" />
</div>
```

### 📄 weltgewebe/apps/web/src/lib/components/DrawerLeft.svelte

**Größe:** 3 KB | **md5:** `6ae20720a86d772bc2ad352b6e991833`

```svelte
<script lang="ts">
  type TabId = 'webrat' | 'naehstuebchen';

  export let open = true;
  let tab: TabId = 'webrat';
  let webratButton: HTMLButtonElement | null = null;
  let naehstuebchenButton: HTMLButtonElement | null = null;

  const orderedTabs: TabId[] = ['webrat', 'naehstuebchen'];

  function select(next: TabId, focus = false) {
    tab = next;
    if (focus) {
      (next === 'webrat' ? webratButton : naehstuebchenButton)?.focus();
    }
  }

  function handleKeydown(event: KeyboardEvent) {
    const { key } = event;
    if (key === 'ArrowLeft' || key === 'ArrowRight' || key === 'Home' || key === 'End') {
      event.preventDefault();
      const currentIndex = orderedTabs.indexOf(tab);
      if (key === 'Home') {
        select(orderedTabs[0], true);
        return;
      }

      if (key === 'End') {
        select(orderedTabs[orderedTabs.length - 1], true);
        return;
      }

      const delta = key === 'ArrowRight' ? 1 : -1;
      const nextIndex = (currentIndex + delta + orderedTabs.length) % orderedTabs.length;
      select(orderedTabs[nextIndex], true);
    }
  }
</script>

{#if open}
<aside class="panel drawer drawer-left" aria-label="Primärer Bereichs-Drawer">
  <div
    class="row"
    style="gap:.5rem"
    role="tablist"
    aria-label="Bereich auswählen"
    aria-orientation="horizontal"
    on:keydown={handleKeydown}
  >
    <button
      class="btn"
      id="drawer-tab-webrat"
      role="tab"
      aria-selected={tab === 'webrat'}
      aria-controls="drawer-panel-webrat"
      type="button"
      tabindex={tab === 'webrat' ? 0 : -1}
      bind:this={webratButton}
      on:click={() => select('webrat')}
    >
      Webrat
    </button>
    <button
      class="btn"
      id="drawer-tab-naehstuebchen"
      role="tab"
      aria-selected={tab === 'naehstuebchen'}
      aria-controls="drawer-panel-naehstuebchen"
      type="button"
      tabindex={tab === 'naehstuebchen' ? 0 : -1}
      bind:this={naehstuebchenButton}
      on:click={() => select('naehstuebchen')}
    >
      Nähstübchen
    </button>
  </div>
  <div class="divider"></div>
  {#if tab === 'webrat'}
    <div id="drawer-panel-webrat" role="tabpanel" aria-labelledby="drawer-tab-webrat">
      <p>Platzhalter – „coming soon“ (Diskussionen/Abstimmungen)</p>
    </div>
  {:else}
    <div id="drawer-panel-naehstuebchen" role="tabpanel" aria-labelledby="drawer-tab-naehstuebchen">
      <p>Platzhalter – „coming soon“ (Community-Werkzeuge)</p>
    </div>
  {/if}
</aside>
{/if}

<style>
  .drawer {
    position: absolute;
    z-index: 2;
    left: 50%;
    transform: translateX(-50%);
    bottom: 12rem;
    width: min(22rem, calc(100% - 1.5rem));
    max-height: min(45vh, 22rem);
    overflow: auto;
  }

  .drawer :global(p) {
    margin: 0;
  }

  .drawer [role="tab"] {
    outline: none;
  }

  .drawer [role="tab"]:focus-visible {
    outline: 2px solid rgba(112, 184, 255, 0.9);
    outline-offset: 2px;
  }

  @media (min-width: 48rem) {
    .drawer {
      top: clamp(0.75rem, 2vw, 1.5rem);
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      left: clamp(0.75rem, 2vw, 1.5rem);
      transform: none;
      width: min(20rem, 28vw);
      max-height: none;
    }
  }
</style>
```

### 📄 weltgewebe/apps/web/src/lib/components/DrawerRight.svelte

**Größe:** 3 KB | **md5:** `c2df462c5482b6b2bf4769f21b32a08f`

```svelte
<script lang="ts">
  export let open = true;
  // UI-State nur im Frontend; keine Persistenz
  let distance = 3;
  const filters = {
    knotentypen: {
      strukturknoten: true,
      faeden: false
    },
    bedarf: {
      bohrmaschine: false,
      schlafplatz: false,
      kinderspass: false,
      essen: false
    }
  };
</script>

{#if open}
<aside
  class="panel drawer drawer-right"
  aria-label="Filter- und Such-Drawer (inaktiv)"
  aria-describedby="filters-disabled-note"
>
  <strong>Suche</strong>
  <label class="col">
    <span class="ghost">Stichwort oder Adresse</span>
    <input type="search" placeholder="z. B. Reparatur" disabled />
  </label>
  <div class="divider"></div>
  <strong>Filter (stummgeschaltet)</strong>
  <div class="divider"></div>
  <div class="col">
    <label class="row"><input type="checkbox" bind:checked={filters.knotentypen.strukturknoten} disabled> Strukturknoten</label>
    <label class="row"><input type="checkbox" bind:checked={filters.knotentypen.faeden} disabled> Fäden</label>
  </div>
  <div class="divider"></div>
  <strong>Bedarf</strong>
  <div class="col">
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.bohrmaschine} disabled> Bohrmaschine</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.schlafplatz} disabled> Schlafplatz</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.kinderspass} disabled> Kinderspaß</label>
    <label class="row"><input type="checkbox" bind:checked={filters.bedarf.essen} disabled> Essen</label>
  </div>
  <div class="divider"></div>
  <label class="col">
    <span>Distanz (km) – UI only</span>
    <input type="range" min="1" max="15" bind:value={distance} disabled />
    <span class="ghost">{distance} km</span>
  </label>
  <p class="ghost" id="filters-disabled-note">Filter sind im Click-Dummy deaktiviert.</p>
</aside>
{/if}

<style>
  .drawer {
    position: absolute;
    z-index: 2;
    left: 50%;
    transform: translateX(-50%);
    bottom: 1rem;
    width: min(22rem, calc(100% - 1.5rem));
    max-height: min(50vh, 24rem);
    overflow: auto;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .drawer :global(label) {
    gap: 0.5rem;
  }

  .drawer input[type="search"],
  .drawer input[type="range"] {
    width: 100%;
    background: #101821;
    border: 1px solid #263240;
    border-radius: 8px;
    padding: 0.45rem 0.6rem;
    color: var(--fg);
  }

  .drawer input[disabled] {
    opacity: 0.6;
  }

  @media (min-width: 48rem) {
    .drawer {
      top: clamp(0.75rem, 2vw, 1.5rem);
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      right: clamp(0.75rem, 2vw, 1.5rem);
      left: auto;
      transform: none;
      width: min(20rem, 28vw);
      max-height: none;
    }
  }
</style>
```

### 📄 weltgewebe/apps/web/src/lib/components/Garnrolle.svelte

**Größe:** 1 KB | **md5:** `598a242724e118a4888305dc6a49eeed`

```svelte
<script lang="ts">
  export let label = 'Mein Konto';
  export let tooltip = 'Garnrolle – Konto';
</script>

<style>
  .wrap{ position:relative; }
  .roll{
    width:34px; height:34px; border-radius:50%;
    background: radial-gradient(circle at 30% 30%, #6aa6ff 0%, #2c6de0 60%, #1b3f7a 100%);
    border:1px solid rgba(255,255,255,0.12);
    box-shadow: var(--shadow);
    display:grid; place-items:center; cursor:pointer;
  }
  .hole{ width:10px; height:10px; border-radius:50%; background:#0f1a2f; box-shadow: inset 0 0 8px rgba(0,0,0,.6); }
  .tip{
    position:absolute; right:0; transform:translateY(calc(-100% - 8px));
    background:var(--panel); border:1px solid var(--panel-border); color:var(--text);
    padding:6px 8px; font-size:12px; border-radius:8px; white-space:nowrap;
    opacity:0; pointer-events:none; transition:.15s ease;
  }
  .wrap:hover .tip{ opacity:1; }
</style>

<div class="wrap" aria-label={label}>
  <div class="roll" title={tooltip}><div class="hole" /></div>
  <div class="tip">{tooltip}</div>
</div>
```

### 📄 weltgewebe/apps/web/src/lib/components/GewebekontoWidget.svelte

**Größe:** 1 KB | **md5:** `30e5f7dbd97602fdd51c419f768a06bb`

```svelte
<script lang="ts">
  export let balance = "1 250 WE";
  export let trend: 'stable' | 'up' | 'down' = 'stable';
  export let note = "Attrappe · UX-Test";

  const trendLabels = {
    stable: 'gleichbleibend',
    up: 'steigend',
    down: 'sinkend'
  } as const;
</script>

<div class="gewebekonto panel" role="group" aria-label="Gewebekonto-Widget (Attrappe)">
  <div class="meta row">
    <span class="badge">Gewebekonto</span>
    <span class="ghost">Status: {trendLabels[trend]}</span>
  </div>
  <div class="balance" aria-live="polite">
    <strong>{balance}</strong>
  </div>
  <p class="note ghost">{note}</p>
  <div class="actions row" aria-hidden="true">
    <button class="btn" type="button" disabled>Einzahlen</button>
    <button class="btn" type="button" disabled>Auszahlen</button>
  </div>
</div>

<style>
  .gewebekonto {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    min-width: 14rem;
  }

  .meta {
    justify-content: space-between;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .balance {
    font-size: 1.25rem;
  }

  .note {
    margin: 0;
  }

  .actions {
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  @media (max-width: 40rem) {
    .gewebekonto {
      width: 100%;
    }
  }
</style>
```

### 📄 weltgewebe/apps/web/src/lib/components/Legend.svelte

**Größe:** 2 KB | **md5:** `9cc8e254463f5321fb576725d548c346`

```svelte
<script lang="ts">
  let open = false;
</script>

<div class="panel legend">
  <div class="legend-header row">
    <strong>Legende</strong>
    <button
      class="btn"
      on:click={() => (open = !open)}
      aria-expanded={open}
      aria-controls="legend-panel"
    >
      {open ? "Schließen" : "Öffnen"}
    </button>
  </div>
  {#if open}
    <div class="divider"></div>
    <div class="col" id="legend-panel">
      <div><span class="legend-dot dot-blue"></span>Blau = Zentrum/Meta</div>
      <div><span class="legend-dot dot-gray"></span>Grau = Grundlagen</div>
      <div><span class="legend-dot dot-yellow"></span>Gelb = Prozesse</div>
      <div><span class="legend-dot dot-red"></span>Rot = Hindernisse</div>
      <div><span class="legend-dot dot-green"></span>Grün = Ziele</div>
      <div><span class="legend-dot dot-violet"></span>Violett = Ebenen</div>
    </div>
    <div class="divider"></div>
    <em class="ghost">Essenz: „Karte sichtbar, aber dumm.“</em>
  {/if}
</div>

<style>
  .legend {
    position: absolute;
    z-index: 2;
    right: clamp(0.75rem, 3vw, 1.5rem);
    top: clamp(0.75rem, 3vw, 1.5rem);
    width: min(18rem, calc(100% - 1.5rem));
  }

  .legend-header {
    justify-content: space-between;
  }

  .legend :global(.col) {
    gap: 0.35rem;
  }

  @media (max-width: 40rem) {
    .legend {
      left: clamp(0.75rem, 3vw, 1.5rem);
      width: auto;
    }
  }

  @media (min-width: 48rem) {
    .legend {
      bottom: clamp(3.5rem, 12vh, 4.75rem);
      top: auto;
    }
  }
</style>
```

### 📄 weltgewebe/apps/web/src/lib/components/TimelineDock.svelte

**Größe:** 687 B | **md5:** `6cfaa4f9be468994236a0a6e14e629dd`

```svelte
<style>
  .dock{
    position:absolute; left:0; right:0; bottom:0; min-height:56px; z-index:28;
    display:flex; align-items:center; gap:12px;
    padding:0 12px calc(env(safe-area-inset-bottom)) 12px;
    backdrop-filter: blur(6px);
    background: linear-gradient(0deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
  }
  .badge{ border:1px solid var(--panel-border); background:var(--panel); padding:6px 10px; border-radius:10px; }
  .spacer{ flex:1; }
</style>

<div class="dock">
  <div class="badge">⏱️ Timeline (Stub)</div>
  <div class="spacer"></div>
  <div style="opacity:.72; font-size:12px;">Tipp: [ = links · ] = rechts · Alt+G = Gewebekonto</div>
</div>
```

### 📄 weltgewebe/apps/web/src/lib/components/TopBar.svelte

**Größe:** 2 KB | **md5:** `6891014f2bb2c82ab7637bd0935b65ea`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import Garnrolle from './Garnrolle.svelte';
  export let onToggleLeft: () => void;
  export let onToggleRight: () => void;
  export let onToggleTop: () => void;
  export let leftOpen = false;
  export let rightOpen = false;
  export let topOpen = false;

  const dispatch = createEventDispatcher<{
    openers: {
      left: HTMLButtonElement | null;
      right: HTMLButtonElement | null;
      top: HTMLButtonElement | null;
    };
  }>();

  let btnLeft: HTMLButtonElement | null = null;
  let btnRight: HTMLButtonElement | null = null;
  let btnTop: HTMLButtonElement | null = null;

  onMount(() => {
    dispatch('openers', { left: btnLeft, right: btnRight, top: btnTop });
  });
</script>

<style>
  .topbar{
    position:absolute; inset:0 0 auto 0; min-height:52px; z-index:30;
    display:flex; align-items:center; gap:8px; padding:0 12px;
    padding:env(safe-area-inset-top) 12px 0 12px;
    background: linear-gradient(180deg, rgba(0,0,0,0.55), rgba(0,0,0,0));
    color:var(--text);
  }
  .btn{
    appearance:none; border:1px solid var(--panel-border); background:var(--panel); color:var(--text);
    height:34px; padding:0 12px; border-radius:10px; display:inline-flex; align-items:center; gap:8px;
    box-shadow: var(--shadow); cursor:pointer;
  }
  .btn:hover{ outline:1px solid var(--accent-soft); }
  .spacer{ flex:1; }
</style>

<div class="topbar" role="toolbar" aria-label="Navigation">
  <button
    class="btn"
    type="button"
    aria-pressed={leftOpen}
    aria-expanded={leftOpen}
    aria-controls="left-stack"
    bind:this={btnLeft}
    on:click={onToggleLeft}
  >
    ☰ Webrat/Nähstübchen
  </button>
  <button
    class="btn"
    type="button"
    aria-pressed={rightOpen}
    aria-expanded={rightOpen}
    aria-controls="filter-drawer"
    bind:this={btnRight}
    on:click={onToggleRight}
  >
    🔎 Filter
  </button>
  <button
    class="btn"
    type="button"
    aria-pressed={topOpen}
    aria-expanded={topOpen}
    aria-controls="account-drawer"
    bind:this={btnTop}
    on:click={onToggleTop}
  >
    🧶 Gewebekonto
  </button>
  <div class="spacer"></div>
  <Garnrolle />
</div>
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_lib_maplibre.md

**Größe:** 10 KB | **md5:** `5c8f16251ede5813c28e6f923a85d1d9`

```markdown
### 📄 weltgewebe/apps/web/src/lib/maplibre/MapLibre.svelte

**Größe:** 2 KB | **md5:** `c9b32f356f200f0927f72fa926e74c14`

```svelte
<script lang="ts">
  import { createEventDispatcher, onMount } from "svelte";
  import "maplibre-gl/dist/maplibre-gl.css";
  import type { FitBoundsOptions, LngLatBoundsLike, LngLatLike, MapOptions } from "maplibre-gl";
  import { initMapContext } from "./context";

  const dispatch = createEventDispatcher();
  const context = initMapContext();

  export let style: string;
  export let center: LngLatLike | undefined;
  export let zoom: number | undefined;
  export let minZoom: number | undefined;
  export let maxZoom: number | undefined;
  export let bounds: LngLatBoundsLike | undefined;
  export let fitBoundsOptions: FitBoundsOptions | undefined;
  export let attributionControl = false;
  export let interactive: boolean | undefined;
  export let options: Partial<MapOptions> = {};

  let container: HTMLDivElement | undefined;
  let map: import("maplibre-gl").Map | null = null;
  let containerProps: Record<string, unknown> = {};

  $: ({ style: _omitStyle, ...containerProps } = $$restProps);

  onMount(async () => {
    const maplibreModule = await import("maplibre-gl");
    context.maplibre = maplibreModule;

    if (!container) {
      return;
    }

    const initialOptions: MapOptions = {
      container,
      style,
      attributionControl,
      ...options
    } as MapOptions;

    if (center) {
      initialOptions.center = normalizeLngLat(center);
    }

    if (zoom !== undefined) {
      initialOptions.zoom = zoom;
    }

    if (minZoom !== undefined) {
      initialOptions.minZoom = minZoom;
    }

    if (maxZoom !== undefined) {
      initialOptions.maxZoom = maxZoom;
    }

    if (interactive !== undefined) {
      initialOptions.interactive = interactive;
    }

    map = new maplibreModule.Map(initialOptions);
    context.map.set(map);

    map.on("load", () => dispatch("load", { map }));
    map.on("error", (event) => dispatch("error", event));

    if (bounds) {
      map.fitBounds(bounds, fitBoundsOptions);
    }

    return () => {
      map?.remove();
      map = null;
      context.map.set(null);
      context.maplibre = null;
    };
  });

  $: if (map && center) {
    map.setCenter(normalizeLngLat(center));
  }

  $: if (map && zoom !== undefined) {
    map.setZoom(zoom);
  }

  $: if (map && bounds) {
    map.fitBounds(bounds, fitBoundsOptions);
  }

  function normalizeLngLat(value: LngLatLike): LngLatLike {
    if (Array.isArray(value)) {
      return value;
    }

    return [value.lng, value.lat];
  }
</script>

<div bind:this={container} {...containerProps}>
  <slot />
</div>
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/Marker.svelte

**Größe:** 2 KB | **md5:** `68831b8c0a3634a486d5b537643f3517`

```svelte
<script lang="ts">
  import type { Anchor, LngLatLike, MarkerOptions, PointLike } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let lngLat: LngLatLike;
  export let anchor: Anchor = "center";
  export let draggable = false;
  export let offset: PointLike | undefined;

  const context = useMapContext();

  let element: HTMLDivElement | undefined;
  let marker: import("maplibre-gl").Marker | null = null;
  let markerProps: Record<string, unknown> = {};
  let currentAnchor: Anchor = anchor;

  $: markerProps = $$restProps;

  const unsubscribe = context.map.subscribe((map) => {
    recreateMarker(map);
  });

  $: if (marker && lngLat) {
    marker.setLngLat(lngLat);
  }

  $: if (marker) {
    marker.setDraggable(draggable);
  }

  $: if (marker && offset !== undefined) {
    marker.setOffset(offset);
  }

  $: if (marker && anchor !== currentAnchor) {
    recreateMarker(get(context.map));
  }

  function recreateMarker(map: import("maplibre-gl").Map | null) {
    if (marker) {
      marker.remove();
      marker = null;
    }

    if (!map || !context.maplibre || !element) {
      return;
    }

    const options: MarkerOptions = {
      element,
      anchor,
      draggable
    };

    if (offset !== undefined) {
      options.offset = offset;
    }

    marker = new context.maplibre.Marker(options).setLngLat(lngLat).addTo(map);
    currentAnchor = anchor;
  }

  onDestroy(() => {
    unsubscribe();

    if (marker) {
      marker.remove();
      marker = null;
    }
  });
</script>

<div bind:this={element} {...markerProps}>
  <slot />
</div>
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/NavigationControl.svelte

**Größe:** 2 KB | **md5:** `ddacf371d91ee0ea654400dfdc70dcc4`

```svelte
<script lang="ts">
  import type { ControlPosition } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let position: ControlPosition = "top-right";
  export let visualizePitch = true;
  export let showCompass = true;
  export let showZoom = true;

  const context = useMapContext();

  let control: import("maplibre-gl").NavigationControl | null = null;
  let signature: string | null = null;
  let lastMap: import("maplibre-gl").Map | null = null;

  const unsubscribe = context.map.subscribe((map) => {
    ensureControl(map);
  });

  $: ensureControl(get(context.map));

  function ensureControl(map: import("maplibre-gl").Map | null) {
    if (!map || !context.maplibre) {
      if (control && lastMap) {
        lastMap.removeControl(control);
        control = null;
      }
      signature = null;
      lastMap = map;
      return;
    }

    const nextSignature = JSON.stringify({ position, visualizePitch, showCompass, showZoom });
    if (control && signature === nextSignature && lastMap === map) {
      return;
    }

    if (control && lastMap) {
      lastMap.removeControl(control);
      control = null;
    }

    control = new context.maplibre.NavigationControl({ visualizePitch, showCompass, showZoom });
    map.addControl(control, position);
    signature = nextSignature;
    lastMap = map;
  }

  onDestroy(() => {
    unsubscribe();
    const map = get(context.map);
    if (control && map) {
      map.removeControl(control);
    } else if (control && lastMap) {
      lastMap.removeControl(control);
    }
    control = null;
    lastMap = null;
  });
</script>
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/ScaleControl.svelte

**Größe:** 2 KB | **md5:** `37e23429d60fa65d8c3c42b3ecb0a59d`

```svelte
<script lang="ts">
  import type { ControlPosition } from "maplibre-gl";
  import { onDestroy } from "svelte";
  import { get } from "svelte/store";
  import { useMapContext } from "./context";

  export let position: ControlPosition = "bottom-left";
  export let maxWidth: number | undefined;
  export let unit: "imperial" | "metric" | "nautical" | undefined;

  const context = useMapContext();

  type ScaleControlOptions = ConstructorParameters<typeof import("maplibre-gl").ScaleControl>[0];

  let control: import("maplibre-gl").ScaleControl | null = null;
  let signature: string | null = null;
  let lastMap: import("maplibre-gl").Map | null = null;

  const unsubscribe = context.map.subscribe((map) => {
    ensureControl(map);
  });

  $: ensureControl(get(context.map));

  function ensureControl(map: import("maplibre-gl").Map | null) {
    if (control && lastMap && lastMap !== map) {
      lastMap.removeControl(control);
      control = null;
    }

    if (!map || !context.maplibre) {
      signature = null;
      lastMap = map;
      return;
    }

    const nextSignature = JSON.stringify({ position, maxWidth, unit });
    if (control && signature === nextSignature && lastMap === map) {
      return;
    }

    if (control && lastMap) {
      lastMap.removeControl(control);
      control = null;
    }

    const options: ScaleControlOptions = {};

    if (maxWidth !== undefined) {
      options.maxWidth = maxWidth;
    }

    if (unit) {
      options.unit = unit;
    }

    control = new context.maplibre.ScaleControl(options);
    map.addControl(control, position);

    signature = nextSignature;
    lastMap = map;
  }

  onDestroy(() => {
    unsubscribe();
    const map = get(context.map);
    if (control && map) {
      map.removeControl(control);
    } else if (control && lastMap) {
      lastMap.removeControl(control);
    }
    control = null;
    lastMap = null;
  });
</script>
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/context.ts

**Größe:** 815 B | **md5:** `8b578cf40bcb3da406f2f04ca730f297`

```typescript
import type * as maplibregl from "maplibre-gl";
import { getContext, setContext } from "svelte";
import { writable, type Writable } from "svelte/store";

export const MAP_CONTEXT_KEY = Symbol("maplibre-context");

export type MapContextValue = {
  map: Writable<maplibregl.Map | null>;
  maplibre: typeof import("maplibre-gl") | null;
};

export function initMapContext(): MapContextValue {
  const value: MapContextValue = {
    map: writable<maplibregl.Map | null>(null),
    maplibre: null
  };

  setContext(MAP_CONTEXT_KEY, value);
  return value;
}

export function useMapContext(): MapContextValue {
  const context = getContext<MapContextValue | undefined>(MAP_CONTEXT_KEY);

  if (!context) {
    throw new Error("MapLibre components must be used inside a <MapLibre> container.");
  }

  return context;
}
```

### 📄 weltgewebe/apps/web/src/lib/maplibre/index.ts

**Größe:** 250 B | **md5:** `1d16218a92d62836dab4f0810c39f1cf`

```typescript
export { default as MapLibre } from "./MapLibre.svelte";
export { default as Marker } from "./Marker.svelte";
export { default as NavigationControl } from "./NavigationControl.svelte";
export { default as ScaleControl } from "./ScaleControl.svelte";
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_lib_stores.md

**Größe:** 2 KB | **md5:** `034da7b00ffec7c651aea7057f6be319`

```markdown
### 📄 weltgewebe/apps/web/src/lib/stores/governance.ts

**Größe:** 2 KB | **md5:** `2302c0165ea60ee88f6368d416add270`

```typescript
import { browser } from "$app/environment";
import { writable, type Subscriber, type Unsubscriber } from "svelte/store";

const TICK_MS = 1000;

/** Countdown-Store, der in festen Intervallen herunterzählt und nach Ablauf automatisch neu startet. */
export interface LoopingCountdown {
  subscribe: (run: Subscriber<number>) => Unsubscriber;
  /** Setzt den Countdown auf die Ausgangsdauer zurück und startet ihn erneut, falls er aktiv war. */
  reset: () => void;
}

/** Steuerungs-Store für einen booleschen Zustand mit sprechenden Convenience-Methoden. */
export interface BooleanToggle {
  subscribe: (run: Subscriber<boolean>) => Unsubscriber;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

export function createLoopingCountdown(durationMs: number): LoopingCountdown {
  const { subscribe: internalSubscribe, set, update } = writable(durationMs);

  let interval: ReturnType<typeof setInterval> | null = null;
  let activeSubscribers = 0;

  const start = () => {
    if (!browser || interval !== null) return;
    interval = setInterval(() => {
      update((previous) => (previous > TICK_MS ? previous - TICK_MS : durationMs));
    }, TICK_MS);
  };

  const stop = () => {
    if (interval !== null) {
      clearInterval(interval);
      interval = null;
    }
    set(durationMs);
  };

  return {
    subscribe(run) {
      activeSubscribers += 1;
      if (activeSubscribers === 1) start();
      const unsubscribe = internalSubscribe(run);
      return () => {
        unsubscribe();
        activeSubscribers -= 1;
        if (activeSubscribers === 0) {
          stop();
        }
      };
    },
    reset() {
      if (!browser) return;
      stop();
      if (activeSubscribers > 0) start();
    }
  };
}

export function createBooleanToggle(initial = false): BooleanToggle {
  const { subscribe, set, update } = writable(initial);
  return {
    subscribe,
    open: () => set(true),
    close: () => set(false),
    toggle: () => update((value) => !value)
  };
}
```

### 📄 weltgewebe/apps/web/src/lib/stores/index.ts

**Größe:** 30 B | **md5:** `2578f505c899216949cce97e01d907b9`

```typescript
export * from "./governance";
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_lib_styles.md

**Größe:** 1 KB | **md5:** `2020f62bb480e31f285c4bcc279b6ef4`

```markdown
### 📄 weltgewebe/apps/web/src/lib/styles/tokens.css

**Größe:** 923 B | **md5:** `3ffc03d6624bf43f77d5b0aa1a7603e8`

```css
:root{
  --bg: #0f1115;
  --panel: rgba(20,22,28,0.92);
  --panel-border: rgba(255,255,255,0.06);
  --text: #e9eef5;
  --muted: #9aa4b2;
  --accent: #6aa6ff;
  --accent-soft: rgba(106,166,255,0.18);
  --radius: 12px;
  --shadow: 0 6px 24px rgba(0,0,0,0.35);
  /* Layout- und Drawer-Defaults */
  --toolbar-offset: 52px;
  --drawer-gap: 12px;
  --drawer-width: 360px;
  --drawer-slide-offset: 20px;

  /* Swipe-Edge Defaults (innenliegende Greifzonen, kollisionsarm mit OS-Gesten) */
  --edge-inset-x: 24px;     /* Abstand von links/rechts */
  --edge-inset-top: 24px;   /* Abstand oben */
  --edge-top-height: 16px;  /* Höhe Top-Zone */
  --edge-left-width: 16px;  /* Breite linke Zone */
  --edge-right-width: 16px; /* Breite rechte Zone */
}

/* Android: Back-Swipe oft breiter → Zone schmaler & leicht weiter innen */
:root.ua-android{
  --edge-inset-x: 28px;
  --edge-left-width: 12px;
  --edge-right-width: 12px;
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_lib_utils.md

**Größe:** 2 KB | **md5:** `f7cddbb2185755af2241d20b2aa7e610`

```markdown
### 📄 weltgewebe/apps/web/src/lib/utils/inert-polyfill.ts

**Größe:** 2 KB | **md5:** `7827c363e57b5dfc9af1dd8169d37ef4`

```typescript
// Minimaler inert-Polyfill:
// - blockiert Focus & Clicks in [inert]
// - setzt aria-hidden, solange inert aktiv ist
// Safari < 16.4 & ältere iPadOS-Versionen profitieren davon.

function applyAriaHidden(el: Element, on: boolean) {
  const prev = (el as HTMLElement).getAttribute('aria-hidden');
  if (on) {
    if (prev !== 'true') (el as HTMLElement).setAttribute('aria-hidden', 'true');
  } else {
    if (prev === 'true') (el as HTMLElement).removeAttribute('aria-hidden');
  }
}

export function ensureInertPolyfill() {
  // Moderne Browser haben bereits inert-Unterstützung.
  if ('inert' in HTMLElement.prototype) return;

  // Style-Schutz zusätzlich (Pointer & Selection aus).
  const style = document.createElement('style');
  style.textContent = `
    [inert] { pointer-events:none; user-select:none; -webkit-user-select:none; -webkit-tap-highlight-color: transparent; }
  `;
  document.head.appendChild(style);

  // Aria-Hidden initial anwenden
  const syncAll = () => {
    document.querySelectorAll<HTMLElement>('[inert]').forEach((el) => applyAriaHidden(el, true));
  };
  syncAll();

  // Fokus- & Click-Blocker
  document.addEventListener('focusin', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      (t as HTMLElement).blur?.();
      (document.activeElement as HTMLElement | null)?.blur?.();
    }
  }, true);
  document.addEventListener('click', (e) => {
    const t = e.target as HTMLElement | null;
    if (t && t.closest('[inert]')) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);

  // Reagiere auf spätere inert-Attribute
  const mo = new MutationObserver((muts) => {
    for (const m of muts) {
      if (!(m.target instanceof HTMLElement)) continue;
      if (m.type === 'attributes' && m.attributeName === 'inert') {
        const el = m.target as HTMLElement;
        const on = el.hasAttribute('inert');
        applyAriaHidden(el, on);
      }
    }
  });
  mo.observe(document.documentElement, { attributes: true, subtree: true, attributeFilter: ['inert'] });
}
```

### 📄 weltgewebe/apps/web/src/lib/utils/ua-flags.ts

**Größe:** 187 B | **md5:** `47cbc1d02f91baf7dfb2478070899b75`

```typescript
export function setUAClasses() {
  const ua = navigator.userAgent || '';
  const isAndroid = /Android/i.test(ua);
  if (isAndroid) document.documentElement.classList.add('ua-android');
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_routes.md

**Größe:** 2 KB | **md5:** `a585d23e37366ec3a187214a98384404`

```markdown
### 📄 weltgewebe/apps/web/src/routes/+layout.svelte

**Größe:** 805 B | **md5:** `4f9a070fe164fe56d1472deff592ba73`

```svelte
<script lang="ts">
  import '../app.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import '$lib/styles/tokens.css';
  import { onMount } from 'svelte';
  import { ensureInertPolyfill } from '$lib/utils/inert-polyfill';
  import { setUAClasses } from '$lib/utils/ua-flags';
  import { page } from '$app/stores';
  import { get } from 'svelte/store';

  export let data: any;

  onMount(() => {
    setUAClasses();
    // Toggle: ?noinert=1 schaltet Polyfill ab (Debug/Kompat)
    const q = new URLSearchParams(get(page).url.search);
    const disable = q.get('noinert') === '1' || (window as any).__NO_INERT__ === true;
    if (!disable) ensureInertPolyfill();
  });
</script>

<svelte:head>
  {#if data?.canonical}
    <link rel="canonical" href={data.canonical} />
  {/if}
</svelte:head>

<slot />
```

### 📄 weltgewebe/apps/web/src/routes/+layout.ts

**Größe:** 192 B | **md5:** `9b63a9d01fca0cbe127d9a061b9f5d59`

```typescript
import type { LayoutLoad } from './$types';

export const load: LayoutLoad = ({ url }) => {
  const canonical = new URL(url.pathname, url.origin).toString();

  return {
    canonical
  };
};
```

### 📄 weltgewebe/apps/web/src/routes/+page.server.ts

**Größe:** 101 B | **md5:** `f4319851426d4c10ea877e8e5de3f83d`

```typescript
import { redirect } from '@sveltejs/kit';

export function load() {
  throw redirect(307, '/map');
}
```

### 📄 weltgewebe/apps/web/src/routes/+page.svelte

**Größe:** 232 B | **md5:** `904b1cf6094055486b945161db807a50`

```svelte
<!-- Platzhalter-Seite, damit die Route "/" existiert und
     der Redirect in +page.server.ts ausgeführt werden kann.
     (In CI/SSR wird sofort umgeleitet.) -->

<noscript>
  Weiterleitung… <a href="/map">/map</a>
</noscript>
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_routes_archive.md

**Größe:** 2 KB | **md5:** `4c1616494b94a520791e46570f663aab`

```markdown
### 📄 weltgewebe/apps/web/src/routes/archive/+page.svelte

**Größe:** 2 KB | **md5:** `a5c4de02e1586fe81976f4aabc4bbbcf`

```svelte
<script lang="ts">
  const archiveMonths = [
    { label: "Mai 2024", path: "/archive/2024/05" },
    { label: "April 2024", path: "/archive/2024/04" },
    { label: "März 2024", path: "/archive/2024/03" }
  ];
</script>

<svelte:head>
  <title>Archiv · Webrat</title>
  <meta
    name="description"
    content="Monatsarchiv der Webrat-Einträge mit einer Übersicht vergangener Beiträge."
  />
</svelte:head>

<main class="archive">
  <header>
    <h1>Archiv</h1>
    <p>
      Im Archiv findest du vergangene Monatsübersichten. Wähle einen Monat aus, um alle Einträge
      aus dieser Zeitspanne zu entdecken.
    </p>
  </header>

  <section aria-labelledby="archive-months">
    <h2 id="archive-months">Monate</h2>
    <ul>
      {#each archiveMonths as month}
        <li><a href={month.path}>{month.label}</a></li>
      {/each}
    </ul>
  </section>
</main>

<style>
  main.archive {
    max-width: 48rem;
    margin: 0 auto;
    padding: 2rem 1.5rem 3rem;
    display: flex;
    flex-direction: column;
    gap: 2rem;
  }

  header p {
    margin-top: 0.75rem;
    line-height: 1.6;
  }

  section ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: grid;
    gap: 0.75rem;
  }

  section li {
    background: #f7f7f7;
    border-radius: 0.5rem;
    padding: 0.85rem 1rem;
    transition: background 0.2s ease-in-out, transform 0.2s ease-in-out;
  }

  section li:hover,
  section li:focus-within {
    background: #ececec;
    transform: translateY(-1px);
  }

  section a {
    color: inherit;
    text-decoration: none;
    font-weight: 600;
  }
</style>
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_src_routes_map.md

**Größe:** 12 KB | **md5:** `eb60c487154ada91ef32bd64cc0a50d9`

```markdown
### 📄 weltgewebe/apps/web/src/routes/map/+page.svelte

**Größe:** 11 KB | **md5:** `0f7b4c6ce4041972ba19cf4b864d9e53`

```svelte
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import '$lib/styles/tokens.css';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import type { Map as MapLibreMap } from 'maplibre-gl';
  import TopBar from '$lib/components/TopBar.svelte';
  import Drawer from '$lib/components/Drawer.svelte';
  import TimelineDock from '$lib/components/TimelineDock.svelte';

  let mapContainer: HTMLDivElement | null = null;
  let map: MapLibreMap | null = null;

  let leftOpen = true;     // linke Spalte (Webrat/Nähstübchen)
  let rightOpen = false;   // Filter
  let topOpen = false;     // Gewebekonto

  type DrawerInstance = InstanceType<typeof Drawer> & {
    setOpener?: (el: HTMLElement | null) => void;
  };
  let rightDrawerRef: DrawerInstance | null = null;
  let topDrawerRef: DrawerInstance | null = null;
  let openerButtons: {
    left: HTMLButtonElement | null;
    right: HTMLButtonElement | null;
    top: HTMLButtonElement | null;
  } = { left: null, right: null, top: null };

  const defaultQueryState = { l: leftOpen, r: rightOpen, t: topOpen } as const;

  function setQuery(next: { l?: boolean; r?: boolean; t?: boolean }) {
    if (typeof window === 'undefined') return;
    const url = new URL(window.location.href);
    if (next.l !== undefined) {
      if (next.l === defaultQueryState.l) {
        url.searchParams.delete('l');
      } else {
        url.searchParams.set('l', next.l ? '1' : '0');
      }
    }
    if (next.r !== undefined) {
      if (next.r === defaultQueryState.r) {
        url.searchParams.delete('r');
      } else {
        url.searchParams.set('r', next.r ? '1' : '0');
      }
    }
    if (next.t !== undefined) {
      if (next.t === defaultQueryState.t) {
        url.searchParams.delete('t');
      } else {
        url.searchParams.set('t', next.t ? '1' : '0');
      }
    }
    history.replaceState(history.state, '', url);
  }

  function syncFromLocation() {
    if (typeof window === 'undefined') return;
    const q = new URLSearchParams(window.location.search);
    leftOpen = q.has('l') ? q.get('l') === '1' : defaultQueryState.l;
    rightOpen = q.has('r') ? q.get('r') === '1' : defaultQueryState.r;
    topOpen = q.has('t') ? q.get('t') === '1' : defaultQueryState.t;
  }

  function toggleLeft(){ leftOpen = !leftOpen; setQuery({ l: leftOpen }); }
  function toggleRight(){ rightOpen = !rightOpen; setQuery({ r: rightOpen }); }
  function toggleTop(){ topOpen = !topOpen; setQuery({ t: topOpen }); }

  type SwipeIntent =
    | 'open-left'
    | 'close-left'
    | 'open-right'
    | 'close-right'
    | 'open-top'
    | 'close-top';

  type SwipeState = {
    pointerId: number;
    intent: SwipeIntent;
    startX: number;
    startY: number;
  } | null;

  let swipeState: SwipeState = null;

  function startSwipe(e: PointerEvent, intent: SwipeIntent) {
    const allowMouse = (window as any).__E2E__ === true;
    if (e.pointerType !== 'touch' && e.pointerType !== 'pen' && !allowMouse) return;

    if (
      (intent === 'open-left' && leftOpen) ||
      (intent === 'close-left' && !leftOpen) ||
      (intent === 'open-right' && rightOpen) ||
      (intent === 'close-right' && !rightOpen) ||
      (intent === 'open-top' && topOpen) ||
      (intent === 'close-top' && !topOpen)
    ) {
      return;
    }

    swipeState = {
      pointerId: e.pointerId,
      intent,
      startX: e.clientX,
      startY: e.clientY
    };
  }

  function finishSwipe(e: PointerEvent) {
    if (!swipeState || swipeState.pointerId !== e.pointerId) return;

    const dx = e.clientX - swipeState.startX;
    const dy = e.clientY - swipeState.startY;
    const absX = Math.abs(dx);
    const absY = Math.abs(dy);
    const threshold = 60;
    const { intent } = swipeState;
    swipeState = null;

    switch (intent) {
      case 'open-left':
        if (!leftOpen && dx > threshold && absX > absY) {
          leftOpen = true;
          setQuery({ l: true });
        }
        break;
      case 'close-left':
        if (leftOpen && -dx > threshold && absX > absY) {
          leftOpen = false;
          setQuery({ l: false });
        }
        break;
      case 'open-right':
        if (!rightOpen && -dx > threshold && absX > absY) {
          rightOpen = true;
          setQuery({ r: true });
        }
        break;
      case 'close-right':
        if (rightOpen && dx > threshold && absX > absY) {
          rightOpen = false;
          setQuery({ r: false });
        }
        break;
      case 'open-top':
        if (!topOpen && dy > threshold && absY > absX) {
          topOpen = true;
          setQuery({ t: true });
        }
        break;
      case 'close-top':
        if (topOpen && -dy > threshold && absY > absX) {
          topOpen = false;
          setQuery({ t: false });
        }
        break;
    }
  }

  function cancelSwipe(e: PointerEvent) {
    if (swipeState && swipeState.pointerId === e.pointerId) {
      swipeState = null;
    }
  }

  function handleOpeners(
    event: CustomEvent<{
      left: HTMLButtonElement | null;
      right: HTMLButtonElement | null;
      top: HTMLButtonElement | null;
    }>
  ) {
    openerButtons = event.detail;
  }

  $: if (rightDrawerRef) {
    rightDrawerRef.setOpener?.(openerButtons.right ?? null);
  }
  $: if (topDrawerRef) {
    topDrawerRef.setOpener?.(openerButtons.top ?? null);
  }

  let keyHandler: ((e: KeyboardEvent) => void) | null = null;
  let popHandler: ((event: PopStateEvent) => void) | null = null;
  onMount(() => {
    const pointerUp = (event: PointerEvent) => finishSwipe(event);
    const pointerCancel = (event: PointerEvent) => cancelSwipe(event);
    window.addEventListener('pointerup', pointerUp);
    window.addEventListener('pointercancel', pointerCancel);

    syncFromLocation();
    popHandler = () => syncFromLocation();
    window.addEventListener('popstate', popHandler);

    (async () => {
      const maplibregl = await import('maplibre-gl');
      const container = mapContainer;
      if (!container) {
        return;
      }
      // Hamburg-Hamm grob: 10.05, 53.55 — Zoom 13
      map = new maplibregl.Map({
        container,
        style: 'https://demotiles.maplibre.org/style.json',
        center: [10.05, 53.55],
        zoom: 13
      });
      map.addControl(new maplibregl.NavigationControl({ showZoom:true }), 'bottom-right');

      keyHandler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          if (topOpen) {
            topOpen = false;
            setQuery({ t: false });
            return;
          }
          if (rightOpen) {
            rightOpen = false;
            setQuery({ r: false });
            return;
          }
          if (leftOpen) {
            leftOpen = false;
            setQuery({ l: false });
            return;
          }
        }
        if (e.key === '[') toggleLeft();
        if (e.key === ']') toggleRight();
        if (e.altKey && (e.key === 'g' || e.key === 'G')) toggleTop();
      };
      window.addEventListener('keydown', keyHandler);
    })();

    return () => {
      window.removeEventListener('pointerup', pointerUp);
      window.removeEventListener('pointercancel', pointerCancel);
      if (popHandler) window.removeEventListener('popstate', popHandler);
    };
  });
  onDestroy(() => {
    if (keyHandler) window.removeEventListener('keydown', keyHandler);
    if (popHandler) window.removeEventListener('popstate', popHandler);
    if (map && typeof map.remove === 'function') map.remove();
  });
</script>

<style>
  .shell{
    position:relative;
    height:100dvh;
    /* keep the raw dynamic viewport height as a fallback for browsers missing safe-area support */
    height:calc(100dvh - env(safe-area-inset-top) - env(safe-area-inset-bottom));
    width:100vw;
    overflow:hidden;
    background:var(--bg);
    color:var(--text);
    padding-top: env(safe-area-inset-top);
    padding-bottom: env(safe-area-inset-bottom);
  }
  #map{ position:absolute; inset:0; }
  #map :global(canvas){ filter: grayscale(0.2) saturate(0.75) brightness(1.03) contrast(0.95); }
  /* Swipe-Edge-Zonen über Tokens (OS-Gesten-freundlich) */
  .edge{ position:absolute; z-index:27; }
  .edge.left{ left:var(--edge-inset-x); top:80px; bottom:80px; width:var(--edge-left-width); touch-action: pan-y; }
  .edge.right{ right:var(--edge-inset-x); top:80px; bottom:80px; width:var(--edge-right-width); touch-action: pan-y; }
  .edge.top{ left:var(--edge-inset-x); right:var(--edge-inset-x); top:var(--edge-inset-top); height:var(--edge-top-height); touch-action: pan-x; }
  .edgeHit{ position:absolute; inset:0; }
  /* Linke Spalte: oben Webrat, unten Nähstübchen (hälftig) */
  .leftStack{
    position:absolute;
    left: var(--drawer-gap);
    top:calc(var(--toolbar-offset) + env(safe-area-inset-top));
    bottom:calc(var(--toolbar-offset) + env(safe-area-inset-bottom));
    width:var(--drawer-width);
    z-index:26;
    display:grid; grid-template-rows: 1fr 1fr; gap:var(--drawer-gap);
    transform: translateX(calc(-1 * var(--drawer-width) - var(--drawer-slide-offset)));
    transition: transform .18s ease;
  }
  .leftStack.open{ transform:none; }
  .panel{
    background:var(--panel); border:1px solid var(--panel-border); border-radius: var(--radius);
    box-shadow: var(--shadow); color:var(--text); padding:var(--drawer-gap); overflow:auto;
  }
  .panel h3{ margin:0 0 8px 0; font-size:14px; color:var(--muted); letter-spacing:.2px; }
  .muted{ color:var(--muted); font-size:13px; }
  @media (max-width: 900px){
    .leftStack{ --drawer-width: 320px; }
  }
  @media (max-width: 380px){
    .leftStack{ --drawer-width: 300px; }
  }
  @media (prefers-reduced-motion: reduce){
    .leftStack{ transition: none; }
  }
</style>

<div class="shell">
  <TopBar
    onToggleLeft={toggleLeft}
    onToggleRight={toggleRight}
    onToggleTop={toggleTop}
    {leftOpen}
    {rightOpen}
    {topOpen}
    on:openers={handleOpeners}
  />

  <!-- Linke Spalte: Webrat / Nähstübchen -->
  <div
    id="left-stack"
    class="leftStack"
    class:open={leftOpen}
    aria-hidden={!leftOpen}
    inert={!leftOpen ? true : undefined}
    on:pointerdown={(event) => startSwipe(event, 'close-left')}
  >
    <div class="panel">
      <h3>Webrat</h3>
      <div class="muted">Beratung, Anträge, Matrix (Stub)</div>
    </div>
    <div class="panel">
      <h3>Nähstübchen</h3>
      <div class="muted">Ideen, Entwürfe, Skizzen (Stub)</div>
    </div>
  </div>

  <!-- Rechter Drawer: Suche/Filter -->
  <Drawer
    bind:this={rightDrawerRef}
    id="filter-drawer"
    title="Suche & Filter"
    side="right"
    open={rightOpen}
    on:pointerdown={(event) => startSwipe(event, 'close-right')}
  >
    <div class="panel" style="padding:8px;">
      <div class="muted">Typ · Zeit · H3 · Delegation · Radius (Stub)</div>
    </div>
  </Drawer>

  <!-- Top Drawer: Gewebekonto -->
  <Drawer
    bind:this={topDrawerRef}
    id="account-drawer"
    title="Gewebekonto"
    side="top"
    open={topOpen}
    on:pointerdown={(event) => startSwipe(event, 'close-top')}
  >
    <div class="panel" style="padding:8px;">
      <div class="muted">Saldo / Delegationen / Verbindlichkeiten (Stub)</div>
    </div>
  </Drawer>

  <!-- Karte -->
  <div id="map" bind:this={mapContainer}></div>

  <div class="edge left" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-left')}>
    <div class="edgeHit"></div>
  </div>
  <div class="edge right" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-right')}>
    <div class="edgeHit"></div>
  </div>
  <div class="edge top" role="presentation" on:pointerdown={(event) => startSwipe(event, 'open-top')}>
    <div class="edgeHit"></div>
  </div>

  <!-- Zeitleiste -->
  <TimelineDock />
</div>
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_apps_web_tests.md

**Größe:** 4 KB | **md5:** `b19d2f6d8a20f074b3eb7245886826d7`

```markdown
### 📄 weltgewebe/apps/web/tests/drawers.spec.ts

**Größe:** 3 KB | **md5:** `ab97256041c7f0f44e14769a9bd338be`

```typescript
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  // Maus-Swipes in Tests erlauben
  await page.addInitScript(() => { (window as any).__E2E__ = true; });
  await page.goto('/map');
});

test('Esc schließt geöffnete Drawer (top → right → left)', async ({ page }) => {
  // Rechts öffnen
  await page.keyboard.press(']');
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeVisible();

  // Esc → schließt rechts
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeHidden();

  // Top öffnen
  await page.keyboard.press('Alt+g');
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeVisible();

  // Esc → schließt top
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeHidden();

  // Links öffnen
  await page.keyboard.press('[');
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();

  // Esc → schließt links (Stack)
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();
});

test('Swipe öffnet & schließt Drawer symmetrisch', async ({ page }) => {
  const map = page.locator('#map');

  // Linke Kante öffnen (drag→ rechts)
  const box = await map.boundingBox();
  if (!box) throw new Error('map not visible');
  const y = box.y + box.height * 0.5;

  // open left
  await page.mouse.move(box.x + 40, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 120, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeVisible();

  // close left (drag ←)
  await page.mouse.move(box.x + 140, y);
  await page.mouse.down();
  await page.mouse.move(box.x + 30, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Webrat' })).toBeHidden();

  // open right (drag ← an rechter Kante)
  const rx = box.x + box.width - 40;
  await page.mouse.move(rx, y);
  await page.mouse.down();
  await page.mouse.move(rx - 100, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeVisible();

  // close right (drag →)
  await page.mouse.move(rx - 120, y);
  await page.mouse.down();
  await page.mouse.move(rx + 20, y, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Suche & Filter' })).toBeHidden();

  // open top (drag ↓ nahe Top)
  const tx = box.x + box.width * 0.5;
  const ty = box.y + 40;
  await page.mouse.move(tx, ty);
  await page.mouse.down();
  await page.mouse.move(tx, ty + 120, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeVisible();

  // close top (drag ↑)
  await page.mouse.move(tx, ty + 140);
  await page.mouse.down();
  await page.mouse.move(tx, ty - 10, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByRole('heading', { name: 'Gewebekonto' })).toBeHidden();
});
```

### 📄 weltgewebe/apps/web/tests/map-smoke.spec.ts

**Größe:** 570 B | **md5:** `79a75ef59118015fac2b3427e2fc9b88`

```typescript
import { expect, test } from "@playwright/test";

test.describe("map route", () => {
  test("shows structure layer controls", async ({ page }) => {
    await page.goto("/map");

    const strukturknotenButton = page.getByRole("button", { name: "Strukturknoten" });
    await expect(strukturknotenButton).toBeVisible();
    await expect(strukturknotenButton).toBeDisabled();

    await expect(page.getByRole("button", { name: "Fäden" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Archiv ansehen" })).toHaveAttribute("href", "/archive/");
  });
});
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_ci.md

**Größe:** 555 B | **md5:** `454cf4b9b71c468e7644ca373c480a0c`

```markdown
### 📄 weltgewebe/ci/README.md

**Größe:** 200 B | **md5:** `d5d468659276cd627ef5d0055a942b75`

```markdown
# CI – Roadmap

- prose (vale)
- web (budgets)
- api (clippy/tests)
- security (trivy)

## CI (Platzhalter)

Diese Repo-Phase ist Docs-only. `ci/budget.json` dient als Referenz für spätere Gates.
```

### 📄 weltgewebe/ci/budget.json

**Größe:** 123 B | **md5:** `d1377d85d1cc1645b5f2440bb0d08f25`

```json
{
  "budgets": {
    "web": {
      "js_kb_max": 60,
      "tti_ms_p95_max": 2000,
      "inp_ms_p75_max": 200
    }
  }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_ci_scripts.md

**Größe:** 4 KB | **md5:** `9453de40db30535923a2bb3e52a75a91`

```markdown
### 📄 weltgewebe/ci/scripts/db-wait.sh

**Größe:** 498 B | **md5:** `4e3c7e73e15e8450e658938904534c12`

```bash
#!/usr/bin/env bash
set -euo pipefail

HOST=${PGHOST:-localhost}
PORT=${PGPORT:-5432}
TIMEOUT=${DB_WAIT_TIMEOUT:-60}
INTERVAL=${DB_WAIT_INTERVAL:-2}

declare -i end=$((SECONDS + TIMEOUT))

while (( SECONDS < end )); do
    if (echo >"/dev/tcp/${HOST}/${PORT}") >/dev/null 2>&1; then
        printf 'Postgres is available at %s:%s\n' "$HOST" "$PORT"
        exit 0
    fi
    sleep "$INTERVAL"
done

printf 'Timed out waiting for Postgres at %s:%s after %ss\n' "$HOST" "$PORT" "$TIMEOUT" >&2
exit 1
```

### 📄 weltgewebe/ci/scripts/validate_wgx_profile.py

**Größe:** 4 KB | **md5:** `53f8d63e9450ddffc57ceff725f860ee`

```python
# SPDX-License-Identifier: MIT
# -*- coding: utf-8 -*-

"""Validate the minimal schema for ``.wgx/profile.yml``.

The wgx-guard workflow embeds this script and previously relied on an inline
Python snippet. A subtle indentation slip in that snippet caused
``IndentationError`` failures in CI.  To make the validation robust we keep the
logic in this dedicated module and ensure the implementation is intentionally
simple and well formatted.
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import sys
from types import ModuleType
from collections.abc import Iterable, Mapping


REQUIRED_TOP_LEVEL_KEYS = ("version", "env_priority", "tooling", "tasks", "wgx")
REQUIRED_WGX_KEYS = ("org",)
REQUIRED_TASKS = ("up", "lint", "test", "build", "smoke")


def _error(message: str) -> None:
    """Emit a GitHub Actions friendly error message."""

    print(f"::error::{message}")


def _missing_keys(data: Mapping[str, object], keys: Iterable[str]) -> list[str]:
    return [key for key in keys if key not in data]


def _load_yaml_module() -> ModuleType | None:
    existing = sys.modules.get("yaml")
    if isinstance(existing, ModuleType) and hasattr(existing, "safe_load"):
        return existing

    module = importlib.util.find_spec("yaml")
    if module is None:
        _error(
            "PyYAML not installed. Install it with 'python -m pip install pyyaml' before running this script."
        )
        return None

    return importlib.import_module("yaml")


def main() -> int:
    yaml = _load_yaml_module()
    if yaml is None:
        return 1

    profile_path = pathlib.Path(".wgx/profile.yml")

    try:
        contents = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        _error(".wgx/profile.yml missing")
        return 1

    try:
        data = yaml.safe_load(contents) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - best effort logging
        _error(f"failed to parse YAML: {exc}")
        return 1

    if not isinstance(data, dict):
        _error("profile must be a mapping")
        return 1

    missing_top_level = _missing_keys(data, REQUIRED_TOP_LEVEL_KEYS)
    if missing_top_level:
        _error(f"missing keys: {missing_top_level}")
        return 1

    env_priority = data.get("env_priority")
    if not isinstance(env_priority, list) or not env_priority:
        _error("env_priority must be a non-empty list")
        return 1

    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        _error("tasks must be a mapping")
        return 1

    missing_tasks = _missing_keys(tasks, REQUIRED_TASKS)
    if missing_tasks:
        _error(f"missing tasks: {missing_tasks}")
        return 1

    wgx_block = data.get("wgx")
    if not isinstance(wgx_block, dict):
        _error("wgx must be a mapping")
        return 1

    missing_wgx = _missing_keys(wgx_block, REQUIRED_WGX_KEYS)
    if missing_wgx:
        _error(f"wgx missing keys: {missing_wgx}")
        return 1

    org = wgx_block.get("org")
    if not isinstance(org, str) or not org.strip():
        _error("wgx.org must be a non-empty string")
        return 1

    meta = data.get("meta")
    if isinstance(meta, dict) and "owner" in meta:
        owner = meta.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            _error("meta.owner must be a non-empty string when provided")
            return 1
        if owner != org:
            _error(f"meta.owner ({owner!r}) must match wgx.org ({org!r})")
            return 1

    print("wgx profile OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_configs.md

**Größe:** 645 B | **md5:** `f75ddbb1a65eef882c75f3e051f3827a`

```markdown
### 📄 weltgewebe/configs/README.md

**Größe:** 323 B | **md5:** `5f291886a54691e71197bd288d398c5f`

```markdown
# Konfigurationsdefaults

`configs/app.defaults.yml` liefert die Basiswerte für die API. Zur Laufzeit können
Deployments eine alternative YAML-Datei via `APP_CONFIG_PATH` angeben oder einzelne
Felder mit `HA_*`-Variablen überschreiben (`HA_FADE_DAYS`, `HA_RON_DAYS`,
`HA_ANONYMIZE_OPT_IN`, `HA_DELEGATION_EXPIRE_DAYS`).
```

### 📄 weltgewebe/configs/app.defaults.yml

**Größe:** 76 B | **md5:** `2e2703e5a92b04e9d68b1ab93b336039`

```yaml
fade_days: 7
ron_days: 84
anonymize_opt_in: true
delegation_expire_days: 28
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_contracts_semantics.md

**Größe:** 2 KB | **md5:** `d46d516a54004c443d05986897df6dd2`

```markdown
### 📄 weltgewebe/contracts/semantics/.upstream

**Größe:** 54 B | **md5:** `5b69f8d0a21f4d7ad4719b99f0873d62`

```plaintext
repo: semantAH
path: contracts/semantics
mode: mirror
```

### 📄 weltgewebe/contracts/semantics/README.md

**Größe:** 111 B | **md5:** `01d4ab919007afe03e6aa996c9b3b3ae`

```markdown
# Semantik-Verträge (Upstream: semantAH)

Quelle: externer Ableger `semantAH`. Nicht editieren, nur spiegeln.
```

### 📄 weltgewebe/contracts/semantics/edge.schema.json

**Größe:** 302 B | **md5:** `8f92b25fdd52e7dc7a589f36c9ed0a3a`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemEdge","type":"object",
  "required":["src","dst","rel"],
  "properties":{"src":{"type":"string"},"dst":{"type":"string"},"rel":{"type":"string"},
    "weight":{"type":"number"},"why":{"type":"string"},"updated_at":{"type":"string"}}
}
```

### 📄 weltgewebe/contracts/semantics/node.schema.json

**Größe:** 358 B | **md5:** `8a55023fb9d91f644833dbcd7243011b`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemNode","type":"object",
  "required":["id","type","title"],
  "properties":{"id":{"type":"string"},"type":{"type":"string"},
    "title":{"type":"string"},"tags":{"type":"array","items":{"type":"string"}},
    "source":{"type":"string"},"updated_at":{"type":"string","format":"date-time"}}
}
```

### 📄 weltgewebe/contracts/semantics/report.schema.json

**Größe:** 311 B | **md5:** `66113d119045d16fdbfdba885d82fb73`

```json
{ "$schema":"http://json-schema.org/draft-07/schema#", "title":"SemReport","type":"object",
  "required":["kind","created_at"],
  "properties":{"kind":{"type":"string"},"created_at":{"type":"string","format":"date-time"},
    "notes":{"type":"array","items":{"type":"string"}},
    "stats":{"type":"object"}}
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs.md

**Größe:** 73 KB | **md5:** `6261c5d1b86fbfb3d85d8fe7d102b52e`

```markdown
### 📄 weltgewebe/docs/README.md

**Größe:** 372 B | **md5:** `d97277ef89d096355ecc33689f5e89a9`

```markdown
# Weltgewebe – Doku-Index

– **Start:** architekturstruktur.md
– **Techstack:** techstack.md
– **Prozess & Fahrplan:** process/README.md
– **ADRs:** adr/
– **Runbooks:** runbooks/README.md
– **Glossar:** glossar.md
– **Inhalt/Story:** inhalt.md, zusammenstellung.md
– **X-Repo Learnings:** x-repo/peers-learnings.md
– **Beitragen:** ../CONTRIBUTING.md
```

### 📄 weltgewebe/docs/architekturstruktur.md

**Größe:** 6 KB | **md5:** `b5ceafe29f2d968072fa413f468ba026`

```markdown
Weltgewebe – Repository-Struktur

Dieses Dokument beschreibt den Aufbau des Repositories.
Ziel: Übersicht für Entwickler und KI, damit alle Beiträge am richtigen Ort landen.

⸻

ASCII-Baum

weltgewebe/weltgewebe-repo/
├─ apps/                       # Anwendungen (Business-Code)
│  ├─ web/                      # SvelteKit-Frontend (PWA, MapLibre)
│  │  ├─ src/
│  │  │  ├─ routes/             # Seiten, Endpunkte (+page.svelte/+server.ts)
│  │  │  ├─ lib/                # UI-Komponenten, Stores, Utilities
│  │  │  ├─ hooks.client.ts     # RUM-Initialisierung (LongTasks)
│  │  │  └─ app.d.ts            # App-Typdefinitionen
│  │  ├─ static/                # Fonts, Icons, manifest.webmanifest
│  │  ├─ tests/                 # Frontend-Tests (Vitest, Playwright)
│  │  ├─ svelte.config.js
│  │  ├─ vite.config.ts
│  │  └─ README.md
│  │
│  ├─ api/                      # Rust (Axum) – REST + SSE
│  │  ├─ src/
│  │  │  ├─ main.rs             # Einstiegspunkt, Router
│  │  │  ├─ routes/             # HTTP- und SSE-Endpunkte
│  │  │  ├─ domain/             # Geschäftslogik, Services
│  │  │  ├─ repo/               # SQLx-Abfragen, Postgres-Anbindung
│  │  │  ├─ events/             # Outbox-Publisher, Eventtypen
│  │  │  └─ telemetry/          # Prometheus/OTel-Integration
│  │  ├─ migrations/            # Datenbankschemata, pg_partman
│  │  ├─ tests/                 # API-Tests (Rust)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
│  ├─ worker/                   # Projector/Indexer/Jobs
│  │  ├─ src/
│  │  │  ├─ projector_timeline.rs # Outbox→Timeline-Projektion
│  │  │  ├─ projector_search.rs   # Outbox→Search-Indizes
│  │  │  └─ replayer.rs           # Rebuilds (DSGVO/DR)
│  │  ├─ Cargo.toml
│  │  └─ README.md
│  │
│  └─ search/                   # (optional) Such-Adapter/SDKs
│     ├─ adapters/              # Typesense/Meili-Clients
│     └─ README.md
│
├─ packages/                    # (optional) Geteilte Libraries/SDKs
│  └─ README.md
│
├─ infra/                       # Betrieb/Deployment/Observability
│  ├─ compose/                  # Docker Compose Profile
│  │  ├─ compose.core.yml       # Basis-Stack: web, api, db, caddy
│  │  ├─ compose.observ.yml     # Monitoring: Prometheus, Grafana, Loki/Tempo
│  │  ├─ compose.stream.yml     # Event-Streaming: NATS/JetStream
│  │  └─ compose.search.yml     # Suche: Typesense/Meili, KeyDB
│  ├─ caddy/
│  │  ├─ Caddyfile              # Proxy, HTTP/3, CSP, TLS
│  │  └─ README.md
│  ├─ db/
│  │  ├─ init/                  # SQL-Init-Skripte, Extensions (postgis, h3)
│  │  ├─ partman/               # Partitionierung (pg_partman)
│  │  └─ README.md
│  ├─ monitoring/
│  │  ├─ prometheus.yml         # Prometheus-Konfiguration
│  │  ├─ grafana/
│  │  │  ├─ dashboards/         # Web-Vitals, JetStream, Edge-Kosten
│  │  │  └─ alerts/             # Alarme: Opex, Lag, LongTasks
│  │  └─ README.md
│  ├─ nomad/                    # (optional) Orchestrierungsspezifikationen
│  └─ k8s/                      # (optional) Kubernetes-Manifeste
│
├─ docs/                        # Dokumentation & Entscheidungen
│  ├─ adr/                      # Architecture Decision Records
│  ├─ techstack.md              # Techstack v3.2 (Referenz)
│  ├─ architektur.ascii         # Architektur-Poster/ASCII-Diagramme
│  ├─ datenmodell.md            # Datenbank- und Projektionstabellen
│  └─ runbook.md                # Woche-1/2 Setup, DR/DSGVO-Drills
│
├─ ci/                          # CI/CD & Qualitätsprüfungen
│  ├─ github/
│  │  └─ workflows/             # GitHub Actions für Build, Tests, Infra
│  │     ├─ web.yml
│  │     ├─ api.yml
│  │     └─ infra.yml
│  ├─ scripts/                  # Hilfsskripte (migrate, seed, db-wait)
│  └─ budget.json               # Performance-Budgets (≤60KB JS, ≤2s TTI)
│
├─ .env.example                 # Beispiel-Umgebungsvariablen
├─ .editorconfig                # Editor-Standards
├─ .gitignore                   # Ignorier-Regeln
├─ LICENSE                      # Lizenztext
└─ README.md                    # Projektüberblick, Quickstart

⸻

Erläuterungen zu den Hauptordnern

- **apps/**
  Enthält alle Anwendungen: Web-Frontend (SvelteKit), API (Rust/Axum), Worker (Eventprojektionen, Rebuilds) und
  optionale Search-Adapter. Jeder Unterordner ist eine eigenständige App mit eigenem README und Build-Konfig.
- **packages/**
  Platz für geteilte Libraries oder SDKs, die von mehreren Apps genutzt werden. Wird erst angelegt, wenn Bedarf an
  gemeinsamem Code entsteht.
- **infra/**
  Infrastruktur- und Deployment-Ebene. Compose-Profile für verschiedene Betriebsmodi, Caddy-Konfiguration,
  DB-Init, Monitoring-Setup. Optional Nomad- oder Kubernetes-Definitionen für spätere Skalierung.
- **docs/**
  Dokumentation und Architekturentscheidungen. Enthält ADRs, Techstack-Beschreibung, Diagramme,
  Datenmodellübersicht und Runbooks.
- **ci/**
  Alles rund um Continuous Integration/Deployment: Workflows für GitHub Actions, Skripte für Tests/DB-Handling,
  sowie zentrale Performance-Budgets (Lighthouse).
- **Root**
  Repository-Metadaten: .env.example (Vorlage), Editor- und Git-Configs, Lizenz und README mit Projektüberblick.

⸻

Zusammenfassung

Diese Struktur spiegelt den aktuellen Techstack (v3.2) wider:

- Mobil-first via PWA (SvelteKit).
- Rust/Axum API mit Outbox/JetStream-Eventing.
- Compose-first Infrastruktur mit klar getrennten Profilen.
- Observability und Compliance fest verankert.
- Erweiterbar durch optionale packages/, nomad/, k8s/.

Dies dient als Referenzrahmen für alle weiteren Arbeiten am Weltgewebe-Repository.
```

### 📄 weltgewebe/docs/datenmodell.md

**Größe:** 4 KB | **md5:** `40e5e1201281b9d2cf8e6928c999fffb`

```markdown
# Datenmodell

Dieses Dokument beschreibt das Datenmodell der Weltgewebe-Anwendung, das auf PostgreSQL aufbaut.
Es dient als Referenz für Entwickler, um die Kernentitäten, ihre Beziehungen und die daraus
abgeleiteten Lese-Modelle zu verstehen.

## Grundprinzipien

- **Source of Truth:** PostgreSQL ist die alleinige Quelle der Wahrheit.
- **Transaktionaler Outbox:** Alle Zustandsänderungen werden transaktional in die `outbox`-Tabelle
  geschrieben, um eine konsistente Event-Verteilung an nachgelagerte Systeme (z.B. via NATS
  JetStream) zu garantieren.
- **Normalisierung:** Das Schreib-Modell ist normalisiert, um Datenintegrität zu gewährleisten.
  Lese-Modelle (Projektionen/Views) sind für spezifische Anwendungsfälle denormalisiert und
  optimiert.
- **UUIDs:** Alle Primärschlüssel sind UUIDs (`v4`), um eine verteilte Generierung zu
  ermöglichen und Abhängigkeiten von sequenziellen IDs zu vermeiden.

---

## Tabellen (Schreib-Modell)

### `nodes`

Speichert geografische oder logische Knotenpunkte, die als Anker für Threads dienen.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Knotens. |
| `location` | `geography(Point, 4326)` | Geografischer Standort (Längen- und Breitengrad). |
| `h3_index`| `bigint` | H3-Index für schnelle geografische Abfragen. |
| `name` | `text` | Anzeigename des Knotens. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `roles`

Verwaltet Benutzer- oder Systemrollen, die Berechtigungen steuern.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator der Rolle. |
| `user_id` | `uuid` (FK) | Referenz zum Benutzer (externes System). |
| `permissions` | `jsonb` | Berechtigungen der Rolle als JSON-Objekt. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

### `threads`

Repräsentiert die Konversationen oder "Fäden", die an Knoten gebunden sind.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Threads. |
| `node_id` | `uuid` (FK, `nodes.id`) | Zugehöriger Knoten. |
| `author_role_id` | `uuid` (FK, `roles.id`) | Ersteller des Threads. |
| `title` | `text` | Titel des Threads. |
| `content` | `text` | Inhalt des Threads (z.B. erster Beitrag). |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
| `updated_at` | `timestamptz` | Zeitstempel der letzten Änderung. |

### `outbox`

Implementiert das Transactional Outbox Pattern für zuverlässige Event-Publikation.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `id` | `uuid` (PK) | Eindeutiger Identifikator des Events. |
| `aggregate_type` | `text` | Typ des Aggregats (z.B. "thread"). |
| `aggregate_id` | `uuid` | ID des betroffenen Aggregats. |
| `event_type` | `text` | Typ des Events (z.B. "thread.created"). |
| `payload` | `jsonb` | Event-Daten. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |

---

## Projektionen (Lese-Modelle)

Diese Views sind für die Lese-Performance optimiert und fassen Daten aus mehreren Tabellen zusammen.
Sie werden von den Workern (Projektoren) asynchron aktualisiert.

### `public_role_view`

Eine denormalisierte Sicht auf Rollen, die nur öffentlich sichtbare Informationen enthält.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `role_id` | `uuid` | Identifikator der Rolle. |
| `display_name` | `text` | Öffentlich sichtbarer Name (ggf. aus einem externen User-Service). |
| `avatar_url` | `text` | URL zu einem Avatar-Bild. |

### `faden_view`

Eine zusammengefasste Ansicht von Threads für die schnelle Darstellung in der Benutzeroberfläche.

| Spalte | Typ | Beschreibung |
|---|---|---|
| `thread_id` | `uuid` | Identifikator des Threads. |
| `node_id` | `uuid` | Zugehöriger Knoten. |
| `node_name` | `text` | Name des zugehörigen Knotens. |
| `author_display_name` | `text` | Anzeigename des Autors. |
| `title` | `text` | Titel des Threads. |
| `comment_count` | `integer` | Anzahl der Kommentare (wird vom Projektor berechnet). |
| `last_activity_at` | `timestamptz` | Zeitstempel der letzten Aktivität. |
| `created_at` | `timestamptz` | Zeitstempel der Erstellung. |
```

### 📄 weltgewebe/docs/geist und plan.md

**Größe:** 12 KB | **md5:** `02c86341270901daedfb5e5634e4493f`

```markdown
Hier ist eine (meinerseits strukturierte) Analyse und Extraktion des „Geistes und Plans“ der Weltweberei basierend auf der Website weltweberei.org. Ich ziehe aus den öffentlich verfügbaren Texten, sortiere nach Themen und ziehe Schlussfolgerungen — du kannst damit weiterarbeiten oder ich helfe dir beim Verdichten / Operationalisieren.

⸻

1. Einleitende, normative Aussagen – der Geist

Diese Passagen geben dir Einsicht in die philosophische / normative Grundhaltung hinter dem Projekt:
	•	Der Name Weltweberei legt den Fokus auf Verflechtung, Weben, Verknüpfen („weben der welt, wie es jedem (!) gefällt“)
	•	Es handelt sich um ein Konzept eines „sichtbaren, gemeinschaftlich ausgehandelten Zusammenwirkens von Nachbarschaften, versammelt um ein gemeinsames Konto“.
	•	Die Teilhabe ist ausdrücklich offen und frei: „anschauen kostet nichts, beitreten … auch nichts, dabei sein auch nicht – nichts kostet irgendetwas.“
	•	Es besteht eine Intention zur freiwilligen Gegenseitigkeit: man kann von Gemeinschaftsressourcen profitieren, aber auch zurückgeben, in welcher Form man will.
	•	Transparenz und Freiwilligkeit sind zentral, insbesondere in Bezug auf Daten: keine Datenerhebung ohne dein Einverständnis, kein Tracking, keine automatische Profilbildung. Nur das, was du freiwillig sichtbar machst, erscheint öffentlich.
	•	Die Struktur ist bewusst offen, flexibel und änderbar: „alles ist jederzeit kollektiv aushandelbar – alles!“
	•	Der Weg ist offen / ergebnisoffen: „der Weg ist das Ziel!“
	•	Es gibt einen utopischen Horizont: ein global anschlussfähiges Netz von Ortszellen, überregionale Zusammenschlüsse ohne Entmachtung der lokalen Zellen, und sogar die Vision eines Ausstiegs aus dem vorherrschenden Geldsystem als denkbare Zukunft.

Kurz gesagt: Der Geist ist partizipativ, dezentral, transparent, nicht-hierarchisch, offen verhandelbar und zukunftsgerichtet. Es geht um kollektive Selbstorganisation, Verantwortung und Autonomie in einem vernetzten Raum.

⸻

2. Funktionale / strukturelle Elemente – der Plan (in Ansätzen)

Neben dem Geist gibt es auf der Website Hinweise auf konkrete Strukturen und Konzepte, wie man dieses Ideal operationalisieren möchte:

Baustein	Zweck / Idee	Bemerkungen & Herausforderungen
Weltgewebe / Karte	Die Plattform oder Leinwand, auf der Aktionen, Wünsche, Kommentare und Verantwortungsübernahmen visualisiert werden.	Hier liegt ein Kern bei dir: wie visualisiert man Fäden, Knoten, Wechselwirkungen?
Ortsgewebekonto	Jedes “Ortsweberei” hat ein gemeinsames Konto, auf das Spenden eingehen und von dem Auszahlungen per Antrag möglich sind – und das im Netz (Karte) sichtbar ist.	Governance von Konten, Transparenz, Zugriffssteuerung, Antragssysteme sind zu designen
Partizipartei / Mandatssystem	Politischer Arm der Ortswebereien: “Fadenträger” fungieren als Mandatsträger, „Fadenreicher“ als Vermittler / Sekretäre. Ihre Arbeit wird öffentlich (gestreamt), Input kann live durch Community eingegeben werden (gefiltert via Up/Down-Voting, Plattform-KI). Stimmen können delegiert (transitär) werden.	Das Mandats- und Delegationssystem muss wasserdicht und nachvollziehbar gestaltet sein (Spielregeln, Sicherheit, Sybil-Schutz etc.).
Skalierbarkeit und Föderation	Ortswebereien sind Zellen; überregionale Bündnisse könnten gemeinsame Konten bilden, aber ohne die Basis zu entmachten. Lokale Entscheidungen bleiben vorherrschend.	Die Herausforderung einer föderalen Architektur mit Rückbindung und Reversibilität ist zentral.
Offene Anpassbarkeit	Jedes Element (Funktionen, Posten, Regeln) kann per Antrag verändert werden — also ein Meta-System zur Änderung der Regeln selbst.	Du brauchst ein Metagovernance-Modul: Regeln über Regeln.
Technische Infrastruktur & Datenschutz	Minimale Datenerhebung, nur das, was Nutzer:innen freiwillig veröffentlichen; temporäres Speichern von Serverlogs; keine automatische Profilbildung.	Datenschutz-Design, Sicherheit, Datenportabilität und Löschbarkeit müssen von Anfang an eingebaut sein.
Visionärer Horizont	In größeren Skalen kann man über Ausstieg aus dem Geldsystem, Verfassungsfragen, kollektive Selbstbestimmung nachdenken.	Diese Visionen sind (im Moment) noch eher hypothetisch. Du musst definieren, wie man von der Basis dorthin gelangen könnte.


⸻

3. Risiken, Widersprüche und offene Fragen

Damit du beim Weiterentwickeln gewappnet bist, hier ein paar erkennbare Spannungen oder Herausforderungen:
	1.	Governance vs. Skalierung — je größer das Netzwerk, desto höher ist die Gefahr von Koordinationsproblemen, Trittbrettfahrern, Machtkonzentration.
	2.	Sicherheit & Identitätsprobleme — wie verhinderst du Sybil-Attacken (falsche Mehrfachidentitäten), wie verifizierst du Mitgliedschaften, wie schützt du sensible Daten?
	3.	Effizienz vs. Inklusivität — partizipative Prozesse sind oft langsamer; wie verhinderst du Blockaden?
	4.	Delegation von Stimmen — das Modell ist spannend (Liquid Democracy), aber praktisch schwierig: wie oft darf delegiert werden, wie lange, wie wird Transparenz gewährleistet?
	5.	Konten & Geldflüsse — wie schafft man Sicherheit, Vertrauen und Transparenz in Finanztransaktionen über dezentrale Komponenten?
	6.	Technische Komplexität — Visualisierung von Geweben, Echtzeit-Interaktion, Skalierung, Datenschutz: das sind keine einfachen Aufgaben.
	7.	Motivations & Engagement-Problem — viele Projekte scheitern daran, dass die Community nicht dauerhaft aktiv bleibt.
	8.	Zwischen Vision und Implementierung — manche Visionen (z. B. Ausstieg aus dem Geldsystem) sind ambitioniert; der Übergang muss sorgfältig gestaltet werden.

⸻

4. Mein zusammengefasster “Geist & Plan” (in deiner Sprache, für deine Nutzung)

Wenn ich das für dein Projekt (Weltgewebe) zusammenfasse, um es nutzbar zu machen:
	•	Geist: Freiheit, Gemeinschaft, Transparenz, Verantwortung, partizipative Autonomie. Ein Raum, in dem Menschen freiwillig ihre Intentionen einbringen, sich verflechten und zusammenwirken, ohne dominante Hierarchien, und in dem Veränderung offen verhandelbar ist.
	•	Plan (Architektur):
	1.	Ein interaktives Karten-/Netzwerkinterface (Weltgewebe), das sichtbar macht, wie Menschen handeln, wünschen, Verantwortung übernehmen.
	2.	Lokale Zellen (“Ortswebereien”) mit eigenen Gemeinschaftskonten, Antragsprozessen und Governance.
	3.	Ein Mandats-/Delegationssystem (Partizipartei), um kollektive Entscheidungen zu treffen, bei maximaler Transparenz (z. B. Streaming, Chat & Voting).
	4.	Eine federative Struktur, die lokale Autonomie bewahrt, aber überregionale Kooperation erlaubt.
	5.	Ein Metasystem zur Anpassung und Veränderung von Regeln („Regeln über Regeln“) durch die Gemeinschaft.
	6.	Ein strenger Datenschutzansatz: nur selbsteingetragene Daten sichtbar, keine Profilbildung, Nutzerkontrolle über ihre Daten.
	7.	Ein visionärer Horizont, in dem globale Skalierung, alternative Wirtschaftsformen oder Systemwechsel denkbar sind — freilich erst als langfristige Option.

⸻

es geht vor allem um koordination von gemeinschaftsaktionen und -interessen: jemand möchte etwas auf die beine stellen, knüpft auf der karte am ort des geplanten handelns einen knoten, beispiel: gemeinsam grillen im park (parkspeise) am donnerstag um 17 uhr. dieser von ihm geknüpfte knoten wird automatisch per faden mit seiner rolle verknüpft (da er urheber ist), es entsteht dort neben den angelegten informationen ein gesprächsraum. andere, die durch diese visuelle plandarstellung auf das angebot aufmerksam geworden sind, können sich nun am gespräch darüber beteiligen oder zusagen etc.. jede aktion eines webers (eingeloggter nutzer) spinnt ebenso automatisch einen faden von dessen rolle zum jeweiligen knoten. kommt es nun zur parkspeise, gibt es natürlich für jedermann die möglichkeit etwas in die gemeinschaftskasse (gewebekonto) zu spenden - als eine art energieausgleich. möchte der urheber nun etwas aus dem gewebekonto erhalten (er hatte schließlich ausgaben etc.), dann muss er einen antrag auf auszahlung aus dem konto stellen.dies wird visualisiert durch einen antragsfaden auf das konto (eigener knoten auf der karte) inkl. 7 tage timer. kein einspruch eines anderen webers innerhalb der frist: auszahlung wird autorisiert. bei einspruch: verlängerung der entscheidung um weitere 7 tage mit anschließender abstimmung.


anderes praxisbeispiel: jeder kann die ressourcen, die er der gemeinschaft zur verfügung stellen will auf seiner garnrolle oder auf entsprechend verorteten knoten hinterlegen. sucht nun jemand nach beispielsweise einem schlafplatz, dann werden ihm alle in der umgebung angezeigt.

Kontextuelle Einordnung

Du hast Dateien hochgeladen, die Philosophie, Struktur und Tech-Stack des Weltgewebes dokumentieren:
	•	inhalt.md: Konzept + Funktionsweise
	•	zusammenstellung.md: systematische Zusammenfassung (Grundprinzipien, Domänenmodell, Governance)
	•	architekturstruktur.md: Repo-Struktur für Entwickler
	•	techstack.md: detaillierter Technologie-Stack

Damit liegt so etwas wie die DNA der Weltweberei vor: Vision, Plan, Architektur und konkrete technische Umsetzung.

⸻

Extraktion: Geist der Weltweberei
	•	Verflechtung als Leitmotiv: alles wird als Knoten und Fäden sichtbar, von Menschen bis Ressourcen.
	•	Radikale Transparenz & Freiwilligkeit: jede Handlung ein sichtbares Event, aber ohne verstecktes Tracking.
	•	Commons-Orientierung: keine künstliche Währung; Engagement und eingebrachte Ressourcen sind die „Währung“.
	•	Vergänglichkeit und Verzwirnung: Fäden verblassen, nur verzwirnte Inhalte werden dauerhaft – Dynamik statt Archivlast.
	•	Demokratische Prozesse: 7+7-Tage-Modell für Anträge, Liquid Democracy mit temporären Delegationen, offene Abstimmungen.
	•	Freiheit + Absicherung: jeder kann Ressourcen freigeben oder Aktionen starten, Anträge werden nur blockiert, wenn Widerspruch entsteht.
	•	Datenschutz: Privacy by Design, RoN-System für Anonymisierung, Unschärferadien für Ortsdaten.

⸻

Extraktion: Plan der Weltweberei
	1.	Domänenmodell
	•	Nutzer = Garnrollen (mit privatem und öffentlichem Bereich).
	•	Inhalte = Knoten (Ereignisse, Ressourcen, Ideen).
	•	Verbindungen = Fäden (Gespräch, Antrag, Delegation, Spende, etc.).
	2.	Funktionale Module
	•	Gewebekonto: Finanzverwaltung, sichtbar als Goldfäden.
	•	Webrat: Governance-Ort für Anträge, Abstimmungen, Delegationen.
	•	Nähstübchen: allgemeine Kommunikation.
	•	RoN-Platzhalter: Sammelstelle für anonymisierte Inhalte.
	3.	Zeitlichkeit & Prozesse
	•	7-Sekunden Sichtbarkeit bei Aktionen.
	•	7-Tage-Timer für Fäden, Knoten, Anträge.
	•	Verlängerung um 7 Tage bei Einspruch → Abstimmung.
	4.	Organisation
	•	Lokale Ortswebereien mit eigenen Konten.
	•	Föderation mehrerer Ortswebereien möglich.
	5.	Technik
	•	Frontend: SvelteKit, MapLibre, PWA.
	•	Backend: Rust (Axum), PostgreSQL + PostGIS + h3, Event-Outbox, NATS JetStream.
	•	Suche: Typesense / MeiliSearch.
	•	Infrastruktur: Nomad, Caddy (HTTP/3), PgBouncer.
	•	Observability: Prometheus, Grafana, Loki, Tempo.
	•	Security: SBOM, Signaturen, DSGVO-Forget-Pipeline, Key-Rotation.
	•	Kostenkontrolle: FinOps-KPIs (€/Session, €/GB Traffic).

⸻

Essenz-Kristall

👉 Die Weltweberei ist eine kartenbasierte Demokratie-Engine: jede Handlung wird als Faden sichtbar, jeder Knoten ist Raum für Aktionen oder Ressourcen, alle Prozesse laufen transparent, freiwillig, temporär und verhandelbar – technisch abgesichert durch Event-Sourcing, föderierbar in Ortsgeweben und getragen von einem klaren DSGVO-Privacy-by-Design.

⸻

Ironische Auslassung

„Früher musste man Plakate drucken und Flugblätter verteilen, um Nachbarn zum Grillen oder Couch-Sharing zu überreden – heute genügt ein Knoten auf der Karte. Demokratie trifft Picknick, mit JetStream und PgBouncer als unsichtbare Grillanzünder.“

⸻

∴fores Ungewissheit
	•	Grad: niedrig–mittel (30–40 %).
	•	Ursachen:
	•	Soziale Dynamik (wie dauerhaft beteiligen sich Leute?).
	•	Governance im Konfliktfall (Abstimmungen bei Missbrauch, Streit über Ressourcen).
	•	Technische Skalierung (Last > 100k Nutzer, Kostenpfad).
	•	Meta-Reflexion: viele Prinzipien sind definiert, aber die echte Bewährung liegt in der Praxis.

⸻

Kontrastvektor

Noch nicht thematisiert:
	•	Konfliktlösung jenseits Abstimmungen (z. B. Mediation).
	•	Schnittstellen zu externen Systemen (öffentliche Verwaltung, lokale Initiativen).
	•	Umgang mit kulturellen Unterschieden bei Föderation globaler Ortswebereien.

⸻
```

### 📄 weltgewebe/docs/glossar.md

**Größe:** 335 B | **md5:** `e1e1c4e097e48c0046706204cbb58a0d`

```markdown
# Glossar

**Rolle** (Garnrolle): auf Wohnsitz verorteter Account.
**Knoten:** lokalisierte Informationsbündel (Idee, Termin, Ort, Werkzeug…).
**Faden/Garn:** temporäre/persistente Verbindung Rolle→Knoten (Verzwirnung = Garn).
**RoN:** Rolle ohne Namen (Anonymisierung).
**Unschärferadius:** Öffentliche Genauigkeit in Metern.
```

### 📄 weltgewebe/docs/inhalt.md

**Größe:** 9 KB | **md5:** `aa4c1484b00984a155cf4eb98cdf4fb1`

```markdown
# Inhalt (MANDATORISCH)

## Was bedeutet Weltweberei?

welt = althochdeutsch weralt = menschenzeitalter
weben = germanisch webaną, indogermanisch webʰ- = flechten, verknüpfen, bewegen

Guten Tag,

schön, dass du hergefunden hast! Tritt gerne ein in unser Weltgewebe oder schau dir erstmal an, um was es
hier überhaupt geht.

Anschauen kostet nichts, beitreten (bald erst möglich) auch nicht, dabei sein auch nicht, nichts kostet
irgendetwas. Du kannst nach eigenem Ermessen und kollektiven Gutdünken von diesem Netzwerk an gemeinsamen
Ressourcen profitieren, bist gleichzeitig aber natürlich ebenso frei der Gemeinschaft etwas von dir
zurückzugeben – was auch immer, wie auch immer.

Weltweberei ist der Name dieses Konzeptes eines sichtbaren, gemeinschaftlich ausgehandelten Zusammenwirkens
von Nachbarschaften, versammelt um ein gemeinsames Konto. weltgewebe.net ist die Leinwand (Karte), auf der
die jeweiligen Aktionen, Wünsche, Kommentare und Verantwortungsübernahmen der Weltweber visualisiert werden
– als dynamisch sich veränderndes Geflecht von Fäden und Knoten.

## Wie funktioniert das Weltgewebe?

Jeder kann auf dem Weltgewebe (Online-Karte) alles einsehen. Wer sich mit Namen und Adresse registriert,
der bekommt eine Garnrolle auf seinen Wohnsitz gesteckt. Diese Rolle ermöglicht es einem Nutzer, sich aktiv
ins Weltgewebe einzuweben, solange er eingeloggt (sichtbar durch Drehung der Rolle) ist. Er kann nun also
neue Knoten (auf der Karte lokalisierte Informationsbündel, beispielsweise über geplante oder ständige
Ereignisse, Fragen, Ideen) knüpfen, sich mit bestehenden verbinden (Zustimmung, Interesse, Ablehnung,
Zusage, Verantwortungsübernahme, etc.), an Gesprächen (Threads auf einem Knoten) teilnehmen, oder Geld an
ein Ortsgewebekonto (Gemeinschaftskonto) spenden.

Jede dieser Aktionen erzeugt einen Faden, der von der Rolle zu dem jeweiligen Knoten führt. Jeder Faden
verblasst sukzessive binnen 7 Tagen. Auch Knoten lösen sich sukzessive binnen 7 Tagen auf, wenn es ein
datiertes Ereignis war und dieses vorbei ist, oder wenn seit 7 Tagen kein Faden (oder Garn) mehr zu diesem
Knoten geführt hat. Führt jedoch ein Garn zu einem Knoten (siehe unten), dann besteht dieser auch permanent,
bis das letzte zu ihm führende Garn entzwirnt ist. Kurzum: Knoten bestehen solange, wie noch etwas Garn oder
Faden zu ihm führt.

### Benutzeroberfläche und Navigation

Der linke Drawer enthält den Webrat und das Nähstübchen. Hier wird über alle ortsunabhängigen Themen
beraten (und abgestimmt. Generell kann jeder jederzeit Abstimmungen einleiten). Im Nähstübchen wird
einfach (orts-/kartenunabhängig) geplaudert. Das Ortsgewebekonto (oberer Slider) ist das
Gemeinschaftskonto. Hier gehen sowohl anonyme Spenden, als auch sichtbare Spenden (als Goldfäden von der
jeweiligen Rolle) ein. Hier, wie auch überall im Gewebe können Weber Anträge (auf Auszahlung, Anschaffung,
Veränderung, etc.) stellen.

Solch ein Antrag ist ebenso durch einen speziellen Antragsfaden mit der Rolle des Webers verbunden und
enthält sichtbar einen 7-Tage Timer. Nun haben alle Weber 7 Tage lang Zeit Einspruch einzulegen.
Geschieht dies nicht, dann geht der Antrag durch, bei Einspruch verlängert sich die Entscheidungszeit um
weitere 7 Tage bis schlussendlich abgestimmt wird. Jeder Antrag eröffnet automatisch einen Raum mitsamt
Thread und Informationen. Überhaupt entsteht mit jedem Knoten ein eigener Raum (Fenster), in dem man
Informationen, Threads, etc. nebeneinander gestalten kann. Alles, was man gestaltet, kann von allen anderen
verändert werden, es sei denn man verzwirnt es. Dies führt automatisch dazu, dass der Faden, der zu dem
Knoten führt und von der Rolle des Verzwirners ausgeht, zu einem Garn wird. Solange also eine Verzwirnung
besteht, solange kann ein Knoten sich nicht auflösen. Die Verzwirnung kann einzelne Elemente in einem
Knoten oder auch den gesamten Knoten betreffen.

Unten ist eine Zeitleiste. Man kann hier in Tagesschritten zurückspringen und vergangene Webungen sehen.
Auf der rechten Seite ist ein Slider mit den Filterkästchen für die toggelbaren Ebenen. Ecke oben rechts:
eigene Kontoeinstellung (nicht zu verwechseln mit Ortsgewebekontodarstellung oben). Man hat in seiner
eigenen Garnrolle einen privaten Bereich (Kontoeinstellungen, etc.) und einen öffentlich einsehbaren. In
dem öffentlich einsehbaren kann man unter anderem Güter und Kompetenzen, die man der Gesamtheit zur
Verfügung stellen möchte, angeben.

Über eine Suche im rechten Drawer kann man alle möglichen Aspekte suchen. Sie werden per Glow auf dem
verorteten Knoten oder Garnrolle und auf einer Liste dargestellt. Die Liste ist geordnet nach Entfernung
zur Bildmitte bei Suchbeginn. Von der Liste springt man zu dem verorteten Knoten oder Garnrolle, wenn man
den Treffer anklickt.

All diese Ebenen (links, oben, Ecke rechts oben, rechts) werden aus der jeweiligen Ecke oder Kante
herausgezogen. Die Standardansicht zeigt nur die Karte. Kleine Symbole zeigen die herausziehbaren Ebenen an.

### Fadenarten und Knotentypen

Es gibt unterschiedliche Fadenarten (in unterschiedlichen Farben):

- **Gesprächsfaden** - für Kommunikation und Diskussion
- **Gestaltungsfaden** - neue Knoten knüpfen, Räume gestalten (mit Informationen versehen, einrichten, etc.)
- **Veränderungsfaden** - wenn man bestehende Informationen verändert
- **Antragsfaden** - für offizielle Anträge im System
- **Abstimmungsfaden** - für Teilnahme an Abstimmungen
- **Goldfaden** - für Spenden und finanzielle Beiträge
- **Meldefaden** - für Meldungen problematischer Inhalte

Alle sind verzwirnbar, um aus den Fäden ein permanentes Garn zu zaubern.

Auch gibt es unterschiedliche Knotenarten:

- **Ideen** - Vorschläge und Konzepte
- **Veranstaltungen** (diversifizierbar) - Events und Termine
- **Einrichtungen** (diversifizierbar) - physische Orte und Gebäude
- **Werkzeuge** - Hilfsmittel und Geräte
- **Schlaf-/Stellplätze** - Übernachtungs- und Parkmöglichkeiten
- etc.

Diese Knotenarten sind auf der Karte filterbar (toggelbar).

## Organisation und Struktur

Weltweberei ist das Konzept. Realisiert wird es durch Ortswebereien, welche sich um ein gemeinsames
Gewebekonto versammeln. Jede Ortsweberei hat eine eigene Unterseite auf weltgewebe.net.

### Accounts und Nutzerkonten

Die Verifizierung übernimmt ein Verantwortlicher der Ortsweberei (per Identitätsprüfung etc.). Damit wird
dem Weber ein Account erstellt, den er beliebig gestalten kann. Es gibt einen öffentlich einsehbaren und
einen privaten Bereich. Der Account wird als Garnrolle auf seiner Wohnstätte visualisiert.

**Wichtige Unterscheidung:**

- Rolle ≠ Funktion im Gewebe
- Rolle = Kurzform für Garnrolle = auf Wohnsitz verorteter Account

Das System der Weltweberei kommt ohne Währungsalternativen oder Creditsysteme aus. Sichtbares Engagement und
eingebrachte bzw. einzubringende Ressourcen (also geleistete und potenzielle Webungen) sind die Währung!

### Ortsgewebekonto

Dies ist das Gemeinschaftskonto der jeweiligen Ortswebereien.

Per Visualisierung im Weltgewebe jederzeit einsehbar.

Hier gehen Spenden ein und werden Anträge auf Auszahlung gestellt, die – wie alles im Weltgewebe – dem
Gemeinschaftswillen zur Disposition stehen.

### Partizipartei

Der politische Arm der jeweiligen Ortswebereien. Der Clou: Alles politische geschieht unter
Live-Beobachtung und -Mitwirkung der Weber und anderer Interessierter (diese jedoch ohne
Mitwirkungsmöglichkeit).

Die Arbeit der Fadenträger (Mandatsträger) und dessen Fadenreicher (Sekretäre, die den Input aus dem
Gewebe aufbereiten und an den Fadenträger weiterreichen) wird während der gesamten Arbeitszeit gestreamt.
Weber können live im Stream-Gruppenchat ihre Ideen (gefiltert durch Aufwertung/Abwertung der Mitweber und
möglicherweise unterstützt / geordnet durch eine Plattform-Künstliche Intelligenz) und Unterstützungen
einbringen. Jeder Funktion, jeder Posten kann – wie alles in dem Weltgewebe – per Antrag umbesetzt oder
verändert werden. Jeder Weber (auch die kleinen) haben eine Stimme. Diese können sie temporär an andere
Weber übertragen. Das bedeutet, dass diejenigen, an die die Stimmen übertragen wurden, bei Abstimmungen
dementsprechend mehr Stimmmacht haben.

Auch übertragene Stimmen können weiterübertragen werden. Übertragungen enden 4 Wochen nach Inaktivität des
Stimmenverleihenden oder durch dessen Entscheidung.

## Kontakt / Impressum / Datenschutz

**E-Mail-Adresse:** <kontakt@weltweberei.org>
Schreib gerne, wenn du interessiert bist, Fragen, Anregungen oder Kritik hast. Oder willst du gar selber
eine Ortsweberei gründen oder dich anderweitig beteiligen?

**Telefon:** +4915563658682
Aktuell benutze ich WhatsApp und Signal

**Verantwortlicher:** Alexander Mohr, Huskoppelallee 13, 23795 Klein Rönnau

**Datenschutz:** Das Weltgewebe ist so konzipiert, dass keine Daten erhoben werden, ohne dass du sie selbst
einträgst. Es gibt kein Tracking, keine versteckten Cookies, keine automatische Profilbildung. Sichtbar
wird nur das, was du freiwillig sichtbar machst: Name, Wohnort, Verbindungen im Gewebe. Deine persönlichen
Daten kannst du jederzeit verändern oder zurückziehen. Die Verarbeitung deiner Daten erfolgt auf Grundlage
von Artikel 6 Absatz 1 lit. a und f der Datenschutzgrundverordnung – also: Einverständnis & legitimes
Interesse an sicherer Gemeinschaftsorganisation.

## Technische Umsetzung

Ich arbeite an einem iPad und an einem Desktop PC.

Die technische Umsetzung soll maximale Kontrolle, Skalierbarkeit und Freiheit berücksichtigen. Es soll
stets die perspektivisch maximalst sinnvolle Lösung umgesetzt werden.
```

### 📄 weltgewebe/docs/quickstart-gate-c.md

**Größe:** 546 B | **md5:** `9ebd955eee6d22093d170300d2822f2a`

```markdown
# Quickstart · Gate C (Dev-Stack)

```bash
cp .env.example .env
make up
# Web:  http://localhost:5173
# Proxy: http://localhost:8081
# API:  http://localhost:8081/api/version  (-> /version via Caddy)
make logs
make down
```

## Hinweise

- Frontend nutzt `PUBLIC_API_BASE=/api` (siehe `apps/web/.env.development`).
- Compose-Profil `dev` schützt vor Verwechslungen mit späteren prod-Stacks.
- `make smoke` triggert den GitHub-Workflow `compose-smoke` für einen E2E-Boot-Test.
- CSP ist im Dev gelockert; für externe Tiles Domains ergänzen.
```

### 📄 weltgewebe/docs/runbook.md

**Größe:** 6 KB | **md5:** `e10a31b002903c4664d2e9ab5ac69bfa`

```markdown
# Runbook

Dieses Dokument enthält praxisorientierte Anleitungen für den Betrieb, die Wartung und das Onboarding
im Weltgewebe-Projekt.

## 1. Onboarding (Woche 1-2)

Ziel dieses Runbooks ist es, neuen Teammitgliedern einen strukturierten und schnellen Einstieg zu ermöglichen.

### Woche 1: Systemüberblick & lokales Setup

- **Tag 1: Willkommen & Einführung**
  - **Kennenlernen:** Team und Ansprechpartner.
  - **Projekt-Kontext:** Lektüre von `README.md`, `docs/overview/inhalt.md` und `docs/geist und plan.md`.
  - **Architektur:** `docs/architekturstruktur.md` und `docs/techstack.md` durcharbeiten, um die
    Komponenten und ihre Zusammenspiel zu verstehen.
  - **Zugänge:** Accounts für GitHub, Docker Hub, etc. beantragen.

- **Tag 2-3: Lokales Setup**
  - **Voraussetzungen:** Git, Docker, Docker Compose, `just` und Rust (stable) installieren.
  - **Codespaces (Zero-Install):** GitHub Codespaces öffnen, das Devcontainer-Setup starten und im
    Terminal `npm run dev -- --host` ausführen. So lassen sich Frontend und API ohne lokale
    Installation testen – ideal auch auf iPad.
  - **Repository klonen:** `git clone <repo-url>`
  - **`.env`-Datei erstellen:** `cp .env.example .env`.
  - **Core-Stack starten:** `just up` (bevorzugt) oder `make up` als Fallback. Überprüfen, ob alle
    Container (`web`, `api`, `db`, `caddy`) laufen: `docker ps`.
  - **Web-Frontend aufrufen:** `http://localhost:5173` (SvelteKit-Devserver) oder – falls der Caddy
    Reverse-Proxy aktiv ist – `http://localhost:3000` im Browser öffnen.
  - **API-Healthcheck:** API-Endpunkt `/health` aufrufen, um eine positive Antwort zu sehen.

- **Tag 4-5: Erster kleiner Beitrag**
  - **Hygiene-Checks:** `just check` ausführen und sicherstellen, dass alle Linter, Formatierer und
    Tests erfolgreich durchlaufen.
  - **"Good first issue" suchen:** Ein kleines, abgeschlossenes Ticket (z.B. eine Textänderung in der
    UI oder eine Doku-Ergänzung) auswählen.
  - **Workflow üben:** Branch erstellen, Änderung implementieren, Commit mit passendem Präfix (`docs:
    ...` oder `feat(web): ...`) erstellen und einen Pull Request zur Review stellen.

### Woche 2: Vertiefung & erste produktive Aufgaben

- **Monitoring & Observability:**
  - **Monitoring-Stack starten:** `docker compose -f infra/compose/compose.observ.yml up -d`.
  - **Dashboards erkunden:** Grafana (`http://localhost:3001`) öffnen und die Dashboards für
    Web-Vitals, API-Latenzen und Systemmetriken ansehen.
- **Datenbank & Events:**
  - **Event-Streaming-Stack starten:** `docker compose -f infra/compose/compose.stream.yml up -d`.
  - **Datenbank-Migrationen:** Verzeichnis `apps/api/migrations/` ansehen, um die
    Schema-Entwicklung nachzuvollziehen.
- **Produktiv werden:**
  - **Erstes Feature-Ticket:** Eine überschaubare User-Story oder einen Bug bearbeiten, der alle
    Schichten (Web, API) betrifft.
  - **Pair-Programming:** Eine Session mit einem erfahrenen Teammitglied planen, um komplexere Teile
    der Codebase kennenzulernen.

---

## 2. Disaster Recovery Drill

Dieses Runbook beschreibt die Schritte zur Simulation eines Totalausfalls und der Wiederherstellung
des Systems. Der Drill sollte quartalsweise durchgeführt werden, um die Betriebsbereitschaft
sicherzustellen.

**Szenario:** Das primäre Rechenzentrum ist vollständig ausgefallen. Das System muss aus Backups in
einer sauberen Umgebung wiederhergestellt werden.

**Ziele (RTO/RPO):**

- **Recovery Time Objective (RTO):** < 4 Stunden
- **Recovery Point Objective (RPO):** < 5 Minuten

### Vorbereitung

1. **Backup-Verfügbarkeit prüfen:** Sicherstellen, dass die letzten WAL-Archive der
   PostgreSQL-Datenbank an einem sicheren, externen Ort (z.B. S3-Bucket) verfügbar sind –
   verschlüsselt (z.B. S3 SSE-KMS) und mittels Object Lock unveränderbar abgelegt.
2. **Infrastruktur-Code:** Sicherstellen, dass der `infra/`-Ordner den aktuellen Stand der
   produktiven Infrastruktur abbildet.
3. **Team informieren:** Alle Beteiligten über den Beginn des Drills in Kenntnis setzen.

### Durchführung

1. **Saubere Umgebung bereitstellen:** Eine neue VM- oder Kubernetes-Umgebung ohne bestehende Daten
   oder Konfigurationen hochfahren.
2. **Infrastruktur aufbauen:**
    - Das Repository auf die neue Umgebung klonen.
    - Die Basis-Infrastruktur über die Compose-Files oder Nomad-Jobs starten
      (`infra/compose/compose.core.yml` etc.). Die Container starten, bleiben aber ggf. im
      Wartezustand, da die Datenbank noch nicht bereit ist.
3. **Datenbank-Wiederherstellung (Point-in-Time Recovery):**
    - Eine neue PostgreSQL-Instanz starten.
    - Das letzte Basis-Backup einspielen.
    - Die WAL-Archive aus dem Backup-Speicher bis zum letzten verfügbaren Zeitpunkt vor
      dem "Ausfall" wiederherstellen.
4. **Systemstart & Event-Replay:**
    - Die Applikations-Container (API, Worker) neu starten, damit sie sich mit der
      wiederhergestellten Datenbank verbinden.
    - Den `outbox`-Relay-Prozess starten. Dieser beginnt, die noch nicht verarbeiteten
      Events aus der `outbox`-Tabelle an NATS JetStream zu senden.
    - Die Worker (Projektoren) starten. Sie konsumieren die Events von JetStream
      und bauen die Lese-Modelle (`faden_view` etc.) neu auf.
5. **Verifikation & Abschluss:**
    - **Datenkonsistenz prüfen:** Stichprobenartige Überprüfung der wiederhergestellten Daten in den
      Lese-Modellen.
    - **Funktionstests:** Manuelle oder automatisierte Smoke-Tests durchführen (z.B. Login, Thread
      erstellen).
    - **Zeitmessung:** Die benötigte Zeit für die Wiederherstellung stoppen und mit dem RTO
      vergleichen.
    - **Datenverlust bewerten:** Den Zeitpunkt des letzten wiederhergestellten
      WAL-Segments mit dem Zeitpunkt des "Ausfalls" vergleichen, um den
      Datenverlust zu ermitteln (sollte RPO nicht überschreiten).
6. **Drill beenden:** Die Testumgebung herunterfahren und die Ergebnisse dokumentieren.

| Startzeit | Endzeit | RTO erreicht? | RPO erreicht? |
|-----------|---------|---------------|---------------|
|           |         | [ ] Ja / [ ] Nein | [ ] Ja / [ ] Nein |

### Nachbereitung

- **Lessons Learned:** Ein kurzes Meeting abhalten, um Probleme oder Verbesserungspotenziale zu besprechen.
- **Runbook aktualisieren:** Dieses Runbook bei Bedarf mit den gewonnenen Erkenntnissen anpassen.
- **Automatisierung nutzen:** `just drill` ausführen, um den Drill reproduzierbar zu starten und
  Smoke-Tests anzustoßen.
```

### 📄 weltgewebe/docs/runbook.observability.md

**Größe:** 471 B | **md5:** `511a008946ed1870e9c0e5ab9ee2d328`

```markdown
# Observability – Local Profile

## Start

```bash
docker compose -f infra/compose/compose.observ.yml up -d
```

- Prometheus: [http://localhost:9090](http://localhost:9090)
- Grafana:    [http://localhost:3001](http://localhost:3001) (anon Viewer)
- Loki:       [http://localhost:3100](http://localhost:3100)
- Tempo:      [http://localhost:3200](http://localhost:3200)

This is purely optional and local, does not block anything – but gives you immediate graphics.
```

### 📄 weltgewebe/docs/techstack.md

**Größe:** 21 KB | **md5:** `87884c4cc1d31d120c8e39eff095fd8e`

```markdown
Weltgewebe Tech Stack

Der Weltgewebe Tech-Stack ist ein vollständig dokumentiertes Systemprofil. Er nutzt eine moderne Web-Architektur mit
SvelteKit im Frontend, PostgreSQL als Source of Truth, NATS JetStream für Event-Distribution, und umfangreiche
Überwachung sowie Sicherheits- und Kostenkonzepte. Die folgenden Abschnitte fassen alle Komponenten zusammen –

<<TRUNCATED: max_file_lines=800>>
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_adr.md

**Größe:** 5 KB | **md5:** `95803e65b746e53361732244d7cdeccb`

```markdown
### 📄 weltgewebe/docs/adr/0042-consume-semantah-contracts.md

**Größe:** 276 B | **md5:** `eebc6c89ed10ea1704ace598b0064f93`

```markdown
# ADR-0042: semantAH-Contracts konsumieren

Status: accepted

Beschluss:

- Weltgewebe liest JSONL-Dumps (Nodes/Edges) als Infoquelle (read-only).
- Kein Schreibpfad zurück. Eventuelle Events: getrennte Domain.

Konsequenzen:

- CI validiert nur Formate; Import-Job später.
```

### 📄 weltgewebe/docs/adr/ADR-0001__clean-slate-docs-monorepo.md

**Größe:** 315 B | **md5:** `a9e740a160cba7d00fa8f071255af7b8`

```markdown
# ADR-0001 — Clean-Slate als Docs-Monorepo

Datum: 2025-09-12
Status: Accepted
Entscheidung: Rückbau auf Doku-only. Re-Entry nur über klar definierte Gates.
Alternativen: Sofortiger Code-Reentry ohne ADR; verworfen wegen Drift-Risiko.
Konsequenzen: Vor Code zuerst Ordnungsprinzipien, Budgets, SLOs festhalten.
```

### 📄 weltgewebe/docs/adr/ADR-0002__reentry-kriterien.md

**Größe:** 354 B | **md5:** `5a6822d1f593300a94d57cc86d6dea1d`

```markdown
# ADR-0002 — Re-Entry-Kriterien (Gates)

Datum: 2025-09-12
Status: Accepted
Gate A (Web): SvelteKit-Skelett + Budgets (TTI ≤2s, INP ≤200ms, ≤60KB JS).
Gate B (API): Health/Version, Contracts, Migrations-Plan.
Gate C (Infra-light): Compose dev, Caddy/CSP-Basis, keine laufenden Kosten.
Gate D (Security-Basis): Secrets-Plan, Lizenz-/Datenhygiene.
```

### 📄 weltgewebe/docs/adr/ADR-0003__privacy-unschaerferadius-ron.md

**Größe:** 3 KB | **md5:** `f864059948a3cbad3cd93757311430b4`

```markdown
# ADR-0003 — Privacy: Unschärferadius & RoN-Platzhalterrolle (v1)

Datum: 2025-09-13  
Status: Accepted

## Kontext

Die Garnrolle ist am Wohnsitz verortet (Residence-Lock). Die Karte und die Fäden sollen ortsbasierte
Sichtbarkeit ermöglichen, ohne den exakten Wohnsitz preiszugeben - sofern dies explizit vom Nutzer gewünscht
ist. Generell gilt: Transparenz ist Standard – Privacy-Optionen sind ein freiwilliges Zugeständnis für
Nutzer, die das wünschen.

## Entscheidung

1) **Unschärferadius r (Meter)**  
   Der Nutzer kann die öffentliche Genauigkeit seiner Garnrolle über einen **Unschärferadius** selbst
   einstellen. Die **öffentliche Anzeige** nutzt eine **ungenaue Position innerhalb dieses Radius**.
   Alle öffentlichen Darstellungen und Beziehungen (Fäden/Garn) beziehen sich auf diese angezeigte Position.

2) **RoN-Platzhalterrolle (Toggle)**  
   Optional kann sich ein Nutzer **als „RoN“** (Rolle ohne Namen) zeigen bzw. Beiträge **anonymisieren**.
   Anonymisierte Fäden verweisen nicht mehr auf die ursprüngliche Garnrolle, sondern auf den
   **RoN-Platzhalter**. Beim Ausstieg werden Beiträge gemäß RoN-Prozess überführt.

3) **Transparenz als Standard**  
   Standard ist **ohne Unschärfe und ohne RoN**. Die Optionen sind **Opt-in** und dienen der persönlichen
   Zurückhaltung, nicht der Norm.

## Alternativen

Weitere Modi (z. B. Kachel-Snapping, Stadt-Centroid) werden **nicht** eingeführt.

## Konsequenzen

- **Einfaches UI**: **Slider** (Meter) für den Unschärferadius, **Toggle** für RoN.  
- **Konsistente Darstellung**: Öffentliche Fäden starten an der öffentlich angezeigten Position der Garnrolle.  
- **Eigenverantwortung**: Nutzer wählen ihre gewünschte Sichtbarkeit bewusst.

## Schnittstellen

- **Events**  
  - `VisibilityPreferenceSet { radius_m }`  
  - `RonEnabled` / `RonDisabled`
- **Views**  
  - intern: `roles_view` (exakte Position, nicht öffentlich)  
  - öffentlich: `public_role_view (id, public_pos, ron_flag, radius_m)`  
  - `faden_view` nutzt `public_pos` als Startpunkt

## UI

**Einstellungen → Privatsphäre**: Unschärfe-Slider (Meter) + RoN-Toggle (inkl. Einstellbarkeit der Tage
(beginnend mit 0, ab der die RoN-Anonymisierung greifen soll). Vorschau der angezeigten Position.

## Telemetrie & Logging

Keine exakten Wohnsitz-Koordinaten in öffentlichen Daten oder Logs, sofern gewünscht; personenbezogene Daten
nur, wo nötig.

## Rollout

- **Web**: Slider + Toggle und Vorschau integrieren.  
- **API**: `/me/visibility {GET/PUT}`, `/me/roles` liefert `public_pos`, `ron_flag`, `radius_m`.  
- **Worker**: Privacy-Auflösung vor Projektionen (`public_role_view` vor `faden_view`).
```

### 📄 weltgewebe/docs/adr/ADR-0004__fahrplan-verweis.md

**Größe:** 874 B | **md5:** `e704ae31604d2be399186837a67ca35b`

```markdown
# ADR-0004 — Fahrplan als kanonischer Verweis

Datum: 2025-02-14
Status: Accepted

## Kontext

Der Projektfahrplan wird bereits in `docs/process/fahrplan.md` gepflegt. Dieses ADR dient lediglich als
stabile, versionierte Referenz auf diesen kanonischen Speicherort und vermeidet inhaltliche Duplikate.

## Entscheidung

- Der Fahrplan bleibt **kanonisch** in `docs/process/fahrplan.md`.
- Dieses Dokument enthält **keine Kopie** des Fahrplans, sondern verweist ausschließlich darauf.

## Konsequenzen

- Anpassungen am Fahrplan erfolgen ausschließlich in der Prozessdokumentation.
- Architekturentscheidungen und weitere Dokumente verlinken auf den Fahrplan über dieses ADR.

## Link

- [Fahrplan in docs/process](../process/fahrplan.md)

## Siehe auch

- [ADR-0003 — Privacy: Unschärferadius & RoN-Platzhalterrolle (v1)](ADR-0003__privacy-unschaerferadius-ron.md)
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_dev.md

**Größe:** 575 B | **md5:** `a9d8c0039b7f8caeffeadf1c8b1d6968`

```markdown
### 📄 weltgewebe/docs/dev/codespaces.md

**Größe:** 448 B | **md5:** `539e936bc772bd3ec55d4aa23b73f07d`

```markdown
# Codespaces: Dev-Server schnell starten

Im Codespace werden die Web-Abhängigkeiten automatisch installiert.

**Start:**

```bash
cd apps/web
npm run dev -- --host
```

Codespaces öffnet automatisch den Port **5173** – Link anklicken, `/map` ansehen.

**Troubleshooting:**  

- „vite: not found“: `npm i -D vite` und erneut starten.  
- „leere Seite“: einmal im Kartenbereich klicken (Keyboard-Fokus), dann `[` / `]` / `Alt+G` testen.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_edge_systemd.md

**Größe:** 988 B | **md5:** `b38db32a1b067aaf24220b13336c8873`

```markdown
### 📄 weltgewebe/docs/edge/systemd/README.md

**Größe:** 214 B | **md5:** `cead3a78ff4ddffd156fd97cde9b4061`

```markdown
# Edge systemd units (optional)

This is **not** the primary orchestration path. Default remains **Docker Compose → Nomad**.
Use these units only for tiny single-node edge installs where Compose isn't available.
```

### 📄 weltgewebe/docs/edge/systemd/weltgewebe-projector.service

**Größe:** 490 B | **md5:** `59549cecea7d486a5ea6ce8db0907aab`

```plaintext
[Unit]
Description=Weltgewebe Projector (timeline/search)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=www-data
Environment=RUST_LOG=info
EnvironmentFile=/etc/weltgewebe/projector.env
ExecStart=/usr/local/bin/weltgewebe-projector
Restart=on-failure
RestartSec=3

# Hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
PrivateDevices=true
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_overview.md

**Größe:** 4 KB | **md5:** `b12e445ec540118a04301d7a15048a6a`

```markdown
### 📄 weltgewebe/docs/overview/inhalt.md

**Größe:** 2 KB | **md5:** `6f065ff394abd87be4043025db5fc89b`

```markdown
# Einführung: Ethik- & UX-First-Startpunkt

Die Weltgewebe-Initiative stellt Menschen und ihre Lebensrealität in den Mittelpunkt.
Die technische Plattform – SvelteKit für das Web-Frontend, Axum als Rust-API sowie Postgres
und JetStream im Daten- und Event-Backbone – ist Mittel zum Zweck: Sie schafft Transparenz,
Handlungssicherheit und nachhaltige Teilhabe.
Dieses Dokument bietet Außenstehenden einen klaren Einstieg in die inhaltliche Stoßrichtung
des Projekts.

## Leitplanken & Prinzipien

- **Ethik vor Feature-Liste:** Entscheidungen werden entlang von Wirkungszielen und Schutzbedarfen
  priorisiert.
  UX-Entscheidungen orientieren sich an Barrierefreiheit, Datenschutz und erklärbaren Abläufen.
- **Partizipation sichern:** Stakeholder:innen aus Zivilgesellschaft, Verwaltung und Forschung
  erhalten früh Zugang zu Prototypen, um Risiken zu erkennen und gemeinsam zu mitigieren.
- **Transparenz herstellen:** Dokumentation, Policies und öffentlich nachvollziehbare
  Entscheidungen haben Vorrang vor reinem Feature-Output.

## Projektumfang (Docs-only, Gate-Strategie)

Das Repository befindet sich in Phase ADR-0001 „Docs-only“.
Technische Re-Entry-Pfade sind über Gates A–D definiert.
So bleiben Experimente nachvollziehbar und können schrittweise in den Produktionskontext
überführt werden.

## Weitere Orientierung

- **Systematik & Struktur:** Siehe `docs/overview/zusammenstellung.md`.
- **Architektur-Details:** `architekturstruktur.md` fasst Domänen, Boundaries und Kommunikationspfade zusammen.
- **Fahrplan & Prozesse:** `docs/process/fahrplan.md` beschreibt Freigaben, Gates und Quality-Gates.

> _Stand:_ Docs-only, Fokus auf Ethik, UX und transparente Entscheidungsprozesse.
> Mit dem Startpunkt hier und der Systematik im Schwesterdokument erhalten Außenstehende in
> zwei Klicks den vollständigen Projektkontext.
```

### 📄 weltgewebe/docs/overview/zusammenstellung.md

**Größe:** 2 KB | **md5:** `ab6cbff930700676b08bb59271a33fbc`

```markdown
# Systematik & Strukturüberblick

Diese Zusammenstellung führt durch die zentralen Orientierungspunkte der Weltgewebe-Dokumentation.
Sie ergänzt die inhaltliche Einführung (`docs/overview/inhalt.md`) und macht deutlich,
wie Ethik & UX entlang des gesamten Vorhabens abgesichert werden.

## Kernartefakte

| Bereich | Zweck | Primäre Ressourcen |
| --- | --- | --- |
| **Ethik & Wirkung** | Leitplanken, Risiken, Schutzbedarfe | `policies/`, `docs/ethik/`, `docs/process/fahrplan.md` |
| **User Experience** | UX-Guidelines, Prototypen, Feedback-Loops | `apps/web/README.md`, `docs/ux/`, `docs/runbooks/` |
| **Architektur** | Technische Boundaries, Integrationen | `architekturstruktur.md`, `docs/architecture/` |
|                 | Datenflüsse                          | `contracts/` |
| **Betrieb & Qualität** | Gates, CI/CD, Observability, Budgets | `docs/process/`, `ci/`, `policies/limits.yaml` |

## Navigationspfad für Außenstehende

1. **Einführung lesen:** `docs/overview/inhalt.md` liefert Vision, Prinzipien und Scope.
2. **Systematik prüfen:** Dieses Dokument zeigt, wo welche Detailtiefe zu finden ist.
3. **Architektur & Fahrplan vertiefen:**
   - `architekturstruktur.md` für Domänen & Komponenten.
   - `docs/process/fahrplan.md` für Timeline, Gates und Verantwortlichkeiten.
4. **Ethik & UX-Vertiefung:**
   - `docs/ethik/` für Entscheidungskriterien und Risikokataloge.
   - `docs/ux/` und `apps/web/README.md` für Prototypen und Research-Ansätze.

## Rollen & Verantwortlichkeiten

- **Ethik/Governance:** Kuratiert Policies, überprüft Releases gegen Schutzbedarfe.
- **UX-Research & Design:** Verantwortet Tests, Insights und Accessibility-Guidelines.
- **Tech Leads:** Halten Architekturdokumentation und Verträge aktuell.
- **Ops & QA:** Betreiben Gates, Observability und Budget-Checks in CI.

## Verbindung zu den Gates

Jedes Gate (A–D) besitzt eine eigene Dokumentation in `docs/process/`.
Die Gates stellen sicher, dass neue Funktionen den Ethik- und UX-Anforderungen
entsprechen, bevor sie in den produktiven Stack überführt werden.
Die Zusammenstellung dient als Index, um die passenden Unterlagen pro Gate rasch
zu finden.

> _Hinweis:_ Ergänzende Artefakte (z. B. Workshops, Entscheidungen, ADRs)
> werden im jeweiligen Ordner verlinkt, sobald sie vorliegen. Diese Systematik
> wird fortlaufend gepflegt und bildet den verbindlichen Einstiegspunkt für neue
> Teammitglieder ebenso wie externe Auditor:innen.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_policies.md

**Größe:** 6 KB | **md5:** `84c763efa906795977a1c5b8b10b8514`

```markdown
### 📄 weltgewebe/docs/policies/orientierung.md

**Größe:** 6 KB | **md5:** `7dc983f456e13978d55a13d1db237f29`

```markdown
# Leitfaden · Ethik & Systemdesign (Weltgewebe)

**Stand:** 2025-10-06  
**Quelle:** inhalt.md · zusammenstellung.md · geist und plan.md · fahrplan.md · techstack.md

---

## 1 · Zweck

Dieses Dokument verdichtet Geist, Plan und technische Architektur des Weltgewebes zu einer verbindlichen Orientierung für
Entwicklung, Gestaltung und Governance.  
Es beschreibt:

- **Was** ethisch gilt,
- **Wie** daraus technische und gestalterische Konsequenzen folgen,
- **Woran** sich Teams bei Entscheidungen künftig messen lassen.

---

## 2 · Philosophie („Geist“)

| Prinzip | Bedeutung | Operative Konsequenz |
|----------|------------|----------------------|
| **Freiwilligkeit** | Keine Handlung ohne bewusste Zustimmung. | Opt-in-Mechanismen, keine versteckten Datenflüsse. |
| **Transparenz** | Alles Sichtbare ist verhandelbar; nichts Geschlossenes. | Offene APIs, nachvollziehbare Governance-Entscheide. |
| **Vergänglichkeit** | Informationen altern sichtbar; kein endloses Archiv. | Zeitliche Sichtbarkeit („Fade-out“), Lösch- und Verblassungsprozesse. |
| **Commons-Orientierung** | Engagement ≠ Geld; Beiträge = Währung. | Spenden (Goldfäden) optional, sonst Ressourcen-Teilung. |
| **Föderation** | Lokale Autonomie + globale Anschlussfähigkeit. | Ortswebereien mit eigenem Konto + föderalen Hooks. |
| **Privacy by Design** | Sichtbar nur freiwillig Eingetragenes. | Keine Cookies / Tracking; RoN-System für Anonymität. |

---

## 3 · Systemlogik („Plan“)

### 3.1 Domänenmodell

| Entität | Beschreibung |
|----------|--------------|
| **Rolle / Garnrolle** | Verifizierter Nutzer (Account) + Position + Privat/Öffentlich-Bereich. |
| **Knoten** | Informations- oder Ereignis-Bündel (Idee, Ressource, Ort …). |
| **Faden** | Verbindung zwischen Rolle ↔ Knoten (Handlung). |
| **Garn** | Dauerhafte, verzwirnte Verbindung = Bestandsschutz. |

### 3.2 Zeit und Prozesse

- **7-Sekunden-Rotation** → sichtbares Feedback nach Aktion.
- **7-Tage-Verblassen** → nicht verzwirnte Fäden/Knoten lösen sich auf.  
- **7 + 7-Tage-Modell** → Anträge: Einspruch → Abstimmung.  
- **Delegation (Liquid Democracy)** → verfällt nach 4 Wochen Inaktivität.  
- **RoN-System** → anonymisierte Beiträge nach gewählter Frist.

---

## 4 · Ethisch-technische Defaults

| Bereich | Schlüssel | Richtwert | Herkunft |
|----------|------------|------------|-----------|
| Sichtbarkeit | `fade_days` | 7 Tage laut zusammenstellung.md | Funktionsbeschreibung, nicht Code. |
| Identität | `ron_alias_valid_days` | 28 Tage (Delegations-Analogon) | Geist & Plan-Ableitung. |
| Anonymisierung | `default_anonymized` | *nicht festgelegt*, nur „Opt-in möglich“ | zusammenstellung.md, III Abschnitt. |
| Ortsdaten | `unschaerferadius_m` | individuell einstellbar | zusammenstellung.md, III Abschnitt. |
| Delegation | `delegation_expire_days` | 28 Tage (4 Wochen) | § IV Delegation. |

> **Hinweis:** Die Werte 7/7/28 Tage sind aus der Beschreibung im Repo abgeleitet – nicht normativ festgelegt.  
> Änderungen erfordern Governance-Beschluss + Changelog-Eintrag.

---

## 5 · Governance-Matrix

| Prozess | Dauer | Sichtbarkeit | Trigger |
|----------|--------|---------------|----------|
| Antrag | 7 Tage + 7 Tage | öffentlich | Timer / Einspruch |
| Delegation | 4 Wochen | transparent (gestrichelte Linien) | Inaktivität |
| Meldung / Freeze | 24 h | eingeklappt | Moderations-Vote |
| RoN-Anonymisierung | variable x Tage | „Rolle ohne Namen“ | User-Opt-in |

---

## 6 · Technische Leitplanken (aus techstack.md)

- **Architektur:** Rust API (Axum) + SvelteKit Frontend + PostgreSQL / NATS JetStream (Event-Sourcing).  
- **Monitoring:** Prometheus + Grafana + Loki + Tempo.  
- **Security:** SBOM + cosign + Key-Rotation + DSGVO-Forget-Pipeline.  
- **HA & Cost Control:** Nomad Cluster · PgBouncer · Opex-KPIs < €1 / Session.  
- **Privacy UI (ADR-0003):** RoN-Toggle + Unschärferadius-Slider (ab Phase C).

---

## 7 · Design-Ethik → UX-Richtlinien

1. **Transparente Zeitlichkeit:** Fade-Animationen zeigen Vergänglichkeit, nicht Löschung.  
2. **Partizipative Interface-Metaphern:** Rollen drehen, Fäden fließen – Verantwortung wird sichtbar.  
3. **Reversible Aktionen:** Alles ist änder- oder verzwirnbar, aber nicht heimlich.  
4. **Privacy Controls Front and Center:** Slider / Toggles direkt im Profil.  
5. **Lokale Sichtbarkeit:** Zoom ≈ Vertraulichkeit; Unschärfe nimmt mit Distanz zu.  
6. **Keine versteckte Gamification:** Engagement wird nicht bewertet, nur sichtbar gemacht.

---

## 8 · Weiterer Fahrplan (Querschnitt aus fahrplan.md)

| Phase | Ziel | Ethik-Bezug |
|-------|------|-------------|
| A | Minimal-Web (SvelteKit + Map) | Transparenz sichtbar machen – Karte hallo sagen |
| B | API + Health + Contracts | Nachvollziehbarkeit von Aktionen |
| C | Privacy UI + 7-Tage-Verblassen | Privacy by Design erlebbar machen |
| D | Persistenz + Outbox-Hook | Integrität von Ereignissen |
| … | Langfristig: Föderation + Delegations-Audits | Verantwortung skaliert halten |

---

## 9 · Governance / Changelog-Pflicht

Alle Änderungen an:

- Datenschutz- oder Ethikparametern
- Governance-Timern  
- Sichtbarkeits-Mechaniken  

→ müssen in `docs/policies/changelog.md` vermerkt und im Webrat veröffentlicht werden.

---

## 10 · Zusammenfassung

> **Das Weltgewebe** ist ein offenes, vergängliches, fälschungssicheres
> Beziehungs-System.  
> Jede Handlung = Event, jedes Event = Faden, jeder Faden = Verantwortung.
> Ethik, Technik und Design greifen ineinander.

---

## Meta

- **Autor (Extraktion):** ChatGPT aus Repo-Docs 2025-10-06  
- **Status:** Draft v1 · Review im Webrat erforderlich  
- **Pfadvorschlag:** `docs/policies/orientierung.md`
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_process.md

**Größe:** 13 KB | **md5:** `46c3b1bf9709a3a2568a3d39234461e7`

```markdown
### 📄 weltgewebe/docs/process/README.md

**Größe:** 350 B | **md5:** `a64145073affb3b77a3cdf93997e0251`

```markdown
# Prozess

Übersicht über Abläufe und Konventionen.

## Index

- [Fahrplan](fahrplan.md) – zeitlicher Ablauf und Meilensteine (**kanonisch**)
- [Sprache](sprache.md) – Leitfaden zur Projektsprache
- [Bash Tooling Guidelines](bash-tooling-guidelines.md) – Best Practices für zukünftige Shell-Skripte

[Zurück zum Doku-Index](../README.md)
```

### 📄 weltgewebe/docs/process/bash-tooling-guidelines.md

**Größe:** 3 KB | **md5:** `ef60df9aa99bb48d8f5b68ea6e049bab`

```markdown
# Bash-Tooling-Richtlinien

Diese Richtlinien beschreiben, wie wir Shell-Skripte im Weltgewebe-Projekt entwickeln, prüfen und ausführen.  
Sie kombinieren generelle Best Practices (Formatierung, Checks) mit projektspezifischen Vorgaben
wie Devcontainer-Setup, CLI-Bootstrap und SemVer.

## Ziele

- Einheitliche Formatierung der Skripte.
- Automatisierte Qualitätssicherung mit statischer Analyse.
- Gute Developer Experience für wiederkehrende Aufgaben.
- Projektkontext: sauberes Devcontainer-Setup, klare CLI-Kommandos, reproduzierbare SemVer-Logik.

## Kernwerkzeuge

### shfmt

- Formatierung gemäß POSIX-kompatiblen Standards.
- Nutze `shfmt -w` für automatische Formatierung.
- Setze `shfmt -d` in CI-Checks ein, um Abweichungen aufzuzeigen.

### ShellCheck

- Analysiert Skripte auf Fehler, Portabilität und Stilfragen.
- Lokaler Aufruf: `shellcheck <skript>`.
- In CI-Pipelines verpflichtend.

### Bash Language Server (optional)

- Bietet Editor-Unterstützung (Autocompletion, Inlay-Hints).
- Installierbar via `npm install -g bash-language-server`.
- Im Editor als LSP aktivieren.

## Arbeitsweise

1. Skripte beginnen mit `#!/usr/bin/env bash` und enthalten `set -euo pipefail`.
2. Vor Commit: `shfmt` und `shellcheck` lokal ausführen.
3. Ergebnisse der Checks im Pull Request sichtbar machen.
4. Neue Tools → Dokumentation hier ergänzen.
5. CI-Checks sind verbindlich; Ausnahmen werden dokumentiert.

## Projektspezifische Ergänzungen

### Devcontainer-Setup

- **Bash-Version dokumentieren** (z. B. Hinweis auf `nameref` → Bash ≥4.3).
- **Paketsammlungen per Referenz (`local -n`)** statt Subshell-Kopien.
- **`check`-Ziel ignorieren**, falls versehentlich mitinstalliert.

### CLI-Bootstrap (`wgx`)

- Debug-Ausgabe optional via `WGX_DEBUG=1`.
- Dispatcher validiert Subcommands:  
  - Ohne Argument → Usage + `exit 1`.  
  - Unbekannte Befehle → Fehlermeldung auf Englisch (für CI-Logs).  
  - Usage-Hilfe auf `stderr`.

### SemVer-Caret-Ranges

- `^0.0.x` → nur Patch-Updates erlaubt.
- Major-Sprünge blockiert (`^1.2.3` darf nicht auf `2.0.0` gehen).  
- Automatisierte Bats-Tests dokumentieren dieses Verhalten.

## Troubleshooting

- Legacy-Skripte mit `# shellcheck disable=...` markieren und begründen.  
- Plattformunterschiede (Linux/macOS) im Skript kommentieren.  
- `shfmt`-Fehler → prüfen, ob Tabs statt Spaces verwendet wurden (wir nutzen nur Spaces).

---

Diese Leitlinien werden zum **Gate-C-Übergang** erneut evaluiert und ggf. in produktive Skripte überführt.  
Weitere Infos werden im Fahrplan dokumentiert.
```

### 📄 weltgewebe/docs/process/fahrplan.md

**Größe:** 9 KB | **md5:** `9b4fd327395da4b4d8d56ec547b027f8`

```markdown
# Fahrplan

**Stand:** 2025-10-20
**Bezug:** ADR-0001 (Clean Slate & Monorepo), ADR-0002 (Re-Entry-Kriterien), ADR-0003 (Privacy: Unschärferadius & RoN)
**Prinzipien:** mobile-first, audit-ready, klein schneiden, Metriken vor Features.

---

## Inhalt

- [Kurzfahrplan (Gates A–D)](#kurzfahrplan-gates-ad)
- [Gate-Checkliste (A–D)](#gate-checkliste-ad)
  - [Gate A — Web (SvelteKit) *Minimal sichtbares Skelett*](#gate-a--web-sveltekit-minimal-sichtbares-skelett)
  - [Gate B — API (Axum) *Health & Kernverträge*](#gate-b--api-axum-health--kernverträge--phaseziele)
  - [Gate C — Infra-light (Compose, Caddy, PG)](#gate-c--infra-light-compose-caddy-pg--phaseziele)
  - [Gate D — Security-Basis](#gate-d--security-basis-grundlagen)
- [0) Vorbereitungen (sofort)](#0-vorbereitungen-sofort)
- [Gate A — Web (SvelteKit) *Minimal sichtbares Skelett* — Phaseziele](#gate-a--web-sveltekit-minimal-sichtbares-skelett--phaseziele)

---

## Kurzfahrplan (Gates A–D)

- **Gate A:** UX Click-Dummy (keine Backends)
- **Gate B:** API-Mock (lokal)
- **Gate C:** Infra-light (Compose, minimale Pfade)
- **Gate D:** Produktive Pfade (härten, Observability)

## Gate-Checkliste (A–D)

### Gate A — Web (SvelteKit) *Minimal sichtbares Skelett*

#### Checkliste „bereit für Gate B“

- [ ] Interaktiver UX-Click-Dummy ist verlinkt (README) und deckt Karte → Knoten → Zeit-UI ab.
- [ ] Contracts-Schemas (`contracts/`) für `node`, `role`, `thread` abgestimmt und dokumentiert.
- [ ] README-Landing beschreibt Click-Dummy, Contracts und verweist auf diesen Fahrplan.
- [ ] Vale-Regeln laufen gegen README/Fahrplan ohne Verstöße.
- [ ] PWA installierbar, Offline-Shell lädt Grundlayout.
- [ ] Dummy-Karte (MapLibre) sichtbar, Layout-Slots vorhanden; Budgets ≤ 60 KB / TTI ≤ 2 s dokumentiert.
- [ ] Minimal-Smoke-Test (Playwright) grün, Lighthouse Mobile ≥ 85.

### Gate B — API (Axum) *Health & Kernverträge*

#### Checkliste „bereit für Gate C“

- [ ] Axum-Service liefert `/health/live`, `/health/ready`, `/version`.
- [ ] OpenAPI-Stub (utoipa) generiert und CI veröffentlicht Artefakt.
- [ ] Kernverträge (`POST /nodes`, `GET /nodes/{id}`, `POST /roles`, `POST /threads`) als Stubs implementiert.
- [ ] `migrations/` vorbereitet (Basis-Tabellen) und CI führt `cargo fmt`, `clippy -D warnings`, `cargo test` aus.
- [ ] `docker compose` (nur API) startet fehlerfrei.
- [ ] Contract-Test gegen `POST /nodes` grün, OpenAPI JSON abrufbar.

### Gate C — Infra-light (Compose, Caddy, PG)

#### Checkliste „bereit für Gate D“

- [ ] `infra/compose/compose.core.yml` umfasst web, api, postgres, pgBouncer, caddy.
- [ ] `infra/caddy/Caddyfile` mit HTTP/3, strikter CSP, gzip/zstd vorhanden.
- [ ] `.env.example` komplettiert, Healthchecks für Dienste konfiguriert.
- [ ] `docker compose -f infra/compose/compose.core.yml up -d` läuft lokal ohne Fehler.
- [ ] Caddy terminiert TLS (self-signed) und proxyt Web+API korrekt.
- [ ] Web-Skelett lädt mit CSP ohne Console-Fehler.

### Gate D — Security-Basis

#### Checkliste „bereit für Re-Entry“

- [ ] Lizenz final (AGPL-3.0-or-later) bestätigt und dokumentiert.
- [ ] Secrets-Plan (sops/age) dokumentiert, keine Klartext-Secrets im Repo.
- [ ] SBOM/Scan (Trivy oder Syft) in CI aktiv, bricht bei kritischen CVEs ab.
- [ ] Runbook „Incident 0“ (Logs sammeln, Restart, Contact) verfügbar.
- [ ] CI schützt Budgets, Policies verlinkt; Observability-Basis beschrieben.

> Details, Akzeptanzkriterien, Budgets und Risiken folgen im Langteil unten.

---

## 0) Vorbereitungen (sofort)

- **Sprache & Vale:** Vale aktiv, Regeln aus `styles/Weltgewebe/*` verbindlich.
- **Lizenz gewählt:** `LICENSE` verwendet **AGPL-3.0-or-later**.
- **Issue-Backlog:** Mini-Issues je Punkt unten (30–90 Min pro Issue).

**Done-Kriterien:** Vale grün in PRs; Lizenz festgelegt; 10–20 Start-Issues.

---

## Gate A — Web (SvelteKit) *Minimal sichtbares Skelett* — Phaseziele

**Ziel:** „Karte hallo sagen“ – startfähiges Web, PWA-Shell, Basislayout, MapLibre-Stub.

### Gate A: Umfang

- PWA: `manifest.webmanifest`, Offline-Shell, App-Icon.
- Layout: Header-Slot, Drawer-Platzhalter (links: Webrat/Nähstübchen, rechts: Filter/Zeitleiste).
- Route `/`: Überschrift + Dummy-Karte (MapLibre einbinden, Tiles später).
- Budgets: **≤60 KB Initial-JS**, **TTI ≤2 s** (Mess-Skript + Budgetdatei).
- Telemetrie (Client): PerformanceObserver für Long-Tasks (nur Log/console bis Gate C).

### Gate A: Aufgabenblöcke

- **UX-Click-Dummy:** Interaktiver Ablauf für Karte → Knoten → Zeit-UI. Figma/Tool-Link im README vermerken.
- **Contracts-Schemas:** JSON-Schemas/OpenAPI für `node`, `role`, `thread`
  abstimmen (Basis für Gate B). Ablage unter `contracts/` und im README
  verlinken.
- **README-Landing:** Landing-Abschnitt aktualisieren (Screenshot/Diagramm +
  Hinweise zum Click-Dummy, Contracts, Fahrplan).
- **Vale-Regeln:** Vale-Regeln aus `styles/Weltgewebe/*` gegen README,
  Fahrplan und Gate-A-Dokumente prüfen, Verstöße beheben.

### Gate A: Done

- Lighthouse lokal ≥ 85 (Mobile), Budgets eingehalten.
- PWA installierbar, Offline-Shell lädt Grundlayout.
- Minimal-Smoke-Test (Playwright) läuft.

---

## Gate B — API (Axum) *Health & Kernverträge* — Phaseziele

**Ziel:** API lebt, dokumentiert und testet minimal **Kernobjekte**: Knoten, Rolle, Faden.

### Gate B: Umfang

- Axum-Service mit `/health/live`, `/health/ready`, `/version`.
- OpenAPI-Stub (utoipa) generiert.
- **Kernverträge:** `POST /nodes`, `GET /nodes/{id}`, `POST /roles`, `POST /threads` (Stub-Implementierung).
- `migrations/` vorbereitet (ohne Fachtabellen).
- CI: `cargo fmt`, `clippy -D warnings`, `cargo test`.

### Gate B: Done

- `docker compose` (nur API) startet grün.
- OpenAPI JSON auslieferbar, minimaler Contract-Test grün (inkl. `POST /nodes`).

---

## Gate C — Infra-light (Compose, Caddy, PG) — Phaseziele

**Ziel:** Dev-Stack per `compose.core.yml` startbar (web+api+pg+caddy).

### Gate C: Umfang

- `infra/compose/compose.core.yml`: web, api, postgres, pgBouncer, caddy.
- `infra/caddy/Caddyfile`: HTTP/3, strikte CSP (später lockern), gzip/zstd.
- `.env.example` vervollständigt; Healthchecks verdrahtet.

### Gate C: Done

- `docker compose -f infra/compose/compose.core.yml up -d` läuft lokal.
- Caddy terminiert TLS lokal (self-signed), Proxies funktionieren.
- Basic CSP ohne Console-Fehler im Web-Skelett.

---

## Gate D — Security-Basis (Grundlagen)

**Ziel:** Minimaler Schutz und Compliance-Leitplanken.

### Gate D: Umfang

- **Lizenz final** (AGPL-3.0-or-later empfohlen).
- Secrets-Plan (sops/age, kein Klartext im Repo).
- SBOM/Scan: Trivy oder Syft in CI (Fail bei kritischen CVEs).
- Doku-Pfad: Kurz-Runbook „Incident 0“ (Logs sammeln, Restart, Contact).

### Gate D: Done

- Lizenz im Repo, CI bricht bei kritischen CVEs.
- Runbook-Skelett vorhanden.

---

## Phase A (Woche 1–2): **Karten-Demo, Zeit-UI, Knoten-Placement**

- Karte sichtbar (MapLibre), Dummy-Layer, UI-Skeleton für Filter & Zeitleiste.
- Zeit-Slider (UI) ohne Datenwirkung, nur State/URL-Sync.
- **Knoten anlegen (UI)**: kleines Formular (Name), flüchtige Speicherung (Client/Mem), Marker erscheint.
- Mobile-Nav-Gesten (Drawer wischen).

**Akzeptanz:** Mobile Lighthouse ≥ 90; TTI ≤ 2 s; UI-Flows klickbar; Knoten-Form erzeugt Marker.

---

## Phase B (Woche 3–4): **Kernmodell — Knoten, Rolle, Faden**

- Domain-Events: `node.created`, `role.created`, `thread.created`.
- Tabellen (PG): `nodes`, `roles`, `threads` (nur ID/Meta), Outbox (leer, aber vorhanden).
- API: `POST /nodes`, `GET /nodes/{id}` echt (PG); `POST /roles`, `POST /threads` stub.
- Web: „Rolle drehen 7 Sekunden“ (UI-Effekt), Faden-Stub Linie Rolle→Knoten (Fake-Data).

**Akzeptanz:** Knoten persistiert in PG; Faden-Stub sichtbar; E2E-Flow „Knoten knüpfen“ klickbar.

---

## Phase C (Woche 5–6): **Privacy-UI (ADR-0003) & 7-Tage-Verblassen**

- UI: **Unschärferadius-Slider** + **RoN-Toggle** (Profil-State; Fake-Persist).
- Zeitleiste wirkt auf Sichtbarkeit (Fäden/Knoten blenden weich aus; Client-seitig).
- `public_pos` im View-Modell (Fake-Backend oder Local-Derivation).

**Akzeptanz:** Vorschau der öffentlichen Position reagiert; Zeitleiste verhält sich wie spezifiziert.

---

## Phase D (Woche 7–8): **Persistenz komplett & Outbox-Hook**

- API: echte Writes für Rolle/Faden in PG; Outbox-Write (noch ohne NATS-Relay).
- Worker-Stub: CLI liest Outbox und füllt Read-Model `public_role_view`.
- Web: liest Read-Model, zeigt `public_pos`, respektiert RoN-Flag.

**Akzeptanz:** Neustart-fest; nach Write→Read-Model erscheint korrekte `public_pos`.

---

## Messpunkte & Budgets

- Web: Initial-JS ≤ 60 KB; p75 Long-Tasks ≤ 200 ms/Route.
- API: p95 Latenz ≤ 300 ms (lokal); Fehlerquote < 1 %.
- Compose-Start ≤ 30 s bis „grün“.

---

## Risiken (kurz)

- Überplanung bremst Tempo → **kleine Issues** erzwingen.
- Privacy-Erwartung vs. Transparenz-Standard → UI-Texte klar formulieren.
- Mobile-Leistung → Budgets als CI-Gate früh aktivieren.

---

## Nächste konkrete Schritte

1. Gate A-Issues anlegen, PWA/Map-Stub bauen.
2. Compose core vorbereiten (web+api+pg+caddy), Caddy mit CSP.
3. API Gate B: `POST /nodes` als erster echter Vertrag, einfache PG-Migration `nodes`.
4. Privacy-UI (Slider/Toggle) per Feature-Flag einhängen.
```

### 📄 weltgewebe/docs/process/sprache.md

**Größe:** 826 B | **md5:** `4557cff8f801c413a82df07f72ad138c`

```markdown
# Sprache & Ton im Weltgewebe

## 1. Grundsatz

- Primärsprache Deutsch (Duden-nah), Du-Form, präzise, knapp.
- Keine Gender-Sonderzeichen (Stern, Doppelpunkt, Binnen-I, Mediopunkt, Slash).
- Anglizismen nur bei echten Fachbegriffen ohne gutes deutsches Pendant.

## 2. Formatkonventionen

- UI: 24-h-Zeit, TT.MM.JJJJ, Dezimalkomma.
- Code/Protokolle: ISO-8601, Dezimalpunkt, SI-Einheiten.

## 3. Artefakte

- Commits: Conventional Commits; Kurzbeschreibung deutsch.
- Code-Kommentare: Englisch (knapp); ADRs/Domäne: Deutsch.
- PRs: deutsch, mit Evidenz-Verweisen.

## 4. Verbote & Alternativen

- Verboten: Schüler:innen, Schüler*innen, SchülerInnen, Schüler/innen, Schüler·innen.
- Nutze Alternativen: Lernende, Team, Ansprechperson, Beteiligte.

## 5. Prüfung

- Vale als Prose-Linter; PR blockt bei Verstößen.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_reports.md

**Größe:** 174 B | **md5:** `9734d00cdc724434f86093ff99ab1103`

```markdown
### 📄 weltgewebe/docs/reports/cost-report.md

**Größe:** 43 B | **md5:** `aa21a19145a081b543bd3b7c24d8fa98`

```markdown
# Cost Report 2025-10

≈ 72.00 EUR/Monat
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_runbooks.md

**Größe:** 3 KB | **md5:** `19f8cd9ddf607445c214df70abe2219e`

```markdown
### 📄 weltgewebe/docs/runbooks/README.md

**Größe:** 205 B | **md5:** `f3721cf652e50a843846daaaced3ed2f`

```markdown
# Runbooks

Anleitungen für wiederkehrende Aufgaben.

- [UV Tooling – Ist-Stand & Ausbauoptionen](uv-tooling.md)
- [Codespaces Recovery](codespaces-recovery.md)
- [Zurück zum Doku-Index](../README.md)
```

### 📄 weltgewebe/docs/runbooks/codespaces-recovery.md

**Größe:** 173 B | **md5:** `4a21868f0d5ab097c1c5e387c812d4a7`

```markdown
# Codespaces Recovery

– Rebuild Container
– remoteUser temporär entfernen
– overrideCommand: true testen
– creation.log prüfen (Pfad siehe postStart.sh Hinweise)
```

### 📄 weltgewebe/docs/runbooks/semantics-intake.md

**Größe:** 233 B | **md5:** `e1aaf4a53383d8fc78af5ff828f74a41`

```markdown

# Semantics Intake (manuell)

1) Von semantAH: `.gewebe/out/nodes.jsonl` und `edges.jsonl` ziehen.
2) In Weltgewebe ablegen unter `.gewebe/in/*.{nodes,edges}.jsonl`.
3) PR eröffnen → Workflow `semantics-intake` validiert Format.
```

### 📄 weltgewebe/docs/runbooks/uv-tooling.md

**Größe:** 2 KB | **md5:** `e5aef3d92b551c437d85b82424d258f6`

```markdown
# UV Tooling – Ist-Stand & Ausbauoptionen

Dieser Runbook-Eintrag fasst zusammen, wie der Python-Paketmanager
[uv](https://docs.astral.sh/uv/) heute im Repo eingebunden ist und welche
Erweiterungen sich anbieten.

## Aktueller Stand

- **Installation im Devcontainer:** `.devcontainer/post-create.sh` installiert `uv`
  per offizieller Astral-Installroutine und macht das Binary direkt verfügbar.
- **Dokumentation im Root-README:** Das Getting-Started beschreibt, dass `uv`
  im Devcontainer bereitgestellt wird und dass Lockfiles (`uv.lock`) eingecheckt
  werden sollen.
- **Python-Tooling-Workspace:** Unter `tools/py` liegt ein `pyproject.toml` mit
  Basiskonfiguration für Python-Helfer; zusätzliche Dependencies würden hier via
  `uv add` gepflegt.

Damit ist `uv` bereits für Tooling-Aufgaben vorbereitet, benötigt aber aktuell
noch keine Abhängigkeiten.

## Potenzial für Verbesserungen

1. **Lockfile etablieren:** Sobald der erste Dependency-Eintrag erfolgt, sollte
   `uv lock` ausgeführt und das entstehende `uv.lock` versioniert werden. Ein
   leeres Lockfile kann auch jetzt schon erzeugt werden, um den Workflow zu
   testen und künftige Änderungen leichter reviewen zu können.
2. **Just-Integration:** Ein `just`-Target (z. B. `just uv-sync`) würde das
   Synchronisieren des Tooling-Environments standardisieren – sowohl lokal als
   auch in CI.
3. **CI-Checks:** Ein optionaler Workflow-Schritt könnte `uv sync --locked`
   ausführen, um zu prüfen, dass das Lockfile konsistent ist, sobald Python-Tasks
   relevant werden.
4. **Fallback für lokale Maschinen:** Außerhalb des Devcontainers sollte das
   README kurz beschreiben, wie `uv` manuell installiert wird (z. B. per
   Installscript oder Paketmanager), damit Contributor:innen ohne Devcontainer
   den gleichen Setup-Pfad nutzen.

Diese Punkte lassen sich unabhängig voneinander umsetzen und sorgen dafür, dass
`uv` vom vorbereiteten Tooling-Baustein zu einem reproduzierbaren Bestandteil
von lokalen und CI-Workflows wird.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_specs.md

**Größe:** 3 KB | **md5:** `d0b989eb22bb870fb3a4e5201c00650d`

```markdown
### 📄 weltgewebe/docs/specs/contract.md

**Größe:** 2 KB | **md5:** `11cb90fa2b4c503b431651ccfac6cdbb`

```markdown
# Weltgewebe Contract – Löschkonzept (Tombstone & Key-Erase)

**Status:** Draft v0.1 · **Scope:** Beiträge, Kommentare, Artefakte

## 1. Modell

- **Event-Sourcing:** Jede Änderung ist ein Event. Historie ist unveränderlich.
- **Inhalt:** Nutzinhalte werden _verschlüsselt_ gespeichert (objektbezogener Daten-Key).
- **Identität:** Nutzer signieren Events (Ed25519). Server versieht Batches mit Transparency-Log
  (Merkle-Hash + Timestamp).

## 2. Löschen („jederzeit möglich“)

- **Semantik:** _Logisch löschen_ durch `DeleteEvent` (Tombstone). Der zugehörige **Daten-Key wird verworfen**
  (Key-Erase).
- **Effekt:**
  - UI zeigt „Gelöscht durch Autor“ (Zeitstempel, optional Grund).
  - Inhaltstext/Binary ist selbst für Admins nicht mehr rekonstruierbar.
  - Event-Spur bleibt (Minimalmetadaten: Objekt-ID, Autor-ID Hash, Zeit, Typ).
- **Unwiderruflichkeit:** Key-Erase ist irreversibel. Wiederherstellung nur möglich, wenn der Autor
  einen **lokal gesicherten Key** besitzt und freiwillig re-upploadet.

## 3. Rechts-/Moderationsbezug

- **Rechtswidrige Inhalte:** Sofortiger **Takedown-Hold**: Inhalt unzugänglich; Forensik-Snapshot
  (Hash + Signatur) intern versiegelt. Öffentlich nur Meta-Ticket.
- **DSGVO:** „Löschen“ i. S. d. Betroffenenrechte = Tombstone + Key-Erase. Historische
  Minimaldaten werden als _technische Protokollierung_ mit berechtigtem Interesse (Art. 6 (1) f)
  geführt.

## 4. API-Verhalten

- `GET /items/{id}`:
  - bei Tombstone: `{ status:"deleted", deleted_at, deleted_by, reason? }`
  - kein Content-Payload, keine Wiederherstellungs-Links
- `DELETE /items/{id}`:
  - idempotent; erzeugt `DeleteEvent` + triggert Key-Erase.

## 5. Migrationshinweis

- Bis zur produktiven Verschlüsselung gilt: _Soft-Delete + Scrub_: Inhalt wird überschrieben (z. B.
  mit Zufallsbytes), Backups erhalten Löschmarker, Replikate werden re-keyed.

## 6. Telemetrie/Transparenz

- Wöchentliche Veröffentlichung eines **Transparency-Anchors** (Root-Hash der Woche).
- Öffentliche Statistik: Anzahl Tombstones, Takedown-Holds, mediane Löschzeit.

---

**Kurzfassung:** Löschen = _Tombstone_ (sichtbar) + _Key-Erase_ (Inhalt weg).
Historie bleibt integer, Privatsphäre bleibt gewahrt.
```

### 📄 weltgewebe/docs/specs/privacy-api.md

**Größe:** 134 B | **md5:** `a5dda2dfc103475fba76f2023ed93589`

```markdown
# Privacy API (ADR-0003)

GET/PUT /me/visibility { radius_m, ron_flag }, View: public_role_view (id, public_pos, ron_flag, radius_m).
```

### 📄 weltgewebe/docs/specs/privacy-ui.md

**Größe:** 107 B | **md5:** `435f90a22ac8fbb74cf057947198dac8`

```markdown
# Privacy UI (ADR-0003)

Slider (r Meter), RoN-Toggle, Vorschau public_pos. Texte: Transparenz = Standard.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_docs_x-repo.md

**Größe:** 3 KB | **md5:** `7e6313e591b126a6560a5043beabc6b5`

```markdown
### 📄 weltgewebe/docs/x-repo/peers-learnings.md

**Größe:** 3 KB | **md5:** `0aa0e6faf00f6d4eba55e8596e31e068`

```markdown

# Kurzfassung: Übertragbare Praktiken aus HausKI, semantAH und WGX-Profil

## X-Repo Learnings → sofort anwendbare Leitplanken für Konsistenz & Qualität

- **Semantische Artefakte versionieren:** Ein leichtgewichtiges Graph-Schema (z. B. `nodes.jsonl`/`edges.jsonl`)
  und eingebettete Cluster-Artefakte direkt im Repo halten, um Beziehungen, Themen und Backlinks
  portabel zu machen.
- **Terminologie & Synonyme pflegen:** Eine gepflegte Taxonomie (z. B. `synonyms.yml`, `entities.yml`)
  unterstützt Suche, Filter und konsistente Begriffsnutzung.
- **Governance-Logik messbar machen:** Domänenregeln (**7-Tage** Verblassen, **84-Tage** RoN-Anonymisierung,
  Delegationsabläufe) über konkrete Metriken, Dashboards und Alerts operationalisieren.
  → vgl. `docs/zusammenstellung.md`
- **WGX-Profil als Task-SSoT:** Ein zentrales Profil `.wgx/profile.yml` definiert Env-Prioritäten &
  Standard-Tasks (`up/lint/test/build/smoke`) und vermeidet Drift zwischen lokal & CI.
- **Health/Readiness mit Policies koppeln:** Die bestehenden `/health/live` und `/health/ready` um
  Policy-Signale (Rate-Limits, Retention, Governance-Timer) ergänzen und in Runbooks verankern.
- **UI/Produkt-Definition testbar machen:** UI-Spezifika (Map-UI, Drawer, Zeitleiste, Knotentypen) als
  Playwright-/Vitest-Szenarien automatisieren, um Regressionen früh zu erkennen.
- **Föderierung & Archiv-Strategie festigen:** Hybrid-Indexierung durch wiederkehrende Archiv-Validierung,
  URL-Kanonisierungstests und CI-Jobs absichern.
- **Delegation/Abstimmung operationalisieren:** Policy-Engines und Telemetrie-Events (z. B.
  `delegation_expired`, `proposal_auto_passed`) etablieren, um Governance-Wirkung zu messen.
- **Kosten-Szenarien als Code umsetzen:** Kostenmodelle (S1–S4) in Versionierung halten und regelmäßige
  `cost-report.md`-Artefakte in CI erzeugen.
- **Security als Release-Gate durchsetzen:** SBOM, Signaturen, Key-Rotation und CVE-Schwellen als harte
  CI-Gates etablieren, um Releases zu schützen.

## Nächste Schritte (knapp & machbar)

- [x] `docs/README.md`: Abschnitt **„X-Repo Learnings“** mit Link auf dieses Dokument ergänzen.
- [ ] `.wgx/profile.yml`: Standard-Tasks `up|lint|test|build|smoke` definieren (Repo-SSoT).
- [ ] `/health/ready`: Policy-Signal-Platzhalter ausgeben (z. B. als JSON-Objekt wie
  `{ "governance_timer_ok": true, "rate_limit_ok": true }`), um den Status relevanter Policies
  maschinenlesbar bereitzustellen.
- [ ] `ci/`: Playwright-Smoke für Map-UI (1–2 kritische Szenarien) hinzufügen.
- [ ] `ci/`: `cost-report.md` (S1–S4) als regelmäßiges Artefakt erzeugen.
- [ ] `ci/`: SBOM+Signatur+Audit als Gate in Release-Workflow aktivieren.
```

### 📄 weltgewebe/docs/x-repo/semantAH.md

**Größe:** 125 B | **md5:** `6f438447ce4e4f73be3ce061c2584c0b`

```markdown
Weltgewebe konsumiert semantAH-Exports. Kein Schreibpfad zurück.
Import-Job und Event-Verdrahtung folgen in separaten ADRs.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_infra_caddy.md

**Größe:** 916 B | **md5:** `6d7d857874a6e3fbe806e4f2ada239a2`

```markdown
### 📄 weltgewebe/infra/caddy/Caddyfile

**Größe:** 789 B | **md5:** `3bfda9b8da56d21a02514d98eb48fd0a`

```plaintext
{
  auto_https off
  servers :8081 {
    protocol {
      experimental_http3
    }
    logs {
      level INFO
    }
  }
}

:8081 {
  encode zstd gzip
  # Strippt /api Prefix, damit /api/health -> /health an der API ankommt
  handle_path /api/* {
    reverse_proxy api:8080
  }
  reverse_proxy /* web:5173
  header {
    # Dev-CSP: HMR/WebSocket & Dev-Assets erlauben; bei Bedarf später härten
    # Für externe Tiles ggf. ergänzen, z.B.:
    #   img-src 'self' data: blob: https://tile.openstreetmap.org https://*.tile.openstreetmap.org;
    Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' ws: wss:; img-src 'self' data: blob:; object-src 'none';"
    X-Frame-Options "DENY"
    Referrer-Policy "no-referrer"
  }
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_infra_compose.md

**Größe:** 3 KB | **md5:** `c3ef6e7b6808cd061b95c407f5a221fd`

```markdown
### 📄 weltgewebe/infra/compose/compose.core.yml

**Größe:** 3 KB | **md5:** `e123001a9bff5640f956ec4a03dfa58c`

```yaml
version: "3.9"

services:
  web:
    profiles: ["dev"]
    image: node:20-alpine
    working_dir: /workspace
    command:
      - sh
      - -c
      - |
        if [ ! -d node_modules ]; then
          npm ci;
        fi;
        exec npm run dev -- --host 0.0.0.0 --port 5173
    volumes:
      - ../../apps/web:/workspace
    ports:
      - "5173:5173"
    depends_on:
      api:
        condition: service_healthy
    environment:
      NODE_ENV: development
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:5173 >/dev/null"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  api:
    profiles: ["dev"]
    image: rust:1.83-bullseye
    working_dir: /workspace
    command: ["cargo", "run", "--manifest-path", "apps/api/Cargo.toml", "--bin", "api"]
    environment:
      API_BIND: ${API_BIND:-0.0.0.0:8080}
      DATABASE_URL: postgres://welt:gewebe@pgbouncer:6432/weltgewebe
      RUST_LOG: ${RUST_LOG:-info}
    depends_on:
      pgbouncer:
        condition: service_started
    ports:
      - "8080:8080"
    volumes:
      - ../..:/workspace
      - cargo_registry:/usr/local/cargo/registry
      - cargo_git:/usr/local/cargo/git
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8080/health/live >/dev/null || curl -fsS http://localhost:8080/health/ready >/dev/null || curl -fsS http://localhost:8080/version >/dev/null"]
      interval: 5s
      timeout: 3s
      retries: 30
    restart: unless-stopped

  db:
    profiles: ["dev"]
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-welt}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-gewebe}
      POSTGRES_DB: ${POSTGRES_DB:-weltgewebe}
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-welt}"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 20s

  pgbouncer:
    profiles: ["dev"]
    image: edoburu/pgbouncer:1.20
    environment:
      DATABASE_URL: postgres://welt:gewebe@db:5432/weltgewebe
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 200
      DEFAULT_POOL_SIZE: 10
      AUTH_TYPE: trust
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "6432:6432"

  caddy:
    profiles: ["dev"]
    image: caddy:2
    ports:
      - "8081:8081"
    volumes:
      - ../caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    depends_on:
      web:
        condition: service_healthy
      api:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pg_data:
  cargo_registry:
  cargo_git:
```

### 📄 weltgewebe/infra/compose/compose.observ.yml

**Größe:** 482 B | **md5:** `ed2503dd1bc994acd9dc84efbfb815c6`

```yaml
version: "3.9"
services:
  prometheus:
    image: prom/prometheus:v2.54.1
    ports: ["9090:9090"]
    # volumes:
    #   - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  grafana:
    image: grafana/grafana:11.1.4
    ports: ["3001:3000"]
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
  loki:
    image: grafana/loki:3.2.1
    ports: ["3100:3100"]
  tempo:
    image: grafana/tempo:2.5.0
    ports: ["3200:3200"]
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_infra_compose_grafana_provisioning_dashboards.md

**Größe:** 2 KB | **md5:** `81db174d70cfab7f67bd0f10052927b3`

```markdown
### 📄 weltgewebe/infra/compose/grafana/provisioning/dashboards/weltgewebe.json

**Größe:** 2 KB | **md5:** `3e09136fc46baf5e4e9d62181c02d2c8`

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "gnetId": null,
  "graphTooltip": 0,
  "iteration": 1,
  "links": [],
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "red",
                "value": null
              },
              {
                "color": "green",
                "value": 1
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 8,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "colorMode": "value",
        "graphMode": "area",
        "justifyMode": "center",
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "",
          "values": false
        },
        "text": {}
      },
      "targets": [
        {
          "editorMode": "code",
          "expr": "up{job=\"api\"}",
          "legendFormat": "",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "API availability",
      "type": "stat"
    }
  ],
  "refresh": "30s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": [
    "weltgewebe"
  ],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-15m",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Weltgewebe Starter",
  "uid": "weltgewebe-starter",
  "version": 1
}
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_infra_compose_monitoring.md

**Größe:** 331 B | **md5:** `9724f0601a112edac86a49ab11096d2e`

```markdown
### 📄 weltgewebe/infra/compose/monitoring/prometheus.yml

**Größe:** 191 B | **md5:** `b120ae667279988bdc058618653cfcfc`

```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: api
    static_configs:
      - targets:
          - host.docker.internal:8080 # on Linux consider host networking or extra_hosts
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_infra_compose_sql_init.md

**Größe:** 280 B | **md5:** `80c3d403b889e407fac627b26dd3681a`

```markdown
### 📄 weltgewebe/infra/compose/sql/init/00_extensions.sql

**Größe:** 140 B | **md5:** `2dcecbff232b900dacd96d7bb6fdb12d`

```sql
-- optional: hilfreiche Extensions als Ausgangspunkt
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_policies.md

**Größe:** 4 KB | **md5:** `6fcc444efe654fded20137f114c4e522`

```markdown
### 📄 weltgewebe/policies/limits.yaml

**Größe:** 1 KB | **md5:** `1dee2dc0df293c029b353894c90a3135`

```yaml
---
# Weltgewebe – Soft Limits (v1)
# Zweck: Leitplanken sichtbar machen. Zunächst nur dokumentarisch; keine harten Gates.
version: v1
updated: 2025-02-14
owner: platform

web:
  bundle:
    # Gesamtbudget für alle produktiven JS/CSS-Assets (komprimiert)
    total_kb: 350
    note: "Muss zum 'ci/budget.json' passen; später automatische Prüfung."
  build:
    max_minutes: 10
    note: "CI-Build der Web-App soll schnell bleiben; Ziel für Developer-Feedback."

api:
  latency:
    p95_ms: 300
    note: "Lokales/dev-nahes Ziel; Produktions-SLOs stehen in policies/slo.yaml."
  test:
    max_minutes: 10
    note: "Schnelle Rust-Tests, damit PR-Feedback nicht stockt."

ci:
  max_runtime_minutes:
    default: 20
    heavy: 45
    note: "Deckel pro Job; deckt sich mit aktuellen Timeouts in Workflows (Stand Februar 2025)."

observability:
  required:
    - "compose.core.yml"
    - "compose.observ.yml"
  note: "Sobald Observability-Compose landet, wird hier 'compose.observ.yml' Pflicht."

docs:
  runbooks_required:
    - "docs/runbooks/README.md"
    - "docs/runbooks/codespaces-recovery.md"
    - "docs/runbooks/observability.md"
  note: "observability.md folgt; zunächst nur als Reminder gelistet."

semantics:
  max_nodes_jsonl_mb: 50
  max_edges_jsonl_mb: 50
  note: "Nur Informationsaufnahme; Import-Job folgt separat."
```

### 📄 weltgewebe/policies/perf.json

**Größe:** 421 B | **md5:** `ec77e50ece7ad6399752423748414e0f`

```json
{
  "frontend": {
    "js_budget_kb": 60,
    "tti_ms_p95": 2500,
    "lcp_ms_p75": 2500,
    "long_tasks_per_view_max": 10
  },
  "api": {
    "latency_ms_p95": 300,
    "db_query_ms_p95": 150,
    "latency_target_note": "API latency target and SLO policy latency target are both set to 300ms intentionally for consistency."
  },
  "edge": {
    "monthly_egress_gb_max": 200,
    "edge_cost_delta_30d_pct_max": 10
  }
}
```

### 📄 weltgewebe/policies/retention.yml

**Größe:** 416 B | **md5:** `67096157882cd66d87f83024d4e5313e`

```yaml
data_lifecycle:
  fade_days: 7
  ron_days: 84
  delegation_expire_days: 28
  anonymize_opt_in_default: true
forget_pipeline:
  - name: primary_accounts
    actions:
      - type: anonymize
        deadline_days: 7
      - type: delete
        deadline_days: 84
  - name: delegation_tokens
    actions:
      - type: revoke
        deadline_days: 28
compliance:
  privacy_by_design: true
  ron_anonymization: enabled
```

### 📄 weltgewebe/policies/security.yml

**Größe:** 371 B | **md5:** `6609aa917e7b36ec6d837afd9e342cb8`

```yaml
content_security_policy:
  default-src: "'self'"
  img-src: "'self' data:"
  script-src: "'self' 'unsafe-inline'"
  connect-src:
    - "'self'"
    - https://api.weltgewebe.internal
allowed_origins:
  - https://app.weltgewebe.example
  - https://console.weltgewebe.example
strict_transport_security:
  max_age_seconds: 63072000
  include_subdomains: true
  preload: true
```

### 📄 weltgewebe/policies/slo.yaml

**Größe:** 437 B | **md5:** `406302df1aad0e217bf229bfeb9c5298`

```yaml
version: 1
services:
  web:
    # availability_target is a percentage (e.g., 99.9% uptime)
    availability_target: 99.9
    latency:
      p95_ms: 3000
      alert_threshold_pct_over_budget: 5
  api:
    # availability_target is a percentage (e.g., 99.95% uptime)
    availability_target: 99.95
    latency:
      p95_ms: 300
      alert_threshold_pct_over_budget: 5
error_budgets:
  window_days: 30
  warn_at_pct: 25
  page_at_pct: 50
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_scripts_tools.md

**Größe:** 2 KB | **md5:** `f66c1415a1962a9d8855cb351475dcdd`

```markdown
### 📄 weltgewebe/scripts/tools/yq-pin.sh

**Größe:** 1 KB | **md5:** `cb5601bb97c2f54026234dd5968f3653`

```bash
#!/usr/bin/env bash
set -euo pipefail

# Minimaler Installer/Pinner für mikefarah/yq v4.x
# Usage: scripts/tools/yq-pin.sh ensure [<version>]
# Default: 4.44.3

CMD="${1:-ensure}"
REQ_VER="${2:-4.44.3}"
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
  local os="linux"
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
  esac
  local url="https://github.com/mikefarah/yq/releases/download/v${ver}/yq_${os}_${arch}"
  echo "Downloading yq v${ver} from: ${url}"
  curl -fsSL "${url}" -o "${BIN}.tmp"
  chmod +x "${BIN}.tmp"
  mv "${BIN}.tmp" "${BIN}"
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
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_tools.md

**Größe:** 609 B | **md5:** `ef080f479c581c3484997cc37106c53c`

```markdown
### 📄 weltgewebe/tools/drill-smoke.sh

**Größe:** 488 B | **md5:** `ab47f66548de5afccc0688ba95c42ba3`

```bash
#!/usr/bin/env bash
set -euo pipefail

printf "[drill] Starting disaster recovery smoke sequence...\n"

# Placeholder: ensure core services are up
if ! docker compose -f infra/compose/compose.core.yml ps >/dev/null 2>&1; then
  printf "[drill] Hinweis: Compose-Stack scheint nicht zu laufen. Bitte zuerst 'just up' ausführen.\n"
  exit 1
fi

docker compose -f infra/compose/compose.core.yml ps

printf "[drill] TODO: Automatisierte Smoke-Tests (Login, Thread-Erstellung) integrieren.\n"
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_tools_py.md

**Größe:** 2 KB | **md5:** `2ed2ce30cb74b5bd5c1d1dde583280cd`

```markdown
### 📄 weltgewebe/tools/py/README.md

**Größe:** 296 B | **md5:** `6a43f76336f99f1d2caf09c2b5ad8e7f`

```markdown
# Weltgewebe – Python Tools

## Schnellstart

```bash
cd tools/py
uv sync        # erstellt venv, installiert deps (aktuell leer)
uv run python -V
```

## Abhängigkeiten hinzufügen

```bash
uv add ruff black
```

Das erzeugt/aktualisiert `uv.lock` – damit sind Builds in CI reproduzierbar.
```

### 📄 weltgewebe/tools/py/policycheck.py

**Größe:** 1 KB | **md5:** `1531eb55d304c38c6b8ceb91980e0a7c`

```python
#!/usr/bin/env python3
"""Basic policy consistency checks."""

from __future__ import annotations

import pathlib
import sys

import yaml


def main() -> int:
    policy_path = pathlib.Path("policies/retention.yml")
    if not policy_path.exists():
        print("::error::policies/retention.yml missing")
        return 1

    data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    lifecycle = data.get("data_lifecycle")
    if not isinstance(lifecycle, dict):
        print("::error::data_lifecycle section missing")
        return 1

    try:
        fade_days = int(lifecycle["fade_days"])
        ron_days = int(lifecycle["ron_days"])
    except (KeyError, TypeError, ValueError) as exc:
        print(f"::error::invalid lifecycle values: {exc}")
        return 1

    if fade_days <= 0:
        print("::error::fade_days must be > 0")
        return 1

    if ron_days < fade_days:
        print("::error::ron_days must be >= fade_days")
        return 1

    print("policy ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 📄 weltgewebe/tools/py/pyproject.toml

**Größe:** 259 B | **md5:** `96b3e59f00667138a66ea5d634b58b6b`

```toml
[project]
name = "weltgewebe-tools"
version = "0.1.0"
description = "Python tooling for Weltgewebe (CLI, lint, ETL, experiments)"
requires-python = ">=3.11"
dependencies = []

[tool.uv]
# uv verwaltet Lockfile uv.lock im Projektroot oder hier im Unterordner.
```
```

### 📄 merges/weltgewebe_merge_2510262237__weltgewebe_tools_py_cost.md

**Größe:** 2 KB | **md5:** `9dfdc0256495fc2443eb63564ea658cd`

```markdown
### 📄 weltgewebe/tools/py/cost/model.csv

**Größe:** 98 B | **md5:** `98ff2a57322a28e11011e8132b3cba57`

```plaintext
metric,value,unit
request_cost_eur,0.0002,EUR
session_avg_requests,12,req
active_users,1000,users
```

### 📄 weltgewebe/tools/py/cost/report.py

**Größe:** 1 KB | **md5:** `8312cd39317502c07772c03ff60f6d4e`

```python
#!/usr/bin/env python3
"""Generate a simple monthly cost report."""

from __future__ import annotations

import csv
import datetime as dt
import pathlib


MODEL_PATH = pathlib.Path("tools/py/cost/model.csv")
OUTPUT_PATH = pathlib.Path("docs/reports/cost-report.md")


def load_metric(rows: list[dict[str, str]], name: str) -> float:
    for row in rows:
        if row["metric"] == name:
            return float(row["value"])
    raise KeyError(name)


def main() -> int:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(MODEL_PATH)

    with MODEL_PATH.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    request_cost_eur = load_metric(rows, "request_cost_eur")
    avg_requests = load_metric(rows, "session_avg_requests")
    active_users = load_metric(rows, "active_users")

    monthly_cost = active_users * avg_requests * request_cost_eur * 30

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        "# Cost Report {:%Y-%m}\n\n≈ {:.2f} EUR/Monat\n".format(
            dt.date.today(), monthly_cost
        ),
        encoding="utf-8",
    )

    print(OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
```

