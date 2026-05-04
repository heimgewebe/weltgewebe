---
id: reports.auth-persistence-next-step
title: "Auth-Persistenz — Nächster Schritt"
doc_type: report
status: active
created: 2026-05-04
lang: de
summary: >
  Diagnosedokument zum nächsten Implementierungsschritt der Auth-Session-Persistenz.
  Belegter Ist-Zustand nach Migration-Schema-PR, Entscheidungsmatrix, offene
  Implementierungsfragen und konkreter Folge-PR-Vorschlag.
  Keine Implementierung — ausschließlich belegter Befund und Entscheidungsgrundlage.
depends_on:
  - docs/reports/auth-persistence-readiness.md
  - docs/reports/optimierungsstatus.md
relations:
  - type: updates
    target: docs/reports/auth-persistence-readiness.md
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
  - type: relates_to
    target: docs/specs/auth-api.md
---

# Auth-Persistenz — Nächster Schritt

> **Zweck:** Diagnose- und Entscheidungsgrundlage. Kein Implementierungs-PR.
> Ziel: belegter Ist-Zustand nach Migration-Schema-PR, Klärung offener
> Implementierungsfragen, konkreter Folge-PR-Vorschlag.

---

## 1. Kurzfazit

Die vorhandene Dokumentation und der aktualisierte Ist-Zustand stützen **PostgreSQL (DB-first)**
als nächsten Implementierungspfad für Session-Persistenz. Redis und Hybrid haben im aktuellen
Befund keinen belegten Zusatznutzen. Strategisch gestützt durch `docs/reports/auth-persistence-readiness.md`
und `docs/blueprints/auth-roadmap.md`; noch nicht runtime-bewiesen.

Seit dem Readiness-Report hat ein Migrations-Schema-PR die `sessions`-Tabellendefinition
eingeführt (`apps/api/migrations/20260428000000_create_sessions.up.sql`). Der aktuelle
Stand weicht damit vom `auth-persistence-readiness.md` ab, das noch kein Migrations-
verzeichnis vorfand.

Was fehlt bis zur vollständigen Session-Persistenz:

1. `DbSessionStore`-Implementierung (async, `PgPool`)
2. Async-Abstraktion für `SessionStore` (Trait oder Enum-Dispatch)
3. Startup-Migration in `apps/api/src/lib.rs`
4. CI-Migrations-Step in `.github/workflows/api.yml`
5. PgBouncer-Kompatibilitätsprüfung (`transaction` mode)

Prämissencheck zur Aufgabenstellung:

| Prämisse | Status | Befund |
|---|---|---|
| Auth-State ist mindestens teilweise flüchtig | **Bestätigt** | Alle 5 Stores sind in-memory. Belegt. |
| Doku markiert Persistenz als Restlücke | **Bestätigt** | OPT-API-002 in `optimierungsstatus.md` = open; README-Note aktiv. |
| Keine belastbare Entscheidung Postgres vs. Redis vs. Hybrid | **Teilweise falsch** | Entscheidung ist getroffen (DB-first). Offen sind Implementierungsdetails, nicht die Strategie. |
| Direkter Implementierungs-PR wäre zu annahmenreich | **Teilweise wahr** | PgBouncer-Modus, async-Abstraktion und CI-Gate sind noch ungeklärt. |

---

## 2. Belegter Ist-Zustand

### 2.1 In-Memory-Stores (alle transient)

Kommando:

```bash
rg "RwLock|HashMap|SessionStore|TokenStore|StepUpTokenStore|ChallengeStore|PasskeyRegistrationStore" \
  apps/api/src/auth apps/api/src/state.rs -n
```

Ergebnis (Auszug, belegt):

```text
apps/api/src/state.rs:70:    pub sessions: SessionStore,
apps/api/src/state.rs:71:    pub challenges: ChallengeStore,
apps/api/src/state.rs:72:    pub tokens: TokenStore,
apps/api/src/state.rs:73:    pub step_up_tokens: StepUpTokenStore,
apps/api/src/state.rs:82:    pub passkey_registrations: PasskeyRegistrationStore,
apps/api/src/auth/session.rs:26:pub struct SessionStore {
apps/api/src/auth/session.rs:26:    store: Arc<RwLock<HashMap<String, Session>>>,
apps/api/src/auth/tokens.rs:16:pub struct TokenStore {
apps/api/src/auth/tokens.rs:16:    store: Arc<RwLock<HashMap<String, TokenData>>>,
apps/api/src/auth/step_up_tokens.rs:29:pub struct StepUpTokenStore {
apps/api/src/auth/step_up_tokens.rs:29:    store: Arc<RwLock<HashMap<String, StepUpTokenData>>>,
apps/api/src/auth/challenges.rs:47:pub struct ChallengeStore {
apps/api/src/auth/challenges.rs:47:    state: Arc<RwLock<ChallengeState>>,
apps/api/src/auth/passkeys.rs:89:pub struct PasskeyRegistrationStore {
apps/api/src/auth/passkeys.rs:90:    store: Arc<RwLock<HashMap<String, PendingRegistration>>>,
```

