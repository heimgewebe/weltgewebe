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
| OPT-API-001 | api | Paginierung Listen-Endpunkte | partial | high | `apps/api/src/routes/query.rs`, `docs/specs/list-pagination-api.md`, `apps/api/tests/api_{nodes,edges,accounts}.rs` | CI-Nachweis (`api-smoke.yml`) der Cursor-Tests abwarten, dann auf `done` |
| OPT-CON-001 | ci | geschlossene Schemas + begrenzte Extension-Flächen | partial | high | `contracts/domain/*.schema.json` (alle 6 gehärtet) | CI-Nachweis `contracts-domain-check` abwarten, dann auf `done` |
| OPT-ARC-001 | api | JSONL → PostgreSQL | open | high | `apps/api/src/routes/nodes.rs` (Ist-Befund) | Migrations- und Cutover-Plan erstellen |
| TASK-CTL-003 | ci | Task-Index-Generator und CI-Guard | partial | medium | `scripts/docmeta/generate_task_index.py`, `scripts/docmeta/tests/test_generate_task_index.py`, `scripts/docmeta/agent_entrypoint_smoke.py`, `scripts/docmeta/tests/test_agent_entrypoint_smoke.py`, `.github/workflows/task-index.yml` | CI-Lauf des `task-index`-Workflows nachweisen, dann auf `done` setzen |

## Blocker

| ID | Blocker | Fehlt | Folge |
|---|---|---|---|
| OPT-ARC-001 | Kein Migrations-/Cutover-Plan | Konzept für sicheren Cutover | JSONL bleibt aktive Datenquelle |
| OPT-API-001 | CI-Nachweis steht aus | grüner `api-smoke.yml`-Lauf der Cursor-Tests | Status bleibt `partial` bis CI grün |

## Nächste PR-Kandidaten

| ID | PR-Schnitt | Akzeptanzkriterium |
|---|---|---|
| OPT-CON-001 | Schema-Constraints: `additionalProperties: false` alle 6 Schemas | `just contracts-domain-check` pass + kein permissives Nested-Object |

## Zurückgestellte / optionale Tasks

| ID | Grund | Wiederaufnahmebedingung |
|---|---|---|
| TASK-CTL-002 | GitHub Issue Forms, PR-Template und Release-Konfiguration sind aktuell nicht eingeführt, weil der Nutzen gegenüber kontextgenauen PR-Bodies nicht belegt ist. | Externe Beitragende ohne Projekteinblick werden relevant, PR-Bodies verlieren wiederholt Task-/Evidenzbezüge oder der Release-Prozess ist stabil genug für Release-Labels. |

## Erledigte Tasks

| ID | Bereich | Titel | Evidenz |
|---|---|---|---|
| TASK-CTL-001 | docs | Task-Control Phase 2 etablieren | `docs/tasks/`, `docs/reports/optimierungsstatus.json`, `scripts/docmeta/validate_task_index.py`, `scripts/docmeta/tests/test_validate_task_index.py` |
| OPT-DOC-001 | docs | Incident-/DB-Recovery-Runbooks | `docs/runbooks/incident-response.md`, `docs/runbooks/db-recovery.md`; Navigation in `docs/runbooks/README.md` + `docs/index.md`; Drill-Querverweis in `docs/runbook.md` §2; Doku-Hygiene-Guards grün |
| OPT-MAP-001 | map | Basemap Runtime Proof | CI-Job `basemap-range-delivery-proof` PROVEN, Commit `14feefd6` |
| OPT-API-002 | api | Session-Persistenz PostgreSQL | `apps/api/src/auth/session_db.rs`, CI PROVEN, Commit `00a43a00` |
| OPT-API-003 | api | DB-Migrationen | `apps/api/migrations/`, CI PROVEN, Commit `00a43a00` |
| OPT-API-004 | api | Limit-Obergrenze `/nodes` & `/accounts` | `apps/api/src/routes/query.rs`, Tests 4+9 passed |
| OPT-FE-003 | web | Panel-Detail-Fetch-Logik extrahieren | `apps/web/src/lib/panels/panelDetails.ts`, 10+5 Tests passed |
