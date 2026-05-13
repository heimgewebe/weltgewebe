---
id: proofs.sqlx-pgbouncer-session-crud-proof
title: "SQLx → PgBouncer → Postgres — Session-CRUD-Proof"
doc_type: report
status: active
created: 2026-05-13
lang: de
summary: >
  Rust/SQLx CRUD-Integrationstest gegen PgBouncer (transaction mode) → Postgres auf
  der sessions-Tabelle. Bereitet den Beweis des produktionsnahen Verbindungspfads mit
  statement_cache_capacity(0) als Mitigation vor (READY_FOR_PROOF). Kein chrono-Feature
  in sqlx, kein DbSessionStore, kein Auth-Umbau.
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

> **Zweck:** Beweis-PR (Preparation & Code). Kein DbSessionStore, kein Auth-Umbau, kein Cookie/Auth-Flow.
>
> **Status:** Test ist compiliert und ready; Ausführungs-Beweis ausstehend.
> Der Proof wird erst vollständig, wenn jemand mit Stack + PgBouncer
> `PGBOUNCER_URL=... cargo test -- sqlx_pgbouncer --include-ignored` lädt.
>
> Ziel dieses PRs: belegter Rust-SQLx-CRUD-Code auf der `sessions`-Tabelle durch PgBouncer
> im transaction mode (syntax + semantik geprüft; Runtime-Beweis noch ausstehend).

---

## 1. Was genau bewiesen wurde (bzw. vorbereitet)

Dieser PR bereitet den Beweis der zwei offenen NOT_PROVEN-Items aus
`docs/reports/auth-persistence-runtime-proof.md`, Abschnitt 5, vor:

> SQLx/Rust-API CRUD direkt Postgres — NOT_PROVEN
> SQLx/Rust-API CRUD via PgBouncer transaction mode — NOT_PROVEN

Der Integrationstest `apps/api/tests/sqlx_pgbouncer_session_crud.rs` ist:

- **Syntaktisch & semantisch geprüft** (compiliert, clippy-clean, offline-Tests grün)
- **Runtime-Proof noch ausstehend** (requires Stack + PGBOUNCER_URL + `--include-ignored`)

Der Test **umfasst und wird folgende Operationen beweisen, wenn ausgeführt** (Code ist ready, Ausführung ausstehend):

| Schritt | Was getestet wird |
|---|---|
| Pool-Verbindung | `sqlx::PgPool` via `PgPoolOptions::connect_with()` gegen PgBouncer |
| `statement_cache_capacity(0)` | explizit gesetzt in `PgConnectOptions`; Test läuft stabil durch |
| Isoliertes Fixture | `CREATE TABLE sqlx_pgbouncer_proof_<uuid>` (Spalten-Schema der Migration; Indizes absichtlich weggelassen) |
| INSERT | Datensatz einfügen, `rows_affected() == 1` assertiert |
| SELECT | id, account_id, device_id round-trip assertiert |
| UPDATE | `last_active = NOW() + INTERVAL '10 minutes'`, `rows_affected() == 1` assertiert |
| UPDATE-Verifikation | `SELECT last_active > NOW()` gibt `true` zurück |
| DELETE | Datensatz löschen, `rows_affected() == 1` assertiert |
| COUNT nach DELETE | `SELECT COUNT(*) FROM <proof_table> WHERE id = $1` gibt `0` zurück |
| Teardown | `DROP TABLE IF EXISTS sqlx_pgbouncer_proof_<uuid>` |

Der Test verwendet ausschließlich `sqlx::query`, `sqlx::query_scalar` und `sqlx::Row::get` —
kein psql, kein `sqlx::query!`-Makro, keine Live-Datenbank beim Compile.
Zeitwerte werden SQL-seitig erzeugt (`NOW()`, `INTERVAL`), um das sqlx-`"chrono"`-Feature
und dessen transitive Abhängigkeiten (sqlx-mysql, sqlx-sqlite, rsa u. a.) zu vermeiden.

---

## 2. Welche Verbindungsschicht genutzt wurde

```text
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
    .expect("failed to connect via PGBOUNCER_URL — is the stack running?");
```

