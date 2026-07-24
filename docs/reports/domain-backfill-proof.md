---
id: reports.domain-backfill-proof
title: Domain Backfill Proof
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: OPT-ARC-001
review_after: 2026-07-16
canonicality: evidence
summary: >
  Proof-Bericht für OPT-ARC-001 Phase C: deterministischer JSONL→PostgreSQL-Backfill
  für Domänendaten ohne Runtime- oder Write-Path-Cutover.
relations:
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: apps/api/tests/db_domain_backfill.rs
  - type: relates_to
    target: .github/workflows/api.yml
---

# Domain Backfill Proof

> **Sicherheitsnachtrag 2026-07-18:** Historische Radius-/Approximate-Datensätze
> ohne private Zufallsbindung werden beim Import nicht mehr öffentlich
> rekonstruiert. Private Koordinaten bleiben erhalten, während `map_state` und
> `radius_m` fail-closed auf `not_on_map` beziehungsweise `0` gesetzt werden.
>
> **Finaler Kontovertrag 2026-07-24:** Nach belegtem Produktionscutover werden
> RoN-, `mode`- und alte Sichtbarkeitsfelder nicht mehr normalisiert, sondern
> abgewiesen. Importierbar sind nur `type=garnrolle` und ein expliziter gültiger
> `map_state`. Die Datenbankspalte `mode` ist entfernt.

## Scope

Phase C only: deterministic JSONL→PostgreSQL import proof for domain data (nodes, edges, accounts).

## Non-Scope

- No runtime read-path switch (`/nodes`, `/edges`, `/accounts` still read from JSONL/In-Memory).
- No write-path switch.
- No JSONL removal.
- No API endpoint behavior changes.
- No production data migration on API startup.
- Does not mark OPT-ARC-001 done.

## Lifecycle

- Zweck: Belegt den OPT-ARC-001 PostgreSQL-Teilpfad für den deterministischen JSONL→PostgreSQL-Backfill im dokumentierten Scope.
- Bereitet vor: Fortlaufende OPT-ARC-001 Cutover- und Proof-Matrix-Entscheidungen.
- Gültig bis: Review am 2026-07-16 oder bis ein neuerer Proof diesen Bericht ersetzt.
- Wird abgelöst durch: Noch offen; mögliche spätere Runtime-/Cutover-Proofs oder aktualisierte Proof-Matrix-Artefakte.

## Phase Boundary Confirmation

Runtime startup still calls:


- `routes::accounts::load_all_accounts().await`
- `routes::nodes::load_nodes().await`
- `routes::edges::load_edges().await`


These paths are unchanged. JSONL is the active runtime truth until Phase D/E.

## Mapping Summary

### domain_nodes

| JSONL field | DB column | Notes |
|---|---|---|
| `id` | `id` (TEXT PK) | Required; record skipped if missing |
| `kind` | `kind` | Default: `"Unknown"` |
| `title` | `title` | Default: `"Untitled"` |
| `location.lat` | `lat` | Optional; NULL if absent |
| `location.lon` | `lon` | Optional; NULL if absent |
| `created_at` | `created_at` (TIMESTAMPTZ) | Parsed as RFC 3339; NULL if absent or unparseable |
| `updated_at` | `updated_at` (TIMESTAMPTZ) | Parsed as RFC 3339; NULL if absent or unparseable |
| `summary`, `info`, `tags` | `payload` (JSONB) | Remaining fields; absent/null keys omitted |
| `_create_actor_id`, `_create_operation_id` | `create_actor_id`, `create_operation_id` | Optional internal pair; never copied into public payload |

### domain_edges

| JSONL field | DB column | Notes |
|---|---|---|
| `id` | `id` (TEXT PK) | Required |
| `source_id` | `source_id` | Required; record skipped if missing |
| `target_id` | `target_id` | Required; record skipped if missing |
| `edge_kind` / `kind` / `edgeKind` | `edge_kind` | serde aliases preserved; default `""` |
| `created_at` | `created_at` (TIMESTAMPTZ) | Optional |
| `source_type`, `target_type`, `note` | `payload` (JSONB) | Participant type hints and free text |
| `_create_actor_id`, `_create_operation_id` | `create_actor_id`, `create_operation_id` | Optional internal pair; never copied into public payload |

### domain_accounts

| JSONL field | DB column | Notes |
|---|---|---|
| `id` | `id` (TEXT PK) | Required |
| `type` | `kind` | Required canonical value: `"garnrolle"` |
| `title` | `title` | Default: `"Untitled"` |
| `map_state` | `map_state` | Required: `not_on_map`, `exact` or `radius` |
| `radius_m` | `radius_m` (BIGINT) | Bound as `i64`; default 0 |
| `disabled` | `disabled` | Default: `false` |
| `location.lat` | `location_lat` | Private residence; never the public radius projection |
| `location.lon` | `location_lon` | Private residence |
| `role` | `role` | Default: `"gast"` |
| `email` | `email` | Optional |
| `webauthn_user_id` | `webauthn_user_id` (UUID) | Validated as UUID before insert; NULL if absent or invalid |
| `created_at` | `created_at` (TIMESTAMPTZ) | Optional |
| `updated_at` | `updated_at` (TIMESTAMPTZ) | Optional |
| `summary`, `tags` | `public_payload` (JSONB) | Public fields not in explicit columns |
| `radius_projection` | `private_payload` (JSONB) | Sichere Radiusbindung bleibt privat; entfernte Identitäts- und Sichtbarkeitsfelder werden nicht gespeichert |

