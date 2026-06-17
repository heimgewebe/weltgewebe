---
id: docs.generated.report-lifecycle-inventory
title: Report Lifecycle Inventory
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generiertes Inventar der Report-Lifecycle-Metadaten.
---
# Report Lifecycle Inventory

Generated automatically. Do not edit manually.
This inventory is descriptive only. Absent core lifecycle metadata is expected at this stage and is not a policy judgement.
Primary references are exact path matches in canonical documentation surfaces. Derived generated references are reported separately.

## Summary

| Metric | Count |
| --- | ---: |
| files_total | 25 |
| files_with_frontmatter | 25 |
| files_without_frontmatter | 0 |
| files_with_status | 25 |
| files_missing_status | 0 |
| files_with_lifecycle_state | 13 |
| files_missing_lifecycle_state | 12 |
| files_with_lifecycle | 13 |
| files_missing_lifecycle | 12 |
| files_with_owner_task | 13 |
| files_missing_owner_task | 12 |
| files_with_review_after | 8 |
| files_missing_review_after | 17 |
| files_primary_referenced | 22 |
| files_primary_unreferenced | 3 |
| files_with_derived_references | 25 |
| files_with_relations | 24 |
| files_with_missing_supersession_target | 0 |

## Doc Type Distribution

| doc_type | Count |
| --- | ---: |
| documentation | 1 |
| reference | 2 |
| report | 20 |
| status-matrix | 2 |

## Reports

| Path | doc_type | status | lifecycle_state | lifecycle | owner_task | review_after | superseded_by | primary refs | derived refs | relations | absent core lifecycle fields | supersession target diagnostic |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| docs/reports/agent-readiness-audit.md | documentation | active |  |  |  |  |  | 2 | 4 | 1 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/auth-persistence-direct-proof-diagnose-audit.md | report | deprecated | superseded | audit | OPT-API-002 |  | docs/reports/optimierungsstatus.md | 0 | 4 | 4 | review_after |  |
| docs/reports/auth-persistence-next-step.md | report | deprecated | superseded | decision-prep | OPT-API-002 |  | docs/reports/optimierungsstatus.md | 6 | 5 | 4 | review_after |  |
| docs/reports/auth-persistence-readiness.md | report | deprecated | superseded | decision-prep | OPT-API-002 |  | docs/reports/auth-persistence-next-step.md | 4 | 5 | 3 | review_after |  |
| docs/reports/auth-persistence-runtime-proof.md | report | deprecated | superseded | proof | OPT-API-002 |  | docs/reports/optimierungsstatus.md | 4 | 4 | 6 | review_after |  |
| docs/reports/auth-persistence-runtime-target-reconciliation.md | report | active | active | decision-prep | OPT-API-002 | 2026-07-17 |  | 1 | 4 | 5 |  |  |
| docs/reports/auth-status-matrix.md | reference | active |  |  |  |  |  | 5 | 4 | 3 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/cost-report.md | reference | active |  |  |  |  |  | 1 | 4 | 0 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/domain-account-email-uniqueness-audit.md | report | active | active | audit | OPT-ARC-001 | 2026-07-13 |  | 2 | 4 | 4 |  |  |
| docs/reports/domain-account-write-path-proof.md | report | active | active | proof | OPT-ARC-001 | 2026-07-16 |  | 7 | 4 | 6 |  |  |
| docs/reports/domain-backfill-proof.md | report | active | active | proof | OPT-ARC-001 | 2026-07-16 |  | 3 | 4 | 4 |  |  |
| docs/reports/domain-edge-create-semantics-preflight.md | report | deprecated | superseded | decision-prep | OPT-ARC-001 |  | docs/reports/domain-edge-write-path-proof.md | 1 | 5 | 7 | review_after |  |
| docs/reports/domain-edge-reference-audit.md | report | active | active | audit | OPT-ARC-001 | 2026-07-16 |  | 0 | 3 | 6 |  |  |
| docs/reports/domain-edge-write-path-proof.md | report | active | active | proof | OPT-ARC-001 | 2026-07-16 |  | 3 | 6 | 8 |  |  |
| docs/reports/domain-node-write-path-proof.md | report | active | active | proof | OPT-ARC-001 | 2026-07-16 |  | 5 | 4 | 6 |  |  |
| docs/reports/domain-provider-role-finding.md | report | active |  |  |  |  |  | 1 | 4 | 3 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/domain-read-path-proof.md | report | active | active | proof | OPT-ARC-001 | 2026-07-16 |  | 5 | 4 | 5 |  |  |
| docs/reports/inwx-zone-reconciliation-plan.md | report | active |  |  |  |  |  | 1 | 4 | 4 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/map-architekturkritik.md | report | active |  |  |  |  |  | 4 | 5 | 2 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/map-basemap-proof-gap-reconciliation.md | report | active |  |  |  |  |  | 2 | 3 | 6 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/map-status-matrix.md | status-matrix | active |  |  |  |  |  | 8 | 5 | 3 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/optimierungsbericht.md | report | active |  |  |  |  |  | 2 | 4 | 4 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/optimierungsstatus.md | status-matrix | active |  |  |  |  |  | 19 | 5 | 4 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/passkey-register-verify-prep.md | report | active |  |  |  |  |  | 0 | 4 | 4 | lifecycle, owner_task, review_after, lifecycle_state |  |
| docs/reports/planning-registration-findings.md | report | active |  |  |  |  |  | 1 | 4 | 2 | lifecycle, owner_task, review_after, lifecycle_state |  |