Startup-Code (`apps/api/src/lib.rs`, Zeilen 49–52), belegt:

```rust
let sessions = crate::auth::session::SessionStore::new();
let challenges = crate::auth::challenges::ChallengeStore::new();
let tokens = crate::auth::tokens::TokenStore::new();
let step_up_tokens = crate::auth::step_up_tokens::StepUpTokenStore::new();
// Kein DB-Bezug, kein await, kein PgPool-Argument
```

### 2.2 Migrations-Infrastruktur (vorhanden, aber nicht aktiviert)

Kommando:

```bash
ls -la apps/api/migrations/
```

Ergebnis:

```text
total 16
drwxr-xr-x 2 root root 4096 May  3 11:54 .
drwxr-xr-x 5 root root 4096 May  3 11:54 ..
-rw-r--r-- 1 root root   21 May  3 11:54 20260428000000_create_sessions.down.sql
-rw-r--r-- 1 root root  376 May  3 11:54 20260428000000_create_sessions.up.sql
```

Inhalt `20260428000000_create_sessions.up.sql` (belegt):

```sql
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

**Hinweis:** `apps/api/README.md` dokumentiert explizit:
> "This PR introduces the migration schema only. Auth-session persistence (`DbSessionStore`)
> and startup/CI migration automation are not yet activated."

Divergenz zu `auth-persistence-readiness.md`: Dieses Vorgängerdokument stellte
fest, dass kein Migrationsverzeichnis existiert. Das ist seit dem Schema-PR nicht mehr
korrekt. Der aktuelle Ist-Zustand enthält ein Migrationsverzeichnis mit einer
plausiblen `sessions`-Tabellendefinition. Runtime-Funktion noch nicht belegt:
`sqlx migrate run` gegen PostgreSQL/PgBouncer und Query-Kompatibilität eines
späteren `DbSessionStore` sind noch zu prüfen.

### 2.3 DB-Pool (vorhanden, für Auth ungenutzt)

Kommando:

```bash
rg "db_pool|PgPool|query_scalar" apps/api/src -n
```

Ergebnis (Auszug, belegt):

```text
apps/api/src/state.rs:59:use sqlx::PgPool;
apps/api/src/state.rs:64:    pub db_pool: Option<PgPool>,
apps/api/src/state.rs:65:    pub db_pool_configured: bool,
apps/api/src/routes/health.rs:15:use sqlx::query_scalar;
apps/api/src/routes/health.rs:164:    match state.db_pool.as_ref() {
```

`db_pool` ist verdrahtet, aber **ausschließlich für den Health-Check** genutzt.
Kein Auth-Handler liest oder schreibt über den Pool.

### 2.4 PgBouncer-Konfiguration (belegt)

Kommando:

```bash
rg "POOL_MODE|pgbouncer" infra/compose/ -n
```

Ergebnis:

```text
infra/compose/compose.core.yml:88:  pgbouncer:
infra/compose/compose.core.yml:90:    image: edoburu/pgbouncer:1.20
infra/compose/compose.core.yml:90:      POOL_MODE: transaction
infra/compose/compose.core.yml:42:      DATABASE_URL: postgres://welt:gewebe@pgbouncer:6432/weltgewebe
```

PgBouncer läuft im `transaction` mode. Relevanz: `sqlx` mit `PgPool` ist in diesem
Modus grundsätzlich kompatibel für einfache CRUD-Operationen (INSERT, SELECT, DELETE,
UPDATE). Kein LISTEN/NOTIFY, keine serverseitigen Prepared Statements über Verbindungs-
grenzen hinweg — beides ist hier nicht nötig. Kein bekanntes Kompatibilitätsproblem
für den `DbSessionStore`-Use-Case, aber noch nicht empirisch geprüft.

### 2.5 Redis-Status (belegt: nicht im Stack)

Kommando:

```bash
rg -i "redis|valkey|deadpool-redis|bb8-redis|fred" apps/api/Cargo.toml infra/compose -n || true
```

Ergebnis:

```text
(no matches)
```

Redis ist **keine vorhandene Infrastruktur** — eine Einführung würde eine neue
Abhängigkeit bedeuten.

### 2.6 Async-Abstraktion für SessionStore (belegt: fehlt)

Kommando:

```bash
rg "DbSessionStore|SessionOps|session_db|async_trait|trait.*Session" apps/api/src -n
```

Ergebnis:

```text
Keine Treffer
```

`SessionStore` ist vollständig synchron (`pub fn create`, `pub fn get`, …).
`sqlx`-basierte DB-Operationen sind `async`. Der Implementierungs-PR muss
diese Inkompatibilität auflösen.

### 2.7 CI-Migrations-Step (belegt: fehlt)

`.github/workflows/api.yml` führt aus:

```text
cargo test --all-features --verbose
```

Kein Migrations-Step, kein `DATABASE_URL`-Service, kein `sqlx migrate run`.
Tests laufen ohne Datenbankverbindung (`db_pool_configured = false` in `test_state()`).
Das muss erhalten bleiben (In-Memory-Pfad für Offline-Tests), ist aber keine
vollständige CI-Abdeckung für persistente Session-Operationen.

---

## 3. Persistenzklassen

| Klasse | Store | Typ | TTL | Verlust bei Restart |
|---|---|---|---|---|
| Session | `SessionStore` | in-memory | 24 h | **kritisch**: alle Nutzer ausgeloggt |
| Magic-Link/E-Mail-Token | `TokenStore` | in-memory | 15 min | tolerierbar: neuer Link anfordern |
| Step-Up-Token | `StepUpTokenStore` | in-memory | 5 min | tolerierbar: Step-up erneut auslösen |
| Challenge | `ChallengeStore` | in-memory | 5 min | tolerierbar: Intent erneut starten |
| Passkey-Registrierung | `PasskeyRegistrationStore` | in-memory | 5 min | tolerierbar: Registrierung noch offen |
| Passkey-Credentials | nicht implementiert | — | — | nicht relevant bis Phase 4 |
| Account-Stammdaten | `AccountStore` (JSONL) | Datei, kein Write-Back | — | separates Problem (OPT-ARC-001) |

---

## 4. Risiko je Klasse

### Session (24h TTL)

| Szenario | Risiko | Bewertung |
|---|---|---|
| Restart / Deploy | Alle Sessions verloren, alle Nutzer ausgeloggt | **hoch** |
| Multi-Instance | Sessions nur auf einer Instanz sichtbar, andere Instanzen erkennen Nutzer nicht | **hoch** |
| Security | Kein Audit-Trail, keine gezielte Invalidierung nach Kompromittierung möglich | **mittel** |
| UX | Regelmäßige unerwartete Abmeldungen bei jedem Deploy | **hoch** |

### Magic-Link/E-Mail-Token (15min TTL)

| Szenario | Risiko | Bewertung |
|---|---|---|
| Restart / Deploy | Token verloren; Nutzer muss neuen Link anfordern | **niedrig** (tolerierbar) |
| Multi-Instance | Token nur auf einer Instanz einlösbar | **mittel** (wenn Multi-Instance) |
| Security | Kein persistenter Audit-Bedarf; In-Memory ist ausreichend sicher | **kein zusätzliches Risiko** |

### Step-Up-Token (5min TTL)

| Szenario | Risiko | Bewertung |
|---|---|---|
| Restart / Deploy | Step-up-Aktion muss wiederholt werden | **niedrig** (tolerierbar) |
| Multi-Instance | Token nur auf erstellender Instanz konsumierbar | **mittel** (wenn Multi-Instance) |

### Challenge (5min TTL)

| Szenario | Risiko | Bewertung |
|---|---|---|
| Restart / Deploy | Intent-Aktion muss erneut ausgelöst werden | **niedrig** (tolerierbar) |
| Multi-Instance | Challenge nur auf erstellender Instanz verifizierbar | **mittel** (wenn Multi-Instance) |

### Passkey-Credentials

Nicht relevant bis Phase 4 (`register/verify` ist noch offen). Passkey-Credentials
müssen bei Einführung zwingend persistent gespeichert werden — aber das ist ein
eigenständiger PR-Scope.

---

## 5. Entscheidungsmatrix

### Für `SessionStore` (einziger kritischer Store)

| Option | Pro | Contra | Bewertung |
|---|---|---|---|
| **In-Memory belassen** | kein Aufwand, aktueller Zustand | Restart = Logout aller Nutzer; kein Multi-Instance | nur für PoC/Dev ohne SLA |
| **PostgreSQL** | Stack vorhanden; Migration vorhanden; `db_pool` verdrahtet; keine neue Abhängigkeit | async-Abstraktion nötig; CI-Gate fehlt; PgBouncer-Modus zu prüfen | **empfohlen** (bereits entschieden) |
| **Redis** | schnell für TTL-basierte Keys; kein Schema nötig | nicht im Stack; neue Abhängigkeit; kein Mehrwert für diesen Use-Case | nicht empfohlen |
| **Hybrid** | kurzlebige Stores in Redis, Sessions in PG | komplexer Stack; zwei Systeme für dasselbe Problem | nicht empfohlen für aktuellen Scope |

### Für kurzlebige Stores (`TokenStore`, `StepUpTokenStore`, `ChallengeStore`, `PasskeyRegistrationStore`)

| Option | Pro | Contra | Bewertung |
|---|---|---|---|
| **In-Memory belassen** | einfach; TTL-Cleanup in Code | Verlust bei Restart (tolerierbar) | **empfohlen** |
| **PostgreSQL** | persistiert | Cleanup-Overhead; kein Mehrwert | nicht empfohlen |
| **Redis** | native TTL | neue Abhängigkeit; kein Mehrwert | nicht empfohlen |

---

## 6. Empfehlung (nach Prämissencheck)

### Strategie: PostgreSQL für Sessions, In-Memory für kurzlebige Stores

Diese Entscheidung ist bereits getroffen (vgl. `auth-persistence-readiness.md`
und `auth-roadmap.md`). Dieses Dokument bestätigt sie auf Basis des aktualisierten
Ist-Zustands.

### Was müsste wahr sein, damit Postgres genügt?

- **Belegt:** `db_pool` ist in `ApiState` vorhanden und `DATABASE_URL` konfiguriert.
- **Belegt:** Eine `sessions`-Migration existiert und definiert die benötigten Kernspalten und Indizes. Runtime-Migrationsbeweis gegen PostgreSQL/PgBouncer und Query-Kompatibilität des späteren `DbSessionStore` stehen noch aus.
- **Belegt:** `sqlx` v0.8.1 ist als Abhängigkeit vorhanden.
- **Offen:** PgBouncer `transaction` mode muss empirisch für `DbSessionStore`-CRUD geprüft sein. Keine bekannten Inkompatibilitäten für einfache CRUD-Queries, aber nicht durch Test belegt.
- **Offen:** Startup-Migration (`sqlx::migrate!`) muss sicher sein bei nicht-konfiguriertem Pool (bestehende Tests nutzen `db_pool: None`).
- **Offen:** CI-Gate muss Migrations- und Integrationstests ohne Datenbankverbindung weiterhin erlauben (aktueller In-Memory-Pfad muss erhalten bleiben).

→ Wenn alle drei offenen Punkte im Implementierungs-PR adressiert sind, genügt Postgres.

### Was müsste wahr sein, damit Redis nötig ist?

- Redis müsste bereits im Stack sein (ist es nicht).
- Multi-Instance mit Latenzanforderungen, die PG nicht erfüllen kann (kein Beleg).
- Session-Zugriffsmuster müssten Hot-Cache-Verhalten zeigen (kein Beleg).

→ Kein einziges dieser Kriterien ist belegt. Redis ist nicht nötig.

### Was müsste wahr sein, damit Hybrid sinnvoll ist?

- Zwei verschiedene Systeme für Sessions vs. kurzlebige Stores müssten einen
  messbaren Vorteil gegenüber dem einfacheren PG-only-Ansatz bieten.
- Kurzlebige Stores müssten über Restarts hinweg überleben müssen (sie tun es nicht).

→ Hybrid ist nicht sinnvoll im aktuellen Scope.

---

## 7. Konkreter Folge-PR-Vorschlag

### PR-Titel

`feat(auth): implement DbSessionStore with Postgres persistence`

### Scope

Dieser PR implementiert Session-Persistenz über PostgreSQL. Er implementiert keine
Persistenz für kurzlebige Stores (Token, StepUpToken, Challenge).

### Dateien

| Datei | Aktion |
|---|---|
| `apps/api/src/auth/session.rs` | `SessionOps`-Trait hinzufügen (async); `DbSessionStore` implementieren oder in separate Datei auslagern |
| `apps/api/src/auth/session_db.rs` | Neue Datei (Option): async `DbSessionStore` mit `PgPool` |
| `apps/api/src/state.rs` | `ApiState.sessions`-Typ auf `SessionBackend`-Enum oder Trait-Objekt umstellen |
| `apps/api/src/lib.rs` | Startup-Migration (`sqlx::migrate!`) nach `initialise_database_pool()`; bedingte Store-Initialisierung |
| `apps/api/src/middleware/auth.rs` | Aufrufstellen auf `await` umstellen |
| `apps/api/src/routes/auth.rs` | Aufrufstellen auf `await` umstellen |
| `apps/api/tests/api_auth.rs` | Bestandstests müssen ohne Datenbankverbindung weiterhin laufen |

### Migrationen

`apps/api/migrations/20260428000000_create_sessions.up.sql` — bereits vorhanden, kein Änderungsbedarf.

Down-Migration: `apps/api/migrations/20260428000000_create_sessions.down.sql` — bereits vorhanden.

### Neue Tests (mindestens)

| Test | Zweck |
|---|---|
| `session_survives_store_recreation` | Neue `DbSessionStore`-Instanz (selber Pool) liest bestehende Session |
| `expired_sessions_not_returned` | `expires_at`-Filter in DB-Query greift |
| `list_by_account_returns_only_active` | Filter + Account-Bindung korrekt |
| `delete_by_device_selective` | Nur Zielgerät-Sessions gelöscht |
| `delete_all_by_account_complete` | Account-Scope vollständig |
| `touch_updates_last_active` | Schreibpfad korrekt |

Tests müssen mit `cfg(feature = "integration")` oder dediziertem `DATABASE_URL`-Guard
isoliert sein, damit der bestehende Offline-Testpfad erhalten bleibt.

### CI-Nachweise

| Schritt | Ort |
|---|---|
| Bestandstests ohne DB weiterhin grün | `.github/workflows/api.yml` (kein Change nötig) |
| Neuer Integration-Test-Step mit `DATABASE_URL` | `.github/workflows/api.yml` (neuer optionaler Job) |
| `sqlx migrate run` als Schritt vor Integration-Tests | `.github/workflows/api.yml` |
| `just db-migrate` lokal funktional | `Justfile` — bereits vorhanden |

### Nicht-Ziele dieses Folge-PRs

- Kein Redis.
- Keine Passkey-Persistenz (Phase 4, offen).
- Keine `AccountStore`-Migration (OPT-ARC-001, separates Problem).
- Keine Persistenz für `TokenStore`, `StepUpTokenStore`, `ChallengeStore`.
- Keine UI-Änderungen.
- Keine neuen Runtime-Abhängigkeiten.

### Offene Implementierungsfragen (zu klären im PR)

1. **Async-Abstraktion:** `SessionOps`-Trait mit `async_trait` oder `SessionBackend`-Enum mit `match`-Dispatch? Beides ist möglich. Enum-Dispatch hat weniger Indirektion; Trait ist erweiterbar. Entscheidung im PR-Review.

2. **PgBouncer `transaction` mode:** Muss verifiziert werden, dass `sqlx::PgPool`-CRUD ohne Prepared-Statement-Caching-Probleme läuft. Empfehlung: `sqlx::query!`-Makros statt dynamische Queries, `statement_cache_size = 0` falls nötig.

3. **Startup-Fehlerverhalten:** Wenn `db_pool_configured = true` und Pool nicht verfügbar, soll die API nicht still auf In-Memory fallen — expliziter Fehler ist korrekt (bereits in `auth-persistence-readiness.md` definiert).

---

## Zusammenfassung der Bewertungen

| Frage | Status | Befund |
|---|---|---|
| Welche Stores sind in-memory? | **belegt** | Alle 5: Sessions, Tokens, StepUpTokens, Challenges, PasskeyRegistrations |
| Was ist kritisch? | **belegt** | Nur `SessionStore` (24h TTL, Restart = Logout aller Nutzer) |
| Migrations-Schema vorhanden? | **belegt** | Ja, seit 2026-04-28 — aber nicht in Startup aktiviert |
| Strategie Postgres vs. Redis vs. Hybrid? | **strategisch gestützt** | PostgreSQL durch Doku und Diagnose als nächster Pfad gestützt; Redis/Hybrid ohne belegten Zusatznutzen; Runtime-Proof noch offen |
| Was fehlt für Implementierung? | **belegt** | async-Abstraktion, `DbSessionStore`, Startup-Migration, CI-Gate |
| PgBouncer-Kompatibilität? | **offen** | Plausibel kompatibel für CRUD, nicht durch Test belegt |
| Weiterer vorgelagerter Diagnose-PR nötig? | **nein** | Kein weiterer Diagnose-PR nötig, sofern der Folge-PR die offenen Target-Proofs enthält: `sqlx`-Migration gegen PostgreSQL/PgBouncer, `DbSessionStore`-CRUD-Integrationstest, weiterhin grüner Offline-Testpfad |
