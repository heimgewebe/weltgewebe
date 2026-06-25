---
id: docs.reference.agent-operability-fixture-matrix
title: Agent-Betriebsfaehigkeit: Fixture-Matrix
doc_type: reference
status: active
summary: Fixture-Matrix fuer Agent-Task-Contracts, Non-Ideal-Guard und Handoff-Validierung.
relations:
  - type: relates_to
    target: contracts/agent/task.schema.json
  - type: relates_to
    target: scripts/agent/check_non_ideal_task.py
  - type: relates_to
    target: scripts/agent/tests/test_check_non_ideal_task.py
  - type: relates_to
    target: contracts/agent/handoff.schema.json
  - type: relates_to
    target: scripts/agent/validate_handoff.py
  - type: relates_to
    target: scripts/agent/tests/test_validate_handoff.py
---

# Agent-Betriebsfaehigkeit: Fixture-Matrix

## Zweck

Diese Matrix dokumentiert die Fixtures fuer minimale Agent-Task-Contracts,
den Non-Ideal-Task-Guard und den anschliessenden Handoff-Validator.

## Valid Fixtures

| Fixture | Task-Typ | Erwartung |
|---|---|---|
| `tests/fixtures/agent/valid-doc-drift-task.json` | `doc_change` | `findings_count = 0` |
| `tests/fixtures/agent/valid-roadmap-claim-task.json` | `governance` | `findings_count = 0` |
| `tests/fixtures/agent/valid-generated-refresh-task.json` | `generated_refresh` | `findings_count = 0`; `docs/_generated/` nur via Generator-Command |

## Invalid Fixtures

| Fixture | Primarer Fehlercode | Regel |
|---|---|---|
| `tests/fixtures/agent/invalid-missing-scope.json` | `NO_ALLOWED_PATHS` | Scope darf nicht fehlen |
| `tests/fixtures/agent/invalid-missing-validation.json` | `NO_VALIDATION_COMMAND` | Validation muss explizit sein |
| `tests/fixtures/agent/invalid-missing-evidence.json` | `NO_EXPECTED_EVIDENCE` | Erwartete Evidence ist Pflicht |
| `tests/fixtures/agent/invalid-forbidden-path.json` | `FORBIDDEN_PATH` | `allowed_paths` und `forbidden_paths` duerfen nicht kollidieren |
| `tests/fixtures/agent/invalid-status-done-by-agent.json` | `STATUS_DONE_BY_AGENT` | Agent darf keinen finalen Status/Decision setzen |

## Zusaetzlich abgedeckte Guard-Codes

- `TASK_SCHEMA_INVALID` (ungueltige Struktur oder JSON)
- `CLAIM_WITHOUT_REGISTRY_ENTRY`
- `SCOPE_TOO_BROAD`
- `TASK_FILE_NOT_FOUND`
- `CLAIM_REGISTRY_NOT_FOUND`
- `CLAIM_REGISTRY_INVALID`
- `CONTRADICTION_FOUND`

## Handoff Fixtures

| Fixture | Erwartung |
|---|---|
| `tests/fixtures/agent/handoff-task.json` | gueltiger Task-Contract und Digest-Quelle |
| `tests/fixtures/agent/handoff-valid.json` | Exit `0`, `status = valid`, keine Findings |
| `tests/fixtures/agent/handoff-invalid-digest.json` | Exit `1`, `TASK_DIGEST_MISMATCH` |
| `tests/fixtures/agent/handoff-invalid-path.json` | Exit `1`, `PATH_OUT_OF_REPO` |
| `tests/fixtures/agent/handoff-invalid-outcome.json` | Exit `0`; transparente `residual_gaps` sind mit Reviewfaehigkeit vereinbar |

Die Handoff-Fixture bindet zur Rueckwaertskompatibilitaet an den bestehenden\n`AGENT-SAFE-004`-Fixture-Contract. Die produktive Capability wird als\n`AGENT-SAFE-005` gefuehrt. Der Handoff ist ein Review-Beleg, keine Merge- oder
Done-Freigabe. Der Validator prueft den kanonischen Task-Contract und den
Non-Ideal-Guard, Task-Bindung, Scope, vollstaendige Claim-Abdeckung, lokale
Evidence, Validierungsresultate und widerspruchsfreie Outcomes. Er fuehrt keine
Kommandos aus und veraendert keine Dateien. Adversariale Unit-Tests decken unter
anderem doppelte JSON-Schluessel, ungueltige Tasks, Pfadzustandswidersprueche,
erfundene Evidence und zusaetzliche fehlgeschlagene Validierungen ab.

## Offene Luecken

- Kein Dry-Run Runner in diesem Slice.
- Kein Write Mode in diesem Slice.
- Keine unabhaengige Run-Attestierung in diesem Slice.
- Keine Git-Aufloesung oder Diff-Bindung von `source_revision` in diesem Slice.

## Handoff-Vertrauensgrenze

Ein erfolgreicher Validatorlauf belegt, dass Task und Handoff ihren Contracts
entsprechen, der Task den Non-Ideal-Guard besteht, der Digest an die exakten
Task-Dateibytes bindet und Scope, Claims, lokale Evidence, Validierungsangaben
und Outcome widerspruchsfrei bilanziert sind. Er belegt nicht die tatsaechliche
Ausfuehrung der gemeldeten Kommandos, fachliche Korrektheit, Git-Diff-Bindung,
Producer-Authentizitaet oder Merge-Reife.

### Pfade und Evidence

- Pfade sind repository-relativ; absolute Pfade, `.` und `..` sind ungueltig.
- Verzeichnisscopes enden mit `/`, Dateiscopes gelten exakt, Globs und Root-Scope
  bleiben verboten.
- `changed_paths` und `deleted_paths` duerfen sich nicht ueberschneiden.
- produzierte Evidence bezeichnet lokale Dateien innerhalb des Repository-Roots.
- `task_contract_sha256` bindet exakte LF-normalisierte Repository-Dateibytes;
  das Fixture-Werkzeug erkennt Digest-Drift ohne Bypass.

### Outcomes

- `ready_for_review`: keine Blocker oder fehlende Evidence; alle Pflichtclaims
  adressiert; alle gemeldeten und geforderten Validierungen `passed`.
  Transparente Restluecken sind erlaubt.
- `blocked`: mindestens ein Blocker.
- `incomplete`: mindestens eine echte offene Position.

`source_revision` wird in diesem Slice nur syntaktisch geprueft. Run-Evidence,
Dry-Run Runner, Git-Ancestry und Write Mode bleiben spaetere Slices.
