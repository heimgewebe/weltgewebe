---
id: deployment-runtime-artifacts
role: reality
status: canonical
last_reviewed: 2023-10-25
verifies_with:
  - scripts/preflight/runtime_contract.sh
---

# Deployment Governance: Required Runtime Artifacts

This document extends deployment governance to explicitly outline the artifacts required for a successful and healthy
production deployment.

## Required Runtime Artifacts

The deployment currently assumes that runtime artifacts exist and enforces them during the preflight deployment
checks.

The following artifacts must be present:

- `policies/limits.yaml`: Used by the API container for runtime policy configuration.
- `frontend build directory`: The production build of the frontend, specifically `apps/web/build/index.html`.

If these artifacts are missing, the preflight guard will fail the deployment early to prevent implicit
runtime assumptions from turning into explicit runtime failures (such as the API healthcheck failing
and rendering a whitepage on the frontend).
