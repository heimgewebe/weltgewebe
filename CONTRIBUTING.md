# CONTRIBUTING

Wie im Weltgewebe-Repository gearbeitet wird: Orientierung, Routing, Workflow, Qualität.

Verbindliche Grundlagen vor jedem Patch:

- [`repo.meta.yaml`](repo.meta.yaml) — Truth Model und Konfliktauflösung.
- [`AGENTS.md`](AGENTS.md) — Agentenleitfaden und Coding Guidelines.
- [`agent-policy.yaml`](agent-policy.yaml) — Schreibrechte und Required Checks.
- [`docs/policies/agent-reading-protocol.md`](docs/policies/agent-reading-protocol.md) — bindendes Lese- und Abbruchprotokoll.

Weitere Referenzen:

- [`docs/architekturstruktur.md`](docs/architekturstruktur.md) — Repo-Architekturüberblick.
- [`docs/techstack.md`](docs/techstack.md) — Stack-Referenz (SvelteKit, Rust/Axum, Postgres + Outbox, JetStream, Caddy).
- [`docs/runbook.md`](docs/runbook.md) — Betrieb, DR/DSGVO-Drills.
- [`docs/datenmodell.md`](docs/datenmodell.md) — Tabellen, Projektionen, Events.
- [`ci/budget.json`](ci/budget.json) — Performance-Budgets.

Kurzprinzip: **„Richtig routen, klein schneiden, sauber messen."**

## 1. Reale Repo-Topographie

```text
apps/
  api/                 # Rust/Axum HTTP-API
  web/                 # SvelteKit-Frontend
contracts/
  domain/              # JSON-Schema-Domain-Contracts (höchste Wahrheits-Präzedenz)
infra/
  caddy/               # Reverse Proxy
  compose/             # Docker-Compose-Profile
docs/                  # ADRs, Blueprints, Specs, Reports, Policies, _generated/
ci/                    # Budgets, Smoke-Tests
scripts/               # Tooling, insb. scripts/docmeta/ für Doku-Indexer und Guards
.github/
  workflows/           # CI/CD
audit/                 # impl-registry.yaml — Implementierungs-Mapping
policies/              # Soft-Limits (limits.yaml, perf.json, retention.yml, slo.yaml ...)
configs/               # App-Defaults (app.defaults.yml)
architecture/          # Architektur-Notizen
runbooks/              # Operative Runbooks
Root                   # Justfile, Makefile, repo.meta.yaml, AGENTS.md, README.md, Lizenz
```

Noch nicht im Repo, aber im Zielbild vorgesehen: `apps/worker/` (Outbox-Projektoren, DSGVO-/DR-Rebuilder), `apps/search/` (Search-Adapter), gemeinsame Library-Pakete unter `packages/`. Patches dürfen diese Strukturen **nicht erfinden**; sie entstehen erst, wenn die jeweilige Gate-Phase erreicht ist.

Details: siehe [`docs/architekturstruktur.md`](docs/architekturstruktur.md).

## 2. Routing-Matrix „Wohin gehört was?"

Nur reale Zielordner. Was nicht existiert, wird hier nicht aufgelistet.

- **Neue Seite oder Route im UI:** `apps/web/src/routes/...` (`+page.svelte`, `+page.ts`, `+server.ts`).
- **UI-Komponente, Store, Util:** `apps/web/src/lib/...`.
- **Statische Assets:** `apps/web/static/`.
- **Neuer API-Endpoint:** `apps/api/src/routes/...`; reale Route-Module: `accounts`, `auth`, `edges`, `health`, `meta`, `nodes`, `query`.
- **Auth-Logik:** `apps/api/src/auth/...` (Sessions, Passkeys, Tokens, Rate-Limiting, Rollen).
- **Middleware:** `apps/api/src/middleware/...` (Auth, AuthZ, CSRF).
- **Querschnitt:** `apps/api/src/{config,state,mailer,utils}.rs`, `apps/api/src/telemetry/...`.
- **DB-Migrationen:** `apps/api/migrations/` (`YYYYMMDDHHMM__beschreibung.sql`).

Fachliche Trennungen wie `apps/api/src/domain/`, `apps/api/src/repo/` oder `apps/api/src/events/` sind **Zielbild**, aber aktuell nicht vorhanden. Neue Unterordner erst nach eigenem Architektur- oder Refactoring-PR einführen — nicht als freie Routing-Entscheidung.

