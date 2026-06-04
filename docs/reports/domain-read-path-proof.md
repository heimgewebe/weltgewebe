---
id: reports.domain-read-path-proof
title: Domain Read Path Proof
doc_type: report
status: active
canonicality: evidence
summary: >
  Phase-D-Beleg für OPT-ARC-001: ein optionaler, read-only PostgreSQL-Lesepfad
  für nodes, edges und accounts hinter dem Config-Gate
  WELTGEWEBE_DOMAIN_READ_SOURCE. JSONL bleibt Default-Lesequelle und
  Schreibwahrheit; db_domain_read_path kompiliert per --no-run, direkter PostgreSQL-Runtime-Proof in dieser Umgebung nicht ausgeführt; PR-CI-Beleg ausstehend.
relations:
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/reports/domain-backfill-proof.md
  - type: relates_to
    target: apps/api/src/config.rs
  - type: relates_to
    target: apps/api/src/domain_db.rs
  - type: relates_to
    target: apps/api/src/lib.rs
  - type: relates_to
    target: apps/api/tests/db_domain_read_path.rs
  - type: relates_to
    target: .github/workflows/api.yml
---

# Domain Read Path Proof

## Scope

Phase D only: an **optional, read-only PostgreSQL read path** for domain data
(nodes, edges, accounts), gated behind an explicit configuration switch.

Implemented in this slice:

1. **Config gate** — `DomainReadSource` (`apps/api/src/config.rs`), selected via
   the `WELTGEWEBE_DOMAIN_READ_SOURCE` env var or the `domain_read_source`
   config-file key.
2. **Read-only loaders** — `apps/api/src/domain_db.rs`:
   `load_nodes_from_postgres`, `load_edges_from_postgres`,
   `load_accounts_from_postgres`.
3. **Startup switch** — `apps/api/src/lib.rs` chooses the read source at startup.

## Non-Scope

- No write-path switch (Phase E). JSONL append/`patch_node`/account writes are unchanged.
- No JSONL removal. JSONL remains the **default** read source and the write truth.
- No dual-write, no startup backfill, no production migration triggered by this slice.
- No endpoint behaviour change in default (JSONL) mode.
- Does not mark OPT-ARC-001 done. Phase E remains open.

## Operational Warning — Read/Write Divergence Before Phase E

`WELTGEWEBE_DOMAIN_READ_SOURCE=postgres` is a **Phase-D read-only startup mode**.
Until Phase E, API writes still go to JSONL. Running postgres read mode in a
mutable deployment can cause restart-visible divergence unless JSONL changes are
backfilled into `domain_*` before restart. Use this mode only for proof or
read-only deployments, or with an explicit backfill discipline.

## Default Invariant

With no configuration, or with `WELTGEWEBE_DOMAIN_READ_SOURCE` absent/empty,
the runtime reads exactly as before:

- `routes::accounts::load_all_accounts().await`
- `routes::nodes::load_nodes().await`
- `routes::edges::load_edges().await`

The PostgreSQL read path is reached only when an operator explicitly opts in.

## Config Gate

| Input | Result |
|---|---|
| absent env / config | `Jsonl` (default) |
| empty env value | keeps configured value (defaults to `Jsonl`) |
| `jsonl` / `file` / `files` (any case) | `Jsonl` |
| `postgres` / `pg` / `db` (any case) | `Postgres` |
| any other non-empty value | hard config error naming `WELTGEWEBE_DOMAIN_READ_SOURCE` |
| config file `domain_read_source: jsonl` / `postgres` | respected; env override wins when both are set |

## Loaders

All loaders are strictly read-only (no writes, no migrations, no backfill) and
return rows ordered by `id ASC`. JSONB columns are read as `::text` and parsed
with `serde_json` in Rust; UUID is read as `::text`; no new sqlx feature is
required, and JSONB booleans are never cast with `::bool`.

The PostgreSQL edge loader honours `MAX_EDGES_CACHE` (shared with the JSONL
loader via `max_edges_cache_limit()`). It fetches at most `limit + 1` rows
to detect truncation without materialising the entire table, and emits a
warning when truncation occurs. JSONL remains the default; Phase E remains open.

| Loader | Source table | Target type |
|---|---|---|
| `load_nodes_from_postgres` | `domain_nodes` | `OrderedCache<Node>` |
| `load_edges_from_postgres` | `domain_edges` | `OrderedCache<Edge>` |
| `load_accounts_from_postgres` | `domain_accounts` | `AccountStore` |

## Account Privacy Reconstruction

