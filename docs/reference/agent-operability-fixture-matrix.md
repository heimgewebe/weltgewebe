---
id: docs.reference.agent-operability-fixture-matrix
title: Agent-Betriebsfaehigkeit: Fixture-Matrix
doc_type: reference
status: active
summary: Fixture-Matrix fuer AGENT-SAFE-004 Task-Contracts und den Non-Ideal-Guard.
relations:
  - type: relates_to
    target: contracts/agent/task.schema.json
  - type: relates_to
    target: scripts/agent/check_non_ideal_task.py
  - type: relates_to
    target: scripts/agent/tests/test_check_non_ideal_task.py
---

# Agent-Betriebsfaehigkeit: Fixture-Matrix

## Zweck

Diese Matrix dokumentiert die AGENT-SAFE-004 Fixtures fuer minimale Agent-Contracts
und den Non-Ideal-Task-Guard.

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

## Offene Luecken

- Kein Dry-Run Runner in diesem Slice.
- Kein Write Mode in diesem Slice.
- Kein Handoff Validator in diesem Slice.
- Kein Blocking-CI in diesem Slice.
