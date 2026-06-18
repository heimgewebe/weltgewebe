---
id: reports.domain-postgres-instance-coherence-decision
title: "Domain PostgreSQL Instance Coherence Decision — DOMAIN-PG-002"
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: DOMAIN-PG-002
review_after: 2026-09-16
created: 2026-06-18
lang: en
summary: >
  DOMAIN-PG-002 decision record. Selects Option A (single-instance invariant)
  for the current PostgreSQL-domain transition: weltgewebe supports exactly one
  API instance for domain read/write state because domain and parts of auth
  state are process-local caches with no tested cross-instance invalidation.
  Backed by a static guard against obvious API scale-out drift.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: apps/api/src/state.rs
  - type: relates_to
    target: scripts/guard/domain-single-instance-guard.sh
  - type: relates_to
    target: scripts/tests/test_domain_single_instance_guard.sh
---

# Domain PostgreSQL Instance Coherence Decision

- Task: DOMAIN-PG-002
- Decision: Option A — Single-Instance-Invariant
- Status: done / decision-recorded / guard-backed

## Kurzurteil

For the current PostgreSQL-domain transition, weltgewebe supports exactly one
API instance for domain read/write state. Horizontal scaling of API instances
is explicitly out of scope until domain reads are fully DB-backed or a tested
cross-instance invalidation/coherence mechanism exists.

This is a deployment invariant, not a cross-instance coherence implementation.

## Problem

The API keeps domain and auth-related state in process-local structures. If
multiple API instances run concurrently, instance A can write state that
instance B does not observe through its local cache. That creates a silent
cache split-brain risk.

Even when a domain read source of PostgreSQL is configured, `nodes`, `edges`
and `accounts` are loaded once into process-local `Arc<RwLock<…>>` caches at
startup and all reads are served from those caches (verified in
`apps/api/src/routes/nodes.rs`, `apps/api/src/routes/edges.rs` and
`apps/api/src/routes/accounts.rs`). The optional PostgreSQL write paths update
both PostgreSQL and the local cache. The code itself documents the boundary at
`apps/api/src/routes/nodes.rs`:

> This is an in-process coherence guard, not a multi-instance cache
> invalidation mechanism.

## Evidence inspected

Runtime / state:

- `apps/api/src/state.rs` (`ApiState`, `OrderedCache`, `Arc<RwLock<…>>` caches)
- `apps/api/src/lib.rs` (state construction; session backend selection)
- `apps/api/src/domain_db.rs` (PostgreSQL load/write helpers)
- `apps/api/src/routes/accounts.rs` (`state.accounts` read/write path)
- `apps/api/src/routes/nodes.rs` (`state.nodes` read/write path; in-process coherence comment)
- `apps/api/src/routes/edges.rs` (`state.edges` read/write path)
- `apps/api/src/routes/auth.rs` (auth flows over the auth stores)
- `apps/api/src/auth/accounts.rs` (`AccountStore`: in-memory map + email index)
- `apps/api/src/auth/session.rs` (`SessionBackend`, in-memory `SessionStore`)
- `apps/api/src/auth/session_db.rs` (`DbSessionStore`: PostgreSQL-backed sessions)
- `apps/api/src/auth/tokens.rs` (`TokenStore`: in-memory)
- `apps/api/src/auth/step_up_tokens.rs` (`StepUpTokenStore`: in-memory)
- `apps/api/src/auth/challenges.rs` (`ChallengeStore`: in-memory)
- `apps/api/src/auth/passkeys.rs` (passkey stores: in-memory)

Deployment / topology:

- `infra/compose/compose.core.yml`
- `infra/compose/compose.prod.yml`
- `infra/compose/compose.prod.override.yml`
- `infra/compose/compose.heimserver.override.yml`
- `infra/caddy/Caddyfile`, `infra/caddy/Caddyfile.dev`, `infra/caddy/Caddyfile.heim`, `infra/caddy/Caddyfile.prod`
- `scripts/weltgewebe-up`
- `.github/workflows/compose-smoke.yml`
- `docs/blueprints/domain-data-postgres-cutover.md`