The public projection of an account is computed by the **same** function as the
JSONL runtime path — `map_json_to_public_account` (made `pub(crate)`; its logic
is unchanged) — fed a JSONL-shaped record reconstructed from the row. The loader
reads the `mode` column from `domain_accounts` and uses it as the primary source
of truth; kind-override rules (`kind == "ron"` or `ron_flag = true`) are applied
before the record is passed to the projection function. The `approximate` +
radius-0 → 250 adjustment is also pre-applied in the loader because
`map_json_to_public_account` only runs that adjustment in its legacy fallback
path. The single rule that function does not model, an explicit
`suppress_public_pos`, is applied as an override afterwards.

| Rule | Behaviour | Proof test |
|---|---|---|
| Private residence (`location_lat`/`location_lon`) | never exposed directly; only `public_pos` is projected | `accounts_loader_verortet_exposes_public_pos_and_never_leaks_location` |
| `visibility = "private"` | `public_pos` suppressed | `accounts_loader_private_visibility_suppresses_public_pos` |
| `suppress_public_pos = true` without `visibility` | `public_pos` suppressed (explicit override) | `accounts_loader_suppress_public_pos_without_visibility` |
| `visibility = "approximate"` + radius 0/missing | `radius_m` becomes `250` | `accounts_loader_approximate_radius_zero_becomes_250` |
| `mode = "ron"` or `ron_flag = true` | no `public_pos` | `accounts_loader_ron_and_ron_flag_suppress_public_pos` |
| DB `mode = "ron"` with location set (no `ron_flag`) | `mode` honoured, `public_pos` suppressed | `accounts_loader_respects_mode_column_ron_even_with_location` |
| DB `mode = "verortet"` with location set | `mode` honoured, `public_pos` exposed | `accounts_loader_respects_mode_column_verortet_with_location` |
| email index | rebuilt for case-insensitive `get_by_email` | `accounts_loader_email_index_is_rebuilt_for_case_insensitive_lookup` |

## Ordering

Loaders return rows in **id-ascending** order, matching the stable order already
used by cursor pagination. This does **not** reproduce the legacy JSONL
file/insertion order used by the offset path; legacy-offset parity with JSONL is
explicitly out of scope. Proven by `loaders_return_rows_in_id_ascending_order`
(rows inserted in non-id order load back id-ascending).

## Validation

### Offline (no PostgreSQL required)

```bash
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --locked -p weltgewebe-api
cargo test --locked -p weltgewebe-api --lib domain_read_source -- --nocapture
cargo test --locked -p weltgewebe-api --test db_domain_read_path --no-run
cargo test --locked -p weltgewebe-api --test db_domain_backfill --no-run
cargo test --locked -p weltgewebe-api --test db_domain_schema_migrations --no-run
```

### Integration (requires direct PostgreSQL)

```bash
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
  cargo test --locked -p weltgewebe-api --test db_domain_read_path \
  -- --include-ignored --test-threads=1
```

### Local PostgreSQL status

No direct PostgreSQL instance was available on `localhost:5432` in this environment. The runtime proof command was therefore not executed locally. Current local evidence is limited to offline compilation and non-ignored tests:

- `db_domain_read_path` compiles via `--no-run`.
- Direct PostgreSQL runtime proof remains pending.
- PR-CI proof via `db-domain-read-path-proof` is pending.

The **canonical PR proof** is the CI job `db-domain-read-path-proof` in
`.github/workflows/api.yml` (PostgreSQL 16 service on direct port 5432,
`--include-ignored --test-threads=1`). **PR-CI-Laufbeleg ausstehend.**

### Task index and docmeta (no database required)

```bash
python3 -m scripts.docmeta.validate_task_index docs/tasks/index.json
python3 -m scripts.docmeta.generate_task_index --check
python3 -m scripts.docmeta.agent_entrypoint_smoke
python3 -m scripts.docmeta.check_planning_registration --mode strict
```

## OPT-ARC-001 Phase Status

| Phase | Description | Status |
|---|---|---|
| A | Blueprint and planning | done |
| B | PostgreSQL schema migrations (domain tables) | done; PR-CI proof pending |
| C | Backfill/import proof | implemented; PR-CI proof pending |
| D | Read-path switch behind config gate (this slice) | implemented (config gate + read-only loaders + startup wiring); db_domain_read_path compiles via --no-run; direct PostgreSQL runtime proof is reserved for PR CI; full API runtime smoke remains Phase F; PR-CI proof pending |
| E | Write-path switch (runtime writes to PostgreSQL) | open |

OPT-ARC-001 remains **partial**: Phase E is open, and JSONL stays the default
read source and the write truth until Phase E is proven. Phase D must not be
marked CI-proven until the `db-domain-read-path-proof` job is green in PR CI.
