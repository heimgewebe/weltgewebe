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

- **Overall:** pass
- **Reason:** All capabilities declared in the readiness matrix passed their configured checks.

## Capability Matrix

| Capability | Status | Hard | Evidence | Missing | Rationale |
|---|---|---:|---|---|---|
| agent_policy | pass | no | `AGENTS.md`, `agent-policy.yaml` | - | Agenten brauchen dokumentierte Grenzen und Schreibregeln. |
| safety_preflight | pass | no | `scripts/agent/check_agent_preflight.py`, `scripts/agent/tests/test_check_agent_preflight.py`, `.github/workflows/agent-safety-preflight.yml`, `docs/security/agent-write-scope-baseline.md` | - | Report-only Preflight schafft belastbare Baseline vor Blocking. |
| claim_evidence_spine | pass | yes | `docs/claims/registry.yml`, `scripts/docmeta/validate_claim_registry.py` | - | Ohne Claim-Registry und Validator fehlt maschinenlesbare Evidenzbindung. |
| agent_contracts | pass | yes | `contracts/agent/task.schema.json` | - | Contracts definieren maschinenlesbare Agent-Task-Grenzen. |
| handoff_validation | pass | yes | See Handoff Evidence | - | Handoff-Checks begrenzen unvollstaendige oder unsichere Uebergaben. Required files and the canonical CLI smoke both pass. |
| non_ideal_guard | pass | yes | `scripts/agent/check_non_ideal_task.py`, `scripts/agent/tests/test_check_non_ideal_task.py` | - | Non-Ideal-Guard erkennt riskante Ausnahmefaelle vor Ausfuehrung. |
| dry_run_runner | pass | yes | `scripts/agent/run_task.py`, `scripts/agent/tests/test_run_task.py`, `tests/fixtures/agent/valid-doc-drift-task.json` | - | Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte. Required files and the canonical dry-run smoke both pass. |
| run_evidence_lite | pass | yes | `contracts/agent/validation.schema.json`, `contracts/agent/run-result.schema.json`, `scripts/agent/run_task.py`, `scripts/agent/tests/test_run_task.py`, `scripts/agent/validate_agent_contracts.py`, `scripts/contracts-agent-check.sh`, `docs/reference/agent-run-evidence-lite.md`, `tests/fixtures/agent/valid-doc-drift-task.json` | - | Erfolgreiche geplante Dry-Runs muessen ein schema-valides, task- und revisionsgebundenes Evidenzbuendel atomar publizieren. Required files and the functional persistence smoke both pass. |

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

- No residual hard gaps detected.

## Interpretation Rule

Dieser Report ist diagnostisch. Er aktiviert keinen Blocking-Mode.
`pass` bezeichnet nur die read-only Contract- und Planungsfaehigkeit der Agent-Safety-Schicht. Es bestaetigt keine Task-Ausfuehrung, keine Run-Attestierung, keine Patch-Anwendung, keinen Write Mode und keine autonome Merge-Faehigkeit.
