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
| Relationen gesamt | 197 |
| — depends_on | 1 |
| — relates_to | 194 |
| — supersedes | 1 |
| — updates | 1 |
| relates_to Anteil | 98% |

### Mögliche supersedes-Lücken

> Dokument-Paare mit namensähnlichen Mustern, die möglicherweise eine supersedes-Relation benötigen.

_Keine Lücken erkannt._

### Cluster-Analyse (relates_to)

> Zusammenhängende Gruppen im relates_to-Graphen.

**Cluster 1** (84 Dokumente):

- `AGENTS.md`
- `agent-policy.yaml`
- `docs/adr/0043-edge-vs-conversation.md`
- `docs/adr/ADR-0001__clean-slate-docs-monorepo.md`
- `docs/adr/ADR-0002__reentry-kriterien.md`
- `docs/adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md`
- `docs/adr/ADR-0004__fahrplan-verweis.md`
- `docs/adr/ADR-0005-auth.md`
- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
- `docs/architekturstruktur.md`
- `docs/blueprints/agent-operability-blaupause.md`
- `docs/blueprints/auth-persistence-runtime-proof.md`
- `docs/blueprints/auth-roadmap.md`
- `docs/blueprints/kartenklarheit-phase6.md`
- `docs/blueprints/kartenklarheit-roadmap.md`
- `docs/blueprints/kartenklarheit.md`
- `docs/blueprints/map-blaupause.md`
- `docs/blueprints/map-roadmap.md`
- `docs/blueprints/ui-blaupause.md`
- `docs/blueprints/ui-roadmap.md`
- `docs/blueprints/ui-state-machine.md`
- `docs/blueprints/versionierungs-blaupause.md`
- `docs/blueprints/versionierungs-statusgrundlage.md`
- `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
- `docs/blueprints/weltgewebe.config.diff.md`
- `docs/blueprints/weltgewebe.deploy.plan.md`
- `docs/datenmodell.md`
- `docs/deploy/CHANGELOG.md`
- `docs/deploy/DRIFT_POLICY.md`
- `docs/deploy/README.md`
- `docs/deploy/heim-first-phase0.md`
- `docs/deploy/heimserver.deployment.md`
- `docs/deploy/heimserver.integration.md`
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
- `docs/process/sprache.md`
- `docs/quickstart-gate-c.md`
- `docs/reference/glossar.md`
- `docs/reports/agent-readiness-audit.md`
- `docs/reports/auth-persistence-next-step.md`
- `docs/reports/auth-persistence-readiness.md`
- `docs/reports/auth-status-matrix.md`
- `docs/reports/map-architekturkritik.md`
- `docs/reports/map-status-matrix.md`
- `docs/reports/optimierungsbericht.md`
- `docs/reports/optimierungsstatus.md`
- `docs/roadmap.md`
- `docs/runbook.md`
- `docs/runbook.observability.md`
- `docs/runbooks/README.md`
- `docs/runbooks/codespaces-recovery.md`
- `docs/runbooks/ops.runbook.weltgewebe-selfhost-deploy.md`
- `docs/runbooks/uv-tooling.md`
- `docs/specs/auth-api.md`
- `docs/specs/auth-blueprint.md`
- `docs/specs/auth-state-machine.md`
- `docs/specs/auth-ui.md`
- `docs/specs/contract.md`
- `docs/specs/privacy-api.md`
- `docs/specs/privacy-ui.md`
- `docs/techstack.md`
- `docs/vision.md`
- `docs/weltgewebe-agenten-manifest.md`
- `docs/zusammenstellung.md`
- `repo.meta.yaml`

**Cluster 2** (3 Dokumente):

- `docs/adr/0042-consume-semantah-contracts.md`
- `docs/x-repo/peers-learnings.md`
- `docs/x-repo/semantAH.md`

### Konkrete Beispiele zur Prüfung

> Dokumente mit den meisten relates_to-Zielen und ihren konkreten Relationen.

**`docs/roadmap.md`**:

- relates_to → `docs/blueprints/agent-operability-blaupause.md`
- relates_to → `docs/blueprints/auth-persistence-runtime-proof.md`
- relates_to → `docs/blueprints/auth-roadmap.md`
- relates_to → `docs/blueprints/kartenklarheit-phase6.md`
- relates_to → `docs/blueprints/kartenklarheit-roadmap.md`
- relates_to → `docs/blueprints/map-roadmap.md`
- relates_to → `docs/blueprints/ui-roadmap.md`
- relates_to → `docs/blueprints/versionierungs-blaupause.md`
- relates_to → `docs/process/fahrplan.md`
- relates_to → `docs/reports/auth-status-matrix.md`
- relates_to → `docs/reports/map-status-matrix.md`
- relates_to → `docs/reports/optimierungsstatus.md`

**`docs/blueprints/auth-persistence-runtime-proof.md`**:

- relates_to → `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
- relates_to → `docs/blueprints/auth-roadmap.md`
- relates_to → `docs/reports/auth-persistence-next-step.md`
- relates_to → `docs/reports/auth-persistence-readiness.md`
- relates_to → `docs/specs/auth-api.md`

**`docs/deploy/README.md`**:

- relates_to → `docs/deploy/heimserver.deployment.md`
- relates_to → `docs/deploy/heimserver.integration.md`
- relates_to → `docs/deploy/security.md`
- relates_to → `docs/deployment.md`
- relates_to → `docs/deployment_governance.md`

### Hinweise

- Alle Ergebnisse dienen der strukturellen Sichtbarmachung.
- `relates_to` ist kein Fehler — die Verteilung zeigt den aktuellen Stand.
- Keine automatischen Korrekturen werden vorgenommen.
