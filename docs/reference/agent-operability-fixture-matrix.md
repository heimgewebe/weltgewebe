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
  - type: relates_to
    target: scripts/agent/run_task.py
  - type: relates_to
    target: scripts/agent/tests/test_run_task.py
---

# Agent-Betriebsfaehigkeit: Fixture-Matrix

## Zweck

Diese Matrix dokumentiert die Fixtures fuer minimale Agent-Task-Contracts,
den Non-Ideal-Task-Guard, den Handoff-Validator und den read-only
Dry-Run-Runner.

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

## Dry-Run Runner Fixtures

| Fixture | Erwartung |
|---|---|
| `tests/fixtures/agent/valid-doc-drift-task.json` | Exit `0`; `status = planned`; `execution_plan` ist nur Scope-Bilanz; Handoff `incomplete`; alle Validierungen `not_run`; keine Repository-Aenderung |
| `tests/fixtures/agent/valid-roadmap-claim-task.json` | Exit `0`; Claims und erwartete Evidence werden bilanziert; keine Task-Kommandos werden ausgefuehrt |
| `tests/fixtures/agent/valid-generated-refresh-task.json` | Exit `0`; Generator-Command bleibt `not_run`; `docs/_generated/agent-readiness.md` wird nicht durch den Runner veraendert |

Der Runner liest die Task-Datei als Raw Bytes, bindet den SHA-256-Digest an das
Handoff und nutzt den echten lokalen `HEAD` in CLI-Laeufen. Tests injizieren die
Source Revision im Core, damit keine oeffentlichen Fake-Flags entstehen.

## Dry-Run Negative Gegenwelten

Die Runner-Tests decken insbesondere ab:

- malformed JSON, Duplicate Keys, `NaN`, `Infinity` und ungueltiges UTF-8
- fehlende Pflichtfelder und whitespace-only Pflichtwerte
- Non-Ideal-Tasks und unbekannte Claims
- absolute Task-Pfade, Parent-Traversal und Task-Symlinks aus dem Repository
- fehlenden Git-`HEAD`
- ungueltiges `--write`
- Output-Ziele im Repository, Symlinks, nicht leere Verzeichnisse und vorhandene Zieldateien
- simulierten Repository-Drift waehrend des Dry Runs
- ungueltig erzeugte Handoffs
- unvollstaendige Evidence- und Validierungsbilanz

Die Determinismus-Tests fuehren denselben Task mit derselben Source Revision in
zwei getrennte externe Output-Verzeichnisse aus und vergleichen `handoff.json`
und `run-result.json` bytegleich.

## Functional Readiness Smoke

`dry_run_runner = pass` entsteht nicht mehr durch Dateinamen. Der
Readiness-Generator fuehrt einen echten Runner-Smoke aus, prueft Strict-JSON,
`mode = dry_run`, `status = planned`, leere Findings, `repository_unchanged`,
ein vorhandenes Handoff, Handoff-Validator-Akzeptanz, `outcome = incomplete`,
vollstaendige `not_run`-Validierungen und einen unveraenderten
inhaltssensitiven Git-Zustandsfingerabdruck.

Explizite False-Green-Gegenwelten pruefen passend benannte Placeholder-Dateien,
ungueltiges JSON, falschen Modus, falschen Status, fehlendes oder ungueltiges
Handoff, `ready_for_review`, faelschlich bestandene Validierungen,
`repository_unchanged = false`, persistente Git-Zustandsdrift und Timeout.

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

- Keine Task-Command-Ausfuehrung in diesem Slice.
- Keine echte Kontextakquise in diesem Slice.
- Kein echter Patch-Plan in diesem Slice.
- Kein persistentes Run-Archiv und keine unabhaengige Run-Attestierung in diesem Slice.
- Kein Write Mode in diesem Slice.
- Keine Git-Ancestry- oder Diff-Bindung von `source_revision` in diesem Slice.

## Vertrauensgrenze

Ein erfolgreicher Validatorlauf belegt Contract-Konformitaet, Task-Digest,
Scope, Claim-Bilanz, lokale Evidence-Bilanz, gemeldete Validierungsresultate und
ein dazu passendes Outcome. Er belegt nicht die tatsaechliche Ausfuehrung der
gemeldeten Kommandos, fachliche Korrektheit, Producer-Authentizitaet oder
Merge-Reife.

`source_revision` wird im Runner-v1 nur als tatsaechlicher lokaler `HEAD`
aufgeloest und syntaktisch gebunden. Run-Evidence, Git-Ancestry, Diff-Bindung
und Write Mode bleiben spaetere Slices.
