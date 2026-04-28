---
id: reports.auth-persistence-readiness
title: "Auth Persistence Readiness — OPT-API-002"
doc_type: report
status: active
created: 2026-04-28
lang: de
summary: >
  Diagnosebericht zu OPT-API-002: Ist-Befund der transienten Auth-Stores,
  Abgrenzung des AccountStore, fehlende DB-Strukturen,
  Entscheidung zur Persistenzstrategie und Minimal-Migrationsplan.
  Keine Implementierung, kein Umbau — ausschließlich belegter Ist-Zustand.
relations:
  - type: depends_on
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/specs/auth-api.md
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
---

# Auth Persistence Readiness — OPT-API-002

> **Zweck:** Diagnosebericht. Kein Patch, kein Umbau.
> Ziel: belegter Ist-Zustand, fehlende Strukturen, Entscheidung, Testplan.

---

## 1. Belegter Ist-Zustand

Alle transienten Auth-Stores sind in-memory.
`AccountStore` ist ein separater Account-Cache auf Basis der JSONL-Datenquelle
und gehört zu OPT-ARC-001 — er ist nicht Teil dieser Diagnose.
Basis: direkter Code-Befund in `apps/api/src/auth/` und `apps/api/src/state.rs`.

### Stores in `ApiState` (`apps/api/src/state.rs`)

| Feld | Typ | Persistenz | TTL |
|---|---|---|---|
| `sessions` | `SessionStore` | in-memory (`Arc<RwLock<HashMap<String, Session>>>`) | 24 h |
| `tokens` | `TokenStore` | in-memory (`Arc<RwLock<HashMap<String, TokenData>>>`) | 15 min |
| `step_up_tokens` | `StepUpTokenStore` | in-memory (`Arc<RwLock<HashMap<String, StepUpTokenData>>>`) | 5 min |
| `challenges` | `ChallengeStore` | in-memory (`Arc<RwLock<HashMap<String, Challenge>>>`) | 5 min |
| `passkey_registrations` | `PasskeyRegistrationStore` | in-memory | 5 min |
| `accounts` | `Arc<RwLock<AccountStore>>` | JSONL-Datei (Startup-Load, kein Write-Back) | — |

`db_pool: Option<PgPool>` und `db_pool_configured: bool` sind in `ApiState` vorhanden,
aber **ausschließlich für den Health-/Bereitschaftscheck verdrahtet** — keine Auth-Operation
nutzt den Pool.

Belegkommando:

```bash
grep -rn "db_pool\|db_pool_configured\|query_scalar\|PgPool" apps/api/src/
```

```text
apps/api/src/lib.rs:22:use sqlx::postgres::PgPoolOptions;
apps/api/src/lib.rs:45:    let (db_pool, db_pool_configured) = initialise_database_pool().await;
apps/api/src/lib.rs:105:        db_pool,
apps/api/src/lib.rs:106:        db_pool_configured,
apps/api/src/lib.rs:181:async fn initialise_database_pool() -> (Option<sqlx::PgPool>, bool) {
apps/api/src/lib.rs:187:    let pool = match PgPoolOptions::new()
apps/api/src/state.rs:59:use sqlx::PgPool;
apps/api/src/state.rs:64:    pub db_pool: Option<PgPool>,
apps/api/src/state.rs:65:    pub db_pool_configured: bool,
apps/api/src/routes/health.rs:15:use sqlx::query_scalar;
apps/api/src/routes/health.rs:160:    if !state.db_pool_configured {
apps/api/src/routes/health.rs:164:    match state.db_pool.as_ref() {
apps/api/src/routes/health.rs:165:        Some(pool) => match query_scalar::<_, i32>("SELECT 1")
apps/api/src/routes/health.rs:320:            db_pool: None,
apps/api/src/routes/health.rs:321:            db_pool_configured: false,
apps/api/src/routes/health.rs:413:        state.db_pool_configured = true;
```

Belegkommando:

```bash
find apps/api -maxdepth 2 -type d -name migrations -print
```

```text
# keine Ausgabe
```

Belegkommando:

```bash
find . -name "*.sql" -print
```

```text
./infra/compose/sql/init/00_extensions.sql
```

Startup-Code (`apps/api/src/lib.rs`, Zeilen 49–52):

```rust
let sessions = crate::auth::session::SessionStore::new();
let tokens = crate::auth::tokens::TokenStore::new();
let step_up_tokens = crate::auth::step_up_tokens::StepUpTokenStore::new();
// ... alle Stores via ::new(), kein DB-Bezug
```

---

## 2. Session-/Token-State-Orte

