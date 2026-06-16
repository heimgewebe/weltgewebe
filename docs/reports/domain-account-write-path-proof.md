---
id: reports.domain-account-write-path-proof
title: "Domain Account Write Path Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: OPT-ARC-001
review_after: 2026-07-16
canonicality: evidence
created: 2026-06-04
lang: de
summary: >
  Proof-Bericht für OPT-ARC-001 Phase E-A: optionaler PostgreSQL-Schreibpfad
  ausschließlich für die Account-Erzeugung (`POST /accounts`) hinter explizitem
  Write-Gate. JSONL bleibt Default; kein Dual-Write; Knoten-, Kanten-, Step-up-
  E-Mail- und WebAuthn-Credential-Persistenz bleiben unverändert.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/reports/domain-read-path-proof.md
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: apps/api/tests/db_domain_account_write_path.rs
  - type: relates_to
    target: .github/workflows/api.yml
---

# Domain Account Write Path Proof

## Scope

Dieser Proof dokumentiert OPT-ARC-001 **Phase E-A** als bewusst engen,
opt-in PostgreSQL-Schreibpfad **ausschließlich für die Account-Erzeugung**
(`POST /accounts`).

Geltende Grenzen:

- JSONL bleibt Default-Schreibpfad und Default-Lesequelle.
- PostgreSQL-Account-Writes werden nur über
  `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE=postgres` bzw.
  `domain_account_write_source: postgres` aktiviert.
- Der Account-Write-Gate ist getrennt vom Read-Gate
  (`WELTGEWEBE_DOMAIN_READ_SOURCE`). Es ist **kein** breiter
  `WELTGEWEBE_DOMAIN_WRITE_SOURCE`, weil nur Account-Create implementiert ist.
- PostgreSQL-Account-Write **erfordert** den PostgreSQL-Read-Source und einen
  konfigurierten Pool. Andernfalls bricht Config-Load bzw. Startup hart ab
  (kein stiller JSONL-Fallback).
- Kein Dual-Write: Im JSONL-Modus wird nie PostgreSQL beschrieben, im
  PostgreSQL-Modus wird nie JSONL angehängt.

## Nicht implementiert (bewusst außerhalb dieser Phase)

- Kein `PATCH /nodes` PostgreSQL-Write (im Postgres-Read-Modus weiterhin
  blockiert).
- Kein Edge-Write-Path.
- Keine Step-up-E-Mail-Persistenz nach PostgreSQL.
- Kein WebAuthn-Credential-Writeback nach PostgreSQL.
- Kein Backfill und kein `NOT NULL` für bestehende Accounts mit
  `webauthn_user_id IS NULL`.
- Keine Entfernung von JSONL.
- Kein Startup-Backfill.
- Kein Produktions-Cutover. OPT-ARC-001 bleibt `partial`.

## Lifecycle

- Zweck: Belegt den OPT-ARC-001 PostgreSQL-Teilpfad für den Account-Schreibpfad `POST /accounts` im dokumentierten Scope.
- Bereitet vor: Fortlaufende OPT-ARC-001 Cutover- und Proof-Matrix-Entscheidungen.
- Gültig bis: Review am 2026-07-16 oder bis ein neuerer Proof diesen Bericht ersetzt.
- Wird abgelöst durch: Noch offen; mögliche spätere Runtime-/Cutover-Proofs oder aktualisierte Proof-Matrix-Artefakte.

## Konfiguration

| Aspekt | Wert |
|---|---|
| Config-Key | `domain_account_write_source` |
| Env-Var | `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE` |
| Akzeptierte Werte | `jsonl`/`file`/`files`, `postgres`/`pg`/`db` |
| Default | `jsonl` |
| Leerer Env-Wert | behält Default |
| Ungültiger Wert | harter Config-Fehler (kein Fallback) |
| Harte Kopplung | `postgres` erfordert `domain_read_source=postgres` (Config-Load) **und** einen Pool (Startup) |

## Route-Verhalten (`POST /accounts`)

| Read-Source | Account-Write-Source | Verhalten |
|---|---|---|
| JSONL | JSONL | Append nach `demo.accounts.jsonl` (unverändert), dann Cache-Update |
| Postgres | JSONL | `409 CONFLICT` + `DOMAIN_READ_SOURCE_READ_ONLY` (kein Write, kein Cache-Update) |
| Postgres | Postgres | Insert nach `domain_accounts`, dann Cache-Update; **kein** JSONL-Append |
| JSONL | Postgres | Config-Load bricht hart ab; manuell konstruierte `ApiState`-Zustände werden defensiv mit `500` / `INVALID_DOMAIN_WRITE_CONFIG` blockiert |

`PATCH /nodes` bleibt im Postgres-Read-Modus unverändert blockiert
(`reject_if_postgres_read_source`).

## Implementierte Belege

- `apps/api/src/config.rs`: `DomainAccountWriteSource` (Default `Jsonl`),
  Env-Parsing, harte Validierung der Read/Write-Kopplung; Unit-Tests für
  Default, Aliase, ungültigen Wert, leeren Wert, Postgres+JSONL-Read-Reject und
  Postgres+Postgres-Read-Accept.
- `apps/api/src/lib.rs`: Startup-Gate — `Postgres` verlangt einen Pool, sonst
  harter Startfehler; klares Logging „account-create write source“.
- `apps/api/src/domain_db.rs`: `NewDomainAccountRow::from_jsonl_record`
  (gleiches semantisches Mapping wie der Phase-C-Backfill) und
  `insert_account_from_jsonl_record` (eine Zeile, plain `INSERT` ohne
  `ON CONFLICT`; UUID/JSONB via `::uuid`/`::jsonb`-Casts, weil der sqlx-Build
  kein `uuid`-Feature hat); `AccountWriteError::{DuplicateId, Mapping, Database}`;
  Unit-Tests für Create-Mapping, private Visibility, approximate-Radius und
  ron_flag.
