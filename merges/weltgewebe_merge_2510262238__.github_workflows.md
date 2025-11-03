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
          fi
```

### 📄 .github/workflows/policycheck.yml

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

### 📄 .github/workflows/python-tooling.yml

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

      - name: Sync dependencies if present
        shell: bash
        run: |
          set -euo pipefail
          found=0
          # Scan all dirs that contain a Python manifest.
          while IFS= read -r dir; do
            found=1
            if [ -f "$dir/uv.lock" ]; then
              echo "::group::uv sync (locked) in $dir"
              (cd "$dir" && uv sync --locked)
              echo "::endgroup::"
            elif [ -f "$dir/requirements.txt" ]; then
              echo "::group::uv pip sync in $dir"
              (cd "$dir" && uv pip sync requirements.txt)
              echo "::endgroup::"
            elif [ -f "$dir/pyproject.toml" ]; then
              echo "::group::uv sync in $dir"
              (cd "$dir" && uv sync)
              echo "::endgroup::"
            fi
          done < <(find . -type f \( -name "uv.lock" -o -name "requirements.txt" -o -name "pyproject.toml" \) -exec dirname {} \; | sort -u)
          if [ "$found" -eq 0 ]; then
            echo "No Python dependency manifests found. Skipping sync."
          fi

      - name: Python sanity check
        run: python -c "import sys; print('python ok:', sys.version)"
```

### 📄 .github/workflows/release.yml

**Größe:** 273 B | **md5:** `e97d7b96bbfd5e7df6cfb569114c6b3e`

```yaml
name: release
on:
  push:
    tags: ['v*.*.*']
jobs:
  publish:
    permissions:
      contents: write
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
```

### 📄 .github/workflows/security.yml

**Größe:** 3 KB | **md5:** `ce280e475e644334210f6284044eaade`

```yaml
name: security

on:
  workflow_dispatch: {}
  pull_request:
    branches: [main]
    paths:
      - "Cargo.toml"
      - "Cargo.lock"
      - "**/Cargo.toml"
      - "**/Cargo.lock"
      - "deny.toml"
      - ".github/workflows/security.yml"
    types: [opened, synchronize, labeled]
  schedule:
    - cron: "45 2 * * *"   # nightly audit (02:45 UTC ≈ 04:45 Berlin)
    - cron: "10 3 * * 0"   # weekly deny (03:10 UTC ≈ 05:10 Berlin)
    - cron: "25 3 * * 0"   # weekly SBOM (03:25 UTC ≈ 05:25 Berlin)

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

env:
  CARGO_TERM_COLOR: always

jobs:
  audit:
    name: cargo audit (nightly + on-demand)
    runs-on: ubuntu-latest
    timeout-minutes: 10
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' &&
       contains(github.event.pull_request.labels.*.name, 'security')) ||
      (github.event_name == 'schedule')
    steps:
      - uses: actions/checkout@v4
      - name: Install Rust toolchain
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: stable
      - name: Cache cargo
        uses: Swatinem/rust-cache@v2
      - name: Install cargo-audit
        run: cargo install cargo-audit --locked --force
      - name: Run cargo audit (JSON report)
        run: cargo audit --json | tee cargo-audit-report.json
      - name: Upload audit report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: cargo-audit-report
          path: cargo-audit-report.json
          retention-days: 14

  deny:
    name: cargo-deny (weekly + on-demand)
    runs-on: ubuntu-latest
    timeout-minutes: 12
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' &&
       contains(github.event.pull_request.labels.*.name, 'security')) ||
      (github.event_name == 'schedule' && github.event.schedule.cron == '10 3 * * 0')
    steps:
      - uses: actions/checkout@v4
      - name: Install Rust toolchain
        uses: dtolnay/rust-toolchain@stable
        with:
          toolchain: stable
      - name: Cache cargo
        uses: Swatinem/rust-cache@v2
      - name: Install cargo-deny
        run: cargo install cargo-deny --locked --force
      - name: Run cargo deny (JSON report)
        run: cargo deny --format json check | tee cargo-deny-report.json
      - name: Upload cargo-deny report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: cargo-deny-report
          path: cargo-deny-report.json
          retention-days: 14

  sbom:
    name: syft sbom (weekly + on-demand)
    runs-on: ubuntu-latest
    timeout-minutes: 15
    if: |
      github.event_name == 'workflow_dispatch' ||
      (github.event_name == 'pull_request' &&
       contains(github.event.pull_request.labels.*.name, 'security')) ||
      (github.event_name == 'schedule' && github.event.schedule.cron == '25 3 * * 0')
    steps:
      - uses: actions/checkout@v4
      - name: Generate SBOM with Syft
        uses: anchore/sbom-action@v0
        with:
          path: .
          format: spdx-json
          output-file: sbom.spdx.json
      - name: Upload SBOM artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: sbom-spdx
          path: sbom.spdx.json
          retention-days: 21
```

