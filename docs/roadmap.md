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
| Versionierung | [versionierungs-blaupause.md](blueprints/versionierungs-blaupause.md) | [versionierungs-statusgrundlage.md](blueprints/versionierungs-statusgrundlage.md) |
| Optimierungsfront | (kein Sub-Plan) | [optimierungsstatus.md](reports/optimierungsstatus.md), [optimierungsbericht.md](reports/optimierungsbericht.md) |

## Strang Auth

Reihenfolge: Kanonisierung → Step-up → Persistenz-Runtime-Proof → DbSessionStore.

- [x] Phase 0 — Kanonisierung & Drift-Stopp · [auth-roadmap §4](blueprints/auth-roadmap.md)
- [x] Phase 1 — Ist-vs-Ziel-Beweis · [auth-roadmap §5](blueprints/auth-roadmap.md)
- [x] Phase 2 — Session-/Device-Modell vervollständigen · [auth-roadmap §6](blueprints/auth-roadmap.md)
- [~] Phase 3 — Step-up Auth · Passkey-Register-Grant-Handoff belegt; Register-Verify und UI-E2E offen · [auth-roadmap §7/§8](blueprints/auth-roadmap.md)
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
- [ ] Phase 6 — Auth-Statusmatrix vollständig grün · [auth-status-matrix.md](reports/auth-status-matrix.md)

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
- [ ] Basemap-Roadmap Phase 4 — Betrieb & Versionierung
- [ ] Basemap-Roadmap Phase 5 — Ausbau (Faden-Dichte)
- [ ] Kartenklarheit Phase 6 — Wahrheitsbeweis (Runtime, E2E, visuelle Abnahme, CI) · [kartenklarheit-phase6.md](blueprints/kartenklarheit-phase6.md)

## Strang Agent-Operability

- [?] Minimaler Action-Layer · Zielbild dokumentiert, Implementierungsstand prüfen · [agent-operability-blaupause.md](blueprints/agent-operability-blaupause.md)
- [?] Agent-Readiness vollständig grün · [agent-readiness-audit.md](reports/agent-readiness-audit.md)

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