- `apps/api/src/routes/domain_write_guard.rs`:
  `reject_account_create_unless_writable` (Account-Create-Gate) neben dem
  unveränderten `reject_if_postgres_read_source` (Node-Writes).
- `apps/api/src/routes/accounts.rs::create_account`: gemeinsame
  Validierung/Record-Bau/Public-Projektion/Duplikatprüfung; Verzweigung nur am
  Persistenzschritt; Cache-Update erst nach erfolgreichem Write; DB-Insert-Fehler
  mappt `DuplicateId` → `409 CONFLICT`, sonst `500`.
- `apps/api/tests/db_domain_account_write_path.rs`: DB-gestützte
  Integrationsproofs (ignored by default).
- `.github/workflows/api.yml`: PR-CI-Job `db-domain-account-write-path-proof`
  (PostgreSQL-16-Service, direkter Port 5432, `--include-ignored --test-threads=1`).

## Spalten, die der Account-Create schreibt

`id`, `kind` (aus `type`, hier `garnrolle`), `title`, `mode` (`verortet`),
`radius_m`, `disabled` (`false`), `location_lat`/`location_lon` (private
Residenz), `role`, `email` (optional), `webauthn_user_id` (beim Account-Create
neu erzeugte UUID), `created_at`/`updated_at` (NULL — wie JSONL-Create +
Backfill),
`public_payload` (`summary`, `tags`), `private_payload` (spiegelt den
Backfill: explizites `mode`; bei Legacy-Eingaben zusätzlich `visibility`,
`suppress_public_pos`, `ron_flag`).

Neue PostgreSQL-Account-Create-Zeilen persistieren damit eine stabile
`webauthn_user_id`, die der lokale Cache unverändert übernimmt und die
`load_accounts_from_postgres` nach einem Reload wiederherstellt. Bestehende
NULL-Werte bleiben über den Legacy-Fallback unterstützt.

`public_pos` ist **keine** gespeicherte Spalte: Sie wird beim Lesen
deterministisch aus `location_lat`/`location_lon`/`radius_m`/`id` berechnet.
Das private Feld `location` wird nie serialisiert. `public_pos` ist die
öffentliche Projektion; bei `radius_m = 0` kann sie exakt den eingereichten
Koordinaten entsprechen, bei `radius_m > 0` wird sie deterministisch
gejittert.

## Validierung

### Offline (ohne PostgreSQL)

```bash
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --locked -p weltgewebe-api --no-run
cargo test --locked -p weltgewebe-api
cargo test --locked -p weltgewebe-api --test db_domain_account_write_path --no-run
```

### Integrationsproof (direkter PostgreSQL)

```bash
DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe \
  cargo test --locked -p weltgewebe-api --test db_domain_account_write_path \
  -- --include-ignored --test-threads=1
```

Testfälle:

- `account_create_persists_stable_webauthn_user_id_across_reload`:
  Erfolg (201), korrekte Spalten/Payloads, Cache enthält den Account sofort,
  kein JSONL-Append; DB, Cache und `load_accounts_from_postgres` verwenden
  dieselbe parsebare `webauthn_user_id`.
- `postgres_account_create_radius_persists_obfuscated_public_pos`:
  Bei `radius_m>0` speichert die DB die reale Residenz und den Radius, die
  Antwort ist gejittert, der Loader reproduziert exakt denselben Jitter.
- `postgres_account_create_duplicate_id_conflicts_without_side_effects`:
  Primärschlüsselkollision → `409`, keine Überschreibung, kein Cache-Update,
  kein JSONL.

### Lokaler PostgreSQL-Status

DB-Suiten für lokalen PostgreSQL-Proof sind vorbereitet (`db_domain_schema_migrations`,
`db_domain_backfill`, `db_domain_read_path`, `db_domain_account_write_path`).
Lokaler PostgreSQL-Proof in dieser Umgebung nicht ausgeführt. PR-CI ist maßgeblich; der PR-CI-Beleg steht aus
(Job `db-domain-account-write-path-proof` in `.github/workflows/api.yml`).

`suppress_public_pos` wird von `POST /accounts` nicht akzeptiert; Phase E-A
erhält Datenschutz über `visibility=private` und bestehende Loader-Semantik
(siehe `NewDomainAccountRow::from_jsonl_record` in `apps/api/src/domain_db.rs`).

## Verbleibende OPT-ARC-001-Phasen

| Phase | Inhalt | Status |
|---|---|---|
| A | Blueprint und Planung | done |
| B | PostgreSQL-Schema-Migrationen | done |
| C | Backfill-/Import-Proof | implementiert; CI-Beleg ausstehend |
| D | Read-Path-Switch (read-only, opt-in) | implementiert; CI-Beleg ausstehend |
| E-A | Account-Create-Write-Path (diese Slice) | implementiert; CI-Beleg ausstehend |
| E-B | Node-Patch-Write-Path (`PATCH /nodes`) | implementiert; CI-Beleg ausstehend |
| E (Rest) | Step-up-E-Mail-Persistenz, WebAuthn-Credential-Writeback, Passkey-Cutover sowie Backfill/Audit und späteres `NOT NULL` für Legacy-NULL-Werte | offen |
| F | Runtime-Smoke und CI-Beweis | offen |
| G | JSONL-Demontage | offen |

OPT-ARC-001 bleibt `partial`. Kein Produktions-Cutover, kein `done` ohne
grünen PR-CI-Beleg.
