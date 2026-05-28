---
id: blueprint-doc-structure-task-control-examples
title: Dokumentationsstruktur und Task-Steuerung Beispiele
doc_type: reference
status: draft
summary: >
  Beispielhafte JSON-, Markdown-, YAML- und Workflow-Skizzen für die spätere
  Umsetzung der Task-Control-Schicht.
relations:
  - type: depends_on
    target: docs/blueprints/doc-structure-task-control.md
  - type: relates_to
    target: docs/blueprints/doc-structure-task-control-roadmap.md
---

# Beispiele: Dokumentationsstruktur und Task-Steuerung

## 0. Rolle

Diese Datei sammelt Beispiele. Sie ist **keine** Umsetzung. Beispiele dürfen
nicht als existierende Repo-Struktur gelesen werden, solange die genannten
Dateien nicht tatsächlich angelegt und validiert sind.

## 1. README-Schnellzugriff

```markdown
## Schnellzugriff

- [Dokumentationsindex](docs/index.md)
- [Beitragen](CONTRIBUTING.md)
- [Agenten-Leitfaden](AGENTS.md)
- [Task-Board](docs/tasks/board.md)
- [Optimierungsstatus](docs/reports/optimierungsstatus.md)
- [Deploy-Änderungsprotokoll](docs/deploy/CHANGELOG.md)
- [Dokumentenindex](docs/_generated/doc-index.md)
- [Implementierungsindex](docs/_generated/impl-index.md)
```

Akzeptanz:

- Alle Links existieren.
- README erklärt Einstieg, Wahrheit, Diagnose und Task-Steuerung getrennt.

## 2. Task-Board

```markdown
# Task Board

## Aktive Prioritäten

| ID | Bereich | Status | Priorität | Evidenz | Nächste Aktion |
|---|---|---|---|---|---|

## Blocker

| ID | Blocker | Fehlt | Folge |
|---|---|---|---|

## Nächste PR-Kandidaten

| ID | PR-Schnitt | Akzeptanzkriterium |
|---|---|---|

## Links

- Optimierungsstatus: ../reports/optimierungsstatus.md
- Maschinenindex: index.json
- Agent Readiness: ../_generated/agent-readiness.md
```

Akzeptanz:

- Jedes offene High-Priority-Paket hat eine nächste Aktion.
- Keine Aufgabe ohne Evidenz-Link oder explizite Leerstelle.

## 3. Task-Index JSON

```json
{
  "schema_version": "1.0.0",
  "generated_at": "2026-05-28T00:00:00Z",
  "source_files": [
    "docs/reports/optimierungsstatus.md",
    "docs/reports/auth-status-matrix.json",
    "docs/reports/map-status-matrix.json"
  ],
  "tasks": [
    {
      "id": "OPT-DOC-001",
      "title": "README als Einstiegskarte neu schneiden",
      "area": "docs",
      "status": "open",
      "priority": "high",
      "effort": "S",
      "risk": "low",
      "owner": "unknown",
      "evidence": [
        "README.md",
        "docs/index.md"
      ],
      "missing_evidence": [],
      "acceptance": [
        "README enthält Schnellzugriff",
        "Alle Links existieren",
        "README erklärt Navigation vs Wahrheit"
      ],
      "links": {
        "issues": [],
        "prs": [],
        "docs": [
          "README.md",
          "docs/index.md"
        ]
      },
      "updated_at": "2026-05-28"
    }
  ]
}
```

Akzeptanz:

- Jede Task-ID ist eindeutig.
- Jeder Pfad existiert oder wird als fehlend markiert.
- High-Priority-Tasks ohne Akzeptanzkriterien schlagen fehl.

## 4. Optimierungsstatus JSON

```json
{
  "schema_version": "1.0.0",
  "source_markdown": "docs/reports/optimierungsstatus.md",
  "items": [
    {
      "id": "OPT-DOC-001",
      "area": "docs",
      "status": "open",
      "priority": "high",
      "evidence_status": "partial",
      "evidence": [],
      "missing_evidence": [
        "maschinenlesbarer Statuszwilling fehlt"
      ],
      "next_action": "optimierungsstatus.json einführen",
      "risk": "medium",
      "updated_at": "2026-05-28"
    }
  ]
}
```

Akzeptanz:

- Enthält alle `OPT-*`-Einträge aus `optimierungsstatus.md`.
- Kein Statuswechsel ohne Evidenz.
- Wird durch CI validiert.

