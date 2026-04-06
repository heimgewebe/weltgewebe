---
id: repo.claude
title: CLAUDE
doc_type: guide
status: active
canonicality: supplementary
summary: Claude Code operational interface for Weltgewebe — commands, navigation, and workflow shortcuts.
relations:
  - type: relates_to
    target: AGENTS.md
  - type: relates_to
    target: repo.meta.yaml
  - type: relates_to
    target: agent-policy.yaml
---

# CLAUDE.md — Weltgewebe

> For Claude Code (AI assistant) working in this repository.
> This file is an operational interface. It does NOT define rules, policies, or architecture.

All normative definitions live exclusively in:

- `repo.meta.yaml`
- `AGENTS.md`
- `agent-policy.yaml`
- `docs/policies/agent-reading-protocol.md`

If any conflict exists between this document and the canonical sources above, the canonical sources always override.

---

## Role of This Document

This document provides:

- operational commands
- navigation guidance
- workflow shortcuts
- shortcuts to canonical activation rules

It does NOT provide:

- normative rules
- architectural decisions
- truth definitions
- automatic activation of cognitive modules

For coding conventions see `AGENTS.md`. For architecture principles see `repo.meta.yaml` and the canonical policies.

---

## Mandatory Reading Order

Before making any changes, read these files in order:

1. `repo.meta.yaml` — truth model and precedence rules
2. `AGENTS.md` — canonical coding guidelines and operational boundaries
3. `agent-policy.yaml` — write permissions and required checks
4. `docs/policies/agent-reading-protocol.md` — binding decision and abort protocol

`docs/index.md` is navigation only. `docs/_generated/*` is diagnostic only — never canonical.

Cognitive modules (e.g. `docs/policies/architecture-critique.md`) are **not** part of the default reading order. They are loaded only through the activation logic defined in `docs/policies/agent-reading-protocol.md` § 8.

---

## What This Repository Is

Weltgewebe is a mobile-first web application for managing nodes, edges, and domain relationships, with a focus on ethics, UX, and community autonomy.

| Layer | Technology |
|---|---|
| Frontend | SvelteKit 2 / Svelte 5 (TypeScript, adapter-static) |
| Backend | Rust / Axum 0.7 (async, tokio) |
| Database | PostgreSQL 16 + PgBouncer 1.20 |
| Messaging | NATS 2.10 JetStream (optional, Gate C) |
| Proxy | Caddy 2.7 (dev) / 2.8 (prod) |
| Orchestration | Docker Compose (multi-profile) |

---

## Repository Layout

```text
weltgewebe/
├── apps/
│   ├── api/                # Rust/Axum HTTP API
│   └── web/                # SvelteKit frontend
├── architecture/           # Docmeta engine blueprint, schema
├── audit/                  # impl-registry.yaml
├── ci/                     # Budget assertions (budget.json), smoke tests, db-wait
├── configs/                # app.defaults.yml (runtime defaults)
├── contracts/domain/       # JSON Schema domain contracts (highest truth precedence)
├── docs/                   # ADRs, specs, blueprints, runbooks (German)
│   ├── adr/                # Architecture Decision Records
│   ├── blueprints/         # UI, auth, map design specs
│   ├── specs/              # API contracts, privacy specs
│   ├── policies/           # Agent/operational policies
│   └── _generated/         # Auto-generated diagnostics (read-only, never edit)
├── infra/
│   ├── compose/            # Docker Compose profiles
│   └── caddy/              # Reverse proxy config
├── manifest/               # repo-index.yaml, review-policy.yaml
├── map-style/              # Map style assets
├── policies/               # Soft-limits, SLOs, retention, security policies
├── runbooks/               # Operational runbooks
├── scripts/                # CI, dev, docmeta, guard, and tooling scripts
├── src/                    # Shared source
├── tools/                  # Drill scripts, Python tooling
├── Justfile                # Primary task runner
├── Makefile                # Alternative task runner (docs-guard, compose shortcuts)
├── Cargo.toml              # Rust workspace root
├── package.json            # pnpm workspace root
├── repo.meta.yaml          # Machine truth model
├── AGENTS.md               # Agent operational boundaries
├── agent-policy.yaml       # Write permissions and checks
└── CONTRIBUTING.md         # Contribution guide
```

