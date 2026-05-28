---
id: blueprint-doc-structure-task-control-roadmap
title: Dokumentationsstruktur und Task-Steuerung Roadmap
doc_type: roadmap
status: draft
summary: >
  Phasenplan und PR-Schnitte für die Einführung einer Task-Control-Schicht
  zwischen Navigation, Statusmatrizen, Task-Artefakten und GitHub-Umlauf.
relations:
  - type: depends_on
    target: docs/blueprints/doc-structure-task-control.md
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/blueprints/doc-structure-task-control-examples.md
---

# Roadmap: Dokumentationsstruktur und Task-Steuerung

## 0. Rolle

Diese Roadmap ist der operative Begleitplan zur
[Blaupause](doc-structure-task-control.md). Sie ist **draft** und wird erst zur
stabilen Statusquelle, wenn die ersten Task-Artefakte implementiert und durch
Guards validiert sind.

Die Master-Roadmap darf auf dieses Dokument als thematischen Arbeitsstrang
verweisen. Die fachliche Begründung bleibt in der Blaupause; belegte
Umsetzungsstände bleiben in Statusmatrizen und PR-Nachweisen.

## Phase 0: Diagnose-Gate

Ziel: Belegen, was aktuell fehlt, bevor neue Struktur eingeführt wird.

Checks:

```bash
test -f docs/tasks/board.md || echo "missing docs/tasks/board.md"
test -f docs/tasks/index.json || echo "missing docs/tasks/index.json"
test -f docs/reports/optimierungsstatus.json || echo "missing optimierungsstatus.json"
test -d .github/ISSUE_TEMPLATE || echo "missing issue templates"
test -f .github/pull_request_template.md || echo "missing PR template"
test -f .github/release.yml || echo "missing release categories"
```

Stop-Kriterium:

- Fehlende Dateien sind eindeutig benannt.
- Kein Patch vor belegtem Ist-Zustand.

## Phase 1: Einstieg und Navigation stabilisieren

Scope:

```text
README.md
CONTRIBUTING.md
docs/index.md
repo.meta.yaml
```

Änderungen:

- README Quicklinks ergänzen.
- README-Pfade korrigieren.
- `CONTRIBUTING.md` an reale Repo-Struktur anpassen.
- `docs/index.md` um relevante Diagnoseartefakte ergänzen.
- `repo.meta.yaml` nur ändern, wenn neue Artefakte tatsächlich eingeführt
  werden und ihre Rolle geklärt ist.

Akzeptanz:

- Alle Links existieren.
- Keine Verweise auf nicht vorhandene Pfade.
- `docs/index.md` erklärt Navigation vs Wahrheit.
- `repo.meta.yaml` und `docs/index.md` widersprechen sich nicht.

## Phase 2: Task-Control-Schicht einführen

Scope:

```text
docs/tasks/README.md
docs/tasks/board.md
docs/tasks/index.json
docs/tasks/schema.json
docs/reports/optimierungsstatus.json
```

Änderungen:

- Menschliches Task-Board anlegen.
- JSON-Task-Index und Schema anlegen.
- Maschinenlesbaren Zwilling für `optimierungsstatus.md` einführen.
- Pflege- und Generierungsstatus der JSON-Artefakte explizit dokumentieren.

Akzeptanz:

- Alle offenen Top-Prioritäten erscheinen im Board.
- JSON ist valide.
- Jede Task-ID ist eindeutig.
- High-Priority-Tasks haben Akzeptanzkriterien.
- Geschlossene Tasks haben Evidenz.

## Phase 3: GitHub-native Arbeitsobjekte anbinden

Scope:

```text
.github/ISSUE_TEMPLATE/*.yml
.github/pull_request_template.md
.github/release.yml
docs/process/labels.md
```

Änderungen:

- Issue Forms einführen.
- Leichtes PR-Meta-Template einführen.
- Label-Taxonomie dokumentieren.
- Optional GitHub Project v2 konfigurieren, aber nur nach Klärung von Rechten
  und Ownern.

Akzeptanz:

- Neue Arbeitspakete enthalten Task-ID, Bereich, Priorität und
  Akzeptanzkriterien.
- PRs verweisen auf Tasks, Docs oder Issues.
- Labels folgen derselben Taxonomie wie Issue Forms und Release Notes.
- Das Template bleibt kurz genug, damit keine Formularlyrik entsteht.

## Phase 4: Generator und Guard integrieren

Scope:

```text
scripts/docmeta/generate_task_index.py
scripts/docmeta/validate_task_index.py
.github/workflows/task-index.yml
.github/workflows/docs-guard.yml
```

Änderungen:

- Task-Index deterministisch erzeugen oder im Check-Modus validieren.
- Pfade, Statuswerte, Akzeptanzkriterien und Evidenz prüfen.
- PR-Checks prüfen, aber schreiben nicht still in den Branch.

Akzeptanz:

- PR-Checks erkennen Drift.
- Task-Index wird deterministisch erzeugt.
- Generated-Files-Regel wird respektiert.
- Fehlende Evidenz wird nicht geglättet, sondern gemeldet.

## Phase 5: Implementierungs-Mapping schließen

Scope:

```text
audit/impl-registry.yaml
docs/_generated/impl-index.md
docs/_generated/doc-coverage.md
```

Änderungen:

- `audit/impl-registry.yaml` für Kernpfade mit `documented_by` und
  `verified_by` füllen.
- `docs/_generated/impl-index.md` als Gate-Signal nutzen, nicht manuell
  ändern.
- Kernbereiche API, Web, CI, Compose und Contracts priorisieren.

Akzeptanz:

- Kernimplementierungen sind nicht mehr „undocumented“.
- Jede Kernimplementierung hat mindestens ein Doku- und ein Prüfartefakt.
- Agents können von Task → Implementierung → Proof navigieren.

## PR-Schnitte

| PR | Fokus | Dateien | Akzeptanz |
|---|---|---|---|
| PR 1 | Navigation reparieren | `README.md`, `CONTRIBUTING.md`, `docs/index.md`, `repo.meta.yaml` | Links korrekt, reale Topologie, Rollen erklärt |
| PR 2 | Task-Artefakte | `docs/tasks/*`, `docs/reports/optimierungsstatus.json` | JSON valide, Top-Prioritäten sichtbar |
| PR 3 | GitHub-Struktur | Issue Forms, PR-Template, Release-Konfig, Labels-Doku | strukturierte Issues und Release-Kategorien |
| PR 4 | Generator und CI | Docmeta-Skripte, Task-Index-Workflow | deterministische Prüfung, Drift-Erkennung |
| PR 5 | Implementierungs-Mapping | `audit/impl-registry.yaml`, generierte Diagnosen | Kernpfade verknüpft und belegbar |

## Messbare Erfolgskriterien

Nach Umsetzung sollte gelten:

```text
README broken links: 0
CONTRIBUTING non-existing path references: 0
High-priority tasks without acceptance: 0
Closed tasks without evidence: 0
Duplicate task IDs: 0
Generated docs missing from docs/index.md: 0
Generated docs missing from repo.meta.yaml: 0
Task JSON schema validation: pass
Docs guard: pass
```

Optional:

```text
Open GitHub issues without task_id: 0 for kind:task
PRs without related-task or related-docs: warning
Release PRs without release-note label: warning
```