## Absent Core Lifecycle Metadata

| Path | Absent fields |
| --- | --- |
| docs/reports/agent-readiness-audit.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/auth-persistence-direct-proof-diagnose-audit.md | review_after |
| docs/reports/auth-persistence-next-step.md | review_after |
| docs/reports/auth-persistence-readiness.md | review_after |
| docs/reports/auth-persistence-runtime-proof.md | review_after |
| docs/reports/auth-status-matrix.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/cost-report.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/domain-edge-create-semantics-preflight.md | review_after |
| docs/reports/domain-provider-role-finding.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/inwx-zone-reconciliation-plan.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/map-architekturkritik.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/map-basemap-proof-gap-reconciliation.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/map-status-matrix.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/optimierungsbericht.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/optimierungsstatus.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/passkey-register-verify-prep.md | lifecycle, owner_task, review_after, lifecycle_state |
| docs/reports/planning-registration-findings.md | lifecycle, owner_task, review_after, lifecycle_state |

## Relations

| Path | Count | Types | Targets |
| --- | ---: | --- | --- |
| docs/reports/agent-readiness-audit.md | 1 | relates_to | docs/policies/agent-reading-protocol.md |
| docs/reports/auth-persistence-direct-proof-diagnose-audit.md | 4 | relates_to | docs/adr/ADR-0007__auth-persistence-production-db-path.md, docs/proofs/sqlx-postgres-direct-session-crud-proof.md, docs/reports/auth-persistence-next-step.md, docs/reports/auth-persistence-readiness.md |
| docs/reports/auth-persistence-next-step.md | 4 | relates_to, supersedes | docs/adr/ADR-0006__auth-magic-link-session-passkey.md, docs/blueprints/auth-roadmap.md, docs/reports/auth-persistence-readiness.md, docs/specs/auth-api.md |
| docs/reports/auth-persistence-readiness.md | 3 | relates_to | docs/adr/ADR-0006__auth-magic-link-session-passkey.md, docs/blueprints/auth-roadmap.md, docs/specs/auth-api.md |
| docs/reports/auth-persistence-runtime-proof.md | 6 | relates_to | docs/adr/ADR-0006__auth-magic-link-session-passkey.md, docs/adr/ADR-0007__auth-persistence-production-db-path.md, docs/blueprints/auth-persistence-runtime-proof.md, docs/blueprints/auth-roadmap.md, docs/proofs/sqlx-postgres-direct-session-crud-proof.md, docs/reports/auth-persistence-next-step.md |
| docs/reports/auth-persistence-runtime-target-reconciliation.md | 5 | relates_to | docs/adr/ADR-0007__auth-persistence-production-db-path.md, docs/blueprints/auth-persistence-runtime-proof.md, docs/proofs/sqlx-pgbouncer-session-crud-proof.md, docs/reports/auth-persistence-runtime-proof.md, docs/roadmap.md |
| docs/reports/auth-status-matrix.md | 3 | relates_to | docs/adr/ADR-0006__auth-magic-link-session-passkey.md, docs/adr/ADR-0007__auth-persistence-production-db-path.md, docs/blueprints/auth-roadmap.md |
| docs/reports/domain-account-email-uniqueness-audit.md | 4 | relates_to | apps/api/src/auth/accounts.rs, apps/api/src/routes/accounts.rs, docs/blueprints/domain-data-postgres-cutover.md, scripts/docmeta/audit_account_email_uniqueness.py |
| docs/reports/domain-account-write-path-proof.md | 6 | relates_to | .github/workflows/api.yml, apps/api/tests/db_domain_account_write_path.rs, docs/blueprints/domain-data-postgres-cutover.md, docs/reports/domain-read-path-proof.md, docs/reports/optimierungsstatus.md, docs/tasks/board.md |
| docs/reports/domain-backfill-proof.md | 4 | relates_to | .github/workflows/api.yml, apps/api/tests/db_domain_backfill.rs, docs/blueprints/domain-data-postgres-cutover.md, docs/tasks/index.json |
| docs/reports/domain-edge-create-semantics-preflight.md | 7 | relates_to | contracts/domain/edge.schema.json, docs/blueprints/domain-data-postgres-cutover.md, docs/reports/domain-account-write-path-proof.md, docs/reports/domain-node-write-path-proof.md, docs/reports/opt-arc-001-db-proof-matrix.json, docs/tasks/board.md, docs/tasks/index.json |
| docs/reports/domain-edge-reference-audit.md | 6 | relates_to | apps/api/migrations/20260531000002_create_domain_edges.up.sql, contracts/domain/edge.schema.json, docs/blueprints/domain-data-postgres-cutover.md, docs/reports/opt-arc-001-db-proof-matrix.json, docs/tasks/board.md, scripts/docmeta/audit_domain_edge_references.py |
| docs/reports/domain-edge-write-path-proof.md | 8 | relates_to, supersedes | docs/blueprints/domain-data-postgres-cutover.md, docs/reports/domain-account-write-path-proof.md, docs/reports/domain-edge-create-semantics-preflight.md, docs/reports/domain-node-write-path-proof.md, docs/reports/domain-read-path-proof.md, docs/reports/optimierungsstatus.md, docs/tasks/board.md, docs/tasks/index.json |
| docs/reports/domain-node-write-path-proof.md | 6 | relates_to | docs/blueprints/domain-data-postgres-cutover.md, docs/reports/domain-account-write-path-proof.md, docs/reports/domain-read-path-proof.md, docs/reports/optimierungsstatus.md, docs/tasks/board.md, docs/tasks/index.json |
| docs/reports/domain-provider-role-finding.md | 3 | relates_to | docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md, docs/runbooks/domain-mail-cutover.md, docs/tasks/board.md |
| docs/reports/domain-read-path-proof.md | 5 | relates_to | docs/blueprints/domain-data-postgres-cutover.md, docs/reports/domain-account-write-path-proof.md, docs/reports/domain-backfill-proof.md, docs/reports/optimierungsstatus.md, docs/tasks/board.md |
| docs/reports/inwx-zone-reconciliation-plan.md | 4 | relates_to | docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md, docs/reports/domain-provider-role-finding.md, docs/runbooks/domain-mail-cutover.md, docs/tasks/board.md |
| docs/reports/map-architekturkritik.md | 2 | relates_to | docs/blueprints/kartenklarheit-roadmap.md, docs/reports/map-status-matrix.md |
| docs/reports/map-basemap-proof-gap-reconciliation.md | 6 | relates_to | .github/workflows/basemap-runtime-proof.yml, docs/blueprints/kartenklarheit-phase6.md, docs/blueprints/kartenklarheit-roadmap.md, docs/proofs/basemap-hamburg-artifact-proof.md, docs/reports/map-status-matrix.md, scripts/guard/basemap-runtime-proof.sh |
| docs/reports/map-status-matrix.md | 3 | relates_to | docs/blueprints/kartenklarheit-roadmap.md, docs/blueprints/ui-interaction-doctrine.md, docs/reports/map-architekturkritik.md |
| docs/reports/optimierungsbericht.md | 4 | relates_to | docs/datenmodell.md, docs/policies/agent-reading-protocol.md, docs/reports/optimierungsstatus.md, docs/techstack.md |
| docs/reports/optimierungsstatus.md | 4 | depends_on, relates_to | docs/policies/agent-reading-protocol.md, docs/reports/auth-persistence-readiness.md, docs/reports/domain-read-path-proof.md, docs/reports/optimierungsbericht.md |
| docs/reports/passkey-register-verify-prep.md | 4 | relates_to | docs/adr/ADR-0006__auth-magic-link-session-passkey.md, docs/blueprints/auth-roadmap.md, docs/reports/auth-status-matrix.md, docs/specs/auth-api.md |
| docs/reports/planning-registration-findings.md | 2 | relates_to | docs/tasks/index.json, scripts/docmeta/check_planning_registration.py |

