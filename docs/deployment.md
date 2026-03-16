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

A successful frontend build does *not* automatically guarantee a successful deployment unless the container mount layer correctly reflects the newly built files. The complete chain (Build + Container-Mount + Edge-Serving) is necessary for server-side deployment correctness. It is a known issue with Docker bind mounts that they can drift from the host directory state (meaning the container sees an empty or outdated directory despite the host having the latest files).

To enforce correct runtime state, the deploy pipeline includes an active guard. After building the UI, `weltgewebe-up` verifies that the `edge-caddy` container can genuinely read the critical build artifacts (`test -s /srv/weltgewebe-web/index.html && test -d /srv/weltgewebe-web/_app`). If this check fails, the pipeline forces a refresh of the edge deployment stack to restore the `edge-caddy` mount coupling, provided frontend delivery is required for the current deploy run.

> **Note on Verification**: The deployment script infers the need for frontend validation dynamically (e.g. from `ENABLE_CADDY`). For deterministic testing or reproducible diagnostic runs, the environment variable `REQUIRE_FRONTEND=1` can be explicitly set to force the script into the frontend validation path regardless of the detected infrastructure state.

### Client-Cache-Kohärenz

Server-side correctness does not intrinsically prevent browsers from rendering stale application states due to aggressive caching. To reduce client divergence and make cache behavior deterministic at the delivery layer, the infrastructure implements distinct caching strategies based on the asset type:

1. **Revalidating Routing (HTML/Root)**: Core HTML entrypoints (e.g. `index.html`, `/map`) strictly use `Cache-Control: no-cache, must-revalidate` to ensure browsers always check for the latest application shell upon load.
2. **Aggressive Caching (Immutable Assets)**: Hashed internal assets located under `/_app/immutable/` are served with `Cache-Control: public, max-age=31536000, immutable`.
3. **Build Diagnosis**: When present, `/_app/version.json` provides a machine-readable build identifier capable of diagnosing client-vs-server build discrepancies.
   - **Client-visible diagnostics**: The technical build identifier is also shown directly in the Settings UI.
   - **Primary use**: Enables immediate comparison of delivered versions across clients (for example, Browser A vs. Browser B).

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
