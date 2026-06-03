---
id: reports.domain-read-path-proof
title: Domain Read Path Proof
doc_type: report
status: active
canonicality: evidence
created: 2026-06-03
lang: de
summary: >
  Phase-D-Proof: Optionaler PostgreSQL-Lesepfad für /nodes, /edges,
  /accounts hinter explizitem Config-Gate WELTGEWEBE_DOMAIN_READ_SOURCE.
  JSONL bleibt Default und Write-Wahrheit bis Phase E.
relations:
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: apps/api/src/domain_db.rs
  - type: relates_to
    target: apps/api/tests/db_domain_read_path.rs
  - type: relates_to
    target: apps/api/src/config.rs
  - type: relates_to
    target: apps/api/src/lib.rs
  - type: relates_to
    target: .github/workflows/api.yml
  - type: relates_to
    target: docs/reports/domain-backfill-proof.md
---

# Domain Read Path Proof

## Scope

Phase D only: optionaler PostgreSQL-Lesepfad für Domänendaten
(`/nodes`, `/edges`, `/accounts`), aktiviert ausschließlich über die
Umgebungsvariable `WELTGEWEBE_DOMAIN_READ_SOURCE=postgres`. Die
bisherigen JSONL-Loader bleiben unverändert und sind der Default.

## Non-Scope

- Kein Write-Path-Switch: Mutationen (`POST /accounts`, `PATCH /nodes`)
  bleiben JSONL-Append, unabhängig vom Read-Gate.
- Kein JSONL-Removal: JSONL-Dateien werden weiter geladen, wenn der
  Gate auf `jsonl` steht oder nicht gesetzt ist.
- Kein Startup-Backfill: die API führt beim Start keinen
  `JSONL → PostgreSQL`-Import durch; der existierende Phase-C-Proof
  bleibt für die Backfill-Pfad zuständig.
- Keine Verhaltensänderung an Endpunkten: Wire-Kontrakt aus
  `docs/specs/list-pagination-api.md` und das Cursor-Verhalten
  bleiben unangetastet.
- Keine Änderung an `auth-domain` Tables, Session-Store, NATS, Mailer.
- Keine Optimierung der DB-Query-Performance.

## Phase Boundary Confirmation

Runtime-Startup kann jetzt einen von zwei Read-Pfaden wählen. Die
Pflichtbefunde bleiben:

- `WELTGEWEBE_DOMAIN_READ_SOURCE` ist standardmäßig nicht gesetzt →
  `DomainReadSource::Jsonl` → `routes::accounts::load_all_accounts()`,
  `routes::nodes::load_nodes()`, `routes::edges::load_edges()` werden
  unverändert aufgerufen.
- `WELTGEWEBE_DOMAIN_READ_SOURCE=postgres` →
  `DomainReadSource::Postgres` → `domain_db::load_*_from_postgres()`
  befüllen dieselben Cache-Typen.
- **Write-Pfad bleibt JSONL.** Es gibt keine Schreiboperation auf
  `domain_nodes`, `domain_edges` oder `domain_accounts` durch die API
  in Phase D.

## Config Gate

```text
WELTGEWEBE_DOMAIN_READ_SOURCE=jsonl|file|files  (default: jsonl)
WELTGEWEBE_DOMAIN_READ_SOURCE=postgres|pg|db    (opt-in, Phase D)
```

Implementiert in `apps/api/src/config.rs`:

- `DomainReadSource::Jsonl` (default) und `DomainReadSource::Postgres`
  (Phase-D-Opt-in).
- `FromStr`-Parser kennt Aliase `jsonl`/`file`/`files` und
  `postgres`/`pg`/`db`.
- **Harter Fehler** bei unbekanntem Wert — kein stilles
  Default-Fallback, damit das Gate ehrlich bleibt.
- Leere Variable (`WELTGEWEBE_DOMAIN_READ_SOURCE=""`) wird wie nicht
  gesetzt behandelt (Default `Jsonl`).
