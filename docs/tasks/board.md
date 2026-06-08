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
| DEPLOY-DNS-001 | infra | INWX Registrar/DNS Cutover vorbereiten und durchführen | open | high | `docs/adr/ADR-0008__domain-mail-provider-boundaries.md`, `docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md`, `docs/runbooks/domain-mail-cutover.md`, `docs/reports/inwx-zone-reconciliation-plan.md`, externe Audit-Artefakte (keine privaten Rohdaten im Repo) | Offline-Zonenmanifest aus aktueller IONOS-Zone finalisieren; INWX-Vor-DNS/Predelegation als nicht verfügbar markieren; abruptes INWX-Aktivierungsfenster, DNSSEC-Deaktivierungs-/Parent-DS-Stop-Gate, Web-Rollenentscheidung, getrennte Brevo-DNS- und post-runtime-cutover Magic-Link-Gates sowie Rollback-Grenzen festhalten; frühere Pre-Delegation-Annahme aus `DEPLOY-DNS-002` ist durch diese Constraint superseded; keine IONOS-Kündigung vor Registrar-/DNS-/Web-/Mail-/Magic-Link-Proof und 48 h Beobachtung |
| OPT-CI-005 | ci | Node-24 Runtime Readiness | partial | high | `.github/workflows/`, `scripts/ci/check_actions_node24_readiness.py`, `scripts/ci/tests/test_check_actions_node24_readiness.py` | PR-CI-Lauf unter erzwungener Node-24-Action-Runtime prüfen; verbleibende Node-20-Metadatenwarnungen für Stage B erfassen |
| DEPLOY-DNS-002 | infra | Historischer INWX-Zonencheck; Pre-Delegation-Annahme superseded | done | high | `docs/tasks/DEPLOY-DNS-001B.md`, externe Audit-Artefakte | Historie bleibt abgeschlossen; keine operative Pre-Delegation-Anweisung. Die Annahme ist durch `DEPLOY-DNS-001` und das abrupte Aktivierungsfenster superseded |
| OPT-API-001 | api | Paginierung Listen-Endpunkte | done | high | `apps/api/src/routes/query.rs`, `docs/specs/list-pagination-api.md`, `apps/api/tests/api_{nodes,edges,accounts}.rs` | Implementiert in PR #1121 (Commit 98bb7e2); Cursor-Paginierung für /nodes, /edges, /accounts mit limit=0-Validierung |
| OPT-CON-001 | ci | geschlossene Schemas + begrenzte Extension-Flächen | partial | high | `contracts/domain/*.schema.json` (alle 6 gehärtet) | CI-Nachweis `contracts-domain-check` abwarten, dann auf `done` |
| OPT-ARC-001 | api | JSONL → PostgreSQL | partial | high | `docs/blueprints/domain-data-postgres-cutover.md`, `apps/api/migrations/20260531000001_create_domain_nodes.up.sql`, `apps/api/migrations/20260531000002_create_domain_edges.up.sql`, `apps/api/migrations/20260531000003_create_domain_accounts.up.sql`, `apps/api/src/config.rs`, `apps/api/src/domain_db.rs`, `apps/api/src/routes/domain_write_guard.rs`, `apps/api/src/routes/accounts.rs`, `apps/api/tests/db_domain_schema_migrations.rs`, `apps/api/tests/db_domain_backfill.rs`, `apps/api/tests/db_domain_read_path.rs`, `apps/api/tests/db_domain_account_write_path.rs`, `docs/reports/domain-backfill-proof.md`, `docs/reports/domain-read-path-proof.md`, `docs/reports/domain-account-write-path-proof.md`, `.github/workflows/api.yml` (`db-domain-schema-migrations-proof`, `db-domain-backfill-proof`, `db-domain-read-path-proof`, `db-domain-account-write-path-proof`) | Phase B + C + D (read-only) implementiert; Phase E-A implementiert: enger PostgreSQL-Account-Create-Write hinter getrenntem Gate `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE` (nur `POST /accounts`, kein Dual-Write); DB-Suiten für lokalen PostgreSQL-Proof vorbereitet; lokaler PostgreSQL-Proof in dieser Umgebung nicht ausgeführt; PR-CI ist maßgeblich; PR-CI-Beleg ausstehend; nächste Aktion: PR-CI-Belege abwarten, Phase E Rest (nodes/edges/step-up/webauthn) bleibt offen |
| TASK-CTL-003 | ci | Task-Index-Generator und CI-Guard | partial | medium | `scripts/docmeta/generate_task_index.py`, `scripts/docmeta/tests/test_generate_task_index.py`, `scripts/docmeta/agent_entrypoint_smoke.py`, `scripts/docmeta/tests/test_agent_entrypoint_smoke.py`, `.github/workflows/task-index.yml` | CI-Lauf des `task-index`-Workflows nachweisen, dann auf `done` setzen |
| AGENT-SAFE-001 | governance | Safety-Preflight Guard minimal einführen | done | high | `scripts/agent/check_agent_preflight.py`, `scripts/agent/tests/test_check_agent_preflight.py`, `.github/workflows/agent-safety-preflight.yml`, `docs/security/agent-write-scope-baseline.md` | Report-only Safety-Preflight Guard ist implementiert; Claim-Spine, Agent-Contracts und Blocking-Mode bleiben bewusst in Folge-Slices (`AGENT-SAFE-002` bis `AGENT-SAFE-004`) |
| AGENT-SAFE-002 | governance | Readiness Hard Fail für Agent-Fähigkeiten einführen | done | high | `scripts/docmeta/generate_agent_readiness.py`, `scripts/docmeta/tests/test_generate_agent_readiness.py`, `docs/tasks/index.json` | Slice abgeschlossen: deterministische Capability-Matrix aktiv und `overall=pass` bei fehlenden Hard-Capabilities ausgeschlossen; offene Capability-Gaps laufen weiter in `AGENT-SAFE-003`/`AGENT-SAFE-004` |
| AGENT-SAFE-003 | governance | Minimale Claim-Evidence-Spine aufbauen | done | high | `docs/claims/registry.yml`, `docs/claims/README.md`, `scripts/docmeta/validate_claim_registry.py`, `scripts/docmeta/tests/test_validate_claim_registry.py`, `scripts/docmeta/generate_agent_readiness.py`, `scripts/docmeta/tests/test_generate_agent_readiness.py` | Slice abgeschlossen: minimale Claim-Evidence-Spine ist maschinenlesbar validierbar; Folge-Slice AGENT-SAFE-004 bleibt offen |
| AGENT-SAFE-004 | governance | Minimale Agent-Contracts und Non-Ideal-Guard einführen | done | high | `contracts/agent/task.schema.json`, `scripts/agent/check_non_ideal_task.py`, `scripts/agent/tests/test_check_non_ideal_task.py`, `tests/fixtures/agent/`, `docs/reference/agent-operability-fixture-matrix.md`, `scripts/docmeta/generate_agent_readiness.py`, `scripts/docmeta/tests/test_generate_agent_readiness.py` | Slice abgeschlossen: minimaler Task-Contract und deterministischer Non-Ideal-Guard sind implementiert; Readiness integriert, weitere Hard-Capabilities (Handoff, Dry-Run, Write-Mode) bleiben offen |
| TASK-CTL-004 | docs | Guard gegen uneingeordnete Blueprints und Pläne einführen | done | medium | `scripts/docmeta/check_planning_registration.py`, `scripts/docmeta/planning_registration.yml`, `scripts/docmeta/tests/test_check_planning_registration.py`, `.github/workflows/task-index.yml` | Guard-Mechanismus umgesetzt; Strict-Ratchet und Bestandsfinding-Triage abgeschlossen in `TASK-CTL-005`; Planning-registration und docmeta Test-Suiten grün |
| TASK-CTL-005 | docs | Bestehende Planning-Registration-Findings triagieren und Ratchet vorbereiten | done | high | `docs/reports/planning-registration-findings.md`, `.github/workflows/task-index.yml`, `scripts/docmeta/check_planning_registration.py` | 8 Findings triagiert (6 via Frontmatter-Relation registriert, 2 als `deprecated` terminal); planning-registration guard läuft blockierend im Strict-Modus |
| DOCMETA-FRESHNESS-001 | docs | Claim-Evidence/Freshness-Spine registrieren und reviewbar halten | partial | medium | `docs/claims/registry.yml`, `docs/claims/README.md`, `docs/doc-freshness-registry.yml`, `scripts/docmeta/validate_claim_registry.py`, `scripts/docmeta/validate_doc_freshness_registry.py`, `scripts/docmeta/freshness_scope_policy.yml`, `scripts/docmeta/generate_claim_evidence_map.py`, `.github/workflows/claim-registry.yml`, `.github/workflows/docs-guard.yml` | Claim-Evidence/Freshness-Spine ist implementiert und validierbar; Markdown-Details je Claim implementiert (DOC-MECH-FRESHNESS-S2); Scope wird deklarativ via `scripts/docmeta/freshness_scope_policy.yml` entschieden, realer Scope bleibt CLAIM-AGENT-SAFE-* (DOC-MECH-FRESHNESS-S3); Folgearbeiten (TYPED-CLAIMINFO, Review-Age-Hygiene) bleiben sichtbar |

## Blocker

| ID | Blocker | Fehlt | Folge |
|---|---|---|---|
| OPT-ARC-001 | PR-CI-Laufbeleg für alle DB-Jobs ausstehend; Phase E-A (POST /accounts) und E-B (PATCH /nodes) implementiert | Grünen CI-Lauf der DB-Jobs belegen; Edge-Writes, Step-up-E-Mail-Persistenz und WebAuthn-User-ID-Writeback ausstehend | JSONL bleibt Default-Lesequelle und Write-Truth bis vollständiger Cutover; POST /accounts und PATCH /nodes schreiben optional PostgreSQL |

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