## 5. Issue Form für Arbeitspakete

```yaml
name: Arbeitspaket
description: Strukturiertes Task-Issue für Repo, Doku und CI
title: "[Task]: "
labels: ["kind:task", "status:triage"]
body:
  - type: dropdown
    id: area
    attributes:
      label: Bereich
      options:
        - docs
        - ci
        - api
        - web
        - infra
        - release
    validations:
      required: true

  - type: dropdown
    id: priority
    attributes:
      label: Priorität
      options:
        - high
        - medium
        - low
    validations:
      required: true

  - type: input
    id: task_id
    attributes:
      label: Interne Task-ID
      placeholder: OPT-DOC-001
    validations:
      required: true

  - type: textarea
    id: problem
    attributes:
      label: Problem
      description: Was ist konkret unklar, gebrochen oder unverbunden?
    validations:
      required: true

  - type: textarea
    id: acceptance
    attributes:
      label: Akzeptanzkriterien
      description: Ein Kriterium pro Zeile.
    validations:
      required: true

  - type: textarea
    id: docs_paths
    attributes:
      label: Relevante Dokumentpfade
      placeholder: |
        README.md
        docs/index.md
        docs/reports/optimierungsstatus.md
    validations:
      required: true
```

## 6. PR-Meta-Template

```markdown
<!-- .github/pull_request_template.md -->

## Kontext
- related-task:
- related-docs:
- related-issue:

## Änderung
- Was wurde verändert?
- Warum hier?
- Welche Pfade sind betroffen?

## Nachweis
- Tests:
- Doku aktualisiert:
- Restlücken:

## Release-Hinweis
- [ ] release-note:feature
- [ ] release-note:fix
- [ ] release-note:docs
- [ ] chore/no-release
```

## 7. Label-Taxonomie

```text
area:docs
area:ci
area:api
area:web
area:infra
area:release

kind:task
kind:bug
kind:doc-drift
kind:decision
kind:proof
kind:refactor

prio:high
prio:medium
prio:low

status:triage
status:ready
status:blocked
status:in-progress
status:needs-review

needs-doc
needs-proof
blocked

release-note:feature
release-note:fix
release-note:docs
chore/no-release
```

## 8. Release-Kategorien

```yaml
changelog:
  categories:
    - title: Features
      labels:
        - release-note:feature
    - title: Fixes
      labels:
        - release-note:fix
    - title: Documentation
      labels:
        - release-note:docs
    - title: Maintenance
      labels:
        - chore
  exclude:
    labels:
      - chore/no-release
```

## 9. Task-Index Workflow

```yaml
name: task-index

on:
  pull_request:
    paths:
      - "README.md"
      - "CONTRIBUTING.md"
      - "docs/**"
      - ".github/ISSUE_TEMPLATE/**"
      - ".github/workflows/task-index.yml"
      - "scripts/docmeta/**"
  workflow_dispatch: {}
  schedule:
    - cron: "17 3 * * *"

permissions:
  contents: read
  issues: read
  pull-requests: read

jobs:
  validate-task-index:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Generate task index
        run: python3 scripts/docmeta/generate_task_index.py --check
      - name: Validate task index
        run: python3 scripts/docmeta/validate_task_index.py docs/tasks/index.json
```

Wichtig: PR-Checks sollen prüfen, nicht still schreiben. Automatische Commits
gehören in separate Bot-PRs.

## 10. Agenten-Prompts

### Dok-Drift-Auditor

```text
Vergleiche README.md, CONTRIBUTING.md, docs/index.md, repo.meta.yaml,
audit/impl-registry.yaml und docs/_generated/*.md.

Liste nur belegte Inkonsistenzen.
Prüfe jeden referenzierten Pfad auf Existenz.
Unterscheide Navigation, Diagnose, Wahrheit und Arbeitspaket.
Erzeuge keine stillen Umdeutungen.
```

### Task-Reconciler

```text
Lies docs/tasks/index.json, docs/reports/optimierungsstatus.json,
offene Issues mit kind:task, Project-Felder und audit/impl-registry.yaml.

Melde alle Maßnahmen ohne Owner, ohne Akzeptanzkriterien,
ohne Evidenz-Link oder mit nicht existierenden Pfaden.
```

### Release-Notes-Kurator

```text
Gruppiere gemergte PRs nach release-note:* Labels.
Verlinke relevante Dokuänderungen.
Ignoriere chore/no-release.
Markiere PRs ohne Release-Kategorie als review_needed.
```
