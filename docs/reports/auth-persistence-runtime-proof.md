---
id: reports.auth-persistence-runtime-proof
title: "Auth-Persistenz — Runtime-Proof"
doc_type: report
status: deprecated
lifecycle_state: superseded
lifecycle: proof
owner_task: OPT-API-002
superseded_by: docs/reports/optimierungsstatus.md
created: 2026-05-12
lang: de
summary: >
  Runtime-Proof-Bericht für den Auth-Persistenz-Pfad (OPT-API-002/003).
  Gesamtergebnis: PARTIAL_PROVEN. psql-basierter Migrations- und CRUD-Smoke
  gegen disposable-local PostgreSQL und PgBouncer (transaction mode) sind belegt.
  SQLx/Rust-CRUD gegen die Session-Tabelle im direkten PostgreSQL-Pfad ist ebenfalls belegt
  (siehe docs/proofs/sqlx-postgres-direct-session-crud-proof.md).
  SQLx/Rust-CRUD gegen PgBouncer, sqlx-cli-Migration und exaktes
  Stack-PgBouncer-Image bleiben NOT_PROVEN. ADR-0007 schränkt PgBouncer auf
  Dev-/Spezialpfade ein; der Produktionspfad ist DATABASE_URL → direkter
  PostgreSQL-Zugriff.
depends_on:
  - docs/blueprints/auth-persistence-runtime-proof.md
  - docs/reports/auth-persistence-next-step.md
  - docs/proofs/sqlx-postgres-direct-session-crud-proof.md
relations:
  - type: relates_to
    target: docs/blueprints/auth-persistence-runtime-proof.md
  - type: relates_to
    target: docs/reports/auth-persistence-next-step.md
  - type: relates_to
    target: docs/proofs/sqlx-postgres-direct-session-crud-proof.md
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
---

# Auth-Persistenz — Runtime-Proof

> **Zweck:** Beweis-PR. Kein Auth-Umbau, kein `DbSessionStore`, keine
> `SessionBackend`-Abstraktion. Kein register/verify.
> Ziel: belegter Runtime-Pfad für die vorhandene `sessions`-Migration mit psql
> und PgBouncer gegen eine wegwerfbare lokale Datenbank. Nach ADR-0007 ist dieser
> PgBouncer-Pfad ein Dev-/Spezialpfad; Produktion nutzt `DATABASE_URL` für
> direkten PostgreSQL-Zugriff.
>
> Blueprint: `docs/blueprints/auth-persistence-runtime-proof.md`

## Lifecycle

- **Lifecycle-State:** superseded
- **Lifecycle:** proof
- **Owner-Task:** OPT-API-002
- **Superseded by:** `docs/reports/optimierungsstatus.md`
- **Bewertung:** Historischer Partial-Proof für Migration und CRUD-Pfad. Der
  Bericht bleibt als Belegkette nützlich, wurde aber durch die spätere
  `DbSessionStore`-Implementierung und den CI-belegten Persistenzpfad überholt.

---

## 1. Ziel

Beweisen, dass:

1. die vorhandene `sessions`-Migration (`apps/api/migrations/20260428000000_create_sessions.up.sql`)
   sauber gegen PostgreSQL läuft (up + down + up),
2. minimaler CRUD (INSERT / SELECT / UPDATE / DELETE) gegen die `sessions`-Tabelle
   direkt über PostgreSQL funktioniert,
3. dieselben CRUD-Operationen über PgBouncer im `POOL_MODE=transaction` via `psql`
   funktionieren,
4. alle bestehenden Offline-Tests (`cargo test --locked -p weltgewebe-api`) weiterhin
   grün sind,
5. kein Auth-Verhalten verändert wurde.

---

## 2. Ist-Zustand vor dem Proof