---

## Development Commands

### Task Runner (just)

```bash
just up                      # Start dev stack (Docker Compose, dev profile)
just down                    # Stop dev stack + remove volumes
just ci                      # Full CI pipeline: web + API + cargo-deny
just fmt                     # Format all Rust code
just clippy                  # Lint Rust (warnings = errors)
just test                    # Run all Rust tests
just check                   # Hygiene: fmt + clippy + test + demo-data + contracts + cargo-deny
just lint                    # Lint shell scripts (bash -n, shfmt, shellcheck)
just db-wait                 # Wait for Postgres readiness
just db-migrate              # Run database migrations
just seed                    # Seed initial data
just contracts-domain-check  # Validate JSON Schema contracts
just demo-data               # Generate demo data (if not present)
just serve-demo              # Start demo API server (PORT=8080 default)
just check-demo              # Smoke-test demo endpoints
just observ                  # Start monitoring profile (Prometheus + Grafana)
just stream                  # Start event streaming profile
just drill                   # Disaster recovery smoke sequence
just reset-web               # Clean restart web dev environment
```

### Makefile (alternative)

```bash
make up                      # Same as just up
make down                    # Same as just down
make docs-guard              # Full doc validation pipeline (docmeta scripts + generated files)
```

`make docs-guard` runs all Python docmeta validators, regenerates `docs/_generated/*`, and asserts no drift via `git diff --exit-code`.

### Frontend (apps/web)

```bash
cd apps/web
pnpm install --frozen-lockfile
pnpm dev                     # Dev server (localhost:5173)
pnpm build                   # Production build (adapter-static)
pnpm check                   # Svelte type checking
pnpm lint                    # Prettier + ESLint (max-warnings=0)
pnpm test:unit               # Vitest unit tests
pnpm test:setup              # Install Playwright browsers (one-time)
pnpm test                    # Playwright E2E tests (builds first, port 4173)
pnpm test:ci                 # E2E in CI mode (dot + HTML + JUnit reporters, 2 retries)
pnpm run ci                  # Budget assertion + lint + typecheck (used in CI)
```

### API (apps/api)

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

# Monitoring (Prometheus + Grafana)
docker compose -f infra/compose/compose.observ.yml up -d

# Production overrides
docker compose -f infra/compose/compose.prod.yml up -d
```

### Documentation

```bash
make docs-guard              # Full doc pipeline: validate, regenerate, drift check
vale docs/                   # Prose style linting (local)
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

| Tool | Version | Source |
|---|---|---|
| Rust | 1.89.0 | `toolchain.versions.yml` |
| Node.js | 20.19.0 | `.node-version`, `.nvmrc` |
| Python | 3.12 | `.python-version`, `toolchain.versions.yml` |
| pnpm | 9.11.0 | `package.json` (`packageManager` field) |
| uv | 0.9.11 | `toolchain.versions.yml` |
| yq | 4.44.3 | `toolchain.versions.yml` |
| cargo-deny | 0.18.8 | `toolchain.versions.yml` |

---

## Write Permissions

Source: `agent-policy.yaml`

| Path | Status |
|---|---|
| `docs/_generated/` | **FORBIDDEN** — auto-generated, never edit manually |
| `secrets/`, `snapshots/` | **FORBIDDEN** |
| `.github/workflows/`, `apps/`, `contracts/`, `docs/`, `infra/`, `scripts/`, `src/` | Guarded — requires target proof + required checks |
| `README.md`, `AGENTS.md`, `docs/` | Safe to read |

Required checks before patching guarded paths:

- `repo-structure-guard`
- `docs-relations-guard`
- `generated-files-guard`
- `lint`
- `test`

Human review required for: `security/`, `deployment/`, `credentials/`

---

## Coding Conventions

All coding conventions are defined in `AGENTS.md`. This section only highlights common entry points.

