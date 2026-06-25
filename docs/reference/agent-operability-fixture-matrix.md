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
den Non-Ideal-Task-Guard und den Handoff-Validator.

## Valid Fixtures

| Fixture | Task-Typ | Erwartung |
|---|---|---|
| `tests/fixtures/agent/valid-doc-drift-task.json` | `doc_change` | `findings_count = 0` |
| `tests/fixtures/agent/valid-roadmap-claim-task.json` | `governance` | `findings_count = 0` |
| `tests/fixtures/agent/valid-generated-refresh-task.json` | `generated_refresh` | `findings_count = 0`; `docs/_generated/` nur via Generator-Command |

## Invalid Fixtures

| Fixture | Primaerer Fehlercode | Regel |
|---|---|---|
| `tests/fixtures/agent/invalid-missing-scope.json` | `NO_ALLOWED_PATHS` | Scope darf nicht fehlen |
| `tests/fixtures/agent/invalid-missing-validation.json` | `NO_VALIDATION_COMMAND` | Validation muss explizit sein |
| `tests/fixtures/agent/invalid-missing-evidence.json` | `NO_EXPECTED_EVIDENCE` | Erwartete Evidence ist Pflicht |
| `tests/fixtures/agent/invalid-forbidden-path.json` | `FORBIDDEN_PATH` | Erlaubte und verbotene Pfade duerfen nicht kollidieren |
| `tests/fixtures/agent/invalid-status-done-by-agent.json` | `STATUS_DONE_BY_AGENT` | Agent darf keinen finalen Status setzen |

## Handoff Fixtures

| Fixture | Erwartung |
|---|---|
| `tests/fixtures/agent/handoff-task.json` | gueltiger Task-Contract und Digest-Quelle |
| `tests/fixtures/agent/handoff-valid.json` | Exit `0`, `status = valid`, keine Findings |
| `tests/fixtures/agent/handoff-invalid-digest.json` | Exit `1`; einziges Finding `TASK_DIGEST_MISMATCH`; einzige Mutation ist der Digest |
| `tests/fixtures/agent/handoff-invalid-path.json` | Exit `1`; einziges Finding `PATH_OUT_OF_REPO`; einzige Mutation ist `changed_paths` |
| `tests/fixtures/agent/handoff-invalid-outcome.json` | Exit `1`; einziges Finding `CONTRADICTORY_OUTCOME`; einzige Mutation ist `outcome: blocked` ohne Blocker |
| `tests/fixtures/agent/handoff-valid-residual-gap.json` | Exit `0`; transparente nicht blockierende `residual_gaps` sind reviewfaehig |

Die Negativ-Fixtures sind vollstaendige Handoffs und unterscheiden sich vom
gueltigen Fixture jeweils in genau einem Feld. Dadurch belegt jedes Fixture
einen einzelnen Validatorpfad statt nur die Anwesenheit irgendeines Fehlers.

Die Handoff-Fixtures verwenden weiterhin den bestehenden
`AGENT-SAFE-004`-Task-Contract. Die produktive Capability wird als
`AGENT-SAFE-005` gefuehrt. Der Handoff ist ein Review-Beleg, keine Merge- oder
Done-Freigabe.

## Evidence-Regeln

- produzierte Evidence bezeichnet lokale Dateien innerhalb des Repository-Roots.
- `missing_evidence` darf nur Pfade aus `expected_evidence` enthalten.
- Erwartete Evidence muss entweder produziert oder ausdruecklich als fehlend
  bilanziert sein.
- Derselbe normalisierte Pfad darf nicht zugleich produziert und fehlend sein.

## Outcome-Regeln

- `ready_for_review`: keine Blocker oder fehlende Evidence; alle Pflichtclaims
  sind adressiert und alle Pflichtvalidierungen sind `passed`.
  Nicht blockierende Restluecken sind erlaubt.
- `blocked`: mindestens ein Blocker.
- `incomplete`: alle Obligationen bleiben ausdruecklich bilanziert, aber
  erwartete Evidence fehlt, eine aufgefuehrte Validierung ist `failed` oder
  `not_run`, oder ein Rest-Gap rechtfertigt die Einstufung.
- Ausgelassene Pflichtclaims oder Pflichtresultate bleiben harte Findings und
  sind kein gueltiges Mittel, um `incomplete` zu erklaeren.

## Offene Luecken

- Kein Dry-Run Runner in diesem Slice.
- Kein Write Mode in diesem Slice.
- Keine unabhaengige Run-Attestierung in diesem Slice.
- Keine Git-Aufloesung oder Diff-Bindung von `source_revision` in diesem Slice.

## Vertrauensgrenze

Ein erfolgreicher Validatorlauf belegt Contract-Konformitaet, Task-Digest,
Scope, Claim-Bilanz, lokale Evidence-Bilanz, gemeldete Validierungsresultate und
ein dazu passendes Outcome. Er belegt nicht die tatsaechliche Ausfuehrung der
gemeldeten Kommandos, fachliche Korrektheit, Producer-Authentizitaet oder
Merge-Reife.

`source_revision` wird in diesem Slice nur syntaktisch geprueft. Run-Evidence,
Dry-Run Runner, Git-Ancestry und Write Mode bleiben spaetere Slices.
