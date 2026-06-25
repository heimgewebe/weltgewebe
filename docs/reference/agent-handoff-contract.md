---
id: docs.reference.agent-handoff-contract
title: "Agent Handoff Contract"
doc_type: reference
status: active
summary: "Maschinenlesbares Übergabeformat für Agent-Task-Handoffs."
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

Das Handoff ist die maschinenlesbare Übergabe nach einer Agent-Task. Es bindet
Ergebnis, Pfade, Claims, Evidence und Validierungsresultate an den Task-Vertrag.
Es ist ein Review-Beleg, keine Merge- oder Done-Freigabe.

## Schema

Das kanonische Schema liegt in
[`contracts/agent/handoff.schema.json`](../../contracts/agent/handoff.schema.json).
AJV und `scripts/agent/json_contract.py` prüfen dieselben Draft-07-Assertions.

## Pflichtfelder

| Feld | Bedeutung |
|---|---|
| `handoff_id` | Eindeutige Handoff-ID |
| `task_id` | Muss zum Task-Vertrag passen |
| `task_contract_sha256` | SHA-256 der exakten Task-Dateibytes |
| `source_revision` | Syntaktisch gültige Git-Revision |
| `producer` | Kennung des produzierenden Agents |
| `outcome` | `ready_for_review`, `blocked` oder `incomplete` |
| `changed_paths` | Geänderte repository-relative Dateien |
| `deleted_paths` | Gelöschte repository-relative Dateien |
| `claims_addressed` | Bilanzierte Task-Claims |
| `evidence_produced` | Erzeugte lokale Evidence-Dateien |
| `missing_evidence` | Erwartete, aber nicht produzierte Evidence |
| `validation_results` | Resultate der Pflichtvalidierungen |
| `blockers` | Blockierende Einträge |
| `residual_gaps` | Bekannte tolerierte Restlücken. Sie dürfen bei `ready_for_review` befüllt sein, sofern sie keine Pflicht-Evidence, Claim-Abdeckung oder bestandene Pflichtvalidierung ersetzen. |

## Task-Bindung

`task_contract_sha256` bindet die exakten Bytes der Task-Datei; Zeilenenden
werden beim Hashing nicht normalisiert. Die repository-eigenen JSON-Contracts
und Agent-Fixtures werden über `.gitattributes` mit LF ausgecheckt. Jede
Byteänderung, einschließlich einer Zeilenendenänderung, macht einen bestehenden
Handoff absichtlich ungültig.

## Outcome-Regeln

| Outcome | Voraussetzungen |
|---|---|
| `ready_for_review` | Alle Obligationen sind bilanziert; keine Blocker oder fehlende Evidence; alle Pflichtvalidierungen sind `passed`. Nicht blockierende Restlücken sind erlaubt. |
| `blocked` | Mindestens ein Eintrag in `blockers` |
| `incomplete` | Alle Obligationen bleiben ausdrücklich bilanziert, aber erwartete Evidence fehlt, eine aufgeführte Validierung ist `failed` oder `not_run`, oder ein Rest-Gap rechtfertigt die Einstufung. |

Bloß ausgelassene Pflichtclaims oder Pflichtresultate sind kein gültiges
`incomplete`. Sie bleiben harte Findings. Ihre Berücksichtigung im
Outcome-Zweig verhindert lediglich ein redundantes zusätzliches
`CONTRADICTORY_OUTCOME`.

## Scope-Regeln

`allowed_paths` müssen konkrete repository-relative Dateien oder Verzeichnisse
benennen. `"."`, `""`, `"/"` und vergleichbare repository-weite Scopes sind
nicht zulässig und werden durch den Non-Ideal-Guard als `SCOPE_TOO_BROAD`
abgelehnt. Globale Prüfkommandos dürfen weiterhin ausgeführt werden; ein
repository-weiter Linter begründet keinen globalen Schreibscope.

## Validierungslogik

1. Doppelte JSON-Keys und NaN/Infinity-Konstrukte werden abgelehnt.
2. Task und Handoff werden gegen ihre kanonischen Schemas geprüft.
3. Task-Claims müssen registriert und im Handoff bilanziert sein.
4. Task-ID und SHA-256-Digest müssen übereinstimmen.
5. Geänderte und gelöschte Pfade müssen im Task-Scope liegen.
6. Produzierte Evidence muss lokal existieren.
7. `missing_evidence` muss eine Teilmenge von `expected_evidence` sein.
8. Das Outcome muss zur vollständig bilanzierten Lage passen.

## Fehlercodes

| Code | Bedeutung |
|---|---|
| `TASK_SCHEMA_INVALID` | Task verletzt sein Schema |
| `HANDOFF_SCHEMA_INVALID` | Handoff verletzt sein Schema |
| `TASK_ID_MISMATCH` | Task-ID stimmt nicht überein |
| `TASK_DIGEST_MISMATCH` | Task-Digest stimmt nicht überein |
| `PATH_OUT_OF_REPO` | Pfad verlässt das Repository |
| `PATH_OUT_OF_SCOPE` | Pfad liegt außerhalb des erlaubten Scopes |
| `FORBIDDEN_PATH` | Pfad ist ausdrücklich verboten |
| `PATH_STATE_CONTRADICTION` | Pfad ist zugleich geändert und gelöscht |
| `DELETE_WITHOUT_PERMISSION` | Löschung ist nicht erlaubt |
| `CLAIM_NOT_DECLARED` | Adressierter Claim steht nicht im Task |
| `CLAIM_NOT_ADDRESSED` | Task-Claim wurde nicht bilanziert |
| `EXPECTED_EVIDENCE_UNACCOUNTED` | Erwartete Evidence ist nicht bilanziert |
| `UNEXPECTED_MISSING_EVIDENCE` | Als fehlend gemeldete Evidence wurde nicht erwartet |
| `EVIDENCE_NOT_FOUND` | Produzierte Evidence existiert nicht lokal |
| `EVIDENCE_PATH_INVALID` | Evidence-Pfad ist ungültig |
| `EVIDENCE_STATE_CONTRADICTION` | Evidence ist zugleich produziert und fehlend |
| `VALIDATION_RESULT_MISSING` | Pflichtresultat fehlt |
| `VALIDATION_RESULT_DUPLICATE` | Validierungsbefehl wurde mehrfach gemeldet |
| `CONTRADICTORY_OUTCOME` | Outcome widerspricht der bilanzierten Lage |

CLI-Eingabefehler und kaputte Contract-Schemas liefern stabile Fehlercodes mit
Exitcode `2`. Fehlercodes werden nicht aus frei formulierten Exception-Texten
abgeleitet.

## Fixtures

Die Negativ-Fixtures unterscheiden sich vom gültigen Handoff jeweils in genau
einem Feld:

- `handoff-invalid-digest.json` → `TASK_DIGEST_MISMATCH`
- `handoff-invalid-path.json` → `PATH_OUT_OF_REPO`
- `handoff-invalid-outcome.json` → `CONTRADICTORY_OUTCOME`

`handoff-valid-residual-gap.json` belegt die zulässige Reviewfähigkeit mit einer
transparenten, nicht blockierenden Restlücke.

Der Task-Digest der gebundenen Fixtures wird durch
`scripts/agent/update_handoff_fixtures.py --check` überwacht.