## Idempotency Contract

All three import functions use:

```sql
INSERT INTO domain_<entity> (...) VALUES (...)
ON CONFLICT (id) DO UPDATE SET <all columns> = EXCLUDED.<column>
```

**Second-run behaviour:** A second import with identical source data updates all
rows to match the source (last-write-wins per record). Row count does not increase.

**Within-import duplicate IDs:** If the same ID appears twice in one JSONL file,
the second occurrence overwrites the first via the same `ON CONFLICT DO UPDATE`
path. The final row contains the last-seen values in file order.

## Malformed / Missing-Field Policy

| Condition | Behaviour |
|---|---|
| Invalid JSON | `malformed_json_lines` incremented; line not imported |
| Missing `id` | `skipped_records` incremented; line not imported |
| Missing `source_id` / `target_id` (edges) | `skipped_records` incremented; line not imported |
| Half-populated or invalid create-operation metadata | `skipped_records` incremented; line not imported |
| Unparseable timestamp | `NULL` stored in TIMESTAMPTZ column |
| Invalid `webauthn_user_id` UUID | `NULL` stored; original string discarded |
| Missing or non-canonical `type` | `skipped_records` incremented; line not imported |
| Missing or invalid `map_state` | `skipped_records` incremented; line not imported |
| `mode`, `ron_flag`, `visibility` or `suppress_public_pos` present | `skipped_records` incremented; line not imported |

No silent continuation: all quarantined lines are counted in `BackfillReport`.

## Duplicate Email Policy (Accounts)

Phase B originally tolerated duplicate emails in `domain_accounts`. TODO 2A
supersedes that for normalized non-empty emails: the partial unique index
`domain_accounts_email_normalized_unique` (`lower(btrim(email))`, where the
trimmed email is non-empty) now rejects a duplicate. The import audits and skips
the duplicate **before** insert, using the SAME normalization as the index:

- Each email is first trimmed; an after-trim-empty value is treated as "no
  email" (NULL).
- Before inserting, a `COUNT` query checks for existing rows with the same
  `lower(btrim(email))` and a different `id` (matching the unique index, not the
  bare `lower(email)` lookup index).
- If a duplicate is found, the trimmed email is added to
  `report.duplicate_emails`, `report.skipped_records` is incremented, and the
  row is skipped before any insert. The normal path therefore avoids an
  intentional unique violation before insert. The constraint-violation branch
  remains only as a defensive backstop against a race or drift; it is not the
  regular transaction mechanism.

After-trim-empty emails are never persisted as a string: the mapper folds them
to NULL, and the `domain_accounts_email_not_empty_after_trim` check constraint
rejects any after-trim-empty value at the storage layer. NULL emails stay
allowed. See `docs/reports/domain-account-email-uniqueness-audit.md` (TODO 2A)
for the constraint policy.


## Final Account Identity Contract

The importer and PostgreSQL read path now enforce one account identity:

- `type` must be exactly `"garnrolle"`.
- `map_state` must be explicitly `not_on_map`, `exact`, or `radius`.
- `mode`, `ron_flag`, `visibility`, and `suppress_public_pos` are rejected.
- A radius projection requires a valid private binding; otherwise the account
  fails closed to `not_on_map` without inventing a public position.
- A non-public account remains a normal Garnrolle with
  `map_state=not_on_map`; it is not converted into another account type.

## Validation

### Compile check (no PostgreSQL required)

```bash
cargo test --locked -p weltgewebe-api --test db_domain_backfill --no-run
```

This verifies the test syntax and type mappings without needing a database.

### Full integration test (requires direct PostgreSQL)

```bash
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
  cargo test --locked -p weltgewebe-api --test db_domain_backfill \
  -- --include-ignored --test-threads=1
```

### Task index and docmeta (no database required)

```bash
python3 -m scripts.docmeta.validate_task_index docs/tasks/index.json
python3 -m scripts.docmeta.generate_task_index --check
python3 -m scripts.docmeta.agent_entrypoint_smoke
python3 -m scripts.docmeta.check_planning_registration --mode strict
```

### Local PostgreSQL status

Direct PostgreSQL not available in this remote execution environment. Full integration proof via CI job `db-domain-backfill-proof` in `.github/workflows/api.yml` (PostgreSQL 16 service on direct port 5432, runs all 7 tests with `--include-ignored --test-threads=1`). **PR-CI-Laufbeleg ausstehend.**

## Remaining OPT-ARC-001 Phases

| Phase | Description | Status |
|---|---|---|
| A | Blueprint and planning | done |
| B | PostgreSQL schema migrations (domain tables) | done |
| C | Backfill/import proof (this slice) | implemented; CI proof pending |
| D | Read-path switch (runtime reads from PostgreSQL) | open |
| E | Write-path switch (runtime writes to PostgreSQL) | open |

Phase D should be implemented behind an explicit configuration gate (env var or
feature flag) so it can be verified independently of Phase E. JSONL must not be
removed until Phase E is proven stable.
