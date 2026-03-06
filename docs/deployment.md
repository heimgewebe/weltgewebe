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

The static preflight `scripts/preflight/csp_contract_static.sh` parses the Caddyfile and the compiled `index.html` to
fail deploys early if an inline script is present but the CSP forbids it. This prevents a whitepage without relying on
a running server.

### Caddyfile Source of Truth

In Heimserver environments, the Caddy container actively mounts a host path (e.g., `/opt/heimgewebe/edge/Caddyfile`)
as its configuration (`/etc/caddy/Caddyfile`). The canonical repository template is `infra/caddy/Caddyfile.heim`.

It is the operator's responsibility to ensure the deployed Caddyfile is synchronized with the repository template.
To ensure the CSP contract is valid, `scripts/weltgewebe-up` explicitly resolves and evaluates the active deployment
target file (e.g., the mounted host path) rather than the repository template, guaranteeing the validation guard tests
the exact configuration that governs the running container.
