---
id: docs.blueprints.agent-operability
title: Minimaler Agent-Operability-Kern
doc_type: blueprint
status: draft
summary: Definition des minimalen Action-Layers zur Ausführung konkreter Entwicklungsaufgaben.
relations:
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
  - type: relates_to
    target: docs/reports/agent-readiness-audit.md
  - type: relates_to
    target: AGENTS.md
  - type: relates_to
    target: agent-policy.yaml
---

# Minimaler Agent-Operability-Kern

## Dialektik

These:
Wir bauen jetzt den minimalen Action-Layer, damit Agents endlich wirksam arbeiten können.
→ Fokus: sofort nutzbar, konkret, implementierbar.

Antithese:
Selbst dieser „minimale“ Layer kann entgleisen:
→ zu viele Contracts, zu abstrakt, keine echte Nutzung → wieder Theorie.

Synthese:
Baue nur das, was in der nächsten echten PR benutzt wird.
→ „Blueprint → Task → Command → PR“ muss sofort funktionieren.

## Ziel

Agents sollen konkrete Entwicklungsaufgaben strukturiert ausführen können.

Nicht mehr. Nicht weniger.

## Architektur

Blueprint → Task → Commands → Execution → Ergebnis

Kein:

- Signal-System
- Policy Engine
- Emergenz

👉 nur Durchstich von Denken → Handeln

## Kernkomponenten

### Command Contracts

WICHTIG:
Diese Commands sind konzeptionelle Contracts und werden perspektivisch als echte Contracts (Schemas) im `contracts/` Layer formalisiert.

*Hinweis: Aktuell keine Schema-Validierung – dient nur als operative Struktur.*

Zweck (Etymologie):
Command ← lat. commandare = „anvertrauen, anweisen“
→ bei dir: strukturierte, überprüfbare Aktion

#### C1: command.read_context

```yaml
id: command.read_context
type: command
input:
  - paths[]
output:
  - extracted_facts
  - uncertainties
constraints:
  - must_reference_files
```

👉 ersetzt:

- „lies repo“
- „analysiere code“

#### C2: command.write_change

```yaml
id: command.write_change
type: command
input:
  - target_file
  - change_type (create|update|delete)
  - content
constraints:
  - target_proof_required
  - no_generated_files
```

👉 verbindet mit deiner bestehenden Diagnose-Regel

#### C3: command.validate_change

```yaml
id: command.validate_change
type: command
input:
  - checks[]
output:
  - success
  - errors[]
checks:
  - lint
  - test
  - docs-guard
```

👉 Warum genau diese 3?
Weil sie exakt abdecken:

- Phase Verstehen: `read_context`
- Phase Handeln: `write_change`
- Phase Prüfen: `validate_change`

👉 alles andere ist Overkill

### Task-System

Etymologie:
Task ← altengl. tæscan = „auferlegte Arbeit“
→ bei dir: strukturierte Arbeitssequenz

#### Minimal-Template

```yaml
task:
  id: fix_map_submission
  goal: "Formularübermittlung implementieren"
  constraints:
    - no breaking changes
    - contract compliance
  steps:
    - command: read_context
    - command: write_change
    - command: validate_change
```

WICHTIG:
👉 Task ≠ Beschreibung
👉 Task = ausführbare Struktur

### Agent-Loop

```text
1. read_context
2. decide (implizit im Agent)
3. write_change
4. validate_change
```

👉 kein Planner-Agent nötig (noch nicht)

### Execution

CLI (bewusst simpel):

```text
wgx task run fix_map_submission
```

Was passiert intern?
load task → execute commands sequentially → log results

## Aktivierung

Diese Blaupause wird angewendet, wenn:

- Agent Entwicklungsaufgaben ausführt
- Blueprint → Implementation überführt wird
- PR-Erstellung automatisiert wird

Nicht anzuwenden für:

- reine Analyse
- Dokumentationsaufgaben ohne Codeänderung

## Repo-Integration

Neue Struktur:

```text
/agent/
  commands/
    read_context.yaml
    write_change.yaml
    validate_change.yaml
  tasks/
    fix_map_submission.yaml
/scripts/
  run-task.ts (oder .py)
```

Verbindung zu bestehendem System:
Schon vorhanden (stark!):

- AGENTS.md → Regeln
- agent-policy.yaml → Guardrails
- CI → Validierung
- Contracts → Wahrheit

Neuer Layer macht:
👉 diese Dinge ausführbar

## Typische Fehler

❌ Fehler 1: Zu viele Commands
→ du brauchst keine 10
→ du brauchst 3 gute

❌ Fehler 2: Tasks als Text
→ nein:

```yaml
steps:
  - "analysiere code"
```

→ wertlos

❌ Fehler 3: Keine echte Nutzung
→ erste Task MUSS echten Bug fixen

Alternative Sinnachse:
Statt: 👉 „Wir bauen ein Agent-System“
Denk: 👉 „Wir bauen ein Makefile für Intelligenz“

## Risiko–Nutzen

Nutzen:

- sofort bessere PRs
- weniger Drift
- reproduzierbare Agent-Arbeit

Risiken:

1. Zu abstrakt → Lösung: nur echte Tasks bauen
2. Agent ignoriert Struktur → Lösung: strikt erzwingen
3. Doppelstruktur zu bestehenden Tools → Lösung: integrieren, nicht ersetzen

## Prämissencheck

Das funktioniert nur, wenn:

- du Agents aktiv nutzt
- du echte Tasks definierst (keine Theorie)
- du Struktur durchsetzt

Konkrete nächste Aktion:
Schritt 1: 3 Command YAMLs anlegen
Schritt 2: 1 echte Task definieren (`fix_map_submission`)
Schritt 3: minimalen Runner bauen

## Erste Implementierung

Erste Task im Repo:

```text
agent/tasks/fix_map_submission.yaml
```

Diese Task dient als Referenzimplementierung und muss real ausführbar sein.

## Maschinenlesbarer Kern

Der folgende Block fasst den operativen Minimal-Kern in kompakter, maschinenlesbarer Form zusammen.

```yaml
agent_operability:
  commands:
    - id: command.read_context
    - id: command.write_change
    - id: command.validate_change
  task_template:
    required_steps:
      - read_context
      - write_change
      - validate_change
  execution:
    type: cli
    entrypoint: scripts/run-task
```

## Essenz

Hebel: Task-System (nicht Agenten, nicht Emergenz)
Entscheidung: Minimaler Action Layer statt komplexer Architektur
Nächste Aktion: → 3 Commands + 1 echte Task implementieren

Unsicherheitsgrad: 0.14
Ursachen: genaue CLI-/Tooling-Struktur im Repo nicht vollständig bekannt
Interpolationsgrad: 0.19
Annahmen: kein bestehender Task-Runner, YAML als praktikables Format

## Humor

Du baust gerade den Unterschied zwischen:

„Der Agent hat verstanden, was zu tun ist“

und

„Der Agent hat es tatsächlich getan“

Spoiler: Nur eines davon zählt.
