---
id: reports.proof-matrix-generalization-decision
title: "Proof-Matrix-Generalisierung — DOCMETA-PROOF-001"
doc_type: report
status: active
lifecycle_state: active
lifecycle: decision
owner_task: DOCMETA-PROOF-001
review_after: 2026-09-29
created: 2026-06-29
lang: de
summary: >
  Retrospektive Entscheidung zu DOCMETA-PROOF-001: Das vorhandene
  OPT-ARC-001-Proof-Matrix-Pattern wird dokumentiert, aber nicht zu einem
  generischen Schema oder Validator verallgemeinert, solange kein zweiter
  echter Anwendungsfall dieselbe Struktur benötigt.
relations:
  - type: relates_to
    target: docs/reports/opt-arc-001-db-proof-matrix.json
  - type: relates_to
    target: scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py
  - type: relates_to
    target: scripts/docmeta/tests/test_validate_opt_arc_001_db_proof_matrix.py
  - type: relates_to
    target: .github/workflows/opt-arc-001-db-proof-matrix.yml
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
---

# Proof-Matrix-Generalisierung — DOCMETA-PROOF-001

## Entscheidung

DOCMETA-PROOF-001 wird als bewusste Nicht-Generalisierung abgeschlossen.

Es wird **kein** generisches Proof-Matrix-Schema und **kein** generischer
Proof-Matrix-Validator eingeführt. Der bestehende Validator bleibt
projektspezifisch für `OPT-ARC-001`.

## Begründung

Der vorhandene Anwendungsfall ist stark an `OPT-ARC-001` gebunden:

- genau definierte DB-Proof-Jobs in `.github/workflows/api.yml`,
- proof-spezifische Testdateien und Reportpfade,
- Status-Sync gegen `docs/tasks/*` und `docs/reports/optimierungsstatus.*`,
- Cutover-Schutz für JSONL als Default-Read-/Write-Truth,
- ein expliziter Non-Goal-Satz für den PostgreSQL-Cutover.

Das sind keine neutralen Schemaeigenschaften, sondern Task-Sicherungen für
einen konkreten Migrationspfad. Eine generische Fassung aus nur diesem einen
Fall würde voraussichtlich zu abstrakt oder falsch normativ werden.

## Was am Pattern wiederverwendbar ist

Wiederverwendbar als Entwurfsmuster sind:

- ein maschinenlesbarer Statusanker,
- eine explizite Evidence-Policy,
- eine kleine Menge erlaubter Proof-Zustände,
- Tests, die Drift zwischen Matrix, Workflow und Statusflächen blockieren,
- ein eigener CI-Guard für den betroffenen Nachweisbereich.

## Was OPT-ARC-spezifisch bleibt

Nicht verallgemeinert werden:

- die sechs DB-Proof-IDs,
- die Phasen B/C/D/E-A/E-B/E-C,
- die PostgreSQL-/JSONL-Cutover-Non-Goals,
- die Cargo-Test-Kommandos,
- die Job- und Reportbindung an `apps/api`.

## Wiedervorlagebedingung

Ein generisches Schema wird erst wieder geprüft, wenn ein zweiter echter
Proof-Guard dieselbe Struktur benötigt. Dann ist retrospektiv zu entscheiden,
welche Teile wirklich gemeinsam sind:

- Matrix-Schema,
- Status-Sync,
- Evidence-Regeln,
- Workflow-Trigger-Regeln,
- Shell-/Testkommando-Prüfung.

Bis dahin bleibt Spezialisierung die sicherere Form. Ein generisches Schema aus
einem Einzelfall wäre Verwaltung mit Laborkittel.

## Nachweis

Aktuelle Evidenz für die Entscheidung:

- `docs/reports/opt-arc-001-db-proof-matrix.json`,
- `scripts/docmeta/validate_opt_arc_001_db_proof_matrix.py`,
- `scripts/docmeta/tests/test_validate_opt_arc_001_db_proof_matrix.py`,
- `.github/workflows/opt-arc-001-db-proof-matrix.yml`.

Diese Artefakte belegen das spezifische Pattern. Sie belegen keinen Bedarf für
einen generischen Validator.
