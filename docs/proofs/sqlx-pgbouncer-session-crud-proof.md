---
id: proofs.sqlx-pgbouncer-session-crud-proof
title: "SQLx → PgBouncer → Postgres — Session-CRUD-Proof"
doc_type: report
status: active
created: 2026-05-12
lang: de
summary: >
  Rust/SQLx CRUD-Integrationstest gegen PgBouncer (transaction mode) → Postgres auf
  der sessions-Tabelle. Beweist den produktionsnahen Verbindungspfad mit
  statement_cache_capacity(0) als Mitigation für die SQLx/PgBouncer-Prepared-Statement-
  Inkompatibilität. Kein DbSessionStore, kein Auth-Umbau.
depends_on:
  - docs/reports/auth-persistence-runtime-proof.md
  - docs/reports/auth-persistence-next-step.md
relations:
  - type: relates_to
    target: docs/reports/auth-persistence-runtime-proof.md
  - type: relates_to
    target: docs/reports/auth-persistence-next-step.md
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
---

# SQLx → PgBouncer → Postgres — Session-CRUD-Proof

> **Zweck:** Beweis-PR. Kein DbSessionStore, kein Auth-Umbau, kein Cookie/Auth-Flow.
> Ziel: belegter Rust-SQLx-CRUD-Pfad auf der `sessions`-Tabelle durch PgBouncer
> im transaction mode.

---

## 1. Was genau bewiesen wurde

Dieser Proof schließt die offene Restlücke aus `docs/reports/auth-persistence-runtime-proof.md`,
Abschnitt 5:

> SQLx/Rust-API CRUD direkt Postgres — NOT_PROVEN
> SQLx/Rust-API CRUD via PgBouncer transaction mode — NOT_PROVEN

Der Integrationstest `apps/api/tests/sqlx_pgbouncer_session_crud.rs` beweist:

| Schritt | Was getestet wird |
|---|---|
| Pool-Verbindung | `sqlx::PgPool` via `PgPoolOptions::connect_with()` gegen PgBouncer |
| `statement_cache_capacity(0)` | explizit gesetzt in `PgConnectOptions`; Test läuft stabil durch |
| `CREATE TABLE IF NOT EXISTS` | sessions-Tabellenschema (identisch mit Migration) via SQLx |
| INSERT | Einen Session-Datensatz einfügen; `rows_affected() == 1` assertiert |
| SELECT | Datensatz lesen; id, account_id, device_id round-trip assertiert |
| UPDATE | `last_active` aktualisieren; `rows_affected() == 1` und Persistenz assertiert |
| DELETE | Datensatz löschen; `rows_affected() == 1` assertiert |
| COUNT nach DELETE | `SELECT COUNT(*) WHERE id = $1` gibt 0 zurück |

Der Test verwendet ausschließlich `sqlx::query`, `sqlx::query_scalar` und `sqlx::Row::get` —
kein psql, kein `sqlx::query!`-Makro, keine Live-Datenbank beim Compile.

---

## 2. Welche Verbindungsschicht genutzt wurde

```
Rust (tokio) → sqlx::PgPool → PgBouncer (POOL_MODE=transaction, Port 6432)
             → PostgreSQL 16 (Port 5432)
```

Konfiguration im Test:

```rust
let connect_opts = PgConnectOptions::from_str(&pgbouncer_url)
    .expect("PGBOUNCER_URL must be a valid postgres connection string")
    .statement_cache_capacity(0);

let pool = PgPoolOptions::new()
    .max_connections(2)
    .connect_with(connect_opts)
    .await
    .expect("failed to connect to PgBouncer");
```

`PGBOUNCER_URL` entspricht dem Produktionspfad der API (`DATABASE_URL` im Compose zeigt
auf PgBouncer Port 6432, nicht direkt auf Postgres Port 5432).

---

## 3. Warum `statement_cache_capacity(0)` relevant ist

SQLx verwendet standardmäßig das PostgreSQL Extended Query Protocol (prepared statements)
und cached diese Statements über die Lebensdauer einer Pool-Connection. Die Cache-Größe
ist standardmäßig 100.

**Das Problem mit PgBouncer transaction mode:**

