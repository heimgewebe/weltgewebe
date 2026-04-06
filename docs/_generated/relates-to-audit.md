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
| Relationen gesamt | 148 |
| — relates_to | 147 |
| — supersedes | 1 |
| relates_to Anteil | 99% |

### Mögliche supersedes-Lücken

> Dokument-Paare mit namensähnlichen Mustern, die möglicherweise eine supersedes-Relation benötigen.

_Keine Lücken erkannt._

### Cluster-Analyse (relates_to)

> Zusammenhängende Gruppen im relates_to-Graphen.

**Cluster 1** (30 Dokumente):

- `docs/adr/ADR-0002__reentry-kriterien.md`
- `docs/adr/ADR-0004__fahrplan-verweis.md`
- `docs/blueprints/versionierungs-blaupause.md`
- `docs/blueprints/versionierungs-statusgrundlage.md`
- `docs/blueprints/weltgewebe.config.diff.md`
- `docs/blueprints/weltgewebe.deploy.plan.md`
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
- `docs/edge/systemd/README.md`
- `docs/process/README.md`
- `docs/process/bash-tooling-guidelines.md`
- `docs/process/fahrplan.md`
- `docs/process/sprache.md`
- `docs/quickstart-gate-c.md`
- `docs/runbook.md`
- `docs/runbook.observability.md`
- `docs/runbooks/README.md`
- `docs/runbooks/codespaces-recovery.md`
- `docs/runbooks/ops.runbook.weltgewebe-selfhost-deploy.md`
- `docs/runbooks/uv-tooling.md`

**Cluster 2** (27 Dokumente):

- `AGENTS.md`
- `docs/adr/0043-edge-vs-conversation.md`
- `docs/adr/ADR-0001__clean-slate-docs-monorepo.md`
- `docs/adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md`
- `docs/architekturstruktur.md`
- `docs/datenmodell.md`
- `docs/domain/modules.md`
- `docs/domain/vocabulary.md`
- `docs/geist-und-plan.md`
- `docs/inhalt.md`
- `docs/konzepte/garnrolle-und-verortung.md`
- `docs/konzepte/garnrolle.md`
- `docs/overview/inhalt.md`
- `docs/overview/zusammenstellung.md`
- `docs/policies/agent-reading-protocol.md`
- `docs/policies/architecture-critique.md`
- `docs/policies/orientierung.md`
- `docs/reference/glossar.md`
- `docs/reports/agent-readiness-audit.md`
- `docs/specs/contract.md`
- `docs/specs/privacy-api.md`
- `docs/specs/privacy-ui.md`
- `docs/techstack.md`
- `docs/vision.md`
- `docs/weltgewebe-agenten-manifest.md`
- `docs/zusammenstellung.md`
- `repo.meta.yaml`

**Cluster 3** (12 Dokumente):

- `docs/adr/ADR-0005-auth.md`
- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
- `docs/blueprints/auth-roadmap.md`
- `docs/blueprints/ui-blaupause.md`
- `docs/blueprints/ui-roadmap.md`
- `docs/blueprints/ui-state-machine.md`
- `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
- `docs/reports/auth-status-matrix.md`
- `docs/specs/auth-api.md`
- `docs/specs/auth-blueprint.md`
- `docs/specs/auth-state-machine.md`
- `docs/specs/auth-ui.md`

**Cluster 4** (3 Dokumente):

- `docs/adr/0042-consume-semantah-contracts.md`
- `docs/x-repo/peers-learnings.md`
- `docs/x-repo/semantAH.md`

**Cluster 5** (3 Dokumente):

- `docs/blueprints/map-blaupause.md`
- `docs/blueprints/map-roadmap.md`
- `docs/reports/map-status-matrix.md`

### Konkrete Beispiele zur Prüfung

> Dokumente mit den meisten relates_to-Zielen und ihren konkreten Relationen.

**`docs/deploy/README.md`**:

- relates_to → `docs/deploy/heimserver.deployment.md`
- relates_to → `docs/deploy/heimserver.integration.md`
- relates_to → `docs/deploy/security.md`
- relates_to → `docs/deployment.md`
- relates_to → `docs/deployment_governance.md`

**`docs/adr/ADR-0006__auth-magic-link-session-passkey.md`**:

- relates_to → `docs/adr/ADR-0005-auth.md`
- relates_to → `docs/blueprints/auth-roadmap.md`
- relates_to → `docs/reports/auth-status-matrix.md`
- relates_to → `docs/specs/auth-blueprint.md`

**`docs/deployment.md`**:

- relates_to → `docs/deploy/README.md`
- relates_to → `docs/deploy/security.md`
- relates_to → `docs/deployment_governance.md`
- relates_to → `docs/runbook.md`

### Hinweise

- Alle Ergebnisse dienen der strukturellen Sichtbarmachung.
- `relates_to` ist kein Fehler — die Verteilung zeigt den aktuellen Stand.
- Keine automatischen Korrekturen werden vorgenommen.
