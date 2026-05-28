<!-- "Docs-only" ist ein formaler Gate-Status (ADR-0001). Das Repo ENTHÄLT operativen Code in apps/ und infra/. Diese Runtime-Artefakte sind Teil der Wahrheitsschicht und müssen gemäß dem definierten Truth Model (repo.meta.yaml) berücksichtigt werden. -->
<!-- Docs-only (ADR-0001 Clean-Slate) • Re-Entry via Gates A–D -->

# Weltgewebe

Mobile-first Webprojekt mit SvelteKit (Web), Rust/Axum (API), Postgres + Outbox, NATS JetStream und Caddy.

## Status des Repos

- Weltgewebe ist ein **eigenständiges Projekt**. Repositories wie `heimgewebe/contracts`, `wgx` oder `hauski` sind optionale Quellen und Werkzeuge, keine monolithische Codebasis.
- Formaler **Docs-only/Clean-Slate**-Status nach ADR-0001. Gleichzeitig enthält das Repo operative Artefakte unter `apps/` und `infra/`, die Teil der Wahrheitsschicht sind.
- Code-Re-Entry erfolgt über die **Gates A–D**; siehe [`docs/process/fahrplan.md`](docs/process/fahrplan.md).
- Wahrheit und Konfliktauflösung folgen strikt [`repo.meta.yaml`](repo.meta.yaml) und dem [Agent Reading Protocol](docs/policies/agent-reading-protocol.md). `docs/index.md` ist Navigation, keine Wahrheitsschicht. `docs/_generated/*` ist Diagnose, nicht Ursprung.

## Schnellzugriff

- [Dokumentationsindex](docs/index.md)
- [Repo-Architektur](docs/architekturstruktur.md)
- [Agenten-Leitfaden](AGENTS.md)
- [Beitragen](CONTRIBUTING.md)
- [Master-Roadmap](docs/roadmap.md)
- [Optimierungsstatus](docs/reports/optimierungsstatus.md)
- [Task-Control-Blaupause](docs/blueprints/doc-structure-task-control.md)
- [Task-Control-Roadmap](docs/blueprints/doc-structure-task-control-roadmap.md)
- [Deployment-Übersicht](docs/deploy/README.md)
- [Gate-Fahrplan](docs/process/fahrplan.md)

## Für Agents

Verbindliche Leseordnung vor jedem Patch:

1. [`repo.meta.yaml`](repo.meta.yaml)
2. [`AGENTS.md`](AGENTS.md)
3. [`agent-policy.yaml`](agent-policy.yaml)
4. [`docs/policies/agent-reading-protocol.md`](docs/policies/agent-reading-protocol.md)
5. [`docs/index.md`](docs/index.md) — nur Navigation
6. betroffene Blueprint-, Report-, Spec- oder Codepfade

Interpolation ist verboten. Bei nicht auflösbaren Widersprüchen oder fehlenden Zielnachweisen MUSS abgebrochen werden.

## Lokal starten

Voraussetzungen: Docker, Docker Compose und `just` (alternativ `make`).

```bash
cp .env.example .env
just up
```

Prüfen:

- Frontend: <http://localhost:8081>
- API Healthcheck: <http://localhost:8081/api/health/live>

Stoppen:

```bash
just down
```

> ⚙️ Der vollständig betriebsbereite Dev-Stack ist Teil von **Gate C** (Infra-light). Für Detailschritte siehe [`docs/quickstart-gate-c.md`](docs/quickstart-gate-c.md). Im VS-Code-Devcontainer richtet `.devcontainer/post-create.sh` Tools wie `just`, `uv` und `vale` automatisch ein.

## Entwicklung und Qualität

- Beitragsregeln und Routing: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Schneller lokaler Hygiene-Check: `just check` (Rust/API-Grundchecks, Demo-Daten, Domain-Contracts, `cargo deny`)
- Breiterer CI-Spiegel bei Web/API-Änderungen: `just ci`
- Frontend-/Gate-A-Prototyp: [`apps/web/README.md`](apps/web/README.md)
- Web-E2E (Playwright): siehe Workflow [`.github/workflows/web-e2e.yml`](.github/workflows/web-e2e.yml); lokal in `apps/web/` mit `pnpm test:setup` (einmalig) und `pnpm test`.
- Performance-Budgets: [`ci/budget.json`](ci/budget.json); Soft-Limits in [`policies/`](policies/).
- Doku- und Relations-Checks: Skripte unter `scripts/docmeta/` plus CI-Workflow `docs-guard.yml`.
- Domain-Contracts lokal validieren: `just contracts-domain-check`.