### 📄 .github/workflows/semantics-intake.yml

**Größe:** 3 KB | **md5:** `08f0a7eb68f951a9355407fbb5c15b9c`

```yaml
name: semantics-intake
on:
  pull_request:
    paths:
      - "contracts/semantics/**"
      - ".gewebe/in/**"
  workflow_dispatch: {}

permissions:
  contents: read
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install PyYAML
        run: python3 -m pip install pyyaml
      - name: Install ajv
        run: npm i -g ajv-cli@5.0.0
      - name: Enforce size limits
        run: |
          python - <<'PY'
            import math
            import sys
            from pathlib import Path

            import yaml

            limits_path = Path("policies/limits.yaml")
            if not limits_path.exists():
                print("::error::policies/limits.yaml missing")
                sys.exit(1)

            data = yaml.safe_load(limits_path.read_text(encoding="utf-8")) or {}
            sem = data.get("semantics", {})
            try:
                max_nodes = int(sem.get("max_nodes_jsonl_mb"))
                max_edges = int(sem.get("max_edges_jsonl_mb"))
            except (TypeError, ValueError):
                print("::error::semantics limits must be integers")
                sys.exit(1)

            def file_size_mb(path: Path) -> int:
                return math.ceil(path.stat().st_size / (1024 * 1024))

            for path in Path(".gewebe/in").glob("*.jsonl"):
                size_mb = file_size_mb(path)
                if path.name.endswith(".nodes.jsonl") and size_mb > max_nodes:
                    print(f"::error::{path} > limit ({size_mb} MB > {max_nodes} MB)")
                    sys.exit(1)
                if path.name.endswith(".edges.jsonl") and size_mb > max_edges:
                    print(f"::error::{path} > limit ({size_mb} MB > {max_edges} MB)")
                    sys.exit(1)
            print("Semantic intake size limits respected")
            PY
      - name: Validate incoming JSONL (if present)
        run: |
          set -euo pipefail
          shopt -s nullglob
          found=0
          for f in .gewebe/in/*.jsonl; do
            [ -f "$f" ] || continue
            schema=""
            case "$f" in
              *.nodes.jsonl) schema=contracts/semantics/node.schema.json ;;
              *.edges.jsonl) schema=contracts/semantics/edge.schema.json ;;
            esac
            [ -n "$schema" ] || continue
            found=1
            while IFS= read -r line; do
              echo "$line" | ajv validate -s "$schema" -d - || exit 1
            done < "$f"
          done
          if [ "$found" -eq 0 ]; then
            echo "No .gewebe/in/*.jsonl found; nothing to validate."
          else
            echo "Validation OK"
          fi
```

### 📄 .github/workflows/seo-archive.yml

**Größe:** 590 B | **md5:** `c57dd8550f672a0e1e209fb2c3f6ce5a`

```yaml
name: seo-archive
permissions:
  contents: read
on:
  pull_request:
    paths:
      - "apps/web/**"
      - "docs/**"
      - ".github/workflows/seo-archive.yml"
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Validate archive routes (static hints)
        run: |
          if ! grep -R "rel=\"canonical\"" -n apps/web; then
            echo "::error::no canonicals found"
            exit 1
          fi
          if ! grep -R "/archive/" -n apps/web; then
            echo "::error::no archive routes"
            exit 1
          fi
```

### 📄 .github/workflows/web-e2e.yml

**Größe:** 1 KB | **md5:** `1ac878d2192143b37a405eac4c6c8766`

```yaml
name: Web E2E (manual)

on:
  workflow_dispatch: {}

permissions:
  contents: read

concurrency:
  group: web-e2e-${{ github.ref }}
  cancel-in-progress: true

defaults:
  run:
    working-directory: apps/web

jobs:
  e2e:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      actions: write   # required for npm cache restore
    env:
      HEADLESS: "1"
      NPM_CONFIG_AUDIT: "false"
      NPM_CONFIG_FUND: "false"
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20.19.0'
          cache: 'npm'
          cache-dependency-path: apps/web/package-lock.json
      - name: Enable Corepack (npm)
        run: corepack enable
      - name: Install deps
        run: npm ci
      - name: Install Playwright browsers
        run: npm run test:setup
      - name: Build app
        run: npm run build
      - name: Run tests
        run: npm run test:ci
      - name: Upload HTML report (always)
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: apps/web/playwright-report/
          if-no-files-found: ignore
      - name: Upload traces (on failure)
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-traces
          path: apps/web/test-results/**/*.zip
          if-no-files-found: ignore
```

### 📄 .github/workflows/web.yml

**Größe:** 2 KB | **md5:** `ff059d45936dd43bfe03f21bbf6f8619`