| Komponente | Befund |
|---|---|
| Migration | `apps/api/migrations/20260428000000_create_sessions.up.sql` vorhanden — `CREATE TABLE sessions` + 2 Indizes |
| Down-Migration | `apps/api/migrations/20260428000000_create_sessions.down.sql` vorhanden — `DROP TABLE sessions` |
| SQLx | Cargo.toml: `sqlx = { version = "0.8.1", features = ["runtime-tokio", "postgres"] }` |
| PgBouncer im Stack | `infra/compose/compose.core.yml`: `edoburu/pgbouncer:1.20`, `POOL_MODE: transaction`, Port 6432 |
| API-Verbindung | Dev-Stack: API-Container verbindet über PgBouncer (Port 6432). Produktion nach ADR-0007: `DATABASE_URL` → direkter PostgreSQL-Zugriff. |
| `db_pool` in ApiState | vorhanden, aber ausschließlich für Health-Check verdrahtet — kein Auth-Pfad nutzt die DB |
| `sqlx-cli` | **nicht** in der CI-Umgebung installiert; Justfile dokumentiert Install-Befehl |
| SessionStore | in-memory, kein Auth-Umbau in diesem PR |

---

## 3. DB-Klasse

### disposable-local

Verwendet wurde ein frisch gestarteter Docker-Container `postgres:16` auf Port 5499,
Datenbank `weltgewebe_proof`. Der Container wurde ausschließlich für diesen Beweis
gestartet und enthält keine geteilten oder produktiven Daten. Die Down-Migration darf
in dieser DB-Klasse ausgeführt werden.

---

## 4. Ausgeführte Kommandos und Outputs

### 4.1 Pflichtdiagnose

```text
git status --short
→ (keine Ausgabe — sauberer Arbeitsstand)

rg -n "sqlx|postgres|PgPool|DATABASE_URL" apps/api/Cargo.toml Cargo.toml .env.example Justfile
→ sqlx 0.8.1 in apps/api/Cargo.toml, DATABASE_URL=postgres://welt:gewebe@localhost:5432/weltgewebe
  in .env.example, PGBOUNCER_URL=postgres://welt:gewebe@localhost:6432/weltgewebe

rg -n "pgbouncer|6432|POOL_MODE|pool_mode|transaction|session" infra .env.example docs apps/api
→ compose.core.yml: POOL_MODE: transaction, Port 6432
  .env.example: PGBOUNCER_URL auf Port 6432
  API-Container: DATABASE_URL=postgres://welt:gewebe@pgbouncer:6432/weltgewebe

ls -la apps/api/migrations
→ 20260428000000_create_sessions.up.sql (376 Bytes)
  20260428000000_create_sessions.down.sql (21 Bytes)
```

### 4.2 Migration gegen direkte PostgreSQL-Verbindung

DB-Klasse: **`disposable-local`** — Port 5499, Datenbank `weltgewebe_proof`.

`sqlx-cli` nicht verfügbar. Migration via `psql -f`.

```bash
PGPASSWORD=gewebe psql -h localhost -p 5499 -U welt -d weltgewebe_proof \
  -f apps/api/migrations/20260428000000_create_sessions.up.sql -v ON_ERROR_STOP=1

Ausgabe:
  CREATE TABLE
  CREATE INDEX
  CREATE INDEX
```

Tabellenstruktur verifiziert:

```text
\d sessions

                     Table "public.sessions"
   Column    |           Type           | Collation | Nullable | Default
-------------+--------------------------+-----------+----------+---------
 id          | text                     |           | not null |
 account_id  | text                     |           | not null |
 device_id   | text                     |           | not null |
 created_at  | timestamp with time zone |           | not null |
 last_active | timestamp with time zone |           | not null |
 expires_at  | timestamp with time zone |           | not null |
Indexes:
    "sessions_pkey" PRIMARY KEY, btree (id)
    "sessions_account_id" btree (account_id)
    "sessions_expires_at" btree (expires_at)
```

### 4.3 Down-Migration und erneute Up-Migration (Reversibilität)

