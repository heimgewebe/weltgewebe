---
id: reports.optimierungsstatus
title: "Optimierungsstatus Weltgewebe"
doc_type: status-matrix
status: active
created: 2026-04-27
lang: de
summary: >
  Operative Statusmatrix zu den Maßnahmen aus dem Optimierungsbericht.
  Diese Datei trennt Fortschrittsstand von Diagnose und verlangt konkrete Nachweise.
relations:
  - type: depends_on
    target: docs/reports/optimierungsbericht.md
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
  - type: relates_to
    target: docs/reports/auth-persistence-readiness.md
---

# Optimierungsstatus Weltgewebe

Diese Datei führt den operativen Umsetzungsstand.
Maßgeblich sind nur belegte Repo-Pfade, Tests und dokumentierte Restlücken.
Keine stillen Haken.
Kein `done` ohne reproduzierbaren Nachweis.

## Statuskriterien

| Status | Kriterium |
|---|---|
| `open` | Kein positiver überprüfbarer Umsetzungsnachweis vorhanden; ein negativer Ist-Befund kann belegt sein |
| `partial` | Mindestens ein überprüfbarer Nachweis vorhanden, aber Restlücke bleibt |
| `done` | Nachweis + reproduzierbarer Test + keine Restlücke |
| `obsolete` | Maßnahme fachlich überholt; Begründung erforderlich |
| `contradicted` | Repo-Zustand oder spätere Entscheidung widerspricht der Empfehlung; Begründung erforderlich |

## Befund-Evidenzgrade

| Befund-Evidenzgrad | Bedeutung |
|---|---|
| `doc-only` | Der Ist-Befund ist nur dokumentarisch belegt |
| `code` | Der Ist-Befund ist durch Code belegbar |
| `code+test` | Der Ist-Befund ist durch Code und Test belegbar |
| `ci` | Der Ist-Befund ist durch CI-Konfiguration oder CI-Pfad belegbar |
| `runtime` | Der Ist-Befund ist durch Laufzeit-/Deploy-Nachweis belegbar |

## Matrix

| id | bereich | maßnahme | status | befund_evidenzgrad | risiko | aufwand | priorität | nachweis | test | restlücke | zuletzt_geprüft |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OPT-API-001 | API | Paginierung Listen-Endpunkte | partial | code+test | mittel | mittel | hoch | `apps/api/src/routes/nodes.rs`, `apps/api/src/routes/edges.rs`, `apps/api/src/routes/accounts.rs` | `apps/api/tests/api_nodes.rs`, `apps/api/tests/api_edges.rs`, `apps/api/tests/api_accounts.rs` | Cursor-Variante, Response-Metadaten und dokumentierter Sortierungsvertrag fehlen | 2026-04-27 |
| OPT-CON-001 | Contracts | `additionalProperties: false` + String-Constraints | partial | code | mittel | niedrig | hoch | `contracts/domain/node.schema.json`, `contracts/domain/account.schema.json`, `contracts/domain/role.schema.json` | fehlt | Vollständiges Schema-für-Schema-Audit inkl. verbleibender permissiver Felder fehlt | 2026-04-27 |
| OPT-DOC-001 | Dokumentation | Incident-/DB-Recovery-Runbooks | partial | doc-only | hoch | niedrig | hoch | `docs/runbook.md`, `docs/runbook.observability.md`, `docs/runbooks/README.md` | fehlt | Eigenständige, durchgehende Incident-Response- und DB-Recovery-Abläufe fehlen | 2026-04-27 |
| OPT-CI-001 | CI/CD | Workflow-Redundanz | partial | ci | mittel | mittel | mittel | `.github/workflows/ci.yml`, `.github/workflows/web.yml`, `.github/workflows/heavy.yml` | fehlt | Konsolidierungskonzept via `workflow_call`, Redundanzkriterien und eigener CI-Strukturcheck fehlen | 2026-04-27 |
| OPT-MAP-001 | Frontend/Maps | Basemap Runtime Proof | partial | ci | hoch | mittel | hoch | `scripts/guard/basemap-runtime-proof.sh`, `.github/workflows/basemap-runtime-proof.yml`, `apps/web/tests/basemap-client-integration.spec.ts` | `scripts/guard/basemap-runtime-proof.sh`; CI-Pfad: `.github/workflows/basemap-runtime-proof.yml` | Echter CI-Proof mit PMTiles-Artefakt, laufendem Caddy und HTTP-206-Beleg fehlt | 2026-04-27 |
| OPT-API-002 | API | Session-Persistenz Redis/DB | open | code | hoch | mittel | hoch | `apps/api/src/auth/session.rs` | fehlt | SessionStore ist weiterhin in-memory (`RwLock<HashMap<...>>`), persistenter Adapter fehlt | 2026-04-27 |
| OPT-API-003 | API | DB-Migrationen | open | code | hoch | niedrig | hoch | `apps/api/src/lib.rs`, `docs/runbook.md` | fehlt | Kein Migrationsverzeichnis `apps/api/migrations/` und kein CI-Pflichtpfad für Migrationen | 2026-04-27 |
| OPT-FE-001 | Frontend | Svelte-5-Runes-Migration | open | code | mittel | hoch | mittel | `apps/web/src/routes/map/+page.svelte`, `apps/web/src/lib/maplibre/Marker.svelte` | fehlt | Keine belegte Nutzung von `$state`, `$derived`, `$effect` in Kernkomponenten | 2026-04-27 |
| OPT-FE-002 | Frontend | Map-Aufteilung | open | code | mittel | mittel | mittel | `apps/web/src/routes/map/+page.svelte` | fehlt | Route bleibt monolithisch; Aufteilung in klar getrennte Teilkomponenten fehlt | 2026-04-27 |
| OPT-INF-001 | Infrastruktur | Trivy Image Scanning | open | ci | mittel | niedrig | mittel | `.github/workflows/security.yml` | fehlt | SBOM mit Syft vorhanden, aber kein Trivy-Container-Scan-Schritt definiert | 2026-04-27 |
| OPT-ARC-001 | Architektur | JSONL → PostgreSQL | open | code | hoch | hoch | hoch | `apps/api/src/routes/nodes.rs` | fehlt | JSONL ist weiterhin aktive Datenquelle; Migrations- und Cutover-Plan fehlt | 2026-04-27 |
