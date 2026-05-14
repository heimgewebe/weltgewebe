---
id: proofs.sqlx-postgres-direct-session-crud-proof
title: "SQLx \u2192 direkter PostgreSQL \u2014 Session-CRUD-Proof"
doc_type: report
status: active
created: 2026-05-14
lang: de
summary: >
  Rust/SQLx CRUD-Integrationstest gegen direkten PostgreSQL-Zugriff (DATABASE_URL /
  PG_DIRECT_URL) auf einem sessions-spaltenkompatiblen Proof-Fixture.
  Produktionspfad per ADR-0007. Ergebnis: PROVEN.
  Kein PgBouncer, kein statement_cache_capacity(0), kein DbSessionStore,
  kein Auth-Umbau.
depends_on:
  - docs/reports/auth-persistence-runtime-proof.md
  - docs/adr/ADR-0007__auth-persistence-production-db-path.md
  - docs/blueprints/auth-persistence-runtime-proof.md
relations:
  - type: closes_gap
    target: docs/reports/auth-persistence-runtime-proof.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
  - type: relates_to
    target: docs/blueprints/auth-persistence-runtime-proof.md
  - type: contrast_with
    target: docs/proofs/sqlx-pgbouncer-session-crud-proof.md
---

# SQLx \u2192 direkter PostgreSQL \u2014 Session-CRUD-Proof

> **Zweck:** Beweis-PR. Kein DbSessionStore, kein Auth-Umbau, kein Cookie/Auth-Flow.
>
> **Status: PROVEN** \u2014 Test ausgef\u00fchrt gegen disposable-local PostgreSQL 17
> auf Port 5432; alle Assertions bestanden.
>
> Dieses Dokument schlie\u00dft die Restl\u00fccke
> `SQLx/Rust-API CRUD direkt Postgres` aus `docs/reports/auth-persistence-runtime-proof.md`
> (Abschnitt 5).

---

## 1. Was bewiesen wurde

Dieses PR beweist den direkten SQLx/Postgres-Persistenzpfad (ADR-0007-Produktionspfad):

> `SQLx/Rust-API CRUD direkt Postgres \u2014 NOT_PROVEN` (auth-persistence-runtime-proof.md)

| Schritt | Was getestet wird |
|---|---|
| URL-Verifikation | `PG_DIRECT_URL` \u00fcberschreibt `DATABASE_URL`; fehlt beides: harter Fehler (kein Skip) |
| Anti-PgBouncer-Guard | URL mit Port 6432 l\u00e4sst Test sofort fehlschlagen |
| Pool-Verbindung | `sqlx::PgPool` via `PgPoolOptions::connect_with()` direkt gegen Postgres |
| Kein `statement_cache_capacity(0)` | Standard-SQLx-Prepared-Statement-Verhalten \u2014 kein PgBouncer-Workaround |
| Proof-Fixture | `CREATE TABLE sqlx_pg_direct_proof_<uuid>` (sessions-spaltenkompatibel; Indizes weggelassen) |
| INSERT | Datensatz einf\u00fcgen, `rows_affected() == 1` assertiert |
| SELECT | id, account_id, device_id round-trip assertiert |
| UPDATE last_active | `last_active = NOW() + INTERVAL '10 minutes'`, `rows_affected() == 1` assertiert |
| UPDATE-Verifikation | `SELECT last_active > NOW()` gibt `true` zur\u00fcck |
| DELETE | Datensatz l\u00f6schen, `rows_affected() == 1` assertiert |
| COUNT nach DELETE | `SELECT COUNT(*) FROM <proof_table> WHERE id = $1` gibt `0` zur\u00fcck |
| Teardown | `DROP TABLE IF EXISTS sqlx_pg_direct_proof_<uuid>` |

---

## 2. Ausgef\u00fchrte Kommandos und Ausgaben

### 2.1 Vorbereitungen (disposable-local DB-Klasse)

DB-Klasse: **`disposable-local`** \u2014 PostgreSQL 17 (Debian-Paket), frisch gestartet,
Port 5432, Datenbank `weltgewebe_proof`, User `welt`.

```bash
sudo service postgresql start
sudo -u postgres psql -c "CREATE USER welt WITH PASSWORD 'gewebe';"
sudo -u postgres psql -c "CREATE DATABASE weltgewebe_proof OWNER welt;"
```

Ausgaben: `Starting PostgreSQL 17 database server: main.` / `CREATE ROLE` / `CREATE DATABASE`.

### 2.2 Proof-Testlauf (SQLx direkt)

```bash
PG_DIRECT_URL="postgres://welt:gewebe@localhost:5432/weltgewebe_proof" \
  cargo test --locked -p weltgewebe-api --test sqlx_postgres_direct_session_crud \
  -- --include-ignored
```

Ausgabe:

```text
Running tests/sqlx_postgres_direct_session_crud.rs
running 1 test
test sqlx_postgres_direct_session_crud ... ok
test result: ok. 1 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 0.06s
```

### 2.3 PgBouncer-Guard-Verifikation

