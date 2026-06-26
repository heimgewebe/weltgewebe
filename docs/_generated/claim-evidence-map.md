---
id: docs.generated.claim-evidence-map
title: Claim Evidence Map
doc_type: generated
status: active
summary: Automatisch generierte Claim-Evidence-Map (Lenskit Bridge).
---

# Claim Evidence Map

Generated automatically. Do not edit.

| id | doc | locator | status | owner | last_verified | evidence |
| --- | --- | --- | --- | --- | --- | --- |
| claim-agent-safe-001 | docs/claims/registry.yml | claims[id=CLAIM-AGENT-SAFE-001] | partial | docs-mechanik | 2026-06-05 | 4 items |
| claim-agent-safe-002 | docs/claims/registry.yml | claims[id=CLAIM-AGENT-SAFE-002] | partial | docs-mechanik | 2026-06-05 | 3 items |
| claim-agent-safe-003 | docs/claims/registry.yml | claims[id=CLAIM-AGENT-SAFE-003] | partial | docs-mechanik | 2026-06-05 | 4 items |
| claim-agent-safe-005 | docs/claims/registry.yml | claims[id=CLAIM-AGENT-SAFE-005] | partial | docs-mechanik | 2026-06-26 | 8 items |
| claim-agent-safe-006 | docs/claims/registry.yml | claims[id=CLAIM-AGENT-SAFE-006] | partial | docs-mechanik | 2026-06-26 | 7 items |

## Details

### CLAIM-AGENT-SAFE-001

- Entry: `claim-agent-safe-001`
- Locator: `claims[id=CLAIM-AGENT-SAFE-001]`
- Status: `partial`
- Owner: `docs-mechanik`
- Last verified: `2026-06-05`

Evidence:

| Kind | Target |
| ---- | ------ |
| `file` | `scripts/agent/check_agent_preflight.py` |
| `test` | `scripts/agent/tests/test_check_agent_preflight.py` |
| `file` | `.github/workflows/agent-safety-preflight.yml` |
| `file` | `docs/security/agent-write-scope-baseline.md` |

Does not prove:

- A green verify does not prove the claims are true or complete, only that no declared claim contradicts its declared evidence.

### CLAIM-AGENT-SAFE-002

- Entry: `claim-agent-safe-002`
- Locator: `claims[id=CLAIM-AGENT-SAFE-002]`
- Status: `partial`
- Owner: `docs-mechanik`
- Last verified: `2026-06-05`

Evidence:

| Kind | Target |
| ---- | ------ |
| `file` | `scripts/docmeta/generate_agent_readiness.py` |
| `test` | `scripts/docmeta/tests/test_generate_agent_readiness.py` |
| `file` | `docs/_generated/agent-readiness.md` |

Does not prove:

- A green verify does not prove the claims are true or complete, only that no declared claim contradicts its declared evidence.

### CLAIM-AGENT-SAFE-003

- Entry: `claim-agent-safe-003`
- Locator: `claims[id=CLAIM-AGENT-SAFE-003]`
- Status: `partial`
- Owner: `docs-mechanik`
- Last verified: `2026-06-05`

Evidence:

| Kind | Target |
| ---- | ------ |
| `file` | `docs/claims/registry.yml` |
| `file` | `docs/claims/README.md` |
| `file` | `scripts/docmeta/validate_claim_registry.py` |
| `test` | `scripts/docmeta/tests/test_validate_claim_registry.py` |

Does not prove:

- A green verify does not prove the claims are true or complete, only that no declared claim contradicts its declared evidence.

### CLAIM-AGENT-SAFE-005

- Entry: `claim-agent-safe-005`
- Locator: `claims[id=CLAIM-AGENT-SAFE-005]`
- Status: `partial`
- Owner: `docs-mechanik`
- Last verified: `2026-06-26`

Evidence:

| Kind | Target |
| ---- | ------ |
| `file` | `contracts/agent/handoff.schema.json` |
| `file` | `scripts/agent/json_contract.py` |
| `file` | `scripts/agent/validate_handoff.py` |
| `file` | `scripts/contracts-agent-check.sh` |
| `test` | `scripts/agent/tests/test_validate_handoff.py` |
| `file` | `docs/reference/agent-operability-fixture-matrix.md` |
| `file` | `.github/workflows/agent-safety-preflight.yml` |
| `file` | `.github/workflows/contracts-validate.yml` |

Does not prove:

- A green verify does not prove the claims are true or complete, only that no declared claim contradicts its declared evidence.

### CLAIM-AGENT-SAFE-006

- Entry: `claim-agent-safe-006`
- Locator: `claims[id=CLAIM-AGENT-SAFE-006]`
- Status: `partial`
- Owner: `docs-mechanik`
- Last verified: `2026-06-26`

Evidence:

| Kind | Target |
| ---- | ------ |
| `file` | `scripts/agent/run_task.py` |
| `test` | `scripts/agent/tests/test_run_task.py` |
| `file` | `scripts/docmeta/generate_agent_readiness.py` |
| `test` | `scripts/docmeta/tests/test_generate_agent_readiness.py` |
| `test` | `scripts/docmeta/tests/test_agent_readiness_smoke_contract.py` |
| `file` | `.github/workflows/agent-safety-preflight.yml` |
| `file` | `docs/reference/agent-dry-run-runner.md` |

Does not prove:

- A green verify does not prove the claims are true or complete, only that no declared claim contradicts its declared evidence.
