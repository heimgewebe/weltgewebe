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

## Runtime Contract for Static UI

Weltgewebe UI deployment fundamentally operates on three coupled layers:

1. **Build layer**: `pnpm build` produces the static artifacts in `apps/web/build`.
2. **Container mount layer**: A bind mount structurally exposes these artifacts to the `edge-caddy` container (`/srv/weltgewebe-web`).
3. **Edge serving layer**: Caddy reads and serves these static files to the client.

A successful frontend build does *not* automatically guarantee a successful deployment unless the container mount layer correctly reflects the newly built files. The complete chain (Build + Container-Mount + Edge-Serving) guarantees deployment correctness. It is an established architectural known issue that Docker container bind mounts can drift from the host directory state (meaning the container sees an empty or outdated directory despite the host having the latest files).

To enforce correct runtime state, the deploy pipeline includes an active guard. After building the UI, `weltgewebe-up` verifies that the `edge-caddy` container can genuinely read the critical build artifacts (`test -s /srv/weltgewebe-web/index.html && test -d /srv/weltgewebe-web/_app`). If this check fails, the pipeline forces a refresh of the edge deployment stack to restore the `edge-caddy` mount coupling, provided frontend delivery is required for the current deploy run.

*Note (Phase B Preparation): Inconsistent browser states can also stem from client-side caching (e.g., Cache-Control headers for HTML versus immutable assets). The server-side guards described here verify server state, but do not guarantee client cache coherence.*

*Note (Phase C Preparation): Future Evaluation: The current bind-mount model could theoretically be replaced by a dedicated Web-Container architecture to eliminate host-mount drift entirely.*

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
