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

## Einordnung 2026-06-16 — optimierte TODO-Liste (Strang A Cutover / Strang B Hygiene)

Die optimierte TODO-Liste wurde gegen den Repo-Stand abgeglichen und einsortiert:

- **Bereits erledigt & belegt — keine Reaktivierung:** E-Mail-Duplicate-Audit (Listen-TODO 1)
  ist umgesetzt (`scripts/docmeta/audit_account_email_uniqueness.py`,
  `docs/reports/domain-account-email-uniqueness-audit.md`, Runtime-Audit 2026-06-13: 0 Duplikate);
  der normalisierte E-Mail-Unique-Index inkl. `409`-Mapping (Listen-TODO 4) ist umgesetzt und
  CI-belegt (`apps/api/migrations/20260613000001_*`, CI-Run `27487642549`). Diese entsprechen den
  repo-internen Schritten „TODO 2 / TODO 2A" als OPT-ARC-001-Sub-Deliverables.
- **Bleibt unter OPT-ARC-001 (nicht dupliziert):** Listenparitäts-Proof (Listen-TODO 3) ist der
  vorhandene Read-Path-Proof-Harness (`prepared`, Legacy-Order-Preservation-Blocker);
  Runtime-Smoke (TODO 11) und JSONL-Demontage (TODO 12) sind OPT-ARC-001-Cutover-Akzeptanz.
- **Neu als eigene PR-Schnitte:** Edge-Orphan-Audit, Edge-Referenz-Policy, Single-/Multi-Instance,
  Step-up-E-Mail- und WebAuthn-Persistenz, `webauthn_user_id`-Backfill, Edge-Cache-Design
  (DB-PROOF-/DOMAIN-PG-/AUTH-PG-IDs).
- **Strang A (PostgreSQL/Auth-Cutover) und Strang B (Repo-/CI-/Docs-Hygiene) nicht in einen PR mischen.**

## Aktive Prioritäten

