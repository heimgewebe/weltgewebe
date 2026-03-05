---
id: deployment-contract
title: Deployment Contract and Preflight Guard
role: norm
status: active
last_reviewed: "2024-03-05"
---

## Required runtime artifacts

Production deploys assume these runtime artifacts exist:

- `policies/limits.yaml` (API policy configuration)
- Frontend build directory, specifically `apps/web/build/index.html` (and `_app/`)

## Preflight guard

`scripts/weltgewebe-up` runs `scripts/preflight/runtime_contract.sh` before `docker compose up`.
If required artifacts are missing, the deploy aborts early to prevent runtime failures (e.g. API readiness 503 and whitepage).