- Startup-Switch in `apps/api/src/lib.rs::run()`:
  - `Postgres` ohne `DATABASE_URL` / `db_pool` → harter Fehler
    (`return Err(anyhow!(...))`), keine stille JSONL-Degradierung.
  - `Postgres` mit gültigem Pool → DB-Loader werden für die
    Cache-Befüllung verwendet.

## Mapping-Anforderungen

### Nodes (Phase D Mapping)

| `domain_nodes` Spalte | `Node` Feld | Hinweise |
|---|---|---|
| `id` | `id` | Primary key, required |
| `kind` | `kind` | Default `"Unknown"` wenn NULL |
| `title` | `title` | Default `"Untitled"` wenn NULL |
| `lat`, `lon` | `location.lat/lon` | NULL-Paar ⇒ Zeile wird geloggt übersprungen |
| `created_at` | `created_at` (RFC 3339) | Fallback auf `updated_at`, dann `1970-01-01T00:00:00Z` |
| `updated_at` | `updated_at` (RFC 3339) | symmetrisch zu `created_at` |
| `payload->>'summary'` | `summary` | optional |
| `payload->>'info'` | `info` | optional |
| `payload->'tags'` | `tags` | Array von Strings, fehlend = leer |

### Edges (Phase D Mapping)

| `domain_edges` Spalte | `Edge` Feld | Hinweise |
|---|---|---|
| `id` | `id` | required |
| `source_id` | `source_id` | required (sonst Skip + Warn) |
| `target_id` | `target_id` | required (sonst Skip + Warn) |
| `edge_kind` | `edge_kind` | leer wenn NULL |
| `created_at` | `created_at` (RFC 3339) | optional |
| `payload->'source_type'` | `source_type` | optional |
| `payload->'target_type'` | `target_type` | optional |
| `payload->>'note'` | `note` | optional |

Stabile ID-ascending-Reihenfolge via `ORDER BY id ASC` — passt zur
JSONL-Pfad-Sortierung (Insertion-Order + Last-Write-Wins per ID).

### Accounts — Privacy-Rekonstruktion (kritisch)

Der DB-Loader ruft die **gleiche** `routes::accounts::map_json_to_public_account`
auf, die auch der JSONL-Pfad nutzt. Damit greifen identische
Privacy-Regeln — getestet in `apps/api/tests/db_domain_read_path.rs`:

| DB-Quelle | Feld in `AccountPublic` | Pflichtverhalten |
|---|---|---|
| `mode = 'verortet'` + `location_lat/lon` | `mode = Verortet`, `public_pos` deterministisch | `public_pos = calculate_jittered_pos(lat, lon, radius_m, id)` |
| `private_payload->>'visibility' = 'private'` | `public_pos = None` | `mode` bleibt `Verortet`, aber private Koordinaten werden **nicht** offengelegt |
| `private_payload->>'visibility' = 'approximate'` + `radius_m = 0` | `radius_m = 250` | Default-Radius für legacy approximate |
| `mode = 'ron'` oder `private_payload->>'ron_flag' = true` | `mode = Ron`, `public_pos = None` | Kein individueller öffentlicher Punkt |
| `kind` Spalte | `kind` (via `type`-Rename) | Default `"garnrolle"` |
| `disabled` | `disabled` (skip serialization) | Default `false` |
| `role` | `Role` | Default `Role::Gast` |
| `email` | `AccountInternal.email` | Empty-String wird als `None` behandelt |
| `webauthn_user_id` | `AccountInternal.webauthn_user_id` | UUID, sonst frische v4 (lazy backfill) |
| `public_payload->'summary'` | `summary` | optional |
| `public_payload->'tags'` | `tags` | optional |

**Wichtig:** `location_lat` und `location_lon` werden in der
`AccountPublic` **nie** exponiert. Die Spalten werden ausschließlich
benutzt, um `public_pos` (deterministisch gejittert) zu berechnen,
wenn die Privacy-Regel das erlaubt.

## Validation

### Compile-Check (kein PostgreSQL nötig)