### `SessionStore` — kritisch, weil langlebig

Datei: `apps/api/src/auth/session.rs`

```rust
Session { id, account_id, device_id, created_at, last_active, expires_at }
SessionStore { store: Arc<RwLock<HashMap<String, Session>>> }
```

Methoden: `create`, `get`, `delete`, `touch`, `list_by_account`,
`delete_by_device`, `delete_all_by_account`.

**Fachliche Methodenoberfläche ist klar, technisch aber noch nicht DB-drop-in-fähig.**
Die aktuelle `SessionStore`-API ist vollständig synchron (`pub fn create`, `pub fn get`, …).
Ein SQLx-basierter Store wäre async. Damit ist ein reiner Typ-Austausch nicht möglich:
Der Implementierungs-PR muss eine async-fähige Abstraktion einführen — entweder
`async_trait`-basierter `SessionOps`-Trait oder ein `SessionBackend`-Enum — und alle
Aufrufstellen in Middleware und Routen anpassen.
Befund: `docs/blueprints/auth-roadmap.md`, Abschnitt „Phase 2“ / „Persistenzentscheidung“.

### `TokenStore` — kurzlebig, Verlust tolerierbar

Datei: `apps/api/src/auth/tokens.rs`

```rust
TokenData { email, expires_at }
TokenStore { store: Arc<RwLock<HashMap<String, TokenData>>> }
```

SHA-256-gehasht. TTL 15 min. Verlust bei Neustart: Nutzer muss neu anfragen — kein Sicherheitsproblem.

### `StepUpTokenStore` — kurzlebig, Verlust tolerierbar

Datei: `apps/api/src/auth/step_up_tokens.rs`

```rust
StepUpTokenData { challenge_id, account_id, device_id, expires_at }
StepUpTokenStore { store: Arc<RwLock<HashMap<String, StepUpTokenData>>> }
```

SHA-256-gehasht. TTL 5 min. Verlust bei Neustart: Step-up-Anforderung muss wiederholt werden.

### `ChallengeStore` — kurzlebig, Verlust tolerierbar

Datei: `apps/api/src/auth/challenges.rs`

TTL 5 min. Verlust: Challenge-gebundene Intent-Aktionen müssen neu ausgelöst werden.

### `PasskeyRegistrationStore` — kurzlebig, Verlust tolerierbar

Datei: `apps/api/src/auth/passkeys.rs`. TTL 5 min.
Nur relevant, wenn `register/verify` implementiert ist — derzeit noch offen.

### `AccountStore` — JSONL, separates Problem

Datei: `apps/api/src/auth/accounts.rs`. Geladen aus JSONL beim Start.
Kein Write-Back. Ist **nicht** Teil dieses Diagnoseberichts —
zugehörig zu OPT-ARC-001 (JSONL → PostgreSQL).

---

## 3. Fehlende persistente Datenstrukturen

### Kein Migrationsverzeichnis

```text
apps/api/migrations/   ← existiert nicht
```

Befund: `find . -name "*.sql"` liefert ausschließlich
`infra/compose/sql/init/00_extensions.sql` (aktiviert `uuid-ossp`, `pgcrypto`).
Kein sqlx-Migrationsframework eingerichtet.

### Fehlende Tabellen

| Tabelle | Priorität | Begründung |
|---|---|---|
| `sessions` | **notwendig** | einziger langlebiger (24 h) Auth-State |
| `magic_link_tokens` | nicht notwendig | TTL 15 min; Verlust tolerierbar |
| `step_up_tokens` | nicht notwendig | TTL 5 min; Verlust tolerierbar |
| `challenges` | nicht notwendig | TTL 5 min; Verlust tolerierbar |

### Keine DB-Anbindung der Auth-Middleware

`apps/api/src/middleware/auth.rs` nutzt `state.sessions.get(session_id)` —
reiner In-Memory-Zugriff, keine Datenbankabfrage.

---

## 4. Entscheidung: DB-first, Redis-first oder Signed-Token-Fallback

### Ergebnis: **DB-first (PostgreSQL)**

#### Begründung

**Für DB-first:**

- `db_pool: Option<PgPool>` ist bereits in `ApiState` verdrahtet —
  Infrastruktur vorhanden, nur nicht für Auth genutzt.
- PostgreSQL ist in den betrachteten Dev-/Prod-Basisstacks vorhanden und wird
  von der API über `DATABASE_URL` adressiert; Profil-Parität und PgBouncer-Policy
  bleiben separat zu prüfen.
- Die DB-Extensions `uuid-ossp` und `pgcrypto` sind bereits aktiv
  (`infra/compose/sql/init/00_extensions.sql`).