## State / cache matrix

| Surface | File | Process-local? | DB-backed? | Cross-instance invalidation? | Consequence |
|---|---|---|---|---|---|
| accounts | apps/api/src/state.rs, apps/api/src/auth/accounts.rs, apps/api/src/routes/accounts.rs | yes | read loads JSONL or PostgreSQL at startup; reads served from cache; `POST /accounts` write opt-in to PostgreSQL | no | single-instance boundary |
| nodes | apps/api/src/state.rs, apps/api/src/routes/nodes.rs | yes | read loads JSONL or PostgreSQL at startup; reads served from cache; `PATCH /nodes` write opt-in to PostgreSQL | no | single-instance boundary |
| edges | apps/api/src/state.rs, apps/api/src/routes/edges.rs | yes | read loads JSONL or PostgreSQL at startup; reads served from cache; `POST /edges` write opt-in to PostgreSQL | no | single-instance boundary |
| sessions | apps/api/src/auth/session.rs, apps/api/src/auth/session_db.rs | only without `DATABASE_URL` | yes — `DbSessionStore` (PostgreSQL) when `DATABASE_URL` is set; in-memory otherwise | n/a when DB-backed (PostgreSQL is shared truth) | coherent when DB-backed; otherwise single-instance |
| tokens (magic-link) | apps/api/src/auth/tokens.rs | yes | no | no | single-instance boundary |
| step_up_tokens | apps/api/src/auth/step_up_tokens.rs | yes | no | no | single-instance boundary |
| challenges | apps/api/src/auth/challenges.rs | yes | no | no | single-instance boundary |
| passkey_registrations | apps/api/src/auth/passkeys.rs | yes | no | no | single-instance boundary |
| passkey_registration_grants | apps/api/src/auth/passkeys.rs | yes | no | no | single-instance boundary |
| passkey_authentications | apps/api/src/auth/passkeys.rs | yes | no | no | single-instance boundary |
| passkeys | apps/api/src/auth/passkeys.rs | yes | no | no | single-instance boundary |
| nats_client | apps/api/src/state.rs | optional infra | n/a | not for domain cache | not a coherence solution |

NATS note: NATS is available as optional infrastructure but is not used as a
tested domain cache invalidation mechanism. `nats_client` is only consulted by
the readiness probe (`apps/api/src/routes/health.rs`); there is no
publish/subscribe or invalidation path for domain caches in the code. It must
not be treated as a coherence solution unless a dedicated invalidation path and
tests are added.

Session note: when `DATABASE_URL` is set, sessions are persisted in PostgreSQL
via `DbSessionStore` and are therefore coherent across instances. Sessions are
the only listed surface that becomes cross-instance coherent under the standard
PostgreSQL deployment. They do not lift the single-instance boundary, because
the domain caches (`nodes`, `edges`, `accounts`) and the remaining auth ephemera
(`tokens`, `step_up_tokens`, `challenges`, passkey stores) stay process-local
and authoritative for reads.

## Topology matrix

| Path | Evidence | API instances | Scale-out evidence | Result |
|---|---|---|---|---|
| dev compose | infra/compose/compose.core.yml | 1 service (`api`) | none found | single-instance |
| prod compose | infra/compose/compose.prod.yml | 1 service (`api`) | none found | single-instance |
| prod override | infra/compose/compose.prod.override.yml | env/volumes only on `api` | none found | single-instance |
| heimserver override | infra/compose/compose.heimserver.override.yml | env only on `api`; no extra replica | none found | single-instance |
| Caddy dev/heim/prod/base | infra/caddy/Caddyfile.dev, Caddyfile.heim, Caddyfile.prod, Caddyfile | `reverse_proxy api:8080` (single upstream per route) | no multi-upstream list | single API upstream |
| scripts | scripts/weltgewebe-up | n/a | only `--scale caddy=0` (scales Caddy down); no `--scale api` | single-instance |
| CI compose smoke | .github/workflows/compose-smoke.yml | `docker compose --profile dev up` (single) | no `--scale api` | single-instance smoke |