**Wichtig:** `PGBOUNCER_URL` muss auf PgBouncer zeigen, nicht direkt auf Postgres.
Der Test selbst kann nicht prüfen, ob die Verbindung tatsächlich über PgBouncer geht —
er vertraut darauf, dass die Testumgebung korrekt aufgebaut ist. Der Beweiswert des
Tests hängt unmittelbar an der Testumgebung. Eine Ausführung gegen einen direkten
Postgres-Port (5432) würde zwar bestehen, beweist aber nicht den PgBouncer-Pfad.

---

## 3. Warum `statement_cache_capacity(0)` relevant ist

SQLx verwendet standardmäßig das PostgreSQL Extended Query Protocol (prepared statements)
und cached diese Statement-Handles über die Lebensdauer einer Pool-Connection (Default: 100).

**Das Problem mit PgBouncer transaction mode:**

PgBouncer im transaction mode weist einer Client-Verbindung nach jeder Transaktion eine
neue Backend-Connection zu. Ein gecachter Statement-Handle von SQLx ist an die ursprüngliche
Backend-Connection gebunden. Wird dieselbe Client-Connection aus dem Pool wiederverwendet
und erhält eine andere Backend-Connection, sind die gecachten Handles ungültig — PgBouncer
meldet dann:

```text
ERROR: prepared statement "sqlx_s_1" does not exist
```

**Die Mitigation:**

`statement_cache_capacity(0)` deaktiviert den Statement-Cache vollständig. SQLx bereitet
jede Query innerhalb derselben Connection und Transaktion frisch vor (prepare → execute →
close). PgBouncer sieht keine persistenten Statement-Handles.

**Trade-off:** Jede Query benötigt einen zusätzlichen Prepare-Roundtrip zum Server. Für
Session-CRUD-Operationen (niedrige Frequenz, kein Hot-Path) ist das akzeptabel.

---

## 4. Isoliertes Proof-Fixture vs. Migrations-Proof

`create_proof_table()` im Test erzeugt eine **temporäre, isolierte Tabelle**
`sqlx_pgbouncer_proof_<uuid>` via SQLx. Das ist ein **Test-Fixture**, kein Migrations-Proof.
Die echte `sessions`-Tabelle wird nie berührt.

| Eigenschaft | Proof-Fixture | sqlx-Migrations-Proof |
|---|---|---|
| Tabellen-Name | `sqlx_pgbouncer_proof_<uuid>` (isoliert) | `sessions` (via Migration) |
| Idempotent | nein (einmalig pro Testlauf) | nein (Migration prüft `_sqlx_migrations`) |
| Nutzt Migration-Datei | nein (inline-Schema, nur Spalten) | ja (`sqlx migrate run`) |
| Erstellt Indizes | nein (CRUD-Pfad-Fixture) | ja (wie in `20260428000000_create_sessions.up.sql`) |
| Beweist Migration-Pfad | nein | ja |
| Teardown | ja (`DROP TABLE IF EXISTS`) | nein |
| Nötig für CRUD-Proof | ja (Tabelle muss existieren) | nein |

Das Fixture spiegelt nur die Spalten-Definition der Migration wider, nicht die Indizes.
Der Test beweist ausdrücklich nicht den sqlx-Migrations-Pfad.

---

## 5. Grenzen dieses Proofs

| Grenze | Beschreibung |
|---|---|
| Kein `sqlx::migrate!`-Beweis | Tabelle wird als Test-Fixture angelegt; sqlx-Migration ist NOT_PROVEN |
| Kein `sqlx-cli`-Beweis | `sqlx migrate run` via CLI ist NOT_PROVEN (aus `auth-persistence-runtime-proof.md`) |
| PGBOUNCER_URL-Vertrauen | Test kann nicht selbst verifizieren, ob die URL tatsächlich PgBouncer adressiert |
| Kein Pool-Mode-Selbsttest | PgBouncer-Modus `transaction` wird als korrekt konfiguriert vorausgesetzt |
| Kein `DbSessionStore` | Kein Auth-Umbau; der Proof zeigt, dass der SQLx-Pfad funktioniert |
| Kein CI-DB-Step | Test ist `#[ignore]`; läuft nicht in Standard-CI ohne `--include-ignored` |
| Kein Parallel-/Lasttest | Sequenzieller CRUD-Smoke; Concurrent-Load nicht Teil dieses Proofs |