- **Rust:** `cargo fmt` + `cargo clippy -- -D warnings`; always pass `--locked` to cargo build/test.
- **TypeScript/Svelte:** `pnpm lint` (Prettier + ESLint, max-warnings=0); Svelte 5 runes preferred.
- **Shell scripts:** POSIX/bash; `shfmt -d -i 2 -ci -sr` + `shellcheck -S style`.
- **Node scripts:** Success messages only after no error thrown; strict type checks on numeric values.
- **Documentation:** German prose; YAML frontmatter required; Vale style linting; see `AGENTS.md` for details.

---

## Testing

### Web

- **Unit tests:** Vitest, files matching `src/**/*.test.ts`, run with `pnpm test:unit`.
- **E2E tests:** Playwright, files in `apps/web/tests/*.spec.ts`.
  - Local: `pnpm test` (builds with `build:e2e` first, preview on port 4173).
  - CI: `pnpm test:ci` (dot + HTML + JUnit reporters, 2 retries).
  - Install browsers once: `pnpm test:setup`.
  - For map-related E2E tests, use `pnpm run build:e2e` (sets `VITE_PUBLIC_ENABLE_TEST_MAP=true`).

### API

- `cargo test --locked` in `apps/api/`.
- Test helpers in `apps/api/src/test_helpers.rs`.
- Use `serial_test` for tests that cannot run in parallel.

---

## CI Workflows

Key workflows in `.github/workflows/` (28 total):

| Workflow | Triggers | Purpose |
|---|---|---|
| `ci.yml` | push main, PRs | Full build/test; skips for docs-only changes |
| `web.yml` | `apps/web/**` | Build, lint, typecheck, vitest, Playwright E2E |
| `web-e2e.yml` | Manual / workflow | Dedicated Playwright E2E pipeline |
| `api.yml` | `apps/api/**` | fmt, clippy, build, test |
| `api-smoke.yml` | API changes | API smoke tests |
| `docs-guard.yml` | `docs/**` | Frontmatter validation, relations, coverage |
| `docs-style.yml` | `docs/**` | Vale prose style checks |
| `contracts-domain.yml` | `contracts/**` | JSON Schema validation |
| `security.yml` | Dependency changes | cargo-deny |
| `infra.yml` | `infra/**` | Infrastructure validation |
| `compose-smoke.yml` | Compose changes | Docker Compose smoke test |
| `policies.yml` | Policy changes | Policy validation |
| `heavy.yml` | Manual | Heavy/long-running tests |

CI enforces: `cargo fmt --check`, `cargo clippy -- -D warnings`, `pnpm lint` (max-warnings=0), Playwright retries=2, `cargo deny check`.

---

## Domain Contracts

JSON Schema files in `contracts/domain/` define the authoritative domain model:

- `node.schema.json` — Node entity
- `edge.schema.json` — Edge relationship
- `role.schema.json` — User role
- `account.schema.json` — Account
- `message.schema.json` — Message
- `conversation.schema.json` — Conversation

Example files in `contracts/domain/examples/`. Changes require `just contracts-domain-check` to pass.

---

## Key Reference Files

| File | Purpose |
|---|---|
| `repo.meta.yaml` | Machine truth model, precedence, discovery roots |
| `AGENTS.md` | Canonical coding guidelines and operational rules |
| `agent-policy.yaml` | Write permissions and required checks |
| `docs/policies/agent-reading-protocol.md` | Binding reading and abort protocol |
| `docs/policies/architecture-critique.md` | Cognitive module (activated on demand) |
| `docs/index.md` | Navigation hub (not a truth source) |
| `docs/techstack.md` | Technology decisions and rationale |
| `docs/datenmodell.md` | Database schema and domain model |
| `docs/adr/` | Architecture Decision Records |
| `CONTRIBUTING.md` | Contribution guide |
| `ci/budget.json` | Frontend performance budgets |
| `configs/app.defaults.yml` | Runtime configuration defaults |
| `policies/` | Soft-limits, SLOs, retention, security policies |
| `toolchain.versions.yml` | Pinned toolchain versions |
| `Justfile` | Primary task runner |
| `Makefile` | Alternative task runner (docs-guard) |