No API scale-out evidence was found in the inspected deployment and automation
surfaces: `infra/compose`, `infra/caddy`, `scripts`, `docs`,
`.github/workflows`, `Makefile`, `Justfile`, `.devcontainer`. This is a static
inspection of those surfaces, not a runtime proof of the live container count.

## Decision

Option A is selected.

The current PostgreSQL-domain transition is constrained to a single API
instance. Multi-instance API deployment is unsupported for domain read/write
state until one of the following exists:

1. domain reads become fully DB-backed and no process-local domain cache is
   authoritative;
2. a tested cross-instance invalidation mechanism exists;
3. a tested external state/coherence layer exists.

## Consequences

- Do not run more than one API instance for the current domain PostgreSQL transition.
- Do not use `docker compose --scale api=N` with `N > 1`.
- Do not add `deploy.replicas > 1` for `api`.
- Do not configure Caddy with multiple API upstreams.
- Future scale-out requires a new task and proof.

## Guard

A scope-limited static guard enforces the obvious, robustly-detectable
scale-out drift:

- `scripts/guard/domain-single-instance-guard.sh`
- `scripts/tests/test_domain_single_instance_guard.sh`

The guard blocks, API-specific and fail-closed:

1. `replicas` on the `api` compose service whose value is not clearly `0` or
   `1` — numeric `>= 2`, or a non-literal/`$`-expanded value (e.g.
   `${API_REPLICAS:-2}`). Quoted and zero-padded values (`"2"`, `02`) are
   normalised. Compose files are found by name; the `services:` indentation is
   detected dynamically (not bound to two spaces).
2. `docker compose --scale api=<value>` whose value is not clearly `0` or `1`,
   across `docs`, `scripts`, `infra`, `.github/workflows`, `Makefile`,
   `Justfile`, `.devcontainer`. The equals and space forms (`--scale=api=N`,
   `--scale api N`), quoted, zero-padded and `$`-expanded (`api=${VAR}`) values
   are all caught.
3. multiple API upstreams on a single Caddy `reverse_proxy`/`to` directive line
   (including `http(s)://` scheme upstreams).

It does not flag: `--scale caddy=0`, a single API instance (`replicas: 1`,
`--scale api=1`), `replicas` on a non-API service, a single API upstream, or a
bare documentation placeholder such as `--scale api=N`.

What the guard is **not**: it is not a runtime proof, not a full YAML or Caddy
AST parser, and it does not (yet) detect multi-line Caddy `to` blocks that place
one upstream per line. Its claims never exceed its static detection scope.

The guard is wired into `scripts/guard/run.sh` and its test runs in the CI
guard-test loop (`.github/workflows/ci.yml`).

## Review triggers

`review_after` is a calendar backstop. This decision should be revisited earlier
when any of the following occurs:

- domain reads become fully DB-backed (no process-local domain cache is authoritative);
- a cross-instance invalidation/coherence mechanism is introduced;
- horizontal API scaling is desired;
- the Caddy or Compose topology is fundamentally changed.

## Future improvements (not blockers for DOMAIN-PG-002)

- central guard helpers for file scanning, excludes and `fail_with_location`;
- a generic guard-test fixture pattern shared across guards;
- an optional YAML AST check (e.g. pinned `yq`) if the core-guard toolchain
  policy is adjusted to allow it;
- an optional Caddy AST check via `caddy adapt` if Caddy is reliably available
  in CI/dev;
- claim-/freshness-system integration for DOMAIN-PG-002.

## Does not prove

- live production currently runs exactly one container
- cross-instance coherence
- runtime correctness
- PostgreSQL cutover readiness
- Edge FK readiness

## Related blockers

- DOMAIN-PG-001 remains blocked by DB-PROOF-001 (representative runtime edge
  audit) and the FK-vs-Guard policy decision.
- AUTH-PG-001 and AUTH-PG-002 may proceed only under this single-instance
  boundary.
- OPT-ARC-001 remains partial.

## Non-goals

- no runtime code changes
- no SQL migrations
- no Edge FK/Guard implementation
- no Auth persistence implementation
- no Redis/PubSub/NATS cache invalidation
- no multi-instance coherence claim
