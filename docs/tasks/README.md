---
id: tasks.readme
title: Task-Control – Einstieg
doc_type: guide
status: active
summary: >
  Einstieg in die Task-Control-Schicht von Weltgewebe.
  Erklärt Zweck, Rollenklärung und Grenzen der Artefakte in docs/tasks/.
relations:
  - type: depends_on
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
---

# Task-Control – Einstieg

## Zweck

`docs/tasks/` ist die Arbeitssteuerungs-Schicht von Weltgewebe.
Sie ergänzt die Statusmatrizen in `docs/reports/`, ist aber keine zweite Wahrheitsschicht.

## Rollenklärung der Artefakte

| Datei | Rolle | Schreibstatus |
|---|---|---|
| `docs/tasks/board.md` | Menschliche Arbeitskarte (aktive Prioritäten, Blocker, nächste PR-Kandidaten) | Manuell gepflegt |
| `docs/tasks/index.json` | Maschinenlesbarer Task-Index (Seed: manuell) | Manuell bis Generator eingeführt |
| `docs/tasks/schema.json` | Validierungsvertrag für `index.json` | Änderungen nur mit begründetem PR |
| `docs/reports/optimierungsstatus.md` | Belegte menschliche Statusmatrix | Maßgeblich für Wahrheitsgehalt |
| `docs/reports/optimierungsstatus.json` | Maschinenlesbarer Zwilling der Statusmatrix | Kein eigenständiger Statusträger |

## Wahrheitsklärung

- `docs/reports/optimierungsstatus.md` ist die menschliche Statusmatrix und bleibt die Wahrheitsquelle für OPT-* Einträge.
- `docs/tasks/index.json` ist eine strukturierte Arbeitskarte, kein Statusersatz.
- Kein Status in `index.json` oder `optimierungsstatus.json` darf dem Markdown widersprechen.
- `done` gilt nicht ohne reproduzierbaren Evidenz-Eintrag in der Statusmatrix.
- Stille Statusupgrades sind verboten.

## Curation-Status

Solange `curation: "manual_phase2_seed"` gesetzt ist, darf `index.json` manuell
gepflegt werden. Sobald ein Generator eingeführt wird (Phase 4), muss der Schreibstatus
neu bewertet und in `CONTRIBUTING.md` dokumentiert werden.

## Phase-Stand

| Phase | Artefakte | Status |
|---|---|---|
| Phase 2 | `docs/tasks/*`, `docs/reports/optimierungsstatus.json`, Validator | **Vorhanden** |
| Phase 3 | `.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md` | **Zurückgestellt** — kein belegter Mehrwert gegenüber freien PR-Bodies |
| Phase 4 | `scripts/docmeta/generate_task_index.py`, CI-Guard | **Nächste Priorität** (TASK-CTL-003) |
| Phase 5 | `audit/impl-registry.yaml`-Ausbau | Geplant |

## GitHub-Arbeitsobjekte

Issue Forms, PR-Template und Release-Konfiguration sind aktuell zurückgestellt. Sie sind keine Voraussetzung für die Task-Control-Schicht.

Begründung: Der aktuelle Engpass ist nicht fehlende Formularstruktur, sondern Drift-Gefahr zwischen Task-Board, Task-Index, Optimierungsstatus und Evidenz. Der nächste operative Schritt ist daher `TASK-CTL-003`: Task-Index-Generator und CI-Guard.

Wiederaufnahme ist sinnvoll, wenn externe Beitragende ohne Projekteinblick aktiv werden, PR-Bodies wiederholt Task-/Evidenzbezüge verlieren oder der Release-Prozess stabil genug für Release-Labels ist.

## Validator

```bash
python3 -m scripts.docmeta.validate_task_index docs/tasks/index.json
```

Exit 0 bei Erfolg, 1 bei Validierungsfehlern.
Keine stillen Fixes, kein Schreiben durch den Validator.
