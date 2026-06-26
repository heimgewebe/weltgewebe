---
id: docs.roadmap
title: Weltgewebe — Master-Umsetzungsroadmap
doc_type: roadmap
status: active
created: 2026-05-08
lang: de
summary: >
  Koordinations-Roadmap, die alle thematischen Sub-Roadmaps (Auth, UI, Map,
  Agent-Operability, Versionierung) ordnet und Meilensteine abhakbar macht.
  Sie ersetzt keine Sub-Roadmap und keinen Statusbericht, sondern verknüpft sie.
relations:
  - type: depends_on
    target: docs/process/fahrplan.md
  - type: depends_on
    target: docs/blueprints/auth-roadmap.md
  - type: depends_on
    target: docs/blueprints/auth-persistence-runtime-proof.md
  - type: depends_on
    target: docs/blueprints/ui-roadmap.md
  - type: depends_on
    target: docs/blueprints/map-roadmap.md
  - type: depends_on
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: depends_on
    target: docs/blueprints/kartenklarheit-phase6.md
  - type: depends_on
    target: docs/blueprints/agent-operability-blaupause.md
  - type: depends_on
    target: docs/blueprints/doc-structure-task-control-roadmap.md
  - type: depends_on
    target: docs/blueprints/versionierungs-blaupause.md
  - type: depends_on
    target: docs/reports/optimierungsstatus.md
  - type: depends_on
    target: docs/reports/auth-status-matrix.md
  - type: depends_on
    target: docs/reports/map-status-matrix.md
---

# Weltgewebe — Master-Umsetzungsroadmap

> **Zweck.** Diese Roadmap ist der **Koordinations-Index** über alle
> thematischen Sub-Roadmaps. Sie ordnet, verknüpft und macht Meilensteine
> abhakbar — sie ist **keine** neue Architekturentscheidung und **kein**
> neuer Plan.
>
> **Abgrenzung.** `docs/process/fahrplan.md` ordnet die infrastrukturellen
> Gates A–D. Diese Datei ordnet die thematischen Stränge.
> `docs/reports/optimierungsstatus.md` führt den belegten Statusbeweis.
> Hier: Reihenfolge & Verlinkung. Dort: Statusmessung mit Nachweisen.

## Statuslegende

- `[ ]` offen
- `[~]` in Arbeit
- `[x]` erledigt (Beleg im Sub-Dokument oder Statusmatrix)
- `[?]` Status unklar — erfordert Belegung in der jeweiligen Statusmatrix

Der eigentliche Wahrheitsbeweis lebt in den Sub-Roadmaps und Statusmatrizen.
Haken hier sind verdichtete Repräsentationen, keine Eigenwahrheiten.

## Leitprinzipien

1. **Kein Haken ohne Beleg.** Verweise auf konkrete Sub-Tasks oder
   Statuszeilen. Kein stilles Glätten.
2. **Sub-Roadmap führt.** Wenn diese Datei und eine Sub-Roadmap divergieren,
   führt die Sub-Roadmap. Diese Datei ist abhängig.
3. **Klein schneiden.** Aufnahme nur dort, wo Koordinationsbedarf zwischen
   Themen besteht. Themen-interne Schritte bleiben in der Sub-Roadmap.
4. **Reihenfolge vor Vollständigkeit.** Diese Datei priorisiert
   Abhängigkeiten zwischen Themen, nicht die Themen-internen Phasen.

## Relations-Hinweis

Diese Roadmap hat bewusst viele ausgehende `depends_on`-Relationen, weil sie
als Koordinations-Index aus Sub-Roadmaps und Statusmatrizen abgeleitet ist.
Ein hoher Outbound-Wert ist hier erwartet und kein eigenständiger Architektur-Hub.
Neue Relationen dürfen nur ergänzt werden, wenn ein Dokument wirklich als
Status- oder Reihenfolgequelle für die Master-Roadmap dient.

## Themen-Übersicht