```yaml
name: Web Check (Gate A)

permissions:
  contents: read

on:
  pull_request:
    branches: [main, dev]
    paths:
      - apps/web/**
      - .github/workflows/web.yml
  push:
    branches: [main, dev, 'feat/**', 'fix/**']
    paths:
      - apps/web/**
      - .github/workflows/web.yml

jobs:
  build:
    name: Build & Lint
    runs-on: ubuntu-latest
    permissions:
      contents: read
      actions: write   # required for npm cache restore
    env:
      PUPPETEER_SKIP_DOWNLOAD: "true"
      NPM_CONFIG_AUDIT: "false"
      NPM_CONFIG_FUND: "false"
    concurrency:
      group: ${{ github.workflow }}-${{ github.ref }}
      cancel-in-progress: true
    defaults:
      run:
        working-directory: apps/web

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20.19.0'
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - name: Enable Corepack (npm)
        run: corepack enable

      - name: Install dependencies
        run: |
          # Bevorzugt deterministisch mit npm ci, fällt aber bei stale lockfile
          # automatisch auf npm install zurück, damit der Run nicht scheitert.
          npm ci || (echo "::warning::package-lock.json ist nicht in Sync – fallback auf 'npm install'"; npm install --include=dev)

      - name: SvelteKit prepare
        run: npm run sync

      - name: Typecheck
        run: npm run check

      - name: Lint
        run: npm run lint

      - name: Build
        run: CI=true npm run build

      - name: Playwright: setup browsers (CI)
        # WICHTIG: Nicht "0" setzen – jede nicht-leere Zeichenkette gilt als truthy
        # und verhindert weiterhin den Download. Ein leerer String sorgt dafür,
        # dass vorhandene job-/repo-/orgweite Defaults überschrieben werden.
        env:
          PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: ""
        run: npm run test:setup

      - name: Test (CI)
        run: npm run test:ci

      - name: Upload Playwright report (best-effort)
        if: always()
        run: npm run test:report || true

      - name: Upload Playwright report artifact
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report
          path: apps/web/playwright-report
          if-no-files-found: ignore
```

### 📄 .github/workflows/wgx-guard.yml

**Größe:** 2 KB | **md5:** `9b34c159b6925906d523f35148702236`

```yaml
name: wgx-guard

on:
  push:
    paths:
      - ".wgx/**"
      - ".github/workflows/wgx-guard.yml"
      - "pyproject.toml"
      - "Cargo.toml"
  pull_request:
    paths:
      - ".wgx/**"
      - ".github/workflows/wgx-guard.yml"
      - "pyproject.toml"
      - "Cargo.toml"
  workflow_dispatch: {}

permissions:
  contents: read

concurrency:
  group: wgx-guard-${{ github.ref }}
  cancel-in-progress: true

jobs:
  guard:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - name: Check .wgx/profile.yml presence
        run: |
          test -f .wgx/profile.yml || { echo "::error::.wgx/profile.yml missing"; exit 1; }
          echo "found .wgx/profile.yml"

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install PyYAML
        run: python -m pip install pyyaml
      - name: Validate minimal schema keys
        run: python ci/scripts/validate_wgx_profile.py

      - name: (Optional) UV bootstrap (pyproject present)
        if: ${{ hashFiles('**/pyproject.toml') != '' }}
        shell: bash
        run: |
          set -euo pipefail
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"
          UV="$HOME/.local/bin/uv"
          "$UV" --version

          status=0
          while IFS= read -r -d '' file; do
            dir="$(dirname "$file")"
            echo "::group::uv sync in $dir"
            if [ -f "$dir/uv.lock" ]; then
              ( cd "$dir" && "$UV" sync --frozen ) \
                || { echo "::error::uv sync failed in $dir (frozen)"; status=1; }
            else
              ( cd "$dir" && "$UV" sync ) \
                || { echo "::error::uv sync failed in $dir"; status=1; }
            fi
            echo "::endgroup::"
          # Use '-type f' to ensure only files named 'pyproject.toml' are processed, not directories.
          # This improves specificity and avoids issues if a directory is named 'pyproject.toml' (unlikely).
          done < <(find . -type f -name "pyproject.toml" -print0)

          exit "$status"

      - name: Done
        run: echo "wgx-guard passed ✅"
```

### 📄 .github/workflows/wgx-smoke.yml

**Größe:** 636 B | **md5:** `bfc873c6791f07dffa31b6fc40393d6a`

```yaml
name: wgx-smoke
on:
  pull_request:
  push: { branches: [main] }
  workflow_dispatch:
permissions:
  contents: read
concurrency:
  group: wgx-${{ github.ref }}
  cancel-in-progress: true
jobs:
  manifest-doctor:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    steps:
      - uses: actions/checkout@v4
      - name: Ensure manifest exists
        run: test -f .wgx/profile.yml
      - name: Dry-run doctor task
        run: |
          echo "Simulate 'wgx doctor' until the CLI is vendor-locked."
          echo "== profile.yml =="
          sed -n '1,40p' .wgx/profile.yml
          grep -E "apiVersion:|tasks:" .wgx/profile.yml
```

