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

- `docs/reports/optimierungsstatus.md` ist die kanonische menschliche Wahrheitsquelle für OPT-IDs und deren Status.
- `docs/tasks/index.json` ist eine strukturierte Task-Control-Fläche und normative Registrierungsquelle für dort eingetragene IDs. Es ist jedoch keine vollständige Wahrheit für alle OPT-IDs und kein Ersatz für OPT-Markdown.
- `docs/reports/optimierungsstatus.json` ist ein maschinenlesbarer Zwilling und dient als Lookup-Fläche. Es besitzt keinen eigenen Wahrheitsstatus. Eine vollständige Parität zum Markdown ist Voraussetzung für eine spätere alleinige maschinelle Nutzung.
- Kein Status in `index.json` oder `optimierungsstatus.json` darf dem Markdown widersprechen.
- `done` gilt nicht ohne reproduzierbaren Evidenz-Eintrag in der Statusmatrix.
- Stille Statusupgrades sind verboten.

## Curation-Status

Solange `curation: "manual_phase2_seed"` gesetzt ist, darf `index.json` manuell
gepflegt werden. Sobald ein echter Generator (mit Schreibzugriff) eingeführt wird, muss der
Schreibstatus neu bewertet und in `CONTRIBUTING.md` dokumentiert werden.

Der in TASK-CTL-003 eingeführte `generate_task_index.py --check` ist ein reiner
Drift-Prüfmechanismus ohne Schreibzugriff und ändert den manuellen Pflegestatus nicht.
Automatische Generierung und Bot-PRs bleiben eine spätere Entscheidung.

## Phase-Stand

| Phase | Artefakte | Status |
|---|---|---|
| Phase 2 | `docs/tasks/*`, `docs/reports/optimierungsstatus.json`, Validator | **Vorhanden** |
| Phase 3 | `.github/ISSUE_TEMPLATE/*`, `.github/pull_request_template.md` | **Zurückgestellt** — kein belegter Mehrwert gegenüber freien PR-Bodies |
| Phase 4 | `scripts/docmeta/generate_task_index.py`, CI-Guard | **In Arbeit** — Check-Modus + CI-Guard vorhanden, CI-Lauf-Nachweis ausstehend (TASK-CTL-003) |
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

## Drift-Check

```bash
python3 -m scripts.docmeta.generate_task_index --check
```

Vergleicht `board.md`, `index.json` und `docs/reports/optimierungsstatus.json` auf Drift:
Aktive Board-Tasks, Blocker oder PR-Kandidaten ohne Index-Eintrag; `open`/`partial` Tasks mit `high`/`medium` Priorität ohne Board-Sichtbarkeit; `done` ohne Evidenz;
High-Priority ohne Akzeptanzkriterium; nicht existierende Evidenz-/Doku-Pfade;
`docs/_generated/*` als Schreibziel; sowie Statuswidersprüche zur Optimierungsstatus-Matrix.

Exit 0 ohne Drift, sonst 1. Reiner Prüfmechanismus, keine neue Wahrheitsschicht: Im
`--check`-Modus werden keine Dateien geschrieben. Läuft im CI über
`.github/workflows/task-index.yml`.
