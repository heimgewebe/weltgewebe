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
- **Reason:** Hard capabilities are still missing: claim_evidence_spine, agent_contracts, handoff_validation, non_ideal_guard, dry_run_runner

## Capability Matrix

| Capability | Status | Hard | Evidence | Missing | Rationale |
|---|---|---:|---|---|---|
| agent_policy | pass | no | `AGENTS.md`, `agent-policy.yaml` | - | Agenten brauchen dokumentierte Grenzen und Schreibregeln. |
| safety_preflight | pass | no | `scripts/agent/check_agent_preflight.py`, `scripts/agent/tests/test_check_agent_preflight.py`, `.github/workflows/agent-safety-preflight.yml`, `docs/security/agent-write-scope-baseline.md` | - | Report-only Preflight schafft belastbare Baseline vor Blocking. |
| claim_evidence_spine | open | yes | - | `docs/claims/registry.yml` | Ohne Claim-Registry fehlt maschinenlesbare Evidenzbindung. |
| agent_contracts | open | yes | - | `contracts/agent/*.schema.json` | Contracts definieren maschinenlesbare Agent-Task-Grenzen. |
| handoff_validation | open | yes | - | `scripts/agent/*handoff*`, `contracts/agent/*handoff*`, `docs/**/*handoff*` | Handoff-Checks begrenzen unvollstaendige oder unsichere Uebergaben. |
| non_ideal_guard | open | yes | - | `non_ideal/non-ideal + guard artifact` | Non-Ideal-Guard erkennt riskante Ausnahmefaelle vor Ausfuehrung. |
| dry_run_runner | open | yes | - | `scripts/agent/*dry_run*runner*` | Dry-Run Runner prueft Agentenpfade ohne schreibende Seiteneffekte. |

## Residual Gaps

- Hard capability missing: claim_evidence_spine
- Hard capability missing: agent_contracts
- Hard capability missing: handoff_validation
- Hard capability missing: non_ideal_guard
- Hard capability missing: dry_run_runner

## Interpretation Rule

Dieser Report ist diagnostisch. Er aktiviert keinen Blocking-Mode.
