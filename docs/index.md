---
id: docs.index
title: Weltgewebe - Doku-Index
doc_type: index
status: active
summary: >
  Kanonischer Doku-Index für das Projekt Weltgewebe.
---
# Weltgewebe – Doku-Index

## Canonical Knowledge

> Dieser Index ist kanonische Navigation, keine eigenständige Wahrheitsschicht.
> Bei Konflikten führen Spezifikationen, ADRs, Policies, Statusmatrizen und
> Code gemäß `repo.meta.yaml`.

<!--
NOTE:
Kanonische Navigation. Neue UI-Dokumente bestehenden Kategorien zuordnen.
-->

### Master-Umsetzungsroadmap

– **Master-Roadmap:** [roadmap.md](roadmap.md) (Koordinations-Index über alle thematischen Sub-Roadmaps)

### System

– **Start:** [architekturstruktur.md](architekturstruktur.md)
– **Vertrauen & Garnrolle:** [konzepte/garnrolle-und-verortung.md](konzepte/garnrolle-und-verortung.md)
– **UI State Machine:** [blueprints/ui-state-machine.md](blueprints/ui-state-machine.md)
– **Techstack:** [techstack.md](techstack.md)
– **Datenmodell:** [datenmodell.md](datenmodell.md)
– **Vision:** [vision.md](vision.md)

### Agenten & Arbeitssteuerung

– **Agent Operability:** [blueprints/agent-operability-blaupause.md](blueprints/agent-operability-blaupause.md) (Blueprint)
– **Agent Safety Control Layer:** [blueprints/blueprint-agent-safety-control-layer.md](blueprints/blueprint-agent-safety-control-layer.md) (Blueprint)
– **Dokumentationsstruktur & Task-Steuerung:** [blueprints/doc-structure-task-control.md](blueprints/doc-structure-task-control.md) (Blueprint)
– **Task-Control Roadmap:** [blueprints/doc-structure-task-control-roadmap.md](blueprints/doc-structure-task-control-roadmap.md) (Roadmap)
– **Task-Control Beispiele:** [blueprints/doc-structure-task-control-examples.md](blueprints/doc-structure-task-control-examples.md) (Referenz)

### Domäne

– **Vokabular:** [domain/vocabulary.md](domain/vocabulary.md)
– **Module:** [domain/modules.md](domain/modules.md)
– **Datenvertrag:** [specs/contract.md](specs/contract.md)
– **Listen-Paginierung (API):** [specs/list-pagination-api.md](specs/list-pagination-api.md)

### UI-System

– **UI Interaction Doctrine:** [blueprints/ui-interaction-doctrine.md](blueprints/ui-interaction-doctrine.md) (Kanonischer Interaktionscontract für Fokuspanel, Kartenlinsen, Komposition und spätere URL-Adressierung)
– **UI-Blaupause:** [blueprints/ui-blaupause.md](blueprints/ui-blaupause.md) (Modell)
– **UI State Machine:** [blueprints/ui-state-machine.md](blueprints/ui-state-machine.md) (Regelwerk)
– **UI Roadmap:** [blueprints/ui-roadmap.md](blueprints/ui-roadmap.md) (Planung)

### Karten-Architektur

– **Kartenklarheit:** [blueprints/kartenklarheit.md](blueprints/kartenklarheit.md) (Blaupause zur Optimierung)
– **Roadmap Kartenklarheit:** [blueprints/kartenklarheit-roadmap.md](blueprints/kartenklarheit-roadmap.md) (Umsetzung)
– **Basemap-Blaupause:** [blueprints/map-blaupause.md](blueprints/map-blaupause.md) (Architektur)
– **Basemap-Roadmap:** [blueprints/map-roadmap.md](blueprints/map-roadmap.md) (Umsetzung)
– **Kartenklarheit Phase 6:** [blueprints/kartenklarheit-phase6.md](blueprints/kartenklarheit-phase6.md) (Der Wahrheitsbeweis)

### Auth-Architektur (Kanonisch)

– **ADR-0006:** [adr/ADR-0006__auth-magic-link-session-passkey.md](adr/ADR-0006__auth-magic-link-session-passkey.md) (Führendes Zielbild)
– **ADR-0007:** [adr/ADR-0007__auth-persistence-production-db-path.md](adr/ADR-0007__auth-persistence-production-db-path.md) (Auth-Persistenz Produktionspfad: direkter PostgreSQL-Zugriff)
– **Auth Roadmap:** [blueprints/auth-roadmap.md](blueprints/auth-roadmap.md) (Umsetzungspfad)
– **Auth-Persistenz Runtime-Proof:** [blueprints/auth-persistence-runtime-proof.md](blueprints/auth-persistence-runtime-proof.md) (Blaupause)
– **Auth Status Matrix:** [reports/auth-status-matrix.md](reports/auth-status-matrix.md) (Aktueller Repo-Beweis)
– **Agent Readiness Audit:** [reports/agent-readiness-audit.md](reports/agent-readiness-audit.md) (Diagnose)
– **Auth Specs:** [specs/auth-api.md](specs/auth-api.md), [specs/auth-ui.md](specs/auth-ui.md), [specs/auth-state-machine.md](specs/auth-state-machine.md)

### Deployment & Betrieb

