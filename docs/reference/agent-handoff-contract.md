---
id: docs.reference.agent-handoff-contract
title: "Agent Handoff Contract"
doc_type: reference
status: active
summary: "Maschinenlesbares Übergabeformat für Agent-Task-Handoffs: Schema, Felder, Validierungsregeln und Fehlercode-Referenz."
relations:
  - type: relates_to
    target: docs/blueprints/blueprint-agent-safety-control-layer.md
  - type: relates_to
    target: contracts/agent/handoff.schema.json
  - type: relates_to
    target: contracts/agent/task.schema.json
  - type: relates_to
    target: scripts/agent/validate_handoff.py
  - type: relates_to
    target: scripts/agent/json_contract.py
  - type: relates_to
    target: tests/fixtures/agent/handoff-valid.json
---

# Agent Handoff Contract

## Zweck

Das Handoff-Dokument ist die maschinenlesbare Übergabe eines Agents nach Abschluss einer Task. Es bindet Ergebnis, geänderte Pfade, adressierte Claims und Validierungsresultate deterministisch an den Task-Vertrag.

## Schema

Das kanonische Schema liegt in [`contracts/agent/handoff.schema.json`](../../contracts/agent/handoff.schema.json). Es ist gegen JSON Schema Draft-07 definiert und wird sowohl von AJV (CI-Shell-Check) als auch von `scripts/agent/json_contract.py` (Python-Tests) geprüft.

## Pflichtfelder

| Feld | Typ | Beschreibung |
|---|---|---|
| `handoff_id` | string | Eindeutige ID, Muster `^[A-Z0-9]+(-[A-Z0-9]+)*$` |
| `task_id` | string | Muss mit `task_id` im Task-Vertrag übereinstimmen |
| `task_contract_sha256` | string | SHA-256-Digest der Task-Datei-Bytes (64 Hex-Zeichen) |
| `source_revision` | string | Git-Revision zum Zeitpunkt der Übergabe (40 oder 64 Hex) |
| `producer` | string | Bezeichner des produzierenden Agents, `minLength: 1`, `maxLength: 128` |
| `outcome` | string | `ready_for_review`, `blocked` oder `incomplete` |
| `changed_paths` | array | Geänderte Dateipfade (repository-relativ, eindeutig) |
| `deleted_paths` | array | Gelöschte Dateipfade (repository-relativ, eindeutig) |
| `claims_addressed` | array | Adressierte Claim-IDs aus dem Task-Vertrag, mindestens 1 |
| `evidence_produced` | array | Erzeugte Evidenz-Dateipfade (müssen im Repository existieren) |
| `missing_evidence` | array | Erwartete, aber nicht produzierte Evidenzen |
| `validation_results` | array | Ergebnisse der Required-Validation-Commands (eindeutig per Command) |
| `blockers` | array | Blockierende Issues bei `outcome: blocked` |
| `residual_gaps` | array | Bekannte, tolerierte Lücken (darf bei `ready_for_review` nicht leer und trotzdem `outcome` ändern) |

## Outcome-Regeln

| Outcome | Voraussetzungen |
|---|---|
| `ready_for_review` | Keine Blocker, keine `missing_evidence`, alle Required-Commands `passed` |
| `blocked` | Mindestens ein Eintrag in `blockers` |
| `incomplete` | Mindestens eine ungelöste Claim, fehlende Evidence, nicht-bestandene Validation oder Residual-Gap |

## Validierungslogik

Die Validierung erfolgt in `scripts/agent/validate_handoff.py` und nutzt `scripts/agent/json_contract.py` für strictes JSON-Laden und deterministische Schema-Prüfung:

1. **Strict JSON**: Doppelte Keys und nicht-standard Konstanten (NaN, Infinity) werden sofort abgelehnt.
2. **Schema-Check**: Task und Handoff werden gegen ihre jeweiligen JSON-Schemas geprüft.
3. **Claim-Registry-Check**: Alle Task-Claims müssen im Claim-Registry vorhanden und adressiert sein.
4. **Binding-Check**: `task_id` und `task_contract_sha256` müssen übereinstimmen.
5. **Scope-Check**: `changed_paths` und `deleted_paths` müssen innerhalb der `allowed_paths` des Tasks liegen.
6. **Evidence-Check**: `evidence_produced`-Dateien müssen im Repository existieren.
7. **Outcome-Check**: `outcome` muss mit den tatsächlichen Ergebnissen übereinstimmen.

## Fehlercode-Referenz

| Code | Bedeutung |
|---|---|
| `TASK_SCHEMA_INVALID` | Task-Vertrag entspricht nicht `task.schema.json` |
| `HANDOFF_SCHEMA_INVALID` | Handoff entspricht nicht `handoff.schema.json` |
| `TASK_ID_MISMATCH` | `task_id` stimmt nicht mit Task überein |
| `TASK_DIGEST_MISMATCH` | `task_contract_sha256` entspricht nicht dem Task-Datei-Digest |
| `PATH_OUT_OF_REPO` | Pfad verlässt das Repository-Verzeichnis |
| `PATH_OUT_OF_SCOPE` | Pfad liegt außerhalb der `allowed_paths` |
| `FORBIDDEN_PATH` | Pfad ist in `forbidden_paths` des Tasks verboten |
| `PATH_STATE_CONTRADICTION` | Pfad ist gleichzeitig in `changed_paths` und `deleted_paths` |
| `DELETE_WITHOUT_PERMISSION` | `deleted_paths` nicht leer, obwohl `delete_allowed: false` |
| `CLAIM_NOT_DECLARED` | Adressierter Claim nicht im Task deklariert |
| `CLAIM_NOT_ADDRESSED` | Task-Claim nicht im Handoff adressiert |
| `EXPECTED_EVIDENCE_UNACCOUNTED` | Erwartete Evidence weder produziert noch als fehlend deklariert |
| `EVIDENCE_NOT_FOUND` | Produzierte Evidence-Datei existiert nicht im Repository |
| `EVIDENCE_PATH_INVALID` | Evidence-Pfad ist kein gültiger repository-relativer Dateipfad |
| `EVIDENCE_STATE_CONTRADICTION` | Evidence gleichzeitig in `evidence_produced` und `missing_evidence` |
| `VALIDATION_RESULT_MISSING` | Required-Command hat kein Ergebnis |
| `VALIDATION_RESULT_DUPLICATE` | Command mehrfach in `validation_results` |
| `CONTRADICTORY_OUTCOME` | `outcome` widerspricht den tatsächlichen Ergebnissen |

## Fixture-Verwaltung

Der SHA-256-Digest der Task-Datei ist in allen Digest-Fixtures (`handoff-valid.json`, `handoff-valid-residual-gap.json`, `handoff-invalid-path.json`) als `task_contract_sha256` gespeichert. Nach Änderungen an `tests/fixtures/agent/handoff-task.json` muss `scripts/agent/update_handoff_fixtures.py --write` ausgeführt werden. CI prüft mit `--check`.

## Beispiel-Fixture

Siehe [`tests/fixtures/agent/handoff-valid.json`](../../tests/fixtures/agent/handoff-valid.json) für ein vollständiges, valides Beispiel.
