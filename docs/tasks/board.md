---
id: tasks.board
title: Weltgewebe Task Board
doc_type: task-board
status: active
summary: >
  Menschliche Arbeitskarte für aktive Task-Control-Prioritäten.
  Keine Wahrheitsschicht – Statuswechsel brauchen Evidenz in Statusmatrizen, Reports, PRs oder Tests.
relations:
  - type: depends_on
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/tasks/README.md
---

# Weltgewebe Task Board

> Arbeitssteuerung, keine Wahrheitsschicht.
> Statuswechsel brauchen Evidenz in Statusmatrizen, Reports, PRs oder Tests.

## Aktive Prioritäten

| ID | Bereich | Titel | Status | Priorität | Evidenz | Nächste Aktion |
|---|---|---|---|---|---|---|
| TASK-CTL-001 | docs | Task-Control Phase 2 etablieren | partial | high | `docs/tasks/README.md`, `scripts/docmeta/validate_task_index.py` | PR mergen, Validator-Pass bestätigen |
| OPT-API-001 | api | Paginierung Listen-Endpunkte | partial | high | `apps/api/src/routes/nodes.rs` | Cursor-Variante + Response-Metadaten implementieren |
| OPT-CON-001 | ci | `additionalProperties: false` + String-Constraints | partial | high | `contracts/domain/node.schema.json` | Schema-für-Schema-Audit abschließen |
| OPT-DOC-001 | docs | Incident-/DB-Recovery-Runbooks | partial | high | `docs/runbook.md` | Eigenständige Runbooks unter `docs/runbooks/` erstellen |
| OPT-ARC-001 | api | JSONL → PostgreSQL | open | high | `apps/api/src/routes/nodes.rs` (Ist-Befund) | Migrations- und Cutover-Plan erstellen |

## Blocker

| ID | Blocker | Fehlt | Folge |
|---|---|---|---|
| OPT-ARC-001 | Kein Migrations-/Cutover-Plan | Konzept für sicheren Cutover | JSONL bleibt aktive Datenquelle |
| OPT-API-001 | Cursor-Variante nicht spezifiziert | Sortierungsvertrag + Response-Metadaten | Paginierung bleibt unvollständig |

## Nächste PR-Kandidaten

| ID | PR-Schnitt | Akzeptanzkriterium |
|---|---|---|
| TASK-CTL-003 | Phase 4: `scripts/docmeta/generate_task_index.py` + CI-Guard | Deterministischer Task-Index, Drift-Erkennung im CI |
| OPT-CON-001 | Schema-Constraints: `additionalProperties: false` alle 6 Schemas | `just contracts-domain-check` pass + kein permissives Nested-Object |
| OPT-DOC-001 | Runbooks: `docs/runbooks/incident-response.md` + `db-recovery.md` | Eigenständige Abläufe, kein DSGVO-Leak-Risiko |

## Erledigte Tasks (Phase 1–2 Referenz)

| ID | Bereich | Titel | Evidenz |
|---|---|---|---|
| OPT-MAP-001 | map | Basemap Runtime Proof | CI-Job `basemap-range-delivery-proof` PROVEN, Commit `14feefd6` |
| OPT-API-002 | api | Session-Persistenz PostgreSQL | `apps/api/src/auth/session_db.rs`, CI PROVEN, Commit `00a43a00` |
| OPT-API-003 | api | DB-Migrationen | `apps/api/migrations/`, CI PROVEN, Commit `00a43a00` |
| OPT-API-004 | api | Limit-Obergrenze `/nodes` & `/accounts` | `apps/api/src/routes/query.rs`, Tests 4+9 passed |
| OPT-FE-003 | web | Panel-Detail-Fetch-Logik extrahieren | `apps/web/src/lib/panels/panelDetails.ts`, 10+5 Tests passed |