- `SessionStore`-Methodenoberfläche deckt alle nötigen Operationen ab;
  der Implementierungs-PR muss eine async-fähige Abstraktion einführen (siehe Abschnitt 2).

**Gegen Redis-first:**

- Redis ist nicht im Stack (Gate C: NATS ist optional; Redis wäre neue Abhängigkeit).
- Zusätzlicher Infrastrukturdienst ohne Mehrwert gegenüber DB für diesen Use Case.
- Erhöht Ops-Komplexität ohne äquivalenten Sicherheitsgewinn.

**Gegen Signed-Token/JWT-Fallback:**

- `auth-api.md` definiert ein serverseitiges Session-Modell mit Invalidierung —
  JWT-Sessions sind clientseitig und nicht serverseitig widerrufbar ohne Denylist.
- Session-Widerruf (`logout`, `logout-all`, `delete_by_device`) ist System-Invariante
  in ADR-0006 — mit reinem JWT nicht erfüllbar.
- Würde signifikante Spec-Änderungen erfordern.

#### Grenzfall: kurzlebige Stores

`TokenStore`, `StepUpTokenStore`, `ChallengeStore` und `PasskeyRegistrationStore`
bleiben **in-memory**. Begründung:

- TTL ≤ 15 min; Verlust bei Neustart erfordert Wiederholung, nicht Sicherheitsmaßnahme.
- Kein Audit-Bedarf für diese transienten Zustände.
- DB-Persistenz würde Cleanup-Overhead ohne Nutzen erzeugen.

---

## 5. Minimal-Migrationsplan

### Vorbedingungen

- sqlx CLI verfügbar (`cargo install sqlx-cli --features postgres`)
- `DATABASE_URL` in `.env` gesetzt
- DB erreichbar und Extensions aktiv

### Schritt 1: Migrationsinfrastruktur

```bash
mkdir -p apps/api/migrations
# Variante aus Repo-Root (-r erzeugt .up.sql + .down.sql):
sqlx migrate add -r create_sessions --source apps/api/migrations
# Alternative:
# (cd apps/api && sqlx migrate add -r create_sessions)
```

Resultat: `apps/api/migrations/<timestamp>_create_sessions.up.sql`
und `apps/api/migrations/<timestamp>_create_sessions.down.sql`
(sqlx verwendet Unix-Timestamp als Präfix, nicht `0001`).

### Schritt 2: `sessions`-Tabelle

```sql
-- apps/api/migrations/<timestamp>_create_sessions.up.sql
CREATE TABLE sessions (
    id          TEXT        PRIMARY KEY,
    account_id  TEXT        NOT NULL,
    device_id   TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL,
    last_active TIMESTAMPTZ NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE INDEX sessions_account_id ON sessions (account_id);
CREATE INDEX sessions_expires_at ON sessions (expires_at);
```

```sql
-- apps/api/migrations/<timestamp>_create_sessions.down.sql
DROP TABLE sessions;
```

### Schritt 3: Startup-Integration

In `apps/api/src/lib.rs`, nach `initialise_database_pool()`:

```rust
if let (Some(pool), true) = (&db_pool, db_pool_configured) {
    sqlx::migrate!("./migrations").run(pool).await
        .context("database migration failed")?;
}
```

### Schritt 4: DB-gestützter `SessionStore`

Neue Variante in `apps/api/src/auth/session.rs` oder eigene Datei
`apps/api/src/auth/session_db.rs`:

```rust
pub struct DbSessionStore {
    pool: PgPool,
}
// impl: create, get, delete, touch, list_by_account, delete_by_device,
//        delete_all_by_account — identische Signatur wie SessionStore
```

### Schritt 5: Conditional Init in `ApiState`

```rust
let sessions: /* SessionStore oder DbSessionStore */ = if db_pool_configured {
    // DbSessionStore::new(pool.clone())
} else {
    SessionStore::new()
};
```

Da die aktuelle `SessionStore`-API synchron ist, ist ein Typ-Austausch nicht trivial.
Der Implementierungs-PR muss wählen zwischen:

- `async_trait`-basierter `SessionOps`-Trait + Impl für beide Backends
- Enum `SessionBackend { InMemory(SessionStore), Db(DbSessionStore) }` mit `match`-Dispatch

In beiden Fällen sind alle Aufrufstellen (Middleware `auth.rs`, Route-Handler in `auth.rs`)
auf `await` umzustellen.

### Schritt 6: CI-Anpassung

- `cargo test --locked` muss `DATABASE_URL` für Integration-Tests kennen
  oder Tests mit `db_pool_configured = false` laufen (bereits der Fall in `test_state()`).