### Build- und Konfigurationsdetails

- Die API liefert `/version` mit Build-Metadaten:
  - `version` kommt aus `env!("CARGO_PKG_VERSION")` (Cargo-Paketmetadaten; **kein Fallback** auf `"unknown"`).
  - `GIT_COMMIT_SHA` und `BUILD_TIMESTAMP` sind optional; sie fallen über `option_env!(...).unwrap_or("unknown")` auf `"unknown"` zurück, wenn nicht vom CI gesetzt.
  - Diese Werte werden **nicht** in `.env` gepflegt.
- Defaults: [`configs/app.defaults.yml`](configs/app.defaults.yml). Overrides via Env-Variablen `HA_FADE_DAYS`, `HA_RON_DAYS`, `HA_ANONYMIZE_OPT_IN`, `HA_DELEGATION_EXPIRE_DAYS` oder `APP_CONFIG_PATH`.
- Policies-Pfad-Override: `POLICY_LIMITS_PATH=/pfad/zur/limits.yaml`.

## Deployment und Betrieb

- Übersicht: [`docs/deploy/README.md`](docs/deploy/README.md)
- Heimserver als Referenz-Integration: [`docs/deploy/heimserver.integration.md`](docs/deploy/heimserver.integration.md)
- Security: [`docs/deploy/security.md`](docs/deploy/security.md)
- Drift-Policy: [`docs/deploy/DRIFT_POLICY.md`](docs/deploy/DRIFT_POLICY.md)
- Runbook: [`docs/runbook.md`](docs/runbook.md); Observability: [`docs/runbook.observability.md`](docs/runbook.observability.md)

> **Hinweis:** Das Heimserver-Deployment ist Referenz-Implementierung des Integration-Contracts. Die langfristige Produktionsumgebung kann abweichen, der Contract bleibt gültig.

## Roadmap und offene Arbeit

- [Master-Roadmap](docs/roadmap.md)
- [Optimierungsstatus](docs/reports/optimierungsstatus.md)
- [Task-Control-Roadmap](docs/blueprints/doc-structure-task-control-roadmap.md)

Task-Control Phase 2 ist eingeführt. Die Arbeitssteuerung liegt jetzt unter `docs/tasks/`; der maschinenlesbare Optimierungsstatus liegt unter `docs/reports/optimierungsstatus.json`.

Offen bleiben Folgephasen: GitHub Issue Forms, PR-Template, Release-Konfig, Task-Index-Generator, CI-Guard und Implementierungs-Mapping.

## Semantik (ausgesetzt)

Die ursprünglich geplante `semantAH`-Integration (ADR-0042) ist ausgesetzt; Contracts und CI-Jobs wurden entfernt. Eine Reaktivierung würde eine neue ADR erfordern.

## Task-Control

Die operative Arbeitssteuerung liegt in `docs/tasks/`:

| Datei | Zweck |
|---|---|
| `docs/tasks/board.md` | Menschliche Arbeitskarte (aktive Prioritäten, Blocker) |
| `docs/tasks/index.json` | Maschinenlesbarer Task-Index (Phase-2-Seed: manuell) |
| `docs/tasks/schema.json` | Validierungsvertrag |
| `docs/reports/optimierungsstatus.md` | Maßgebliche Statusmatrix (Wahrheitsquelle für OPT-* Einträge) |
| `docs/reports/optimierungsstatus.json` | Maschinenlesbarer Zwilling der Statusmatrix |

Noch nicht umgesetzt (Folge-PRs): GitHub Issue Forms, PR-Template, Release-Konfig, Generator und CI-Guard.

```bash
python3 -m scripts.docmeta.validate_task_index docs/tasks/index.json
```

## Beiträge & Docs

Stilprüfung via Vale läuft automatisch bei Doku-PRs; lokal `vale docs/` für Hinweise.
