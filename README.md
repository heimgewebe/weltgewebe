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

### Build-Zeit-Metadaten (Version/Commit/Zeitstempel)

Die API stellt unter `/version` Build-Infos bereit:

```json
{ "version": "0.1.0", "commit": "<git sha>", "build_timestamp": "<UTC ISO8601>" }
```

Diese Werte werden **zur Compile-Zeit** gesetzt. In CI exportieren die Workflows
`GIT_COMMIT_SHA` und `BUILD_TIMESTAMP` als Umgebungsvariablen. Lokal sind sie optional
und fallen auf `"unknown"` zurück. Es ist **nicht nötig**, diese Variablen in `.env` zu pflegen.

### Build-Zeit-Variablen

`GIT_COMMIT_SHA`, `CARGO_PKG_VERSION` und `BUILD_TIMESTAMP` stammen direkt aus dem
CI bzw. Compiler. Sie werden **nicht** in `.env` oder `.env.example` gepflegt.
Beim lokalen Build ohne CI-Kontext setzen wir sie automatisch auf `"unknown"`,
während die Pipelines im CI die echten Werte einspeisen. Es besteht daher kein
Bedarf, `.env.example` um diese Variablen zu erweitern.

### Soft-Limits & Policies

- Zweck: **Frühwarnung, kein Hard-Fail.**
- Hinweis: **Werden nach und nach automatisiert in CI erzwungen.**

Unter `policies/limits.yaml` dokumentieren wir Leitplanken (z. B. Web-Bundle-Budget,
CI-Laufzeiten). Sie sind zunächst informativ und werden derzeit über Kommentare in der
CI gespiegelt. Abweichungen dienen als Diskussionsgrundlage im Review.

## Continuous Integration

Docs-Only-CI aktiv mit den Checks Markdown-Lint, Link-Check, YAML/JSON-Lint und Budget-Stub (ci/budget.json).

## Beiträge & Docs

Stilprüfung via Vale läuft automatisch bei Doku-PRs; lokal `vale docs/` für Hinweise.