```bash
PG_DIRECT_URL="postgres://welt:gewebe@localhost:6432/weltgewebe_proof" \
  cargo test --locked -p weltgewebe-api --test sqlx_postgres_direct_session_crud \
  -- --include-ignored
```

Ausgabe:

```text
test sqlx_postgres_direct_session_crud ... FAILED
panicked at apps/api/tests/sqlx_postgres_direct_session_crud.rs:63:5:
PG_DIRECT_URL / DATABASE_URL must point to direct PostgreSQL, not PgBouncer
(port 6432 detected in URL). Use port 5432 or the correct direct-Postgres port.
```

### 2.4 Missing-URL-Verifikation (kein stiller Skip)

```bash
unset DATABASE_URL && unset PG_DIRECT_URL && \
  cargo test --locked -p weltgewebe-api --test sqlx_postgres_direct_session_crud \
  -- --include-ignored
```

Ausgabe:

```text
test sqlx_postgres_direct_session_crud ... FAILED
panicked at ...:227:10:
PG_DIRECT_URL or DATABASE_URL must be set to run this proof test -- ...: NotPresent
```

### 2.5 Offline-Tests

```bash
cargo test --locked -p weltgewebe-api
```

Ausgabe: alle 240+ Tests bestanden, 0 fehlgeschlagen, 2 ignoriert (PgBouncer- und Direktpfad-Proof).

---

## 3. DB-Klasse

### disposable-local

PostgreSQL 17 (Debian-Paket, `postgresql` v17+278), Datenbank `weltgewebe_proof`,
Port 5432. Keine geteilten oder produktiven Daten. Testinstanz ausschlie\u00dflich f\u00fcr diesen Proof.

Der Test nutzt **kein** `sqlx::migrate!` \u2014 er erstellt ein isoliertes Proof-Fixture
(`sqlx_pg_direct_proof_<uuid>`) und l\u00f6scht es nach dem Test. Die reale `sessions`-Tabelle
und die Migration `20260428000000_create_sessions.up.sql` werden nicht ber\u00fchrt.

---

## 4. Was dieser Proof belegt

| Teilschritt | Ergebnis |
|---|---|
| SQLx direkt Postgres: Pool-Verbindung via DATABASE_URL | \u2705 PROVEN |
| SQLx direkt Postgres: INSERT | \u2705 PROVEN |
| SQLx direkt Postgres: SELECT (round-trip) | \u2705 PROVEN |
| SQLx direkt Postgres: UPDATE last_active | \u2705 PROVEN |
| SQLx direkt Postgres: UPDATE-Verifikation (boolean) | \u2705 PROVEN |
| SQLx direkt Postgres: DELETE | \u2705 PROVEN |
| SQLx direkt Postgres: COUNT nach DELETE | \u2705 PROVEN |
| Anti-PgBouncer-Guard (Port 6432 rejected) | \u2705 PROVEN |
| Hard-Fail bei fehlender URL (kein stiller Skip) | \u2705 PROVEN |
| Kein `statement_cache_capacity(0)` n\u00f6tig | \u2705 PROVEN |
| Offline-Tests unver\u00e4ndert gr\u00fcn | \u2705 PROVEN |
| Kein Auth-Verhalten ge\u00e4ndert | \u2705 PROVEN |

### Gesamtergebnis: PROVEN

Der SQLx/Rust-Direktpfad gegen PostgreSQL via `DATABASE_URL` / `PG_DIRECT_URL` ist
runtime-bewiesen. Dieser Proof schlie\u00dft die Restl\u00fccke aus
`docs/reports/auth-persistence-runtime-proof.md`, Abschnitt 5:

> `SQLx/Rust-API CRUD direkt Postgres \u2014 NOT_PROVEN` \u2192 **PROVEN**

---

## 5. Was dieser Proof nicht belegt

- `sqlx::migrate!` oder `sqlx-cli`-Migrationsausf\u00fchrung (separater Proof-Schritt)
- Produktion `SessionStore`-Verdrahtung (kein `DbSessionStore` in diesem PR)
- PgBouncer-Kompatibilit\u00e4t (siehe `docs/proofs/sqlx-pgbouncer-session-crud-proof.md`)

---

## 6. Abgrenzung zum PgBouncer-Proof

| Merkmal | Dieser Proof (direkt) | PgBouncer-Proof |
|---|---|---|
| Verbindungspfad | `DATABASE_URL` \u2192 Postgres direkt | `PGBOUNCER_URL` \u2192 PgBouncer \u2192 Postgres |
| `statement_cache_capacity(0)` | **nicht gesetzt** | gesetzt (Mitigation) |
| Port | 5432 (direkt) | 6432 (PgBouncer) |
| ADR-0007-Rolle | Produktionspfad | Dev-/Spezialpfad |
| Status | **PROVEN** | READY\_FOR\_PROOF |
| Anti-Port-Guard | rejects 6432 | nicht vorhanden |

---

## 7. Testdatei

`apps/api/tests/sqlx_postgres_direct_session_crud.rs`

Ausf\u00fchren:

```bash
PG_DIRECT_URL=postgres://welt:gewebe@localhost:5432/weltgewebe_proof \
  cargo test -p weltgewebe-api -- sqlx_postgres_direct --include-ignored
```
