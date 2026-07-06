---
id: deploy.vps-migration-safe-runtime-smoke
title: VPS Migration-Safe Runtime Smoke
doc_type: runbook
status: draft
summary: Bounded wg-prod-1 runtime smoke path that may start the real API only after proving verify-applied startup migration mode.
relations:
  - type: relates_to
    target: docs/deploy/vps-http-smoke.md
  - type: relates_to
    target: docs/deploy/vps-http-route-smoke.md
  - type: relates_to
    target: docs/deploy/vps-http-route-smoke-risks.md
  - type: relates_to
    target: infra/compose/compose.vps.override.yml
  - type: relates_to
    target: scripts/ops/check_vps_migration_safe_runtime_env.py
---

# VPS Migration-Safe Runtime Smoke

This runbook defines the narrow runtime evidence path after the
`WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied` startup mode exists.

It is not route-only evidence. A real API process may start only after the
migration-mode boundary is proven. A successful run still does not prove DNS,
INWX, ACME, HTTPS, mail, SMTP, frontend, basemap, or cutover readiness.

## Decision boundary

Use `docs/deploy/vps-http-route-smoke.md` when the operation proves only Caddy
route shape and must not start the production API process.

Use this runbook only when all of the following are true:

- a fresh operator decision permits a bounded runtime smoke on `wg-prod-1`
- the selected repo commit is explicit
- starting the real API is necessary for the evidence
- database migrations are outside scope
- the selected runtime env source resolves through `services.api.env_file`
- the effective env source sets
  `WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied`
- the VPS compose override does not set that variable in
  `services.api.environment`

If any of these points is false, stop. The correct result is blocked, not an
improvised smoke.

## What this can prove

A passing migration-safe runtime smoke can prove only:

- the selected VPS checkout can start the API without applying SQLx migration SQL
- `_sqlx_migrations` contains the embedded up-migration versions as successful
  records with matching checksums
- duplicate, failed, extra, missing, pending, or checksum-mismatched migration
  history blocks startup
- selected loopback Host-header health checks pass during the approved window

It does not prove full schema semantics, app behavior, frontend readiness,
public DNS, TLS, mail, SMTP, or production cutover.

## Hard non-actions

Do not:

- publish confidential runtime values
- paste raw rendered compose output into GitHub if it contains confidential values
- change DNS, INWX, ACME, HTTPS, mail, SMTP, credentials, or provider state
- run database migrations
- use the normal API startup mode under a no-migration boundary
- close #1348 on config-only, route-only, or synthetic-upstream evidence

The recurring mistake is to treat route shape as app readiness. This runbook keeps
those evidence classes separate.

## Source-level preflight

Before any runtime start, run the narrow env/compose source-boundary probe from
the selected checkout:

```bash
python3 scripts/ops/check_vps_migration_safe_runtime_env.py \
  --compose-source infra/compose/compose.vps.override.yml \
  --env-file <selected-runtime-env-file> \
  --expected-mode verify-applied
```

If the compose file relies on `WELTGEWEBE_ENV_FILE` interpolation, either export
that variable in the operator shell or pass it explicitly without exposing
confidential values:

```bash
python3 scripts/ops/check_vps_migration_safe_runtime_env.py \
  --compose-source infra/compose/compose.vps.override.yml \
  --env-file <selected-runtime-env-file> \
  --compose-env WELTGEWEBE_ENV_FILE=<selected-runtime-env-file> \
  --expected-mode verify-applied
```

The helper checks only the allowed migration-mode key in the effective env source
and the non-confidential compose source. It does not invoke Docker, start
containers, render the full compose model, or print arbitrary runtime config.

Expected redacted shape:

```text
PASS: migration-safe runtime-smoke source boundary is proven
- checked key: WELTGEWEBE_API_STARTUP_MIGRATIONS
- observed mode: verify-applied
- service-level migration override: absent
- helper printed confidential values: no
- helper started runtime: no
```

If the effective env source is missing the key, sets it more than once, sets a
value other than `verify-applied`, or the API service sets the key in
`environment`, stop.

## Compose evidence discipline

The source-level helper is not a replacement for a separately reviewed runtime
receipt. It verifies that the selected env source is bound to the compose
`env_file` declaration and that no service-level migration-mode override is
present in the checked compose source.

The final receipt may mention that compose was rendered successfully, but it
must not paste raw rendered config or runtime env source contents. Instead record
sanitized facts:

- selected compose files
- selected Caddyfile path
- selected env source path
- whether the source-level boundary probe passed
- whether the API service has no service-level
  `WELTGEWEBE_API_STARTUP_MIGRATIONS` override
- whether the effective env source sets exactly
  `WELTGEWEBE_API_STARTUP_MIGRATIONS=verify-applied`

This deliberately orders evidence by safety. A sanitized key proof is weaker than
full config publication, but full config publication may disclose confidential
runtime values. The weaker proof is the correct one here.

## Runtime receipt requirements

If a separately approved runtime smoke is performed later, the receipt must state:

- timestamp
- host identity
- selected repo commit
- selected compose/Caddyfile/env source
- result of `check_vps_migration_safe_runtime_env.py`
- whether any container/API process was started
- API startup result under `verify-applied`
- loopback Host-header check results
- explicit non-actions for DNS, INWX, ACME, HTTPS, confidential runtime values,
  credentials, database migrations, mail, SMTP, and cutover
- explicit statement that this is migration-safe runtime evidence, not
  route-only evidence and not full production readiness

## Stop table

| Observation | Meaning | Decision |
| --- | --- | --- |
| Env key missing or duplicated in the effective source. | Effective migration mode is ambiguous. | Stop. |
| Env key is not `verify-applied`. | Normal startup may run SQLx migrations. | Stop. |
| Compose service environment sets the key. | It may override the selected env source. | Stop. |
| `--env-file` is not the effective env source for the key. | The helper would be checking the wrong file. | Stop. |
| API refuses startup on pending, failed, extra, missing, duplicate, or checksum-mismatched migration history. | `verify-applied` did its job. | Record blocked runtime evidence; do not retry with `run`. |
| Health checks pass under `verify-applied`. | Bounded runtime smoke passed. | Keep #1348 open until the receipt is reviewed against its full acceptance criteria. |
| DNS/ACME/HTTPS/mail/SMTP/confidential-value work becomes necessary. | The operation left this scope. | Stop and create a new approved operation. |