## Primary Referenced Reports

- `docs/reports/agent-readiness-audit.md`
  - `docs/blueprints/agent-operability-blaupause.md`
  - `docs/blueprints/blueprint-agent-safety-control-layer.md`

- `docs/reports/auth-persistence-next-step.md`
  - `docs/blueprints/auth-persistence-runtime-proof.md`
  - `docs/proofs/sqlx-pgbouncer-session-crud-proof.md`
  - `docs/reports/auth-persistence-direct-proof-diagnose-audit.md`
  - `docs/reports/auth-persistence-readiness.md`
  - `docs/reports/auth-persistence-runtime-proof.md`
  - `docs/reports/passkey-register-verify-prep.md`

- `docs/reports/auth-persistence-readiness.md`
  - `docs/blueprints/auth-persistence-runtime-proof.md`
  - `docs/reports/auth-persistence-direct-proof-diagnose-audit.md`
  - `docs/reports/auth-persistence-next-step.md`
  - `docs/reports/optimierungsstatus.md`

- `docs/reports/auth-persistence-runtime-proof.md`
  - `docs/adr/ADR-0007__auth-persistence-production-db-path.md`
  - `docs/proofs/sqlx-pgbouncer-session-crud-proof.md`
  - `docs/proofs/sqlx-postgres-direct-session-crud-proof.md`
  - `docs/reports/auth-persistence-runtime-target-reconciliation.md`

