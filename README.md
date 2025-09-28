<!-- Repo ist aktuell Docs-only. Befehle für spätere Gates sind unten als Vorschau markiert. -->
<!-- Docs-only (ADR-0001 Clean-Slate) • Re-Entry via Gates A–D -->
# Weltgewebe

Mobile-first Webprojekt auf SvelteKit (Web), Rust/Axum (API), Postgres+Outbox, JetStream, Caddy.  
Struktur und Beiträge: siehe `architekturstruktur.md` und `CONTRIBUTING.md`.

## Getting started

> ⚙️ **Preview:** Die folgenden Schritte werden mit Gate C (Infra-light) aktiviert.
> Solange das Repo Docs-only ist, dienen sie lediglich als Ausblick.

### Development quickstart

- Install Rust (stable), Docker, Docker Compose, and `just`.
- Bring up the core stack:

  ```bash
  just up
  ```

- Run hygiene checks locally:

  ```bash
  just check
  ```

- CI enforces: `cargo fmt --check`, `clippy -D warnings`, `cargo deny check`.
- Performance budgets & SLOs live in `policies/` and are referenced in docs & dashboards.

> **Hinweis:** Aktuell **Docs-only/Clean-Slate** gemäß ADR-0001. Code-Re-Entry erfolgt über die Gates A–D (siehe
> `docs/process/fahrplan.md`).

## Continuous Integration

Docs-Only-CI aktiv mit den Checks Markdown-Lint, Link-Check, YAML/JSON-Lint und Budget-Stub (ci/budget.json).
