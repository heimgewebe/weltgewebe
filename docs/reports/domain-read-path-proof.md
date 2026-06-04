---
id: reports.domain-read-path-proof
title: Domain Read-Path Proof (Phase D)
doc_type: report
status: active
canonicality: evidence
relations:
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: apps/api/tests/db_domain_read_path.rs
  - type: relates_to
    target: docs/reports/domain-backfill-proof.md
---

# Domain Read-Path Proof (Phase D)

## Scope

Phase D only: read-path query semantics proven for PostgreSQL domain tables
(accounts, nodes, edges). Covers the four distinct proof layers:

| Layer | Status |
|---|---|
| Config gate (`WELTGEWEBE_DOMAIN_READ_SOURCE`) | Implemented — env-var switch wired in code |
| PostgreSQL loaders (query semantics) | Proven locally via `db_domain_read_path` suite |
| Startup switch | Wired in code |
| Full API runtime smoke (Phase F) | Not proven here |

## Non-Scope

- No write-path switch.
- No JSONL removal.
- No API endpoint behavior change.
- No default data source change — JSONL remains the active default until Phase E.
- Does not mark OPT-ARC-001 done.

## Phase Boundary Confirmation

Runtime startup still invokes the JSONL/in-memory loaders by default:

- `routes::accounts::load_all_accounts().await`
- `routes::nodes::load_nodes().await`
- `routes::edges::load_edges().await`

These paths are unchanged. PostgreSQL loaders are only activated when
`WELTGEWEBE_DOMAIN_READ_SOURCE=postgres` is set explicitly.

## What Is Proven

### Account Privacy Semantics

Three privacy projection paths are proven against the `domain_accounts` table:

- `visibility="private"` in `private_payload` alone suppresses `public_pos`
  in the read projection (no `suppress_public_pos` field required).
- `suppress_public_pos=true` in `private_payload` (without `visibility`)
  suppresses `public_pos` independently.
- `ron_flag=true` in `private_payload` overrides a `mode="verortet"` DB
  column: the loader must treat the account as RoN regardless of the column.

### Node Loader

- `kind`, `lat`, `lon` field mapping is correct.
- Unlocated nodes have `NULL` `lat`/`lon`.

### Edge Loader

- `source_id`, `target_id`, `edge_kind` field mapping is correct.
- A configurable cap (analogous to `MAX_EDGES_CACHE`) is exercised via `LIMIT`.

## Test Suite

Tests live in `apps/api/tests/db_domain_read_path.rs`.

All tests are `#[ignore]` (require direct PostgreSQL, not PgBouncer) and use
`#[serial]` to avoid fixture conflicts. The suite compiles as part of the
standard `cargo test --locked -p weltgewebe-api` build; runtime execution
against a live database requires:

```
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
  cargo test --locked -p weltgewebe-api --test db_domain_read_path \
  -- --include-ignored --test-threads=1
```

PR-CI proof (green run with PostgreSQL service): pending.

## What Remains Open

- PR-CI run with `--include-ignored` and a live PostgreSQL service (analogous
  to `db-domain-backfill-proof`).
- Phase E: write-path switch and JSONL removal.
- Phase F: full API runtime smoke against the PostgreSQL read path.
- Tile-directory and structural PMTiles validation (separate domain).
