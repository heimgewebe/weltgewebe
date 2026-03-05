---
id: deployment-contract
title: Deployment Contract and Preflight Guard
role: norm
status: active
last_reviewed: "2026-03-05"
---

## Required runtime artifacts

Production deploys assume the following runtime artifacts exist.

Always required:

- `policies/limits.yaml`

Conditionally required (when the frontend is deployed):

- `apps/web/build/index.html`
- `apps/web/build/_app`

## Preflight guard

`scripts/weltgewebe-up` runs `scripts/preflight/runtime_contract.sh` before `docker compose up`.

The guard validates required artifacts and aborts the deployment early if mandatory runtime contracts are violated.

## CSP contract

The production frontend currently contains an inline bootstrap `<script>` (SvelteKit).
Therefore the served `Content-Security-Policy` must allow that inline script, either via:

- `script-src 'unsafe-inline'` (pragmatic), or
- a nonce/hash-based CSP (preferred hardening, follow-up work).

The preflight `scripts/preflight/csp_contract.sh` fails deploys early if an inline script is present
but the CSP forbids it (to prevent a whitepage).