- `docs/reports/auth-persistence-runtime-target-reconciliation.md`
  - `docs/adr/ADR-0007__auth-persistence-production-db-path.md`

- `docs/reports/auth-status-matrix.md`
  - `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
  - `docs/blueprints/auth-roadmap.md`
  - `docs/reports/optimierungsstatus.md`
  - `docs/reports/passkey-register-verify-prep.md`
  - `docs/roadmap.md`

- `docs/reports/cost-report.md`
  - `docs/tasks/board.md`

- `docs/reports/domain-account-email-uniqueness-audit.md`
  - `docs/reports/domain-backfill-proof.md`
  - `docs/tasks/board.md`

- `docs/reports/domain-account-write-path-proof.md`
  - `docs/blueprints/domain-data-postgres-cutover.md`
  - `docs/reports/domain-edge-create-semantics-preflight.md`
  - `docs/reports/domain-edge-write-path-proof.md`
  - `docs/reports/domain-node-write-path-proof.md`
  - `docs/reports/domain-read-path-proof.md`
  - `docs/reports/optimierungsstatus.md`
  - `docs/tasks/board.md`

- `docs/reports/domain-backfill-proof.md`
  - `docs/reports/domain-read-path-proof.md`
  - `docs/reports/optimierungsstatus.md`
  - `docs/tasks/board.md`

- `docs/reports/domain-edge-create-semantics-preflight.md`
  - `docs/reports/domain-edge-write-path-proof.md`

- `docs/reports/domain-edge-write-path-proof.md`
  - `docs/reports/domain-edge-create-semantics-preflight.md`
  - `docs/reports/optimierungsstatus.md`
  - `docs/tasks/board.md`

- `docs/reports/domain-node-write-path-proof.md`
  - `docs/blueprints/domain-data-postgres-cutover.md`
  - `docs/reports/domain-edge-create-semantics-preflight.md`
  - `docs/reports/domain-edge-write-path-proof.md`
  - `docs/reports/optimierungsstatus.md`
  - `docs/tasks/board.md`

- `docs/reports/domain-provider-role-finding.md`
  - `docs/reports/inwx-zone-reconciliation-plan.md`

- `docs/reports/domain-read-path-proof.md`
  - `docs/reports/domain-account-write-path-proof.md`
  - `docs/reports/domain-edge-write-path-proof.md`
  - `docs/reports/domain-node-write-path-proof.md`
  - `docs/reports/optimierungsstatus.md`
  - `docs/tasks/board.md`

- `docs/reports/inwx-zone-reconciliation-plan.md`
  - `docs/tasks/board.md`

- `docs/reports/map-architekturkritik.md`
  - `docs/blueprints/kartenklarheit-phase6.md`
  - `docs/blueprints/kartenklarheit-roadmap.md`
  - `docs/blueprints/kartenklarheit.md`
  - `docs/reports/map-status-matrix.md`

- `docs/reports/map-basemap-proof-gap-reconciliation.md`
  - `docs/blueprints/kartenklarheit-roadmap.md`
  - `docs/reports/map-status-matrix.md`

- `docs/reports/map-status-matrix.md`
  - `docs/blueprints/kartenklarheit-phase6.md`
  - `docs/blueprints/kartenklarheit-roadmap.md`
  - `docs/blueprints/kartenklarheit.md`
  - `docs/blueprints/map-roadmap.md`
  - `docs/blueprints/ui-interaction-doctrine.md`
  - `docs/reports/map-architekturkritik.md`
  - `docs/reports/map-basemap-proof-gap-reconciliation.md`
  - `docs/roadmap.md`

- `docs/reports/optimierungsbericht.md`
  - `docs/blueprints/domain-data-postgres-cutover.md`
  - `docs/reports/optimierungsstatus.md`

- `docs/reports/optimierungsstatus.md`
  - `docs/blueprints/auth-persistence-runtime-proof.md`
  - `docs/blueprints/doc-structure-task-control-examples.md`
  - `docs/blueprints/doc-structure-task-control-roadmap.md`
  - `docs/blueprints/doc-structure-task-control.md`
  - `docs/blueprints/domain-data-postgres-cutover.md`
  - `docs/reports/auth-persistence-direct-proof-diagnose-audit.md`
  - `docs/reports/auth-persistence-next-step.md`
  - `docs/reports/auth-persistence-readiness.md`
  - `docs/reports/auth-persistence-runtime-proof.md`
  - `docs/reports/domain-account-write-path-proof.md`
  - `docs/reports/domain-edge-create-semantics-preflight.md`
  - `docs/reports/domain-edge-write-path-proof.md`
  - `docs/reports/domain-node-write-path-proof.md`
  - `docs/reports/domain-read-path-proof.md`
  - `docs/reports/optimierungsbericht.md`
  - `docs/roadmap.md`
  - `docs/specs/list-pagination-api.md`
  - `docs/tasks/README.md`
  - `docs/tasks/board.md`

- `docs/reports/planning-registration-findings.md`
  - `docs/tasks/board.md`

## Derived Referenced Reports

- `docs/reports/agent-readiness-audit.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/auth-persistence-direct-proof-diagnose-audit.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/auth-persistence-next-step.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`
  - `docs/_generated/supersession-map.md`

- `docs/reports/auth-persistence-readiness.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`
  - `docs/_generated/supersession-map.md`

- `docs/reports/auth-persistence-runtime-proof.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/auth-persistence-runtime-target-reconciliation.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/auth-status-matrix.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/cost-report.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/orphans.md`
  - `docs/_generated/relations-analysis.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/domain-account-email-uniqueness-audit.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/domain-account-write-path-proof.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/domain-backfill-proof.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/domain-edge-create-semantics-preflight.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`
  - `docs/_generated/supersession-map.md`

- `docs/reports/domain-edge-reference-audit.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/domain-edge-write-path-proof.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/relations-analysis.md`
  - `docs/_generated/report-lifecycle.md`
  - `docs/_generated/supersession-map.md`

- `docs/reports/domain-node-write-path-proof.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/domain-provider-role-finding.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/domain-read-path-proof.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/inwx-zone-reconciliation-plan.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/map-architekturkritik.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/impl-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/map-basemap-proof-gap-reconciliation.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/map-status-matrix.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/impl-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/optimierungsbericht.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/optimierungsstatus.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/relations-analysis.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/passkey-register-verify-prep.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

- `docs/reports/planning-registration-findings.md`
  - `docs/_generated/backlinks.md`
  - `docs/_generated/doc-index.md`
  - `docs/_generated/relates-to-audit.md`
  - `docs/_generated/report-lifecycle.md`

## Primary Unreferenced Reports

- `docs/reports/auth-persistence-direct-proof-diagnose-audit.md`
- `docs/reports/domain-edge-reference-audit.md`
- `docs/reports/passkey-register-verify-prep.md`

## Supersession Target Diagnostics

None.

## Parse Warnings

None.