```bash
cargo test --locked -p weltgewebe-api --test db_domain_read_path --no-run
cargo test --locked -p weltgewebe-api --test db_domain_backfill --no-run
cargo test --locked -p weltgewebe-api --test db_domain_schema_migrations --no-run
cargo test --locked -p weltgewebe-api
```

Diese Befehle übersetzen die neue Loader- und Test-Suite, ohne
PostgreSQL zu benötigen — sie bleiben der Standard-Smoke für PRs.

### Voller Integrationstest (benötigt direktes PostgreSQL)

```bash
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
  cargo test --locked -p weltgewebe-api \
    --test db_domain_read_path \
    -- --include-ignored --test-threads=1
```

Der CI-Job `db-domain-read-path-proof` in `.github/workflows/api.yml`
führt diesen Befehl mit einem frischen `postgres:16`-Service auf direktem
Port `5432` (kein PgBouncer `:6432`) aus.

### Lokaler Status

- Direktes PostgreSQL in dieser Remote-Ausführungsumgebung nicht
  verfügbar.
- Lokaler `--no-run` Build kann ohne Cargo nicht ausgeführt werden
  (Cargo-Toolchain auf `heim-pc` fehlt).
- CI-Proof verbleibt als autoritativer Laufbeleg.

## Privacy-Testfälle (im `db_domain_read_path` Test-Suite)

1. `db_read_path_accounts_reconstruct_privacy_semantics`:
   - **verortet**: `public_pos` ≈ `(53.5, 10.0)` (radius_m=0 ⇒ exact)
   - **private** (`visibility:"private"` + `suppress_public_pos:true`):
     `public_pos == None` trotz gesetztem `location_lat/lon`
   - **approximate** (`visibility:"approximate"` + `radius_m=0`):
     `radius_m == 250`
   - **ron** (`mode:"ron"` + `ron_flag:true`): `public_pos == None`
2. `db_read_path_loads_nodes_with_payload_fields`:
   - `kind`, `title`, `location`, `summary`, `info`, `tags` korrekt
   - Last-write-wins per ID bleibt durch Cache-Insertion erhalten
3. `db_read_path_loads_edges_with_payload_fields`:
   - `source_id`, `target_id`, `edge_kind`, `note` korrekt
4. `db_read_path_empty_table_returns_empty_caches`:
   - Loader scheitern nicht auf einer leeren Tabelle (Smoke)

## Out of Scope / Phase E Risiko

- **Mutierende Endpunkte in `postgres`-Modus** sind in Phase D
  *nicht* blockiert. Deren Verhalten bleibt unverändert (JSONL-Append).
  Das ist eine bewusste Wahl, um den Scope klein zu halten; ein
  Phase-D-Block könnte mit den existierenden
  `require_admin`/`require_write`-Middlewares kombiniert werden, wenn
  Phase E startet.
- **Cache-Invalidierung bei externer DB-Mutation:** Wenn ein
  externer Prozess `domain_accounts` direkt verändert, sieht die
  laufende API das erst nach Neustart (gleicher JSONL-Cache-Truth).

## CI-Beleg

CI-Pflichtjob: `db-domain-read-path-proof` in `.github/workflows/api.yml`.

PostgreSQL 16 Service auf direktem Port `5432`,
`WELTGEWEBE_DOMAIN_READ_SOURCE=postgres` env gesetzt,
`cargo test --locked --test db_domain_read_path -- --include-ignored
--test-threads=1`. **PR-CI-Laufbeleg ausstehend.**

## Remaining OPT-ARC-001 Phases

| Phase | Inhalt | Status |
|---|---|---|
| A | Blueprint + Statusabgleich | done |
| B | PostgreSQL-Schema-Migrationen | done |
| C | Backfill-/Import-Proof | done (CI-Laufbeleg ausstehend) |
| D | Read-Path-Switch hinter Config-Gate | **implemented; CI proof pending** |
| E | Write-Path-Switch | open |
| F | Runtime-Smoke + CI-Beweis | open |
| G | JSONL-Demontage | open |

OPT-ARC-001 bleibt `partial` bis Phase D in PR-CI grün bewiesen ist
und Phase E in Angriff genommen wird.
