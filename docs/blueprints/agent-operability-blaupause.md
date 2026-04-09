---
id: agent-operability-blaupause
title: Minimaler Agent-Operability-Kern
doc_type: blueprint
status: draft
summary: Definition des minimalen Action-Layers zur Ausführung konkreter Entwicklungsaufgaben.
relations:
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
  - type: relates_to
    target: docs/reports/agent-readiness-audit.md
  - type: depends_on
    target: AGENTS.md
---

Dialektik

These:
Wir bauen jetzt den minimalen Action-Layer, damit Agents endlich wirksam arbeiten können.
→ Fokus: sofort nutzbar, konkret, implementierbar.

Antithese:
Selbst dieser „minimale“ Layer kann entgleisen:
→ zu viele Contracts, zu abstrakt, keine echte Nutzung → wieder Theorie.

Synthese:
Baue nur das, was in der nächsten echten PR benutzt wird.
→ „Blueprint → Task → Command → PR“ muss sofort funktionieren.

⸻

🧭 BLAUPAUSE: Minimaler Agent-Operability-Kern

Ziel (präzise)

Agents sollen:

konkrete Entwicklungsaufgaben strukturiert ausführen können

Nicht mehr. Nicht weniger.

⸻

🧱 1. Architektur (Minimalform)

Blueprint → Task → Commands → Execution → Ergebnis

Kein:
 • Signal-System
 • Policy Engine
 • Emergenz

👉 nur Durchstich von Denken → Handeln

⸻

⚙️ 2. Kernkomponenten

⸻

2.1 Command Contracts (3 Stück, nicht mehr)

WICHTIG:
Diese Commands sind konzeptionell Contracts und müssen perspektivisch in `contracts/` als maschinenvalidierbare Schemas überführt werden.


Zweck (Etymologie)

Command ← lat. commandare = „anvertrauen, anweisen“

→ bei dir:
strukturierte, überprüfbare Aktion

⸻

C1: command.read_context

id: command.read_context
type: command

input:

- paths[]

output:

- extracted_facts
- uncertainties

constraints:

- must_reference_files

👉 ersetzt:
 • „lies repo“
 • „analysiere code“

⸻

C2: command.write_change

id: command.write_change
type: command

input:

- target_file
- change_type (create|update|delete)
- content

constraints:

- target_proof_required
- no_generated_files

👉 verbindet mit deiner bestehenden Diagnose-Regel

⸻

C3: command.validate_change

id: command.validate_change
type: command

input:

- checks[]

output:

- success
- errors[]

checks:
 • lint
 • test
 • docs-guard

⸻

👉 Warum genau diese 3?

Weil sie exakt abdecken:

Phase Command
Verstehen read_context
Handeln write_change
Prüfen validate_change

👉 alles andere ist Overkill

⸻

## Aktivierung

Diese Blaupause wird angewendet, wenn:

- Agent Entwicklungsaufgaben ausführt
- Blueprint → Implementation überführt wird
- PR-Erstellung automatisiert wird

Nicht anzuwenden für:

- reine Analyse
- Dokumentationsaufgaben ohne Codeänderung

🧩 2.2 Task-System (der eigentliche Hebel)

Etymologie

Task ← altengl. tæscan = „auferlegte Arbeit“

→ bei dir:
strukturierte Arbeitssequenz

⸻

Minimal-Template

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


⸻

WICHTIG

👉 Task ≠ Beschreibung
👉 Task = ausführbare Struktur

⸻

🤖 2.3 Agent-Loop (ultra simpel)

1. read_context
2. decide (implizit im Agent)
3. write_change
4. validate_change

👉 kein Planner-Agent nötig (noch nicht)

⸻

🖥️ 2.4 Execution (Startpunkt)

CLI (bewusst simpel)

wgx task run fix_map_submission


⸻

Was passiert intern?

load task
→ execute commands sequentially
→ log results


⸻

📁 3. Repo-Integration (konkret)

Neue Struktur

/agent/
  commands/
    read_context.yaml
    write_change.yaml
    validate_change.yaml

  tasks/
    fix_map_submission.yaml

/scripts/
  run-task.ts (oder .py)


⸻

🔗 4. Verbindung zu bestehendem System

Schon vorhanden (stark!)
 • AGENTS.md → Regeln
 • agent-policy.yaml → Guardrails
 • CI → Validierung
 • Contracts → Wahrheit

⸻

Neuer Layer macht:

👉 diese Dinge ausführbar

⸻

⚠️ Typische Fehler (vermeiden)

❌ Fehler 1: Zu viele Commands

→ du brauchst keine 10
→ du brauchst 3 gute

⸻

❌ Fehler 2: Tasks als Text

→ nein:

steps:

- "analysiere code"

→ wertlos

⸻

❌ Fehler 3: Keine echte Nutzung

→ erste Task MUSS echten Bug fixen

⸻

🔁 Alternative Sinnachse

Statt:

👉 „Wir bauen ein Agent-System“

Denk:

👉 „Wir bauen ein Makefile für Intelligenz“

⸻

📊 Risiko–Nutzen

Nutzen
 • sofort bessere PRs
 • weniger Drift
 • reproduzierbare Agent-Arbeit

⸻

Risiken

1. Zu abstrakt

→ Lösung: nur echte Tasks bauen

1. Agent ignoriert Struktur

→ Lösung: strikt erzwingen

1. Doppelstruktur zu bestehenden Tools

→ Lösung: integrieren, nicht ersetzen

⸻

🧪 Prämissencheck

Das funktioniert nur, wenn:
 • du Agents aktiv nutzt
 • du echte Tasks definierst (keine Theorie)
 • du Struktur durchsetzt

⸻

🚀 KONKRETE NÄCHSTE AKTION

Schritt 1 (heute)
 • 3 Command YAMLs anlegen

⸻

Schritt 2
 • 1 echte Task definieren:
👉 fix_map_submission

⸻

Schritt 3
 • minimalen Runner bauen

⸻

🧩 Essenz

Hebel:
Task-System (nicht Agenten, nicht Emergenz)

Entscheidung:
Minimaler Action Layer statt komplexer Architektur

Nächste Aktion:
→ 3 Commands + 1 echte Task implementieren

⸻

🔍 Unsicherheit

Unsicherheitsgrad: 0.14
Ursachen:
 • genaue CLI-/Tooling-Struktur im Repo nicht vollständig bekannt

Interpolationsgrad: 0.19
Annahmen:
 • kein bestehender Task-Runner
 • YAML als praktikables Format

⸻

## Erste Implementierung (verbindlich)

Erste Task im Repo:

agent/tasks/fix_map_submission.yaml

Diese Task dient als Referenzimplementierung und muss real ausführbar sein.

🧠 Humor (präzise)

Du baust gerade den Unterschied zwischen:

„Der Agent hat verstanden, was zu tun ist“

und

„Der Agent hat es tatsächlich getan“

Spoiler: Nur eines davon zählt.


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