PgBouncer im transaction mode weist einer Client-Verbindung nach jeder Transaktion eine
neue Backend-Connection zu. Eine von SQLx gecachte prepared statement handle ist an die
ursprüngliche Backend-Connection gebunden. Wird dieselbe Client-Connection aus dem Pool
wiederverwendet und erhält eine andere Backend-Connection, sind die gecachten Handles
ungültig — PgBouncer meldet dann:

```
ERROR: prepared statement "sqlx_s_1" does not exist
```

**Die Mitigation:**

`statement_cache_capacity(0)` deaktiviert den Cache vollständig. SQLx bereitet jede
Query neu vor (prepare → execute → close), alles innerhalb derselben Connection und
Transaktion. PgBouncer sieht keine persistenten Statement-Handles — die Inkompatibilität
entsteht nicht.

**Trade-off:**

Jede Query benötigt einen zusätzlichen Prepare-Roundtrip zum Server. Für die erwarteten
Session-Operationen (niedrige Frequenz, keine Hot-Path-Latenz-Anforderungen) ist dieser
Overhead akzeptabel und dokumentiert vertretbar.

---

## 4. Grenzen dieses Proofs

| Grenze | Beschreibung |
|---|---|
| Kein `sqlx::migrate!` | Der Test verwendet `CREATE TABLE IF NOT EXISTS`, nicht `sqlx::migrate!`. Die sqlx-Library-Migration ist noch nicht durch Rust-Code bewiesen. |
| Kein `sqlx-cli` | `sqlx migrate run` via CLI ist NOT_PROVEN (bereits in `auth-persistence-runtime-proof.md` dokumentiert). |
| Kein `edoburu/pgbouncer:1.20`-Image-Nachweis | Der Test läuft gegen den Stack mit dem konfigurierten PgBouncer. Die Image-Äquivalenz zu genau 1.20 ist nicht Teil dieses Proofs. |
| Kein `DbSessionStore` | Kein Auth-Umbau. Der Proof zeigt, dass der SQLx-Pfad funktioniert — er verdrahtet nichts in der Auth-Schicht. |
| Kein CI-DB-Step | Der Test ist `#[ignore]` und läuft nicht in der Standard-CI ohne `--include-ignored` und aktive DB. |
| Kein Parallel-/Lasttest | Nur sequenzieller CRUD-Smoke. Transaktionssicherheit unter Concurrent Load ist nicht Teil dieses Proofs. |

---

## 5. Testausführung

Der Test ist `#[ignore]` und wird im Standard-CI-Lauf (`cargo test --locked`) nicht
ausgeführt — Offline-Tests bleiben unverändert grün.

Für den Proof-Lauf mit aktiver DB:

```bash
PGBOUNCER_URL=postgres://welt:gewebe@localhost:6432/weltgewebe \
  cargo test -p weltgewebe-api -- sqlx_pgbouncer --include-ignored
```

Erwartete Ausgabe:

```text
test sqlx_pgbouncer_session_crud_through_transaction_mode ... ok
```

---

## 6. Warum dieser PR das korrekte Gate vor dem Persistenz-PR ist

Aus `docs/reports/auth-persistence-runtime-proof.md`, Abschnitt 8:

> **Stop-Regel:** Wenn SQLx über PgBouncer scheitert, keine Session-Persistenz
> verdrahten — erst Ursache isolieren und Mitigation belegen.

Dieser PR liefert den Beweis, dass SQLx/PgBouncer mit `statement_cache_capacity(0)` stabil
funktioniert. Erst mit diesem Nachweis ist der `DbSessionStore`-PR architektonisch
abgesichert — nicht vorher.

---

## 7. Dateien dieses PRs

| Datei | Aktion | Beschreibung |
|---|---|---|
| `apps/api/Cargo.toml` | geändert | `"chrono"` zu sqlx-Features hinzugefügt (nötig für `DateTime<Utc>`-Binding) |
| `apps/api/tests/sqlx_pgbouncer_session_crud.rs` | neu | Integrationstest (ignoriert, requires PGBOUNCER_URL) |
| `docs/proofs/sqlx-pgbouncer-session-crud-proof.md` | neu | Dieser Proof-Report |

Nicht verändert: `apps/api/src/`, Migrations, Auth-Middleware, SessionStore, Routen, CI-Workflows.