- Neuer CI-Step: `sqlx migrate run --source apps/api/migrations` vor `cargo test`
  in `api.yml` oder Ausführung aus `apps/api/`.

---

## 6. Testplan

### Unit-Tests (bestehend, ausreichend für In-Memory-Verhalten)

`apps/api/src/auth/session.rs` enthält bereits:

- `create_produces_session_with_correct_account_id`
- `get_returns_created_session`
- `delete_removes_session`
- `list_by_account_returns_sessions`
- `delete_by_device_removes_correct_sessions`
- `session_expires_at_is_approximately_one_day`

Diese Tests müssen nach Einführung der `DbSessionStore`-Variante
mit gleicher Schnittstelle parallel für beide Backends bestehen.

### Neue Integrationstests (für Persistenz)

| Test | Zweck |
|---|---|
| Session nach Neustart des Stores abrufbar | Persistenz-Beweis: neue Store-Instanz (selber Pool) liest bestehende Session |
| Abgelaufene Sessions nicht zurückgegeben | `expires_at`-Filter in DB-Query korrekt |
| `list_by_account` gibt nur nicht-abgelaufene zurück | Filter + Account-Bindung |
| `delete_by_device` löscht nur Zielgerät | Selektivität der Löschung |
| `delete_all_by_account` löscht vollständig | Account-Scope |
| `touch` aktualisiert `last_active` | Schreibpfad korrekt |
| Parallelzugriff: keine Phantom-Reads | Transaktionssicherheit |

### Regressionstests

- `api_auth.rs`-Integrationstests müssen mit `db_pool_configured = false`
  weiterhin ohne Datenbankverbindung laufen (aktuell der Fall, muss erhalten bleiben).

---

## 7. Risikoabschätzung

| Risiko | Schwere | Wahrscheinlichkeit | Maßnahme |
|---|---|---|---|
| API-Neustart löscht alle Sessions (Ist-Zustand) | hoch | bei jedem Deploy | `sessions`-Tabelle einführen |
| DB-Ausfall bei persistentem Store → alle Auth-Ops fehlerhaft | hoch | kontextabhängig / nicht abschließend belegt | Klar scheitern statt In-Memory-Fallback; Readiness/Health muss DB-Ausfall sichtbar machen; PgBouncer-Parität für Dev/Prod separat prüfen |
| Migration läuft nicht idempotent → CI-Bruch | mittel | niedrig | Keine `IF NOT EXISTS`-Kaschierung in der Up-Migration; die Migration soll bei unerwartetem Vorzustand scheitern. Das sqlx-Migrationsprotokoll verhindert reguläre Doppelausführung. |
| `DbSessionStore` verdrängt `SessionStore` → In-Memory-Testharness bricht | niedrig | niedrig | `test_state()` nutzt `db_pool: None` → bleibt in-memory |
| Falsche Indexwahl → Performance bei hoher Session-Zahl | niedrig | niedrig | `sessions_account_id` + `sessions_expires_at` decken alle Abfragen ab |
| Token-Stores bleiben in-memory → Verlust bei Neustart | akzeptiert | bei jedem Deploy | TTL ≤ 15 min; dokumentiertes Design-Entscheid |

### Nicht kritisch und daher ausgeklammert

- `AccountStore` (JSONL): Separates Problem (OPT-ARC-001).
- `PasskeyRegistrationStore`: Erst relevant nach `register/verify` (Phase 4, offen).
- `ChallengeStore`, `StepUpTokenStore`: 5-min-TTL, kein Persistenzbedarf.

---

## Zusammenfassung

| Frage | Antwort |
|---|---|
| Was ist in-memory? | Alle transienten Auth-Stores: Sessions (24 h), Tokens (15 min), Step-up-Tokens (5 min), Challenges (5 min), Passkey-Registrierungen (5 min) |
| Was ist kritisch? | Ausschließlich `SessionStore` — langlebig (24 h), Verlust = Logout aller Nutzer |
| Welche DB-Strukturen fehlen? | `apps/api/migrations/` (kein Verzeichnis), `sessions`-Tabelle (nicht vorhanden) |
| Strategie? | DB-first (PostgreSQL); `db_pool` bereits in `ApiState`; Implementierungs-PR muss async-Abstraktion einführen |
| Nächster Schritt? | Migrationsverzeichnis + `sqlx migrate add -r create_sessions --source apps/api/migrations`, dann `DbSessionStore` mit `SessionOps`-Trait |
| Bestehende Tests? | Alle laufen ohne DB (In-Memory-Fallback); müssen erhalten bleiben |