```text
PGPASSWORD=gewebe psql -h localhost -p 5499 -U welt -d weltgewebe_proof \
  -f apps/api/migrations/20260428000000_create_sessions.down.sql -v ON_ERROR_STOP=1
→ DROP TABLE

PGPASSWORD=gewebe psql -h localhost -p 5499 -U welt -d weltgewebe_proof \
  -c "\dt sessions"
→ Did not find any relation named "sessions".

PGPASSWORD=gewebe psql -h localhost -p 5499 -U welt -d weltgewebe_proof \
  -f apps/api/migrations/20260428000000_create_sessions.up.sql -v ON_ERROR_STOP=1
→ CREATE TABLE / CREATE INDEX / CREATE INDEX

PGPASSWORD=gewebe psql -h localhost -p 5499 -U welt -d weltgewebe_proof \
  -c "SELECT COUNT(*) FROM sessions;"
→ count: 0
```

### 4.4 CRUD-Smoke — direkte PostgreSQL-Verbindung

```sql
-- INSERT
INSERT INTO sessions (id, account_id, device_id, created_at, last_active, expires_at)
VALUES ('smoke-session-001', 'account-test-001', 'device-test-001',
        NOW(), NOW(), NOW() + INTERVAL '24 hours');
→ INSERT 0 1

-- SELECT
SELECT id, account_id, device_id, created_at, last_active, expires_at
FROM sessions WHERE id = 'smoke-session-001';
→ 1 Zeile zurück, alle Spalten korrekt

-- UPDATE last_active
UPDATE sessions SET last_active = NOW() + INTERVAL '1 minute'
WHERE id = 'smoke-session-001' RETURNING id, last_active;
→ UPDATE 1, last_active aktualisiert

-- DELETE
DELETE FROM sessions WHERE id = 'smoke-session-001' RETURNING id;
→ DELETE 1

-- Bestätigung
SELECT COUNT(*) FROM sessions;
→ count: 0
```

### 4.5 PgBouncer-Verbindungspfad

Stack-Ziel: `edoburu/pgbouncer:1.20`, `POOL_MODE=transaction`.
Für den Proof verwendet: natives `pgbouncer 1.22.0` (Ubuntu-Paket) mit
`POOL_MODE=transaction`-Konfiguration, da das Docker-Image
`edoburu/pgbouncer:1.20` in der Sandbox-Registry nicht verfügbar war. Die Version
1.22.0 ist neuer als 1.20. Für den getesteten psql-basierten CRUD-Smoke wurde
keine abweichende PgBouncer-Semantik beobachtet; das exakte Stack-Image
`edoburu/pgbouncer:1.20` bleibt jedoch NOT_PROVEN. Eine vollständige
versionsspezifische Differenzanalyse zwischen 1.22.0 und 1.20 wurde in diesem
Proof nicht durchgeführt.

PgBouncer-Konfiguration:

```ini
[databases]
weltgewebe_proof = host=172.17.0.2 port=5432 dbname=weltgewebe_proof user=welt password=gewebe

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6499
auth_type = trust
pool_mode = transaction
max_client_conn = 50
default_pool_size = 5
```

CRUD-Smoke via PgBouncer (Port 6499):

```sql
-- SELECT (Baseline)
SELECT COUNT(*) FROM sessions;
→ sessions_count: 0

-- INSERT
INSERT INTO sessions (...) VALUES ('pgb-smoke-001', 'account-001', 'device-001', ...);
→ INSERT 0 1

-- SELECT
SELECT id, account_id FROM sessions WHERE id = 'pgb-smoke-001';
→ 1 Zeile: pgb-smoke-001 / account-001

-- UPDATE last_active
UPDATE sessions SET last_active = NOW() + INTERVAL '5 minutes'
WHERE id = 'pgb-smoke-001' RETURNING id, last_active;
→ UPDATE 1

-- DELETE
DELETE FROM sessions WHERE id = 'pgb-smoke-001' RETURNING id;
→ DELETE 1
```

PgBouncer-Log: keine Fehler, keine Warnungen. Verbindung zu `172.17.0.2:5432` erfolgreich
aufgebaut, alle Operationen durchgelaufen.

### 4.6 Cargo Tests

```text
cargo test --locked -p weltgewebe-api

Ergebnis: alle Suites grün
  lib:    146 passed
  api_auth: 73 passed
  weitere Suites: 21 passed
  Gesamt: 240 passed, 0 failed
```

