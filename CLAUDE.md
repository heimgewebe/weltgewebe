---
id: repo.claude
title: CLAUDE
doc_type: policy
status: active
canonicality: supplementary
summary: Claude Code operational guide for Weltgewebe — codebase structure, workflows, and conventions.
---

# CLAUDE.md — Weltgewebe

> **For Claude Code (AI assistant) working in this repository.**
> This file is a supplementary guide. It does NOT override canonical sources.

---

## Mandatory Reading Order

Before making any changes, read these files in order:

1. `repo.meta.yaml` — truth model and precedence rules
2. `AGENTS.md` — canonical coding guidelines and operational boundaries
3. `agent-policy.yaml` — write permissions and required checks
4. `docs/policies/agent-reading-protocol.md` — binding decision and abort protocol

`docs/index.md` is navigation only. `docs/_generated/*` is diagnostic only — never canonical.

---

## What This Repository Is

**Weltgewebe** is a mobile-first web application for managing nodes, edges, and domain relationships, with a focus on ethics, UX, and community autonomy.

| Layer | Technology |
|---|---|
| Frontend | SvelteKit 2 / Svelte 5 (TypeScript, static adapter) |
| Backend | Rust / Axum 0.7 (async, tokio) |
| Database | PostgreSQL 16 + PgBouncer 1.20 |
| Messaging | NATS JetStream (optional, Gate C) |
| Proxy | Caddy |
| Orchestration | Docker Compose (multi-profile) |

---

## Repository Layout

```
weltgewebe/
├── apps/
│   ├── api/          # Rust/Axum HTTP API
│   └── web/          # SvelteKit frontend
├── contracts/domain/ # JSON Schema domain contracts (highest truth precedence)
├── docs/             # ADRs, architecture specs, runbooks (German)
│   ├── adr/          # Architecture Decision Records
│   ├── blueprints/   # UI, auth, map design specs
│   ├── specs/        # API contracts, privacy specs
│   ├── policies/     # Agent/operational policies
│   └── _generated/   # Auto-generated diagnostics (read-only, never edit)
├── infra/
│   ├── compose/      # Docker Compose profiles
│   └── caddy/        # Reverse proxy config
├── scripts/          # CI, dev, docmeta, and tooling scripts
├── ci/               # Budget assertions, smoke tests
├── .github/workflows/ # 20+ CI/CD workflows
├── Justfile          # Primary task runner
├── Cargo.toml        # Rust workspace root
└── package.json      # pnpm workspace root
```

---

## Development Commands

### Task Runner (`just`)

```bash
just up              # Start dev stack (Docker Compose, dev profile)
just down            # Stop dev stack + remove volumes
just ci              # Full CI pipeline: web + API + dependency check
just fmt             # Format all Rust code
just clippy          # Lint Rust (warnings = errors)
just test            # Run all Rust tests
just check           # Hygiene: fmt + clippy + test + contracts + cargo-deny
just lint            # Lint shell scripts (bash -n, shfmt, shellcheck)
just db-wait         # Wait for Postgres readiness
just db-migrate      # Run database migrations
just seed            # Seed initial data
just contracts-domain-check  # Validate JSON Schema contracts
just demo-data       # Generate demo data (if not present)
just serve-demo      # Start demo API server (PORT=8080 default)
```

### Frontend (`apps/web`)

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm dev             # Dev server (localhost:5173)
pnpm build           # Production build
pnpm check           # Svelte type checking
pnpm lint            # Prettier + ESLint (max-warnings=0)
pnpm test:unit       # Vitest unit tests
pnpm test:setup      # Install Playwright browsers (one-time)
pnpm test            # Playwright E2E tests
pnpm run ci          # Bundle budget + lint + check (used in CI)
```

### API (`apps/api`)

```bash
cd apps/api
cargo fmt -- --check         # Check formatting
cargo clippy -- -D warnings  # Lint (deny all warnings)
cargo build --locked         # Build (locked dependencies)
cargo test --locked          # Run all tests
cargo run                    # Start API server
```

### Docker Compose Profiles

```bash
# Dev stack (web + api + db + pgbouncer + caddy)
docker compose -f infra/compose/compose.core.yml --profile dev up -d --build

