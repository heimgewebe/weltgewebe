---
id: deploy.vps-http-route-smoke
title: VPS HTTP Route Smoke
doc_type: runbook
status: draft
summary: DNS-free route-only preflight for the VPS when the real API startup path must not run.
relations:
  - type: relates_to
    target: docs/deploy/vps-http-smoke.md
  - type: relates_to
    target: docs/deploy/vps-http-route-smoke-risks.md
  - type: relates_to
    target: infra/caddy/Caddyfile.http-smoke
  - type: relates_to
    target: infra/compose/compose.vps.override.yml
---
# VPS HTTP Route Smoke

This runbook defines a narrower evidence class than the normal VPS HTTP smoke. It exists for the case where the real API startup path is not allowed because startup database migrations are outside the operation scope.

The route-only smoke may verify the DNS-free HTTP host-header routing shape before public DNS cutover. It must not be treated as proof that the production API process, database schema, mail, SMTP, ACME, frontend build, CSP runtime, or public DNS path is ready.

## Why this is narrower than the normal HTTP smoke

The normal VPS HTTP smoke is a runtime check. It can start the compose stack and can prove live proxy-to-API readiness when that is inside the approved operation boundary.

The route-only smoke is different. Under a strict `no database migration` boundary, any path that starts the configured production API binary is out of scope when the API startup path can apply pending SQLx migrations after a configured PostgreSQL pool is available. In that situation, a retry of the normal smoke would not be a smaller proof; it would be a boundary violation.

## Claim boundary

A route-only pass may claim only:

- the intended HTTP-only smoke Caddyfile is the selected route surface
- the Caddyfile uses an explicit `http://weltgewebe.net` site address
- automatic HTTPS or ACME issuance is not requested by that smoke Caddyfile
- `/health/proxy` is locally handled by Caddy
- `/api/*` and `/health/*` are routed toward the API upstream by configuration
- non-health, non-API paths are not served as the full app by this smoke Caddyfile

A route-only pass must not claim:

- real API readiness
- `/api/health/ready` success from the production API process
- PostgreSQL connectivity or schema readiness
- absence or success of database migrations
- frontend build, CSP, asset, map, or basemap readiness
- DNS, INWX, ACME, HTTPS, mail, or SMTP readiness
- production cutover completion
- closure of an ops issue whose acceptance criteria require a live API health result

## Safety limits

During this route-only smoke:

- do not change DNS or INWX records
- do not request or force ACME or HTTPS issuance
- do not print local environment files or secrets
- do not load the production `.env` merely to prove routes
- do not start the production API binary
- do not run database migrations
- do not treat the result as production cutover evidence

## Acceptable implementation shape

A route-only implementation may be static, or it may run only a bounded proxy/config harness that cannot start the production API process.

Acceptable checks include:

- reading the selected smoke Caddyfile path
- validating that the smoke Caddyfile contains no TLS site block
- validating that the smoke Caddyfile does not serve the frontend app
- validating the expected `/health/proxy`, `/api/*`, and `/health/*` route declarations
- verifying that `infra/compose/compose.vps.override.yml` still exposes `WELTGEWEBE_CADDYFILE` as the Caddyfile selection point
- optionally adapting or validating the Caddy config without loading production secrets

For a route-only compose render, the Caddyfile selection must be explicit, for example `WELTGEWEBE_CADDYFILE=../caddy/Caddyfile.http-smoke`. The default VPS override may remain production-oriented; the route-only receipt must show that the smoke path, not the default production Caddyfile, was selected.

If a dynamic harness is added later, it must use a synthetic upstream or no upstream at all unless an explicit migration-safe API mode exists. A synthetic upstream may prove Caddy path forwarding mechanics; it must not prove real API readiness and must be reported as synthetic route evidence only.

A run that starts the real API process is no longer route-only. Under a no-migration boundary, that separate migration-safe runtime smoke must use `WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied` or a separately approved migration window. It verifies that embedded SQLx migrations are already recorded as successful in `_sqlx_migrations` and refuses to start on pending, failed, missing, or checksum-mismatched migrations. It does not apply migration SQL and it still does not prove frontend, DNS, ACME, mail, SMTP, or public cutover readiness.

## Success definition and exit criteria

A route-only smoke succeeds only if all of these conditions hold:

- the selected Caddyfile is `infra/caddy/Caddyfile.http-smoke`
- the compose/config surface selects that file explicitly through `WELTGEWEBE_CADDYFILE=../caddy/Caddyfile.http-smoke` or an equivalent non-secret path override
- the Caddyfile keeps an explicit `http://weltgewebe.net` site address
- `/health/proxy`, `/api/*`, and `/health/*` have the expected route declarations
- the Caddyfile contains no TLS, HTTPS, ACME, frontend `file_server`, or SPA fallback surface
- no production API process is started and no production `.env` is loaded just to prove routes
- the receipt uses the required route-only language below

Exit as failed or blocked if any of these conditions appears:

- the selected config is the normal production Caddyfile rather than the HTTP smoke Caddyfile
- proving routes would require starting the production API with a configured database connection outside `WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied` or a separately approved migration window
- Caddy route validation would require secrets, DNS changes, ACME, HTTPS, mail, SMTP, or production env output
- a synthetic upstream result is being treated as `/api/health/ready` from the real API
- bind/port conflicts or host-header mismatches make the route result ambiguous

## Pass/fail decision table

| Observation | Meaning | Next action |
| --- | --- | --- |
| Static route checks pass and the receipt is route-only. | Route/config drift is less likely. Real runtime readiness is still unproven. | Keep #1348 open and choose a separate runtime path. |
| Caddyfile or compose selection differs from this runbook. | Route-only proof is ambiguous or stale. | Stop and repair the docs/config boundary before any VPS retry. |
| A synthetic upstream returns 200. | Caddy forwarding mechanics may work. The Rust API was not proven. | Record as synthetic-only evidence; do not close a live-API gate. |
| The normal API would be started with `DATABASE_URL`. | The operation can run migrations and leaves the no-migration boundary. | Do not run it without a separate runtime/migration approval. |
| Any DNS, INWX, ACME, HTTPS, mail, SMTP, secret, or env-file action is needed. | The operation has left route-only scope. | Stop and create a new explicitly approved operation. |

## Required receipt language

A passing receipt must say that this was route-only evidence. It must explicitly say:

- no production API process was started
- no database migration was run
- no DNS, INWX, HTTPS, ACME, mail, or SMTP action was performed
- real API readiness remains unproven
- any issue requiring `/api/health/ready` from the real API remains open until a separate approved runtime path exists

## Decision after a pass

A route-only pass is useful as a guard against route/config drift. It is not a deploy success signal by itself.

The next step after a route-only pass must be one of:

1. schedule an explicitly approved migration/runtime window and then run the normal VPS HTTP smoke, or
2. build a separately reviewed migration-safe API health mode before attempting a live API smoke, or
3. keep the VPS runtime issue blocked and record the missing evidence.
