---
id: docs.generated.agent-readiness
title: Agent Readiness
doc_type: generated
status: active
summary: Deterministische Agent-Readiness-Matrix.
---

## Weltgewebe Agent Readiness

Generated automatically. Do not edit.

## Overall Status

- **Overall:** plan_ready
- **Reason:** Repository logic supports planning and validation. Execution relies on external operator.

## Capability Matrix

| Dimension | Capability | Status | Hard | Evidence | Missing | Rationale |
|---|---|---|---:|---|---|---|
| discover | discover | pass | yes | `agent-contract.json`, `contracts/agent/agent-contract.schema.json`, `AGENTS.md`, `scripts/agent/validate_repo_agent_contract.py`, `scripts/docmeta/agent_entrypoint_smoke.py` | - | The repository must expose a deterministic machine contract, entry card, validator, and entrypoint smoke before planning. |
| understand | agent_policy | pass | no | `AGENTS.md`, `agent-policy.yaml` | - | Agenten brauchen dokumentierte Grenzen und Schreibregeln. |
| understand | agent_contracts | pass | yes | `contracts/agent/task.schema.json` | - | Contracts definieren maschinenlesbare Agent-Task-Grenzen. |
| plan | dry_run_runner | pass | yes | `scripts/agent/run_task.py`, `scripts/agent/tests/test_run_task.py`, `tests/fixtures/agent/valid-doc-drift-task.json` | - | Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte. Required files and the canonical dry-run smoke both pass. |
| workspace | workspace | open | no | - | `external_operator_execution` | Capability resides with the external operator (Grabowski). |
| write | write | open | no | - | `external_operator_execution` | Capability resides with the external operator (Grabowski). |
| validate | safety_preflight | pass | no | `scripts/agent/check_agent_preflight.py`, `scripts/agent/tests/test_check_agent_preflight.py`, `.github/workflows/agent-safety-preflight.yml`, `docs/security/agent-write-scope-baseline.md` | - | Report-only Preflight schafft belastbare Baseline vor Blocking. |
| validate | claim_evidence_spine | pass | yes | `docs/claims/registry.yml`, `scripts/docmeta/validate_claim_registry.py` | - | Ohne Claim-Registry und Validator fehlt maschinenlesbare Evidenzbindung. |
| validate | handoff_validation | pass | yes | See Handoff Evidence | - | Handoff-Checks begrenzen unvollstaendige oder unsichere Uebergaben. Required files and the canonical CLI smoke both pass. |
| validate | non_ideal_guard | pass | yes | `scripts/agent/check_non_ideal_task.py`, `scripts/agent/tests/test_check_non_ideal_task.py` | - | Non-Ideal-Guard erkennt riskante Ausnahmefaelle vor Ausfuehrung. |
| validate | run_evidence_lite | pass | yes | `contracts/agent/validation.schema.json`, `contracts/agent/run-result.schema.json`, `scripts/agent/json_contract.py`, `scripts/agent/run_task.py`, `scripts/agent/tests/test_json_contract.py`, `scripts/agent/tests/test_run_task.py`, `scripts/agent/validate_agent_contracts.py`, `scripts/contracts-agent-check.sh`, `docs/reference/agent-run-evidence-lite.md`, `tests/fixtures/agent/validation-valid.json`, `tests/fixtures/agent/run-result-valid.json`, `tests/fixtures/agent/valid-doc-drift-task.json` | - | Erfolgreiche geplante Dry-Runs muessen ein schema-valides, task- und revisionsgebundenes Evidenzbuendel atomar publizieren. Required files and the functional persistence smoke both pass. |
| review | review | open | no | - | `external_operator_execution` | Capability resides with the external operator (Grabowski). |
| publish | publish | open | no | - | `external_operator_execution` | Capability resides with the external operator (Grabowski). |
| deploy | deploy | open | no | - | `external_operator_execution` | Capability resides with the external operator (Grabowski). |
| cleanup | cleanup | open | no | - | `external_operator_execution` | Capability resides with the external operator (Grabowski). |
| recovery | recovery | open | no | - | `external_operator_execution` | Capability resides with the external operator (Grabowski). |

## Handoff Evidence

- `contracts/agent/task.schema.json`
- `contracts/agent/handoff.schema.json`
- `scripts/agent/json_contract.py`
- `scripts/agent/check_non_ideal_task.py`
- `scripts/agent/validate_handoff.py`
- `scripts/agent/tests/test_validate_handoff.py`
- `scripts/docmeta/docmeta.py`
- `scripts/docmeta/validate_claim_registry.py`
- `docs/claims/registry.yml`
- `tests/fixtures/agent/handoff-task.json`
- `tests/fixtures/agent/handoff-valid.json`

## Residual Gaps

- No residual hard repository gaps detected.

## External Operator Dependencies

- `workspace` / `workspace`: provided by the external operator (Grabowski), not by this repository.
- `write` / `write`: provided by the external operator (Grabowski), not by this repository.
- `review` / `review`: provided by the external operator (Grabowski), not by this repository.
- `publish` / `publish`: provided by the external operator (Grabowski), not by this repository.
- `deploy` / `deploy`: provided by the external operator (Grabowski), not by this repository.
- `cleanup` / `cleanup`: provided by the external operator (Grabowski), not by this repository.
- `recovery` / `recovery`: provided by the external operator (Grabowski), not by this repository.

## Interpretation Rule

Dieser Report ist diagnostisch. Er aktiviert keinen Blocking-Mode.
`pass` bezeichnet nur die read-only Contract- und Planungsfaehigkeit der Agent-Safety-Schicht. Es bestaetigt keine Task-Ausfuehrung, keine Run-Attestierung, keine Patch-Anwendung, keinen Write Mode und keine autonome Merge-Faehigkeit.
