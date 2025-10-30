<!-- Repo ist aktuell Docs-only. Befehle für spätere Gates sind unten als Vorschau markiert. -->
<!-- Docs-only (ADR-0001 Clean-Slate) • Re-Entry via Gates A–D -->
# Weltgewebe

Mobile-first Webprojekt auf SvelteKit (Web), Rust/Axum (API), Postgres+Outbox, JetStream, Caddy.
Struktur und Beiträge: siehe `architekturstruktur.md` und `CONTRIBUTING.md`.

## Landing

Für einen schnellen Einstieg in Ethik, UX und Projektkontext:

- [Einführung: Ethik- & UX-First-Startpunkt](docs/overview/inhalt.md)
- [Systematik & Strukturüberblick](docs/overview/zusammenstellung.md)

> **Hinweis / Scope**
>
> - **Kein** Teilnahme-/Freigabeprozess für Fleet-Rollouts oder operativen Leitstandbetrieb.
> - Optionales Dashboard-Widget liest **ausschließlich** über das Leitstand-REST/Gateway;
>   **kein Direktzugriff** auf JSONL-Dateien.
> - Entspricht ADR-0001 (Docs-only) und bleibt kompatibel mit den Gates A–D.
>

## Getting started

> ⚙️ **Preview:** Die folgenden Schritte werden mit Gate C (Infra-light) aktiviert.
> Solange das Repo Docs-only ist, dienen sie lediglich als Ausblick.

### Development quickstart

(Preview; wird mit Gate C aktiviert – siehe `docs/process/fahrplan.md`.)

- Install Rust (stable), Docker, Docker Compose, and `just`.
- Bring up the core stack:

  ```bash
  just up
  ```

  Alternativ steht ein äquivalentes Makefile zur Verfügung:

  ```bash
  make up
  ```

- Siehe auch `docs/quickstart-gate-c.md` für die Compose-Befehle.

- Run hygiene checks locally:

  ```bash
  just check
  ```

- Öffnest du das Repo im VS Code Devcontainer, richtet `.devcontainer/post-create.sh`
  die benötigten Tools (u. a. `just`, `uv`, `vale`) automatisch ein. Danach stehen
  Python-Helfer über `uv` sofort zur Verfügung (`uv --version`).
  Falls du Python-Tools in Unterordnern verwaltest (z. B. `tools/py/`), achte darauf,
  das entstehende `uv.lock` mit einzuchecken – standardmäßig landet es im jeweiligen
  Projektstamm (Root oder Unterordner).

- CI enforces: `cargo fmt --check`, `clippy -D warnings`, `cargo deny check`.
- Performance budgets & SLOs live in `policies/` and are referenced in docs & dashboards.
- Für lokale Web-E2E-Tests installierst du die Playwright-Browser einmalig mit
  `npx playwright install --with-deps` (Details unten im Abschnitt
  [Web-E2E-Quickstart](#web-e2e-quickstart-preview)).

> **Hinweis:** Aktuell **Docs-only/Clean-Slate** gemäß ADR-0001.
> Code-Re-Entry erfolgt über die Gates A–D (siehe
> [docs/process/fahrplan.md](docs/process/fahrplan.md)). Dort sind die Gate-Checklisten (A–D) als
> To-dos dokumentiert.

### Web-E2E-Quickstart (Preview)

Abgeleitet aus dem manuellen CI-Workflow (siehe `.github/workflows/web-e2e.yml`).
Damit Playwright lokal zuverlässig läuft, orientiere dich an den folgenden
Schritten – zusätzliche Details findest du bei Bedarf in der Workflowdatei:

1. Voraussetzungen: Node.js ≥ 20.19 (oder ≥ 22.12).

    ```bash
    corepack enable
    ```

    (aktiviert npm ≥ 10, falls noch nicht global geschehen)
2. Dependencies installieren:

    ```bash
    cd apps/web
    npm ci
    ```

3. Playwright-Browser nachrüsten (**einmalig pro Maschine**):

    ```bash
    npx playwright install --with-deps
    # alternativ: npm run test:setup
    ```

4. App builden, damit `npm run preview` die statischen Assets servieren kann:

    ```bash
    npm run build
    ```

5. Tests headless ausführen (startet automatisch einen Preview-Server – Standard:
   lokal 4173, im CI 5173; via `PORT` überschreibbar):

    ```bash
    npx playwright test
    # CI-Spiegel: npm run test:ci
    ```

Optional kannst du `PLAYWRIGHT_SKIP_WEBSERVER=1` setzen, wenn bereits ein lokaler
`npm run preview` läuft (Standard-Ports: lokal 4173, CI 5173; via `PORT` überschreibbar).
Den HTML-Report findest du nach den Läufen unter `apps/web/playwright-report/`.

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

### Policies-Pfad (Override)

Standardmäßig sucht die API die Datei `policies/limits.yaml`. Für abweichende Layouts
kannst du den Pfad via `POLICY_LIMITS_PATH=/pfad/zur/limits.yaml` setzen.

### Konfigurations-Overrides (HA_*)

Die API liest Standardwerte aus `configs/app.defaults.yml`. Für Deployments können
wir diese Defaults über folgende Umgebungsvariablen anpassen:

- `HA_FADE_DAYS`
- `HA_RON_DAYS`
- `HA_ANONYMIZE_OPT_IN`
- `HA_DELEGATION_EXPIRE_DAYS`

Optional kann `APP_CONFIG_PATH` auf eine alternative YAML-Datei zeigen.

### Soft-Limits & Policies

- Zweck: **Frühwarnung, kein Hard-Fail.**
- Hinweis: **Werden nach und nach automatisiert in CI erzwungen.**

Unter `policies/limits.yaml` dokumentieren wir Leitplanken (z. B. Web-Bundle-Budget,
CI-Laufzeiten). Sie sind zunächst informativ und werden derzeit über Kommentare in der
CI gespiegelt. Abweichungen dienen als Diskussionsgrundlage im Review.

## Semantik (Externe Quelle: semantAH)

- Verträge: `contracts/semantics/*.schema.json`
- Manuelle Aufnahme: siehe `docs/runbooks/semantics-intake.md`
- Aktuell: nur Infos, kein Event-Import.

## Continuous Integration

Docs-Only-CI aktiv mit den Checks Markdown-Lint, Link-Check,
YAML/JSON-Lint und Budget-Stub (ci/budget.json).

## Gate-Fahrplan & Gate A – UX Click-Dummy

- **Gate-Checklisten:**
  [docs/process/fahrplan.md](docs/process/fahrplan.md) (Gates A–D mit konkreten Prüfpunkten)
- **Gate A (Preview/Docs):**
  [apps/web/README.md](apps/web/README.md) (Frontend-Prototyp für Karte · Drawer ·
  Zeitleiste · Ethik-UI)

## Beiträge & Docs

Stilprüfung via Vale läuft automatisch bei Doku-PRs; lokal `vale docs/` für Hinweise.