| Thema | Sub-Roadmap | Statusbeleg |
|---|---|---|
| Auth | [auth-roadmap.md](blueprints/auth-roadmap.md) | [auth-status-matrix.md](reports/auth-status-matrix.md) |
| Auth-Persistenz (Runtime-Proof) | [auth-persistence-runtime-proof.md](blueprints/auth-persistence-runtime-proof.md) | [auth-persistence-readiness.md](reports/auth-persistence-readiness.md), [auth-persistence-next-step.md](reports/auth-persistence-next-step.md) |
| UI | [ui-roadmap.md](blueprints/ui-roadmap.md) | (UI-State-Machine-Tests) |
| Basemap | [map-roadmap.md](blueprints/map-roadmap.md) | [map-status-matrix.md](reports/map-status-matrix.md) |
| Kartenklarheit | [kartenklarheit-roadmap.md](blueprints/kartenklarheit-roadmap.md) | [map-architekturkritik.md](reports/map-architekturkritik.md) |
| Kartenklarheit Phase 6 (Wahrheitsbeweis) | [kartenklarheit-phase6.md](blueprints/kartenklarheit-phase6.md) | [map-status-matrix.md](reports/map-status-matrix.md) |
| Agent-Operability | [agent-operability-blaupause.md](blueprints/agent-operability-blaupause.md) | [agent-readiness-audit.md](reports/agent-readiness-audit.md) |
| Agent Safety Control Layer | [blueprint-agent-safety-control-layer.md](blueprints/blueprint-agent-safety-control-layer.md) | Blueprint gemergt; Umsetzung erfolgt in der Task-Control-Schicht: [board.md](tasks/board.md), [index.json](tasks/index.json) (`AGENT-SAFE-001` bis `AGENT-SAFE-007`, `TASK-CTL-004`). `AGENT-SAFE-006` ist als PR #1262 auf `main`; `AGENT-SAFE-007` ergänzt Run Evidence Lite in PR #1265; Merge und post-merge Verifikation stehen aus. Keine Aussage, dass PR 1–PR 16 bereits umgesetzt seien. |
| Dokumentationsstruktur & Task-Steuerung | [doc-structure-task-control-roadmap.md](blueprints/doc-structure-task-control-roadmap.md), [Blueprint](blueprints/doc-structure-task-control.md) | Beleg in der Task-Control-Schicht: [tasks/README.md](tasks/README.md), [board.md](tasks/board.md), [index.json](tasks/index.json), Drift-Guard `.github/workflows/task-index.yml`. Phase 2 vorhanden; Phase 4 Check-Modus + CI-Guard vorhanden (CI-Lauf-Nachweis offen, `TASK-CTL-003`); Schreibgenerator/Bot-PRs und Implementierungs-Mapping offen. Kein gesonderter OPT-Eintrag in `reports/optimierungsstatus.md` — Task-Control-Phasen laufen über `docs/tasks/`. |
| Versionierung | [versionierungs-blaupause.md](blueprints/versionierungs-blaupause.md) | [versionierungs-statusgrundlage.md](blueprints/versionierungs-statusgrundlage.md) |
| Optimierungsfront | (kein Sub-Plan) | [optimierungsstatus.md](reports/optimierungsstatus.md), [optimierungsbericht.md](reports/optimierungsbericht.md) |

## Strang Auth

Reihenfolge: Kanonisierung → Step-up → Persistenz-Runtime-Proof → DbSessionStore.

