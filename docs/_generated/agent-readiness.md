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

- **Overall:** partial
- **Reason:** Hard capabilities are still missing: dry_run_runner

## Capability Matrix

| Capability | Status | Hard | Evidence | Missing | Rationale |
|---|---|---:|---|---|---|
| agent_policy | pass | no | `AGENTS.md`, `agent-policy.yaml` | - | Agenten brauchen dokumentierte Grenzen und Schreibregeln. |
| safety_preflight | pass | no | `scripts/agent/check_agent_preflight.py`, `scripts/agent/tests/test_check_agent_preflight.py`, `.github/workflows/agent-safety-preflight.yml`, `docs/security/agent-write-scope-baseline.md` | - | Report-only Preflight schafft belastbare Baseline vor Blocking. |
| claim_evidence_spine | pass | yes | `docs/claims/registry.yml`, `scripts/docmeta/validate_claim_registry.py` | - | Ohne Claim-Registry und Validator fehlt maschinenlesbare Evidenzbindung. |
| agent_contracts | pass | yes | `contracts/agent/task.schema.json` | - | Contracts definieren maschinenlesbare Agent-Task-Grenzen. |
| handoff_validation | pass | yes | See Handoff Evidence | - | Handoff-Checks begrenzen unvollstaendige oder unsichere Uebergaben. Required files and the canonical CLI smoke both pass. |
| non_ideal_guard | pass | yes | `scripts/agent/check_non_ideal_task.py`, `scripts/agent/tests/test_check_non_ideal_task.py` | - | Non-Ideal-Guard erkennt riskante Ausnahmefaelle vor Ausfuehrung. |
| dry_run_runner | open | yes | - | `scripts/agent/*dry_run*runner*` | Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte. |

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

- Hard capability missing: dry_run_runner

## Interpretation Rule

Dieser Report ist diagnostisch. Er aktiviert keinen Blocking-Mode.