– **Deployment Contract:** [deployment.md](deployment.md)
– **Deployment Governance:** [deployment_governance.md](deployment_governance.md)
– **Deploy-Übersicht:** [deploy/README.md](deploy/README.md)
– **Security:** [deploy/security.md](deploy/security.md)
– **Heimserver:** [deploy/heimserver.deployment.md](deploy/heimserver.deployment.md), [deploy/heimserver.integration.md](deploy/heimserver.integration.md)
– **Runbook:** [runbook.md](runbook.md)
– **Observability:** [runbook.observability.md](runbook.observability.md)
– **Incident Response:** [runbooks/incident-response.md](runbooks/incident-response.md)
– **DB Recovery:** [runbooks/db-recovery.md](runbooks/db-recovery.md)

### Task-Control

– **Task-Control Einstieg:** [tasks/README.md](tasks/README.md) (Rollenklärung und Phase-Stand)
– **Task Board:** [tasks/board.md](tasks/board.md) (Menschliche Arbeitskarte – aktive Prioritäten, Blocker, nächste PR-Kandidaten)
– **Task Index:** [tasks/index.json](tasks/index.json) (Maschinenlesbarer Task-Index – Phase-2-Seed, manuell gepflegt)
– **Optimierungsstatus JSON:** [reports/optimierungsstatus.json](reports/optimierungsstatus.json) (Maschinenlesbarer Zwilling der OPT-Statusmatrix)

### Berichte & Audits

– **Optimierungsbericht:** [reports/optimierungsbericht.md](reports/optimierungsbericht.md) (Schichtenanalyse mit Handlungsempfehlungen)
– **Optimierungsstatus:** [reports/optimierungsstatus.md](reports/optimierungsstatus.md) (Operative Statusmatrix mit Nachweisen – Wahrheitsquelle für OPT-* Einträge)
– **Auth-Persistenzbereitschaft:** [reports/auth-persistence-readiness.md](reports/auth-persistence-readiness.md) (Diagnose zu OPT-API-002)
– **Auth-Persistenz Zielarchitektur-Abgleich:** [reports/auth-persistence-runtime-target-reconciliation.md](reports/auth-persistence-runtime-target-reconciliation.md) (ADR-0007: Produktion direkter Postgres; PgBouncer Dev-/Spezialpfad)
– **Passkey Register-Verify Vorbereitung:** [reports/passkey-register-verify-prep.md](reports/passkey-register-verify-prep.md) (Diagnose und Folge-PR-Entscheidung)
– **Cost Report:** [reports/cost-report.md](reports/cost-report.md)

### Prozess

– **Prozess & Fahrplan:** [process/README.md](process/README.md), [process/fahrplan.md](process/fahrplan.md)
– **ADRs:** [adr/](adr/)
– **Runbooks:** [runbooks/README.md](runbooks/README.md)
– **Glossar:** [reference/glossar.md](reference/glossar.md)
– **Sprache:** [process/sprache.md](process/sprache.md)
– **Bash-Richtlinien:** [process/bash-tooling-guidelines.md](process/bash-tooling-guidelines.md)
– **Inhalt/Story:** [inhalt.md](inhalt.md), [zusammenstellung.md](zusammenstellung.md)
– **Vision & Geist:** [geist-und-plan.md](geist-und-plan.md)
– **X-Repo Learnings:** [x-repo/peers-learnings.md](x-repo/peers-learnings.md), [x-repo/semantAH.md](x-repo/semantAH.md)
– **Beitragen:** [../CONTRIBUTING.md](../CONTRIBUTING.md)

### Policies & Orientierung

– **Orientierung:** [policies/orientierung.md](policies/orientierung.md)
– **Agent Reading Protocol:** [policies/agent-reading-protocol.md](policies/agent-reading-protocol.md) (Bindend)
– **Architekturkritik-Skill:** [policies/architecture-critique.md](policies/architecture-critique.md) (Kognitives Protokoll)
– **Agenten-Manifest:** [weltgewebe-agenten-manifest.md](weltgewebe-agenten-manifest.md)
– **Privacy:** [specs/privacy-api.md](specs/privacy-api.md), [specs/privacy-ui.md](specs/privacy-ui.md)

### Entwicklung

– **Quickstart Gate C:** [quickstart-gate-c.md](quickstart-gate-c.md)
– **Codespaces:** [dev/codespaces.md](dev/codespaces.md)
– **Codespaces Recovery:** [runbooks/codespaces-recovery.md](runbooks/codespaces-recovery.md)

## Generated Knowledge Maps

- [Doc Index](_generated/doc-index.md)
- [System Map](_generated/system-map.md)
- [Backlinks](_generated/backlinks.md)
- [Implementation Index](_generated/impl-index.md)
- [Orphans](_generated/orphans.md)
- [Supersession Map](_generated/supersession-map.md)

## Repo Observatorium

- [Architecture Drift](_generated/architecture-drift.md)
- [Doc Coverage](_generated/doc-coverage.md)
- [Knowledge Gaps](_generated/knowledge-gaps.md)
- [Implicit Dependencies](_generated/implicit-dependencies.md)
- [Change Resonance](_generated/change-resonance.md)
- [Staleness Report](_generated/staleness-report.md)
- [Agent Readiness](_generated/agent-readiness.md)