# Optional observability (Prometheus + Grafana)
docker compose -f infra/compose/compose.observ.yml up -d

# Optional event streaming (NATS JetStream)
docker compose -f infra/compose/compose.stream.yml up -d
```

---

## Environment Variables

Copy `.env.example` to `.env` for local development. Key variables:

```bash
NODE_ENV=development
RUST_LOG=info
WEB_PORT=5173
API_BIND=0.0.0.0:8080
AUTH_DEV_LOGIN=0
AUTH_COOKIE_SECURE=1
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe
PGBOUNCER_URL=postgres://welt:gewebe@localhost:6432/weltgewebe
```

Production uses `.env.prod.example`. Never commit `.env` files.

---

## Toolchain Versions

Defined in `toolchain.versions.yml`:

| Tool | Version |
|---|---|
| Rust | 1.89.0 |
| Node.js | 20.19.0 (`.node-version`, `.nvmrc`) |
| Python | 3.12 (`.python-version`) |
| pnpm | 9.11.0 |
| cargo-deny | 0.18.8 |

---

## Write Permissions

| Path | Status |
|---|---|
| `docs/_generated/` | **FORBIDDEN** — auto-generated, never edit manually |
| `secrets/`, `snapshots/` | **FORBIDDEN** |
| `.github/workflows/`, `apps/`, `contracts/`, `docs/`, `infra/`, `scripts/`, `src/` | **Guarded** — requires target proof + required checks |
| `README.md`, `AGENTS.md`, `docs/` | Safe to read |

**Required checks before patching guarded paths:**
`repo-structure-guard`, `docs-relations-guard`, `generated-files-guard`, `lint`, `test`

**Human review required for:** `security/`, `deployment/`, `credentials/`

---

## Coding Conventions

### General

- Always read actual files before suggesting changes. Never guess file content.
- Show complete affected blocks (full function, full script) — not fragmented lines.
- Mark omissions explicitly with `// ...` or `# ...` without breaking syntax.
- All code suggestions must be syntactically correct, runnable, and CI-ready.

### Rust

- Use `cargo fmt` (rustfmt defaults); formatting errors block CI.
- Clippy is run with `-D warnings` — all warnings are errors.
- Dependencies locked via `Cargo.lock`; always pass `--locked` to cargo commands.
- Async runtime: tokio multi-threaded. DB access via sqlx with `PgPool`.
- Tests use `serial_test` for isolation when needed; `tempfile` for fixtures.

### TypeScript / Svelte

- ESLint 9 flat config (`eslint.config.js`); `max-warnings=0` in CI.
- Prettier for formatting; `pnpm format` to fix, `pnpm lint` to check.
- SvelteKit path aliases: `$lib`, `$components`, `$stores`, `$routes`.
- Adapter: `@sveltejs/adapter-static` (static site generation).
- No `@html` tags in templates (ESLint rule enforced).
- Svelte 5 runes syntax preferred for new components.

### Shell Scripts

- POSIX/bash only; always include spaces around `[` and `]`.
- Use `${VAR:-default}` for variable defaults declared at top of script.
- Redirections need full paths and slashes: `echo >"/dev/tcp/$HOST/$PORT"`.
- Never use pseudo-compact tokens (`devtcpHOSTPORT`, `SECONDS end`, etc.).
- Scripts linted with `bash -n`, `shfmt -d -i 2 -ci -sr`, and `shellcheck -S style`.

### JavaScript (Node scripts, e.g. `assert-web-budget.mjs`)

- Success messages (`console.log(...)`) only execute when no error was thrown.
- Type-check numeric values: `typeof x !== 'number' || Number.isNaN(x)`.
- Error messages: clear, single-line, no trailing punctuation.
- All `throw` paths must prevent any downstream "all OK" output.