- [x] Phase 0 — Kanonisierung & Drift-Stopp · [auth-roadmap §4](blueprints/auth-roadmap.md)
- [x] Phase 1 — Ist-vs-Ziel-Beweis · [auth-roadmap §5](blueprints/auth-roadmap.md)
- [x] Phase 2 — Session-/Device-Modell vervollständigen · [auth-roadmap §6](blueprints/auth-roadmap.md)
- [~] Phase 3 — Step-up Auth · Passkey-Register-Grant-Handoff belegt; Passkey Register-Verify ist durch CI belegt ([Run 27487642565](https://github.com/heimgewebe/weltgewebe/actions/runs/27487642565), Commit `cc54460`); Passkey-Login-Flow (`auth/options`, `auth/verify`), Management, UI und dauerhafte Persistenz bleiben offen · [auth-roadmap §7/§8](blueprints/auth-roadmap.md)
- [~] Phase 4 — Auth-Persistenz Runtime-Proof
  - SQL/psql-Migration + psql-basierter PgBouncer-CRUD-Smoke belegt
  - SQLx/Rust-CRUD gegen direkten PostgreSQL-Pfad ist belegt (PROVEN; Session-Tabellen-CRUD-Primitive)
  - SQLx/PgBouncer-Rust-Proof bleibt optionaler Dev-/Spezialpfad und weiterhin nicht belegt (NOT_PROVEN / READY_FOR_PROOF)
  - Zielarchitekturentscheidung geschlossen: Produktion nutzt direkten PostgreSQL-Zugriff via `DATABASE_URL`; PgBouncer ist kein Produktions-Gate
  - Belege: [ADR-0007](adr/ADR-0007__auth-persistence-production-db-path.md),
    [auth-persistence-runtime-proof.md](blueprints/auth-persistence-runtime-proof.md),
    [Report](reports/auth-persistence-runtime-proof.md),
    [Direct-SQLx-Proof](proofs/sqlx-postgres-direct-session-crud-proof.md),
    [Zielarchitektur-Abgleich](reports/auth-persistence-runtime-target-reconciliation.md)
- [x] Phase 5 — `DbSessionStore`-Verdrahtung über vorhandene `SessionBackend`/`SessionOps`-Abstraktion · direkter SQLx/PostgreSQL-Persistenzpfad implementiert (PR #1072)
- [x] Phase 5b — CI-Gate für `db_session_store_persistence`-Test · PROVEN · Run [`26394569642`](https://github.com/heimgewebe/weltgewebe/actions/runs/26394569642), Job [`77692063785`](https://github.com/heimgewebe/weltgewebe/actions/runs/26394569642/job/77692063785), Commit `00a43a009c53c546355a14c08086131bd84cf8ad` (Branch `main`); direkter PostgreSQL-Port `5432` (nicht PgBouncer `6432`); `test db_session_store_persistence ... ok`, `6 passed; 0 failed`
- [ ] Phase 6 — nachgelagerter Teilstand: Cookie/session proof CI PROVEN (begrenzt) · Run [`26455010837`](https://github.com/heimgewebe/weltgewebe/actions/runs/26455010837), Job [`77886363989`](https://github.com/heimgewebe/weltgewebe/actions/runs/26455010837/job/77886363989), headSha `20c7e30136fc5872e286ab17738a64b0d03aec56`; `session_cookie_has_secure_attributes_on_magic_link_consume ... ok`, `session_cookie_insecure_when_auth_cookie_secure_disabled ... ok`, `2 passed; 0 failed`, `PROVEN: cookie/session proof tests passed (phase 6)`; verbleibende Auth-/Browser-/Passkey-Proofs weiterhin offen · [auth-status-matrix.md](reports/auth-status-matrix.md)

## Strang UI

- [x] Phase 1 — Kompositionseditor vollenden · [ui-roadmap Phase 1](blueprints/ui-roadmap.md)
- [x] Phase 2 — Zustandsdurchsetzung härten · [ui-roadmap Phase 2](blueprints/ui-roadmap.md)
- [x] Phase 3 — Fokus-Panels (Node/Account/Edge) · [ui-roadmap Phase 3](blueprints/ui-roadmap.md)
- [x] Phase 4 — Suche, Filter, A11y · [ui-roadmap Phase 4](blueprints/ui-roadmap.md)
- [x] Phase 5 — Doku-/Strukturpflege · [ui-roadmap Phase 5](blueprints/ui-roadmap.md)
- [~] Auth-UI-Integration: Step-up-Consume + Passkey-Eintragspunkt · Step-up-Consume ist als eigener Pfad unter `/auth/step-up/consume` belegt; Passkey-Eintragspunkt ist als deaktivierter Stub in der `/settings`-Account-Sektion sichtbar. Aktivierung folgt aus Auth-Phase 4 · siehe [auth-roadmap §9](blueprints/auth-roadmap.md)

## Strang Karte (Basemap + Kartenklarheit)

Reihenfolge: Daten-/Szenenklarheit → Souveräne Basemap-Pipeline → Runtime-Proof.

- [x] Kartenklarheit Phasen 0–3 — Ist sichern, Datenquelle, Szenengrenzen · [kartenklarheit-roadmap.md](blueprints/kartenklarheit-roadmap.md)
- [~] Kartenklarheit Phase 4 — Regressionen teilweise; Keyboard-/Query-Parameter-Navigation offen · [kartenklarheit-roadmap.md](blueprints/kartenklarheit-roadmap.md)
- [~] Kartenklarheit Phase 5 — Souveräne Basemap-Infrastruktur · [kartenklarheit-roadmap §155](blueprints/kartenklarheit-roadmap.md)
- [~] Basemap-Roadmap Phasen 1–3 — Pipeline, Style, Runtime-Integration · [map-roadmap.md](blueprints/map-roadmap.md)
- [~] Hamburg-PMTiles-Artefakt lokal auf heimserver erzeugt; PMTiles-Magic/SHA256/Guard-Scope pmtiles-content PROVEN; Range-Delivery PROVEN; tiefe Strukturvalidierung + visuelle Abnahme offen · [docs/proofs/basemap-hamburg-artifact-proof.md](proofs/basemap-hamburg-artifact-proof.md)
- [ ] Basemap-Roadmap Phase 4 — Betrieb & Versionierung
- [ ] Basemap-Roadmap Phase 5 — Ausbau (Faden-Dichte)
- [ ] Kartenklarheit Phase 6 — Wahrheitsbeweis (Runtime, E2E, visuelle Abnahme, CI) · [kartenklarheit-phase6.md](blueprints/kartenklarheit-phase6.md)

## Strang Agent-Operability

- [?] Minimaler Action-Layer · Zielbild dokumentiert, Implementierungsstand prüfen · [agent-operability-blaupause.md](blueprints/agent-operability-blaupause.md)
- [?] Agent-Readiness vollständig grün · [agent-readiness-audit.md](reports/agent-readiness-audit.md)
- [~] Agent Safety Control Layer · Blueprint gemergt; Safety-Preflight, Readiness Hard Fail, Claim-Spine, Agent-Contracts, Non-Ideal-Guard, Handoff-Validierung und read-only Dry-Run sind ueber `AGENT-SAFE-001` bis `AGENT-SAFE-006` belegt; `AGENT-SAFE-007` implementiert Run Evidence Lite in PR #1265. Universelle Failure-Evidence, externe Attestierung und Write Mode bleiben offen · [blueprint-agent-safety-control-layer.md](blueprints/blueprint-agent-safety-control-layer.md)
- [x] Blueprint-/Roadmap-Registration-Guard · Guard-Mechanismus umgesetzt in `TASK-CTL-004` · [board.md](tasks/board.md)
- [x] Planning-Registration-Findings triagiert und Strict-Ratchet aktiv · `TASK-CTL-005`: 8 bestehende Findings triagiert (6 via Frontmatter-Relation registriert, 2 als `deprecated` terminal), Guard läuft blockierend in `--mode strict` · [board.md](tasks/board.md), [planning-registration-findings.md](reports/planning-registration-findings.md)

## Strang Versionierung

- [?] Versionierungsmodell festziehen · Blueprint ist draft · [versionierungs-blaupause.md](blueprints/versionierungs-blaupause.md)
- [?] Statusgrundlage gegen Repo prüfen · Statusgrundlage ist active, aber Master-Status bleibt nur aus Sub-Beleg ableitbar · [versionierungs-statusgrundlage.md](blueprints/versionierungs-statusgrundlage.md)

## Strang Optimierungsfront

- Verfolgt direkt in [optimierungsstatus.md](reports/optimierungsstatus.md). Diese Roadmap dupliziert die Tickets nicht.

## Themenübergreifende Reihenfolge (Was vor Was)

1. **Direkter SQLx/Postgres-Persistenzpfad-Nachweis** vor produktivem `DbSessionStore`; PgBouncer-Proofs sind nach ADR-0007 optionaler Dev-/Spezialpfad.
2. **Auth-Phase 3 (Step-up)** vor **UI Auth-Integration**.
3. **Kartenklarheit Phase 5 (souveräne Pipeline)** vor **Phase 6 (Wahrheitsbeweis)**.
4. **Basemap-Roadmap Phase 3 (Runtime-Integration)** überlappt mit
   **Kartenklarheit Phase 5/6** — gemeinsame Schnittmenge: PMTiles-Auslieferung
   über Caddy mit reproduzierbarem Artefakt.
5. **Versionierungs-Statusgrundlage** vor jedem Feature, das semver-relevante
   Schemata berührt (Domain-Contracts).

## Pflege-Regeln

- Diese Datei ist nur dann anzupassen, wenn eine Sub-Roadmap einen Phasen-
  oder Reihenfolge-Wechsel bekommt. Themen-interne Detail-Tasks gehören
  **nicht** hierher.
- Statuswechsel hier nur, wenn die zugehörige Sub-Roadmap oder Statusmatrix
  den Wechsel bereits belegt.
- Bei Drift zwischen dieser Datei und einer Sub-Roadmap: Sub-Roadmap führt;
  diese Datei nachziehen oder einen Drift-Eintrag in
  [optimierungsstatus.md](reports/optimierungsstatus.md) anlegen.