Die Offline-Tests laufen ohne Datenbankverbindung durch — das Offline-Prinzip
aus Blueprint Abschnitt 3.4 ist erfüllt.

### 4.7 Git-Diff-Check

```bash
git diff --check
→ (keine Ausgabe, Exit 0 — keine Whitespace-Fehler)
```

---

## 5. Ergebnis

| Teilschritt | Ergebnis |
|---|---|
| Migration up (direkt Postgres, psql) | ✅ PROVEN |
| Tabelle und Indizes korrekt | ✅ PROVEN |
| Migration down (disposable-local, psql) | ✅ PROVEN |
| Migration up nach down (psql) | ✅ PROVEN |
| CRUD direkt Postgres (psql) | ✅ PROVEN |
| CRUD via PgBouncer transaction mode (psql) | ✅ PROVEN |
| Offline-Tests grün | ✅ PROVEN |
| Kein Auth-Verhalten geändert | ✅ PROVEN |
| SQLx/Rust CRUD gegen Session-Tabelle direkt Postgres | ✅ PROVEN |
| SQLx/Rust CRUD via PgBouncer transaction mode | ❌ NOT_PROVEN |
| `sqlx migrate run` via sqlx-cli | ❌ NOT_PROVEN |
| Exaktes Stack-Image `edoburu/pgbouncer:1.20` | ❌ NOT_PROVEN |

### Gesamtergebnis: PARTIAL_PROVEN

Der psql-basierte Migrations- und CRUD-Pfad gegen PostgreSQL und PgBouncer
(transaction mode) ist reproduzierbar belegt. Der direkte SQLx/Rust-CRUD-
Pfad gegen die Session-Tabelle in PostgreSQL ist ebenfalls belegt (separater
Proof-Report: `docs/proofs/sqlx-postgres-direct-session-crud-proof.md`).
Offen bleibt der SQLx/Rust-Pfad gegen PgBouncer transaction mode für
Dev-/Spezialfälle. Nach ADR-0007 ist PgBouncer kein Produktions-Gate.

### 5.1 Scope-Abgrenzung (kurz)

PROVEN:

- SQLx/Rust-CRUD gegen direkten PostgreSQL-Pfad (`PG_DIRECT_URL`, im Test als `DATABASE_URL` exportiert)
- psql-Migrations- und CRUD-Pfad gegen disposable-local PostgreSQL
- psql-CRUD über PgBouncer transaction mode

NOT_PROVEN:

- SQLx/Rust-CRUD über PgBouncer transaction mode
- `sqlx migrate run` via sqlx-cli im CI-Kontext
- Exaktes Stack-Image `edoburu/pgbouncer:1.20` im Runtime-Proof

Warum `DbSessionStore` nicht Teil dieses PR ist:

- Dieser PR ist ein Runtime-Proof-Scope ohne Auth-Router-Umbau.
- Das Ziel ist Nachweisbarkeit des Persistenzpfads, nicht produktive
  Store-Einführung.
- `DbSessionStore` bleibt der nächste, separate Implementierungs-PR.

---

## 6. Restlücken

### Restlücke 1: SQLx Prepared Statements gegen PgBouncer (Rust-API-Ebene)

#### Status: offen für Dev-/Spezialpfad; kein Produktions-Gate nach ADR-0007

Alle CRUD-Operationen wurden über den `psql`-Client ausgeführt, der keine
Prepared Statements im SQLx-Sinne verwendet. SQLx nutzt standardmäßig
PostgreSQL-Extended-Query-Protokoll (Prepared Statements), was mit
`POOL_MODE=transaction` in PgBouncer bekannte Kompatibilitätsprobleme
verursachen kann.

Der Beweis auf Rust-API-Ebene — also SQLx-`query!` oder `query_as!` gegen
PgBouncer im transaction mode — ist noch offen.

**Mitigation (falls PR 2 scheitert):** `PgConnectOptions::statement_cache_capacity(0)`
deaktiviert den SQLx-Prepared-Statement-Cache und ist eine dokumentierte Mitigation-Option
für einfache Queries gegen transaction-mode-PgBouncer; der konkrete SQLx-Pfad
muss durch Rust-Integrationstests belegt werden.