- **Compose-Profile:** `infra/compose/*.yml`.
- **Proxy, Headers, CSP:** `infra/caddy/`.
- **CI-Workflow:** `.github/workflows/*.yml`.
- **Performance-Budget:** `ci/budget.json`.
- **Soft-Limits / SLOs:** `policies/`.
- **App-Defaults:** `configs/app.defaults.yml`.
- **Architektur-Entscheidung:** `docs/adr/ADR-xxx__<slug>.md`.
- **Architektur-Blaupause:** `docs/blueprints/<slug>.md`.
- **Spezifikation:** `docs/specs/<slug>.md`.
- **Statusbericht / Diagnose:** `docs/reports/<slug>.md` (Markdown plus optional `.json`-Zwilling, dokumentiert).
- **Runbook:** `docs/runbook.md` oder `docs/runbooks/<slug>.md`.
- **Domain-Contract:** `contracts/domain/<entity>.schema.json`.
- **Doku-Indexer / Relations-Skript:** `scripts/docmeta/`.

Outbox-Projektoren (Timeline, Search), DSGVO-/DR-Rebuilder und Search-Adapter haben noch keinen realen Zielordner und entstehen erst mit der entsprechenden Gate-Phase.

## 3. Doku-Rollen und Schreibgrenzen

| Pfad | Rolle | Schreibstatus |
|---|---|---|
| `repo.meta.yaml`, `AGENTS.md`, `agent-policy.yaml`, `docs/policies/*` | Kanonische Wahrheits- und Steuerungsschicht | guarded |
| `contracts/domain/*.schema.json` | Höchste Wahrheits-Präzedenz | guarded, erfordert `contracts-domain-check` |
| `docs/adr/*`, `docs/specs/*`, `docs/blueprints/*` | Normative Spezifikation und Architekturplanung | guarded |
| `docs/reports/*` | Diagnostische Berichte und Statusmatrizen mit Evidenz | guarded |
| `docs/index.md` | Navigation, **keine** Wahrheit | guarded |
| `docs/_generated/*` | Diagnose, automatisch generiert | **forbidden** für manuelle Edits |
| `audit/impl-registry.yaml` | Implementations-Mapping | guarded |
| `docs/tasks/*` | Geplante Task-Control-Schicht (Roadmap) | noch nicht eingeführt — nicht ohne Roadmap-Phase 2 anlegen |
| `secrets/`, `snapshots/` | Sensitive Daten / Snapshots | **forbidden** |

Vollständige bindende Pfadliste siehe [`agent-policy.yaml`](agent-policy.yaml).

## 4. Arbeitsweise und Workflow

- Branch-Strategie: kurzes Feature-Branching gegen `main`. Kleine, thematisch fokussierte Pull Requests.
- Commit-Präfixe: `feat(web): …`, `feat(api): …`, `feat(infra): …`, `fix(...)`, `chore(...)`, `refactor(...)`, `docs(adr|runbook|...)`.
- PR-Prozess:
  1. Lokal: Lints, Tests und Budgets ausführen (`just check`).
  2. PR klein halten; Zweck und „Wie getestet" kurz erläutern.
  3. Bei Architektur- oder Sicherheitsauswirkungen: ADR oder Runbook-Update beilegen oder verlinken.
- CI-Gates (brechen Builds):
  - Frontend-Budget aus `ci/budget.json` (Initial-JS ≤ 60 KB, TTI ≤ 2000 ms).
  - Lints/Formatter: Web (ESLint/Prettier, `max-warnings=0`), Rust (`cargo fmt`, `cargo clippy -D warnings`).
  - Tests (`pnpm test`, `cargo test --locked`).
  - Sicherheits- und Konsistenzchecks (`cargo deny`, Workflow `docs-guard.yml`, Compose-Smoke).

Generierte Dateien unter `docs/_generated/` sind abgeleitete Diagnoseartefakte und werden nicht manuell editiert. CI regeneriert sie für Beobachtbarkeit; Drift wird gemeldet und soll zeitnah behoben oder bewusst dokumentiert werden.

Blockierende Doku-Validierung läuft deterministisch über `make ci-validate` (Alias zu `make validate`).

## 5. Domain-Contracts lokal validieren

JSON-Schemas und Beispiele unter `contracts/domain/` prüfen:

- Voraussetzungen: Node.js ≥ 20, `ajv-cli` und `ajv-formats` (z. B. `pnpm install -g ajv-cli ajv-formats`).
- Ausführung: `just contracts-domain-check` oder `npm run contracts:domain:check`.

Das Skript kompiliert alle Schemas und validiert die Beispiel-Instanzen dagegen.

## 6. Tooling-Differenzierung (Lokal vs. CI)

- **`scripts/tools/yq-pin.sh`** — lokaler Installer für reproduzierbare Umgebung (ohne sudo). Lädt `yq` mit Wiederholungen, prüft Checksums, legt das Binary unter `~/.local/bin` ab (inkl. PATH-Hinzufügung).
- **CI-Workflows (`.github/workflows/ci.yml`)** — eigener gepinnter `yq`-Installer, da Runner root-Rechte und frisches Dateisystem haben.
- **Link-Prüfung:** Im CI läuft `lychee` mit strengen Parametern (`--retry`, niedrige Parallelität). Der nächtliche Workflow (`links.yml`) ist Watchdog mit reduziertem Profil, kein hartes Qualitäts-Gate.