| ID | Bereich | Titel | Status | Priorität | Evidenz | Nächste Aktion |
|---|---|---|---|---|---|---|
| DEPLOY-DNS-001 | infra | INWX Registrar/DNS Cutover vorbereiten und durchführen | open | high | `docs/adr/ADR-0008__domain-mail-provider-boundaries.md`, `docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md`, `docs/runbooks/domain-mail-cutover.md`, `docs/reports/inwx-zone-reconciliation-plan.md`, externe Audit-Artefakte (keine privaten Rohdaten im Repo) | Offline-Zonenmanifest aus aktueller IONOS-Zone finalisieren; INWX-Vor-DNS/Predelegation als nicht verfügbar markieren; abruptes INWX-Aktivierungsfenster, DNSSEC-Deaktivierungs-/Parent-DS-Stop-Gate, Web-Rollenentscheidung, getrennte Brevo-DNS- und post-runtime-cutover Magic-Link-Gates sowie Rollback-Grenzen festhalten; frühere Pre-Delegation-Annahme aus `DEPLOY-DNS-002` ist durch diese Constraint superseded; keine IONOS-Kündigung vor Registrar-/DNS-/Web-/Mail-/Magic-Link-Proof und 48 h Beobachtung |
| OPT-CI-005 | ci | Node-24 Runtime Readiness | partial | high | `.github/workflows/`, `scripts/ci/check_actions_node24_readiness.py`, `scripts/ci/tests/test_check_actions_node24_readiness.py` | PR-CI-Lauf unter erzwungener Node-24-Action-Runtime prüfen; verbleibende Node-20-Metadatenwarnungen für Stage B erfassen |
| DEPLOY-DNS-002 | infra | Historischer INWX-Zonencheck; Pre-Delegation-Annahme superseded | done | high | `docs/tasks/DEPLOY-DNS-001B.md`, externe Audit-Artefakte | Historie bleibt abgeschlossen; keine operative Pre-Delegation-Anweisung. Die Annahme ist durch `DEPLOY-DNS-001` und das abrupte Aktivierungsfenster superseded |
| OPT-API-001 | api | Paginierung Listen-Endpunkte | done | high | `apps/api/src/routes/query.rs`, `docs/specs/list-pagination-api.md`, `apps/api/tests/api_{nodes,edges,accounts}.rs` | Implementiert in PR #1121 (Commit 98bb7e2); Cursor-Paginierung für /nodes, /edges, /accounts mit limit=0-Validierung |
| OPT-CON-001 | ci | geschlossene Schemas + begrenzte Extension-Flächen | partial | high | `contracts/domain/*.schema.json` (alle 6 gehärtet) | CI-Nachweis `contracts-domain-check` abwarten, dann auf `done` |
| OPT-ARC-001 | api | JSONL → PostgreSQL | partial | high | `docs/blueprints/domain-data-postgres-cutover.md`, `apps/api/migrations/20260531000001_create_domain_nodes.up.sql`, `apps/api/migrations/20260531000002_create_domain_edges.up.sql`, `apps/api/migrations/20260531000003_create_domain_accounts.up.sql`, `apps/api/src/config.rs`, `apps/api/src/domain_db.rs`, `apps/api/src/routes/domain_write_guard.rs`, `apps/api/src/routes/accounts.rs`, `apps/api/src/routes/nodes.rs`, `apps/api/src/routes/edges.rs`, `apps/api/tests/db_domain_schema_migrations.rs`, `apps/api/tests/db_domain_backfill.rs`, `apps/api/tests/db_domain_read_path.rs`, `apps/api/tests/db_domain_account_write_path.rs`, `apps/api/tests/db_domain_node_write_path.rs`, `apps/api/tests/db_domain_edge_write_path.rs`, `docs/reports/domain-backfill-proof.md`, `docs/reports/domain-read-path-proof.md`, `docs/reports/domain-account-write-path-proof.md`, `docs/reports/domain-node-write-path-proof.md`, `docs/reports/domain-edge-write-path-proof.md`, `.github/workflows/api.yml` (`db-domain-schema-migrations-proof`, `db-domain-backfill-proof`, `db-domain-read-path-proof`, `db-domain-account-write-path-proof`, `db-domain-node-write-path-proof`, `db-domain-edge-write-path-proof`), CI-Job: `db-domain-edge-write-path-proof`, `docs/reports/opt-arc-001-db-proof-matrix.json`, `scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py` | Phase B, C, D, E-A, E-B und E-C sind implementiert; Schema- und Backfill-Proof bleiben belegt; der Read-Path-Proof-Harness ist wegen List-Order-Gap-Diagnostic wieder prepared und braucht frische PR-CI-Evidence; Legacy-Order-Preservation für `/nodes` und `/edges` bleibt Cutover-Blocker; POST /edges schreibt optional PostgreSQL; Edge-Write-Proof in PR-CI belegt (PR-CI-Lauf 27441828545 (pull_request, PR #1188, Commit `75ad1ebb`): db-domain-edge-write-path-proof grün); Step-up-E-Mail-Persistenz, WebAuthn-User-ID-Writeback, Runtime-Smoke, Cutover und JSONL-Demontage bleiben offen; JSONL bleibt Default-Lesequelle und Write-Truth; kein Dual-Write |
| AGENT-SAFE-001 | governance | Safety-Preflight Guard minimal einführen | done | high | `scripts/agent/check_agent_preflight.py`, `scripts/agent/tests/test_check_agent_preflight.py`, `.github/workflows/agent-safety-preflight.yml`, `docs/security/agent-write-scope-baseline.md` | Report-only Safety-Preflight Guard ist implementiert; Claim-Spine, Agent-Contracts und Blocking-Mode bleiben bewusst in Folge-Slices (`AGENT-SAFE-002` bis `AGENT-SAFE-004`) |
| AGENT-SAFE-002 | governance | Readiness Hard Fail für Agent-Fähigkeiten einführen | done | high | `scripts/docmeta/generate_agent_readiness.py`, `scripts/docmeta/tests/test_generate_agent_readiness.py`, `docs/tasks/index.json` | Slice abgeschlossen: deterministische Capability-Matrix aktiv und `overall=pass` bei fehlenden Hard-Capabilities ausgeschlossen; offene Capability-Gaps laufen weiter in `AGENT-SAFE-003`/`AGENT-SAFE-004` |
| AGENT-SAFE-003 | governance | Minimale Claim-Evidence-Spine aufbauen | done | high | `docs/claims/registry.yml`, `docs/claims/README.md`, `scripts/docmeta/validate_claim_registry.py`, `scripts/docmeta/tests/test_validate_claim_registry.py`, `scripts/docmeta/generate_agent_readiness.py`, `scripts/docmeta/tests/test_generate_agent_readiness.py` | Slice abgeschlossen: minimale Claim-Evidence-Spine ist maschinenlesbar validierbar; Folge-Slice AGENT-SAFE-004 bleibt offen |
| AGENT-SAFE-004 | governance | Minimale Agent-Contracts und Non-Ideal-Guard einführen | done | high | `contracts/agent/task.schema.json`, `scripts/agent/check_non_ideal_task.py`, `scripts/agent/tests/test_check_non_ideal_task.py`, `tests/fixtures/agent/`, `docs/reference/agent-operability-fixture-matrix.md`, `scripts/docmeta/generate_agent_readiness.py`, `scripts/docmeta/tests/test_generate_agent_readiness.py` | Slice abgeschlossen: minimaler Task-Contract und deterministischer Non-Ideal-Guard sind implementiert; Readiness integriert, weitere Hard-Capabilities (Handoff, Dry-Run, Write-Mode) bleiben offen |
| TASK-CTL-004 | docs | Guard gegen uneingeordnete Blueprints und Pläne einführen | done | medium | `scripts/docmeta/check_planning_registration.py`, `scripts/docmeta/planning_registration.yml`, `scripts/docmeta/tests/test_check_planning_registration.py`, `.github/workflows/task-index.yml` | Guard-Mechanismus umgesetzt; Strict-Ratchet und Bestandsfinding-Triage abgeschlossen in `TASK-CTL-005`; Planning-registration und docmeta Test-Suiten grün |
| TASK-CTL-005 | docs | Bestehende Planning-Registration-Findings triagieren und Ratchet vorbereiten | done | high | `docs/reports/planning-registration-findings.md`, `.github/workflows/task-index.yml`, `scripts/docmeta/check_planning_registration.py` | 8 Findings triagiert (6 via Frontmatter-Relation registriert, 2 als `deprecated` terminal); planning-registration guard läuft blockierend im Strict-Modus |
| DOCMETA-FRESHNESS-001 | docs | Claim-Evidence/Freshness-Spine registrieren und reviewbar halten | partial | medium | `docs/claims/registry.yml`, `docs/claims/README.md`, `docs/doc-freshness-registry.yml`, `scripts/docmeta/validate_claim_registry.py`, `scripts/docmeta/validate_doc_freshness_registry.py`, `scripts/docmeta/freshness_scope_policy.yml`, `scripts/docmeta/generate_claim_evidence_map.py`, `.github/workflows/claim-registry.yml`, `.github/workflows/docs-guard.yml` | Claim-Evidence/Freshness-Spine ist implementiert und validierbar; Markdown-Details je Claim implementiert (DOC-MECH-FRESHNESS-S2); Scope wird deklarativ via `scripts/docmeta/freshness_scope_policy.yml` entschieden, realer Scope bleibt CLAIM-AGENT-SAFE-* (DOC-MECH-FRESHNESS-S3); Claim-Evidence-Information ist intern als `ClaimInfo` typisiert (DOC-MECH-FRESHNESS-TYPED-CLAIMINFO); Review-Age-Hygiene für kanonische Architektur-/Runtime-/Runbook-Dokumente durchgeführt (DOCMETA-FRESHNESS-REVIEW-AGE-001); bleibt `partial`, da Scope bewusst klein bleibt und alle drei Claims `requires_live_check` tragen (kein Wahrheits-/Suffizienz-/Kausalitäts-/Vollständigkeitsbeweis) |
| DOCMETA-PROOF-001 | docs | Proof-Matrix-Validator-Schema vormerken | open | medium | `docs/reports/opt-arc-001-db-proof-matrix.json`, `scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py`, `scripts/docmeta/tests/test_validate_opt_arc_001_db_proof_matrix.py`, `.github/workflows/opt-arc-001-db-proof-matrix.yml` | Zweiten echten Proof-Matrix-Anwendungsfall abwarten; danach OPT-ARC-001-Pattern retrospektiv prüfen und nur bei wiederholter Struktur ein generisches Schema/Validator-Pattern ableiten |
| DB-PROOF-001 | api | Edge-Orphan- und Referenz-Audit | open | high | `apps/api/migrations/20260531000002_create_domain_edges.up.sql` (FK in Migration ausdrücklich deferred); Pendant zu `scripts/docmeta/audit_account_email_uniqueness.py` fehlt für Edges | Read-only Audit-Skript + redigierten Report bauen; valide/Orphan-Counts; Option A (FK auf `domain_nodes(id)`) vs. Option B (Guard/Quarantäne) entscheidungsfähig machen; keine Migration |
| DOMAIN-PG-002 | infra | Single-Instance-Invariante oder Multi-Instance-Kohärenz entscheiden | open | high | keine dokumentierte Betriebsentscheidung; prozesslokale Caches unadressiert | Single-Instance-Grenze ODER Cross-Instance-Kohärenz entscheiden und im Cutover-Blueprint verankern; kein stiller Cache-Split-Brain |
| AUTH-PG-001 | auth | Step-up-E-Mail-Persistenz nach PostgreSQL | open | high | `apps/api/src/routes/auth.rs` (PUT /auth/me/email vorhanden); OPT-ARC-001-Non-Goal `step_up_email_persistence` | PostgreSQL-Write-Pfad + Restart-Stabilitäts-Proof; E-Mail-Unique-Regel bleibt gewahrt (409) |
| AUTH-PG-002 | auth | WebAuthn-Credential-Persistenz / Passkey-Cutover | open | high | `apps/api/src/auth/passkeys.rs` (PasskeyStore In-Memory); OPT-ARC-001-Non-Goal `webauthn_credential_writeback` | PostgreSQL-Persistenzmodell + Restart-Proof (Register→Reload→Login); Public/Private-Trennung; menschliches Review (credentials/) |
| OPT-CI-004 | ci | Dependency-Update-Automation (Dependabot/Renovate) | open | medium | keine `.github/dependabot.yml`/Renovate-Config (Statusmatrix: `docs/reports/optimierungsstatus.md`) | Dependabot ODER Renovate konfigurieren; PR-Flut begrenzen (Limit/Gruppierung); Ökosysteme bewusst ein-/ausschließen |
| CI-TOOL-001 | ci | Dev-Setup: Task-Runner-Dedup (Makefile/Justfile) + Node/pnpm engines | open | medium | `Makefile`, `Justfile` (beide direkt `docker compose ... up/down`), `apps/web/package.json` (engines vorhanden), Root-`package.json` (engines fehlt) | Eine Compose-Ebene führt, andere delegiert; engines konsistent ergänzen; kleiner risikoarmer PR |
| DOCS-CTL-001 | docs | Orphan-Dokumente einordnen (cost-report, DEPLOY-DNS-001B) | open | medium | `docs/reports/cost-report.md`, `docs/tasks/DEPLOY-DNS-001B.md` (beide im Orphan-Generator) | Fachliche Lifecycle-Einordnung statt kosmetischer Verlinkung; alte Deploy-/DNS-Aufgabe nicht reaktivieren |
| DOCS-CTL-002 | docs | Blueprint-/Planning-Status-Konsistenz | open | medium | `docs/reports/planning-registration-findings.md`; `kartenklarheit.md`/`map-blaupause.md` sind `draft`, in `docs/index.md` aber als aktiv/normativ geführt | Betroffene Blueprints einzeln prüfen; nicht pauschal hochstufen; deprecated nicht reaktivieren; Planning-Guard bleibt grün |

## Blocker

| ID | Blocker | Fehlt | Folge |
|---|---|---|---|
| OPT-ARC-001 | Step-up-E-Mail-Persistenz und WebAuthn-User-ID-Writeback offen; Runtime-Smoke und Cutover ausstehend; JSONL-Demontage ausstehend | Offene Migrationsteile bzw. Cutover-Proof vorbereiten | JSONL bleibt Default-Lesequelle und Write-Truth bis vollständiger Cutover; POST /accounts, PATCH /nodes und POST /edges schreiben optional PostgreSQL; Schema- und Backfill-Proof sind belegt; der geänderte Read-Path-Proof-Harness wartet auf frische PR-CI-Evidence |
| DOMAIN-PG-001 | Edge-Referenz-Policy (FK oder Guard) hängt am Edge-Orphan-Audit | DB-PROOF-001 nicht abgeschlossen; FK-Entscheidung in der Edge-Schema-Migration ausdrücklich deferred | Kein FK-/Referenz-Cutover vor Audit; Orphans dürfen nicht still verworfen werden |
| AUTH-PG-003 | `webauthn_user_id`-Backfill und späteres `NOT NULL` hängen an WebAuthn-Persistenz | AUTH-PG-002 fachlich offen; kein NULL-Audit, kein Backfill-Test | Kein `NOT NULL` vor Audit + Backfill; keine stille UUID-Neuerzeugung bei Reload |

## Nächste PR-Kandidaten

| ID | PR-Schnitt | Akzeptanzkriterium |
|---|---|---|
| OPT-CON-001 | Schema-Constraints: `additionalProperties: false` alle 6 Schemas | `just contracts-domain-check` pass + kein permissives Nested-Object |
| DB-PROOF-001 | Edge-Orphan-/Referenz-Audit (read-only, keine Migration) | Reproduzierbarer redigierter Bericht: valide/Orphan-Counts + Policy-Empfehlung (Option A FK vs. Option B Guard) |
| CI-TOOL-001 | Dev-Setup: Makefile/Justfile-Dedup + Node/pnpm engines (kleiner Hygiene-PR) | Eine Compose-Ebene führt, andere delegiert; engines konsistent; JSON valide; keine Container-Starts nötig |

## Zurückgestellte / optionale Tasks

| ID | Grund | Wiederaufnahmebedingung |
|---|---|---|
| TASK-CTL-002 | GitHub Issue Forms, PR-Template und Release-Konfiguration sind aktuell nicht eingeführt, weil der Nutzen gegenüber kontextgenauen PR-Bodies nicht belegt ist. | Externe Beitragende ohne Projekteinblick werden relevant, PR-Bodies verlieren wiederholt Task-/Evidenzbezüge oder der Release-Prozess ist stabil genug für Release-Labels. |
| DOMAIN-PG-003 | Edge-Cache-Limit-Performance: kein Lastproblem und kein Cutover-Blocker nachgewiesen (TODO C1) | Erst Messpunkt/Design mit Trade-offs, dann ggf. Umbau; kein spekulativer Performance-Umbau |
| OPT-CI-003 | dtolnay/uv-Ref-Vereinheitlichung: niedrige Priorität, nicht cutover-relevant | Jederzeit als kleiner CI-Hygiene-PR möglich |
| OPT-INF-002 | SHA-Pinning der Third-Party-Actions: erst nach Update-Automation sinnvoll (TODO C3) | Nach OPT-CI-004 (Dependency-Update-Automation/Policy) |

## Erledigte Tasks

| ID | Bereich | Titel | Evidenz |
|---|---|---|---|
| TASK-CTL-001 | docs | Task-Control Phase 2 etablieren | `docs/tasks/`, `docs/reports/optimierungsstatus.json`, `scripts/docmeta/validate_task_index.py`, `scripts/docmeta/tests/test_validate_task_index.py` |
| TASK-CTL-003 | ci | Task-Index-Generator und CI-Guard | `scripts/docmeta/generate_task_index.py`, `scripts/docmeta/tests/test_generate_task_index.py`, `scripts/docmeta/agent_entrypoint_smoke.py`, `scripts/docmeta/tests/test_agent_entrypoint_smoke.py`, `.github/workflows/task-index.yml`; PR-CI-Lauf 27643872404 (PR #1209, Commit `7cb5ec3364e1f47562574ca6fc729679c5056b29`): `task-index` grün |
| DOCMETA-START-HERE-001 | docs | Start-Here Navigation und System-Map Drift Guard | `README.md`, `architecture/blueprint.docmeta-engine.md`, `scripts/docmeta/generate_system_map.py`, `Makefile` |
| DOCMETA-WARN-MODE-001 | docs | Warn-Mode stderr semantics für Docmeta-Guards schließen | `scripts/docmeta/review_impact.py`, `scripts/docmeta/check_links.py`, `scripts/docmeta/tests/test_review_impact.py`, `scripts/docmeta/tests/test_check_links.py`, `architecture/blueprint.docmeta-engine.md` |
| DOCMETA-DEPENDS-ON-CANONICAL-001 | docs | Direktes depends_on als kanonisches Docmeta-Feld durchsetzen | `contracts/docmeta.schema.json`, `scripts/docmeta/docmeta.py`, `scripts/docmeta/review_impact.py`, `architecture/docmeta.schema.md`, `architecture/blueprint.docmeta-engine.md`, `scripts/docmeta/tests/test_docmeta.py`, `scripts/docmeta/tests/test_validate_schema.py` |
| OPT-DOC-001 | docs | Incident-/DB-Recovery-Runbooks | `docs/runbooks/incident-response.md`, `docs/runbooks/db-recovery.md`; Navigation in `docs/runbooks/README.md` + `docs/index.md`; Drill-Querverweis in `docs/runbook.md` §2; Doku-Hygiene-Guards grün |
| OPT-MAP-001 | map | Basemap Runtime Proof | CI-Job `basemap-range-delivery-proof` PROVEN, Commit `14feefd6` |
| OPT-API-002 | api | Session-Persistenz PostgreSQL | `apps/api/src/auth/session_db.rs`, in CI belegt, Commit `00a43a00` |
| OPT-API-003 | api | DB-Migrationen | `apps/api/migrations/`, in CI belegt, Commit `00a43a00` |
| OPT-API-004 | api | Limit-Obergrenze `/nodes` & `/accounts` | `apps/api/src/routes/query.rs`, Tests 4+9 passed |
| OPT-FE-003 | web | Panel-Detail-Fetch-Logik extrahieren | `apps/web/src/lib/panels/panelDetails.ts`, 10+5 Tests passed |