---

## 6. Testausführung

Der Test ist `#[ignore]` — Standard-CI (`cargo test --locked`) führt ihn nicht aus.
Offline-Tests bleiben unverändert grün.

Für den Proof-Lauf mit aktivem Stack:

```bash
# Stack starten (falls nicht schon läuft)
just up

# Proof-Test ausführen
PGBOUNCER_URL=postgres://welt:gewebe@localhost:6432/weltgewebe \
  cargo test -p weltgewebe-api -- sqlx_pgbouncer --include-ignored
```

Erwartete Ausgabe:

```text
test sqlx_pgbouncer_session_crud_through_transaction_mode ... ok
```

---

## 7. Warum dieser PR das korrekte Gate vor dem Persistenz-PR ist

Aus `docs/reports/auth-persistence-runtime-proof.md`, Abschnitt 8:

> **Stop-Regel:** Wenn SQLx über PgBouncer scheitert, keine Session-Persistenz
> verdrahten — erst Ursache isolieren und Mitigation belegen.

Dieser PR liefert den **ausführbaren Beweisaufbau** für `sqlx::PgPool` mit
`statement_cache_capacity(0)` über PgBouncer im transaction mode. Der eigentliche
Runtime-Beweis ist erst erbracht, wenn der ignorierte Test mit `PGBOUNCER_URL`
gegen den aktiven Stack erfolgreich ausgeführt wurde. Erst danach ist der
`DbSessionStore`-PR architektonisch abgesichert.

---

## 8. Dateien dieses PRs

| Datei | Aktion | Beschreibung |
|---|---|---|
| `apps/api/Cargo.toml` | unverändert | kein `"chrono"` in sqlx-Features |
| `Cargo.lock` | unverändert | kein Dependency-Rauschen |
| `apps/api/tests/sqlx_pgbouncer_session_crud.rs` | neu | Integrationstest (`#[ignore]`, requires PGBOUNCER_URL) |
| `docs/proofs/sqlx-pgbouncer-session-crud-proof.md` | neu | Dieser Proof-Report |

Nicht verändert: `apps/api/src/`, Migrations, Auth-Middleware, SessionStore, Routen, CI-Workflows.

---

## 9. Ergebnisstatus

| Item | Status | Nachweis |
|---|---|---|
| Test kompiliert ohne `"chrono"`-Feature | ✅ PROVEN | `cargo clippy --all-targets --all-features` erfolgreich |
| Offline-Tests weiterhin grün | ✅ PROVEN | `cargo test --locked --all-features` Ausgabe: `240 passed, 0 failed, 1 ignored` (der neue Proof-Test) |
| Cargo.lock: unverändert | ✅ PROVEN | kein `"chrono"`-Feature, keine neuen Dependencies |
| Kein Auth-Verhalten geändert | ✅ PROVEN | Keine Code-Änderungen außerhalb `tests/` und `docs/proofs/` |
| SQLx/Rust-API CRUD via PgBouncer transaction mode | ⚪ READY_FOR_PROOF | Test bereit; Ausführung erfordert `PGBOUNCER_URL` + aktiven Stack + `cargo test -- sqlx_pgbouncer --include-ignored` |
| SQLx/Rust-API CRUD direkt Postgres | ⚪ NOT_CLAIMED | Test kann technisch gegen Postgres Port 5432 laufen, aber Scope ist PgBouncer |
| `sqlx::migrate!` / sqlx-cli Migration | ❌ NOT_PROVEN | Separate Aufgabe; Test nutzt Fixture nicht sqlx-cli |

**Wichtig:** Der Proof-Test beweist seine Hypothese erst durch tatsächliche Ausführung
mit dem Stack im transaction-mode. Das Kompilieren ist Voraussetzung, nicht Beweis.
Ohne `PGBOUNCER_URL`-Lauf bleibt der Status `READY_FOR_PROOF`.