### Documentation

- Documentation is in **German**. ADRs, runbooks, and architecture docs are all German.
- All docs must have YAML frontmatter with `id`, `title`, `doc_type`, `status`, `summary`.
- `doc_type` must be one of: `adr`, `blueprint`, `spec`, `policy`, `runbook`, `reference`, `overview`.
- New docs must be linked from `docs/index.md` and cross-referenced where relevant.
- Do not manually edit anything in `docs/_generated/`.
- After adding docs, consider if `audit/impl-registry.yaml` needs updating.

---

## Testing

### Web

- **Unit tests:** Vitest, files matching `src/**/*.test.ts`, run with `pnpm test:unit`.
- **E2E tests:** Playwright, files in `apps/web/tests/*.spec.ts`.
  - Local: `pnpm test` (builds first, uses port 4173).
  - CI: `pnpm test:ci` (port 5173, HTML + JUnit reporters, 2 retries).
  - Install browsers once: `pnpm test:setup`.

### API

- Cargo test: `cargo test --locked` in `apps/api/`.
- Test helpers in `apps/api/src/test_helpers.rs`.
- Use `serial_test` for tests that cannot run in parallel.

---

## CI Workflows

Key workflows in `.github/workflows/`:

| Workflow | Triggers | What it does |
|---|---|---|
| `ci.yml` | push main, PRs | Markdown lint, link check, YAML/JSON lint |
| `web.yml` | `apps/web/**` changes | Build, lint, typecheck, vitest, Playwright E2E |
| `api.yml` | `apps/api/**` changes | fmt, clippy, build, test, cargo-deny |
| `docs-guard.yml` | `docs/**` changes | Frontmatter validation, relations, coverage |
| `contracts-domain.yml` | `contracts/**` | JSON Schema validation |
| `security.yml` | Dependency changes | cargo-deny + npm audit |

CI enforces: `cargo fmt --check`, `cargo clippy -- -D warnings`, `pnpm lint` (max-warnings=0), Playwright retries=2.

---

## Domain Contracts

JSON Schema files in `contracts/domain/` define the authoritative domain model:

- `node.schema.json` — Node entity
- `edge.schema.json` — Edge relationship
- `role.schema.json` — User role
- `account.schema.json` — Account
- `message.schema.json` — Message
- `conversation.schema.json` — Conversation

These have the **highest truth precedence** in the canonical hierarchy. Changes here require `just contracts-domain-check` to pass.

---

## Architecture Notes

- **Truth model precedence** (highest to lowest): domain contracts → canonical policies → runtime configs/code → normative specs → diagnostic reports → navigation indices → generated diagnostics.
- **No silent interpolation:** If information is missing or contradictory, name the gap explicitly rather than guessing.
- **Abort rule:** If contradictions are unresolvable or required files are missing, stop and report the gap.
- **Small PRs:** Prefer narrow, focused changes with clear scope boundaries.
- **Gate C:** Current status is Infrastructure-light. NATS JetStream is optional.
- **Outbox pattern:** Used for reliable event delivery from the API to downstream consumers.

---

## Key Reference Files

| File | Purpose |
|---|---|
| `repo.meta.yaml` | Machine truth model, precedence, discovery roots |
| `AGENTS.md` | Canonical coding guidelines and operational rules |
| `agent-policy.yaml` | Write permissions and required checks |
| `docs/policies/agent-reading-protocol.md` | Binding reading and abort protocol |
| `docs/index.md` | Navigation hub (not a truth source) |
| `docs/techstack.md` | Technology decisions and rationale |
| `docs/datenmodell.md` | Database schema and domain model |
| `docs/adr/` | Architecture Decision Records |
| `ci/budget.json` | Frontend performance budgets |
| `toolchain.versions.yml` | Pinned toolchain versions |
| `Justfile` | All development tasks |