### Restlücke 2: `sqlx-cli` nicht in CI-Umgebung installiert

#### Status: dokumentiert

Migrationen wurden via `psql -f` ausgeführt. Im regulären Deploy-Pfad (`just db-migrate`)
wird `sqlx-cli 0.8.1` erwartet:

```bash
cargo install sqlx-cli --version 0.8.1 --locked --no-default-features --features native-tls,postgres
```

Für CI-Migrationsschritte muss `sqlx-cli` installiert oder ein alternativer
Migrationspfad (z.B. `psql -f` im CI) explizit dokumentiert sein.

### Restlücke 3: `edoburu/pgbouncer:1.20`-Image nicht in Sandbox verfügbar

#### Status: dokumentiert (Image-Differenz)

Für den Beweis wurde `pgbouncer 1.22.0` (Ubuntu-Paket) verwendet, nicht das
Stack-Image `edoburu/pgbouncer:1.20`. Der Test deckt denselben Zielmodus
`POOL_MODE=transaction` ab. Eine vollständige Äquivalenz zum Stack-Image
`edoburu/pgbouncer:1.20` ist damit nicht vollständig bewiesen; mögliche
versionsspezifische Unterschiede wurden nicht untersucht. Die Docker-Compose-Konfiguration
des Stacks bleibt unverändert.

---

## 7. Risikoabschätzung

| Risiko | Wahrscheinlichkeit | Auswirkung | Mitigation |
|---|---|---|---|
| SQLx Extended-Query scheitert an PgBouncer transaction mode | mittel | mittel | `statement_cache_capacity(0)` pro Pool-Verbindung |
| `sqlx-cli` fehlt in CI für `just db-migrate` | niedrig | niedrig | Install-Schritt in CI dokumentieren |
| Shared-dev Drift: Tabelle existiert ohne SQLx-Migrationseintrag | mittel | mittel | Vor `sqlx migrate run` Migrationshistorie prüfen; Drift dokumentieren statt blind ausführen |

---

## 8. Entscheidungsempfehlung: nächster sicherer Schritt

**Empfehlung: `feat(auth): implement DbSessionStore against direct PostgreSQL path`**

Der direkte SQLx/PostgreSQL-CRUD-Pfad gegen die Session-Tabelle ist jetzt als Proof belegt. Damit ist
die zentrale Vorbedingung aus ADR-0007 für den nächsten Implementierungsschritt
erfüllt.

Vorgehen für den nächsten PR:

1. `DbSessionStore` gegen direkten PostgreSQL-Zugriff implementieren.
2. `SessionBackend`/`SessionOps`-Wiring nur soweit anpassen, wie für Persistenz nötig.
3. Login/Logout/Refresh-Verhalten unverändert halten.
4. Offline-Testpfad weiterhin grün halten.

**Stop-Regel:** Kein PgBouncer-spezifischer Umbau als Produktions-Gate.

Optionaler Spezialpfad: Der SQLx/PgBouncer-Proof mit `statement_cache_capacity(0)`
kann weiterhin ausgeführt werden, wenn ein Dev-/Spezialbetrieb PgBouncer nutzt.
Er ist aber kein Produktions-Gate und blockiert `DbSessionStore` gegen direkten
PostgreSQL-Zugriff nicht.

Zweite Alternative: erst `refactor(auth): introduce SessionBackend abstraction`
als eigenen PR, wenn die Änderungsfläche nach erster Messung breit erscheint
(Blueprint Abschnitt 7, Pfad B).

---

## 9. CI-Relevanz

| Check | Status |
|---|---|
| `cargo test --locked -p weltgewebe-api` | ✅ 240 passed, lokal ausgeführt |
| `git diff --check` | ✅ clean |
| `cargo fmt --check` | ✅ ausgeführt |
| `cargo clippy -p weltgewebe-api --all-targets --all-features -- -D warnings` | ✅ ausgeführt |
| `pnpm lint` (Web) | nicht betroffen |

Dieser Sync-PR enthält Änderungen in `docs/reports/` und im `Justfile`.
Keine Produktionscode-Änderungen.
