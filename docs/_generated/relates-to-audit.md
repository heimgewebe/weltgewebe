---
id: docs.generated.relates-to-audit
title: Relates-To Audit
doc_type: generated
status: active
summary: Strukturelle Beobachtung der relates_to-Nutzung — Typen, Cluster, Beispiele.
---

## Weltgewebe Relates-To Audit

Generated automatically. Do not edit.

### Zusammenfassung

| Metrik | Wert |
| --- | --- |
| Relationen gesamt | 422 |
| — depends_on | 18 |
| — relates_to | 401 |
| — supersedes | 3 |
| relates_to Anteil | 95% |

### Mögliche supersedes-Lücken

> Dokument-Paare mit namensähnlichen Mustern, die möglicherweise eine supersedes-Relation benötigen.

_Keine Lücken erkannt._

### Cluster-Analyse (relates_to)

> Zusammenhängende Gruppen im relates_to-Graphen.

**Cluster 1** (153 Dokumente):

- `.github/workflows/api.yml`
- `.github/workflows/basemap-runtime-proof.yml`
- `AGENTS.md`
- `agent-policy.yaml`
- `apps/api/migrations/20260531000002_create_domain_edges.up.sql`
- `apps/api/src/auth/accounts.rs`
- `apps/api/src/routes/accounts.rs`
- `apps/api/src/routes/edges.rs`
- `apps/api/src/routes/nodes.rs`
- `apps/api/src/state.rs`
- `apps/api/tests/db_domain_account_write_path.rs`
- `apps/api/tests/db_domain_backfill.rs`
- `audit/impl-registry.yaml`
- `contracts/domain/edge.schema.json`
- `docs/_generated/report-lifecycle-inventory.md`
- `docs/adr/0043-edge-vs-conversation.md`
- `docs/adr/ADR-0001__clean-slate-docs-monorepo.md`
- `docs/adr/ADR-0002__reentry-kriterien.md`
- `docs/adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md`
- `docs/adr/ADR-0004__fahrplan-verweis.md`
- `docs/adr/ADR-0005-auth.md`
- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
- `docs/adr/ADR-0007__auth-persistence-production-db-path.md`
- `docs/adr/ADR-0008__domain-mail-provider-boundaries.md`
- `docs/architekturstruktur.md`
- `docs/blueprints/agent-operability-blaupause.md`
- `docs/blueprints/auth-persistence-runtime-proof.md`
- `docs/blueprints/auth-roadmap.md`
- `docs/blueprints/blueprint-agent-safety-control-layer.md`
- `docs/blueprints/doc-structure-task-control-examples.md`
- `docs/blueprints/doc-structure-task-control-roadmap.md`
- `docs/blueprints/doc-structure-task-control.md`
- `docs/blueprints/domain-data-postgres-cutover.md`
- `docs/blueprints/kartenklarheit-phase6.md`
- `docs/blueprints/kartenklarheit-roadmap.md`
- `docs/blueprints/kartenklarheit.md`
- `docs/blueprints/map-blaupause.md`
- `docs/blueprints/map-roadmap.md`
- `docs/blueprints/ui-blaupause.md`
- `docs/blueprints/ui-interaction-doctrine.md`
- `docs/blueprints/ui-roadmap.md`
- `docs/blueprints/ui-state-machine.md`
- `docs/blueprints/versionierungs-blaupause.md`
- `docs/blueprints/versionierungs-statusgrundlage.md`
- `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
- `docs/blueprints/weltgewebe.config.diff.md`
- `docs/blueprints/weltgewebe.deploy.plan.md`
- `docs/claims/README.md`
- `docs/datenmodell.md`
- `docs/deploy/CHANGELOG.md`
- `docs/deploy/DRIFT_POLICY.md`
- `docs/deploy/README.md`
- `docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md`
- `docs/deploy/heim-first-phase0.md`
- `docs/deploy/heimserver.deployment.md`
- `docs/deploy/heimserver.integration.md`
- `docs/deploy/public-app-base-url.md`
- `docs/deploy/secondary-domain-web-surfaces.md`
- `docs/deploy/security.md`
- `docs/deploy/vps.md`
- `docs/deploy/weltgewebe.naming.md`
- `docs/deployment.md`
- `docs/deployment_governance.md`
- `docs/dev/codespaces.md`
- `docs/domain/modules.md`
- `docs/domain/vocabulary.md`
- `docs/edge/systemd/README.md`
- `docs/geist-und-plan.md`
- `docs/inhalt.md`
- `docs/konzepte/garnrolle-und-verortung.md`
- `docs/konzepte/garnrolle.md`
- `docs/overview/inhalt.md`
- `docs/overview/zusammenstellung.md`
- `docs/policies/agent-reading-protocol.md`
- `docs/policies/architecture-critique.md`
- `docs/policies/orientierung.md`
- `docs/process/README.md`
- `docs/process/bash-tooling-guidelines.md`
- `docs/process/fahrplan.md`
- `docs/process/report-lifecycle-contract-alignment.md`
- `docs/process/report-lifecycle.md`
- `docs/process/sprache.md`
- `docs/proofs/basemap-hamburg-artifact-proof.md`
- `docs/proofs/sqlx-pgbouncer-session-crud-proof.md`
- `docs/proofs/sqlx-postgres-direct-session-crud-proof.md`
- `docs/quickstart-gate-c.md`
- `docs/reference/glossar.md`
- `docs/reports/agent-readiness-audit.md`
- `docs/reports/auth-persistence-direct-proof-diagnose-audit.md`
- `docs/reports/auth-persistence-next-step.md`
- `docs/reports/auth-persistence-readiness.md`
- `docs/reports/auth-persistence-runtime-proof.md`
- `docs/reports/auth-persistence-runtime-target-reconciliation.md`
- `docs/reports/auth-status-matrix.md`
- `docs/reports/domain-account-email-uniqueness-audit.md`
- `docs/reports/domain-account-write-path-proof.md`
- `docs/reports/domain-backfill-proof.md`
- `docs/reports/domain-edge-create-semantics-preflight.md`
- `docs/reports/domain-edge-reference-audit.md`
- `docs/reports/domain-edge-write-path-proof.md`
- `docs/reports/domain-node-write-path-proof.md`
- `docs/reports/domain-postgres-instance-coherence-decision.md`
- `docs/reports/domain-provider-role-finding.md`
- `docs/reports/domain-read-path-proof.md`
- `docs/reports/domain-runtime-data-source-reconciliation.md`
- `docs/reports/inwx-zone-reconciliation-plan.md`
- `docs/reports/map-architekturkritik.md`
- `docs/reports/map-basemap-proof-gap-reconciliation.md`
- `docs/reports/map-status-matrix.md`
- `docs/reports/opt-arc-001-db-proof-matrix.json`
- `docs/reports/optimierungsbericht.md`
- `docs/reports/optimierungsstatus.md`
- `docs/reports/passkey-register-verify-prep.md`
- `docs/reports/planning-registration-findings.md`
- `docs/reports/report-lifecycle-restbestand-triage.md`
- `docs/roadmap.md`
- `docs/runbook.md`
- `docs/runbook.observability.md`
- `docs/runbooks/README.md`
- `docs/runbooks/codespaces-recovery.md`
- `docs/runbooks/db-recovery.md`
- `docs/runbooks/domain-mail-cutover.md`
- `docs/runbooks/incident-response.md`
- `docs/runbooks/ops.runbook.weltgewebe-selfhost-deploy.md`
- `docs/runbooks/uv-tooling.md`
- `docs/security/agent-write-scope-baseline.md`
- `docs/specs/auth-api.md`
- `docs/specs/auth-blueprint.md`
- `docs/specs/auth-state-machine.md`
- `docs/specs/auth-ui.md`
- `docs/specs/contract.md`
- `docs/specs/list-pagination-api.md`
- `docs/specs/privacy-api.md`
- `docs/specs/privacy-ui.md`
- `docs/tasks/DEPLOY-DNS-001B.md`
- `docs/tasks/README.md`
- `docs/tasks/board.md`
- `docs/tasks/index.json`
- `docs/techstack.md`
- `docs/vision.md`
- `docs/weltgewebe-agenten-manifest.md`
- `docs/zusammenstellung.md`
- `infra/compose/compose.prod.override.yml`
- `repo.meta.yaml`
- `scripts/basemap/build-hamburg-pmtiles.sh`
- `scripts/docmeta/audit_account_email_uniqueness.py`
- `scripts/docmeta/audit_domain_edge_references.py`
- `scripts/docmeta/check_planning_registration.py`
- `scripts/docmeta/validate_claim_registry.py`
- `scripts/docmeta/validate_report_lifecycle.py`
- `scripts/guard/basemap-runtime-proof.sh`
- `scripts/guard/domain-single-instance-guard.sh`
- `scripts/tests/test_domain_single_instance_guard.sh`

**Cluster 2** (4 Dokumente):

- `.github/workflows/cost-report.yml`
- `docs/reports/cost-report.md`
- `tools/py/cost/model.csv`
- `tools/py/cost/report.py`

**Cluster 3** (4 Dokumente):

- `contracts/agent/task.schema.json`
- `docs/reference/agent-operability-fixture-matrix.md`
- `scripts/agent/check_non_ideal_task.py`
- `scripts/agent/tests/test_check_non_ideal_task.py`

**Cluster 4** (3 Dokumente):

- `docs/adr/0042-consume-semantah-contracts.md`
- `docs/x-repo/peers-learnings.md`
- `docs/x-repo/semantAH.md`

### Konkrete Beispiele zur Prüfung

> Dokumente mit den meisten relates_to-Zielen und ihren konkreten Relationen.

**`docs/blueprints/domain-data-postgres-cutover.md`**:

- relates_to → `apps/api/src/routes/accounts.rs`
- relates_to → `apps/api/src/routes/edges.rs`
- relates_to → `apps/api/src/routes/nodes.rs`
- relates_to → `apps/api/src/state.rs`
- relates_to → `docs/reports/domain-account-write-path-proof.md`
- relates_to → `docs/reports/domain-node-write-path-proof.md`
- relates_to → `docs/reports/domain-postgres-instance-coherence-decision.md`
- relates_to → `docs/reports/optimierungsbericht.md`
- relates_to → `docs/reports/optimierungsstatus.md`
- relates_to → `docs/specs/contract.md`
- relates_to → `docs/specs/list-pagination-api.md`
- relates_to → `docs/tasks/board.md`
- relates_to → `docs/tasks/index.json`

**`docs/blueprints/blueprint-agent-safety-control-layer.md`**:

- relates_to → `AGENTS.md`
- relates_to → `agent-policy.yaml`
- relates_to → `audit/impl-registry.yaml`
- relates_to → `docs/blueprints/agent-operability-blaupause.md`
- relates_to → `docs/policies/agent-reading-protocol.md`
- relates_to → `docs/reports/agent-readiness-audit.md`
- relates_to → `docs/roadmap.md`
- relates_to → `docs/tasks/index.json`
- relates_to → `repo.meta.yaml`

**`docs/deploy/README.md`**:

- relates_to → `docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md`
- relates_to → `docs/deploy/heimserver.deployment.md`
- relates_to → `docs/deploy/heimserver.integration.md`
- relates_to → `docs/deploy/secondary-domain-web-surfaces.md`
- relates_to → `docs/deploy/security.md`
- relates_to → `docs/deployment.md`
- relates_to → `docs/deployment_governance.md`

### Hinweise

- Alle Ergebnisse dienen der strukturellen Sichtbarmachung.
- `relates_to` ist kein Fehler — die Verteilung zeigt den aktuellen Stand.
- Keine automatischen Korrekturen werden vorgenommen.
