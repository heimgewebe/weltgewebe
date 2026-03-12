---
id: deployment-contract
title: Deployment Contract and Preflight Guard
doc_type: guide
status: active
canonicality: canonical
summary: Anleitung und Dokumentation zum Deployment.
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

In Heimserver environments, the Heimserver's Edge-Caddy acts as the primary reverse proxy and frontdoor, meaning
`infra/caddy/Caddyfile.heim` strictly serves as a repository-internal reference for the expected routing.

It is an architectural invariant that the actively deployed Edge-Caddyfile (e.g., in `/opt/heimgewebe/edge/Caddyfile`)
remains synchronized with the repository's reference proxy routing.
To ensure the CSP contract is valid, `scripts/weltgewebe-up` explicitly
resolves and evaluates the active deployment target file (e.g., the mounted host path) rather than the repository
template, guaranteeing the validation guard tests the exact configuration that governs the running container.

## Postflight Guards & Failure Bundles

After launching the stack, `weltgewebe-up` executes a series of Integration Guards
(verifying DNS, container health, and proxy routes).
If these critical assertions fail, the script fails hard and automatically generates a diagnostic `Failure Bundle`
(symlinked to `/tmp/weltgewebe-deploy-failure`) capturing the precise Docker state, logs,
and curl outputs to aid debugging without relying on manual archaeology.

## Future Work

- [ ] Add missing tests for the deploy-hardening guards introduced with `weltgewebe-up`.
