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

### Domain-Contracts lokal validieren

Um die JSON-Schemas und Beispiele unter `contracts/domain/` lokal zu prüfen und sicherzustellen, dass sie
mit der CI übereinstimmen, kann ein Validierungsskript ausgeführt werden.

**Voraussetzungen:**

- Node.js ≥ 20
- `ajv-cli` und `ajv-formats` global installiert (z.B. mit `pnpm install -g ajv-cli ajv-formats`)

**Ausführung:**

- `just contracts-domain-check`
- oder `npm run contracts:domain:check`

Das Skript kompiliert alle Schemas und validiert die Beispiel-Instanzen dagegen.

## 4. Tooling-Differenzierung (Lokal vs. CI)

- **`scripts/tools/yq-pin.sh`** – lokaler Installer für eine reproduzierbare Umgebung (ohne sudo).
  Erkennt Download-Ziele, lädt mit Wiederholungen (`curl --retry*`), prüft Checksums und legt
  alles unter `~/.local/bin` ab (inkl. PATH-Hinzufügung).

- **CI-Workflows (`.github/workflows/ci.yml`)** – nutzen einen eigenen `yq`-Installer (gepinnte Version,
  direkter Download), da Runner root-Rechte und ein frisches Dateisystem haben. So bleibt der
  Workflow ohne Dotfiles/Cache deterministisch.

- **Link-Prüfung:** Im CI läuft `lychee` mit strengen Parametern (`--retry`, niedrige Parallelität),
  um Flakes zu vermeiden. Der nächtliche Workflow (`links.yml`) dient als Watchdog mit
  reduziertem Profil und ist kein hartes Qualitäts-Gate.
