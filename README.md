<!-- Repo ist aktuell Docs-only. Befehle für spätere Gates sind unten als Vorschau markiert. -->
<!-- Docs-only (ADR-0001 Clean-Slate) • Re-Entry via Gates A–D -->
# Weltgewebe

Mobile-first Webprojekt mit SvelteKit (Web), Rust/Axum (API), Postgres+Outbox, JetStream und Caddy.
Struktur und Beiträge: siehe `architekturstruktur.md` und `CONTRIBUTING.md`.

## Landing

Für einen schnellen Einstieg in Ethik, UX und Projektkontext:

- [Vision & Leitidee](docs/vision.md)
- [Einführung: Ethik- & UX-First-Startpunkt](docs/overview/inhalt.md)
- [Systematik & Strukturüberblick](docs/overview/zusammenstellung.md)

> **Hinweis / Scope**
>
> - **Kein** Teilnahme-/Freigabeprozess für Fleet-Rollouts oder operativen Leitstandbetrieb.
> - Optionales Dashboard-Widget liest **ausschließlich** über das Leitstand-REST/Gateway,
>   **kein Direktzugriff** auf JSONL-Dateien.
> - Entspricht ADR-0001 (Docs-only) und bleibt kompatibel mit den Gates A–D.

## Getting started

> ⚙️ **Preview:** Die folgenden Schritte werden mit Gate C (Infra-light) aktiviert.
> Solange das Repo Docs-only ist, dienen sie lediglich als Ausblick.

### Development Quickstart

1. **Voraussetzungen:** Docker, Docker Compose und `just` müssen installiert sein.
   Alternativ zu `just` kann `make` verwendet werden.

2. **.env erstellen:** Kopiere die Vorlage `.env.example` nach `.env`.
   Für den lokalen Start sind in der Regel keine Änderungen nötig.

    ```bash
    cp .env.example .env
    ```

3. **Dev-Stack starten:**

    ```bash
    just up
    ```

    Der Befehl `make up` ist ein Alias und macht dasselbe.
    *Hinweis: Der erste Start kann einige Minuten dauern, da Docker-Images gebaut werden.*

4. **Erfolg prüfen:**
    - **Frontend:** Öffne [http://localhost:8081](http://localhost:8081) im Browser.
    - **API-Healthcheck:** Rufe [http://localhost:8081/api/health/live](http://localhost:8081/api/health/live) auf.

5. **Stack anhalten:**

    ```bash
    just down
    ```

- Für weitere Details siehe `docs/quickstart-gate-c.md`.
- Um Code-Qualität lokal zu prüfen, nutze `just check`.

- Im VS Code Devcontainer richtet `.devcontainer/post-create.sh` die benötigten Tools
  (u. a. `just`, `uv`, `vale`) automatisch ein. Python-Helfer über `uv` stehen
  danach sofort zur Verfügung (`uv -V`).
- Falls du Python-Tools in Unterordnern verwaltest (z. B. `tools/py/`), achte darauf,
  das entstehende `uv.lock` mit einzuchecken – es landet standardmäßig im jeweiligen
  Projektstamm (Root oder Unterordner).
- Außerhalb des Devcontainers stellst du die gewünschte `uv`-Version mit
  `scripts/tools/uv-pin.sh ensure` sicher (optional via `UV_VERSION=<ziel>`).

- CI enforces: `cargo fmt --check`, `clippy -D warnings`, `cargo deny check`.
- Performance-Budgets & SLOs leben in `policies/` und werden in Docs & Dashboards referenziert.
- Für lokale Web-E2E-Tests installierst du die Playwright-Browser einmalig
  (Details im Abschnitt [Web-E2E-Quickstart](#web-e2e-quickstart-preview)):
  `npx playwright install --with-deps`

> **Hinweis:** Aktuell **Docs-only/Clean-Slate** gemäß ADR-0001.
> Code-Re-Entry erfolgt über die Gates A–D (siehe [docs/process/fahrplan.md](docs/process/fahrplan.md)).
> Dort sind die Gate-Checklisten (A–D) als To-dos dokumentiert.

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

5. Tests headless ausführen (startet automatisch einen Preview-Server):

    ```bash
    npx playwright test
    # CI-Spiegel: npm run test:ci
    ```

Optional kannst du `PLAYWRIGHT_SKIP_WEBSERVER=1` setzen, wenn bereits ein lokaler
`npm run preview` läuft. Den HTML-Report findest du nach den Läufen unter
`apps/web/playwright-report/`.

### Build-Zeit-Metadaten (Version/Commit/Zeitstempel)

Die API stellt unter `/version` Build-Infos bereit:

```json
{
  "version": "0.1.0",
  "commit": "<git sha>",
  "build_timestamp": "<UTC ISO8601>"
}
```

Diese Werte werden zur Compile-Zeit gesetzt. In CI exportieren die Workflows `GIT_COMMIT_SHA`
und `BUILD_TIMESTAMP` als Umgebungsvariablen. Lokal sind sie optional und fallen auf
`"unknown"` zurück. Es ist **nicht nötig**, diese Variablen in `.env` zu pflegen.

### Build-Zeit-Variablen

`GIT_COMMIT_SHA`, `CARGO_PKG_VERSION` und `BUILD_TIMESTAMP` stammen direkt aus dem CI
bzw. Compiler. Sie werden **nicht** in `.env` oder `.env.example` gepflegt.
Beim lokalen Build ohne CI-Kontext setzen wir sie automatisch auf `"unknown"`, während
die Pipelines im CI die echten Werte einspeisen.

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

Unter `policies/limits.yaml` dokumentieren wir Leitplanken (z. B. Web-Bundle-Budget, CI-Laufzeiten).
Sie sind zunächst informativ und werden derzeit über Kommentare in der CI gespiegelt. Abweichungen
dienen als Diskussionsgrundlage im Review.

## Semantik (Optionale zukünftige Integration – derzeit inaktiv)

- Ursprünglicher Plan: `semantAH`-Integration (siehe ADR-0042).
- Status: Vorerst ausgesetzt, Contracts und CI-Jobs entfernt.
- Eine Reaktivierung würde eine neue ADR erfordern.

## Continuous Integration

Docs-Only-CI aktiv mit den Checks Markdown-Lint, Link-Check,
YAML/JSON-Lint und Budget-Stub (ci/budget.json).

## Gate-Fahrplan & Gate A – UX Click-Dummy

- **Gate-Checklisten:** [docs/process/fahrplan.md](docs/process/fahrplan.md)
  (Gates A–D mit konkreten Prüfpunkten)
- **Gate A (Preview/Docs):** [apps/web/README.md](apps/web/README.md)
  (Frontend-Prototyp für Karte · Drawer · Zeitleiste · Ethik-UI)

## Beiträge & Docs

Stilprüfung via Vale läuft automatisch bei Doku-PRs; lokal `vale docs/` für Hinweise.
