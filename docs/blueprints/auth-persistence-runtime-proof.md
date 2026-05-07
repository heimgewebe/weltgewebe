---
id: blueprints.auth-persistence-runtime-proof
title: "Auth-Persistenz — Runtime-Proof-Blaupause"
doc_type: blueprint
status: active
created: 2026-05-06
lang: de
summary: >
  Blueprint für sichere und schlanke Auth-Session-Persistenz: erst SQLx-,
  PostgreSQL- und PgBouncer-Runtime-Pfad beweisen, danach DbSessionStore oder
  SessionBackend-Abstraktion implementieren.
depends_on:
  - docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - docs/blueprints/auth-roadmap.md
  - docs/reports/auth-persistence-readiness.md
  - docs/reports/auth-persistence-next-step.md
  - docs/reports/optimierungsstatus.md
relations:
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
  - type: relates_to
    target: docs/specs/auth-api.md
  - type: relates_to
    target: docs/reports/auth-persistence-readiness.md
  - type: relates_to
    target: docs/reports/auth-persistence-next-step.md
---

# Auth-Persistenz — Runtime-Proof-Blaupause

> **Status:** Blueprint für die nächste Auth-Persistenz-Arbeit.
> Dieses Dokument macht den Runtime-Proof zum verpflichtenden nächsten Schritt.
> Es ersetzt nicht ADR-0006, sondern ordnet den Umsetzungspfad für persistente
> Auth-Sessions.

## 0. Dialektik

### These

`SessionStore` soll persistent werden. PostgreSQL ist der naheliegende Zielpfad,
weil bereits `sqlx`, `PgPool`, PostgreSQL, PgBouncer und eine `sessions`-Migration
im Repo vorhanden sind.

### Antithese

Direkt `DbSessionStore` zu bauen ist riskant, solange SQLx, PostgreSQL,
PgBouncer und Migrationen im echten Runtime-Pfad nicht bewiesen sind. Ein
Feature-PR ohne Runtime-Beleg würde Auth-Code, async-Abstraktion und
Infrastruktur-Risiken vermischen.

### Synthese

Runtime-Proof zuerst, danach adaptive Implementierung. Der Idealfall besteht aus
zwei PRs:

1. Runtime-Proof gegen PostgreSQL und, falls im aktiven Stack vorgesehen, PgBouncer.
2. Persistenz-Implementierung mit kleinem Scope: entweder direkt `DbSessionStore`
   oder zuerst eine `SessionBackend`-/`SessionOps`-Abstraktion.

Mehr Phasen entstehen nur, wenn PR 1 echte Hindernisse belegt.

---

## 1. Ziel

Persistente Auth-Sessions über PostgreSQL.

Ergebnisziel:

- Sessions überleben API-Neustarts.
- Serverseitiger Widerruf bleibt möglich.
- Offline-Tests ohne Datenbank bleiben grün.
- Runtime-Pfad mit PostgreSQL und, sofern Stack-Ziel, PgBouncer ist belegt.

---

## 2. Nicht-Ziele

Nicht mitziehen:

- Redis
- JWT-Strategiewechsel
- `TokenStore`-Persistenz
- `StepUpTokenStore`-Persistenz
- `ChallengeStore`-Persistenz
- `PasskeyRegistrationStore`-Persistenz
- `AccountStore` / JSONL → PostgreSQL
- UI-Änderungen
- Startup-Migration ohne gesonderte Entscheidung

---

## 3. Grundprinzipien

### 3.1 Beweis vor Umbau

Kein Auth-Umbau ohne Runtime-Beweis.

### 3.2 Geschlossen fehlschlagen (fail closed)

Wenn DB-Persistenz konfiguriert ist, aber kein DB-Pool verfügbar ist:

- Fehler werfen.
- Nicht still auf In-Memory zurückfallen.

### 3.3 Keine Drift-Kaschierung

Migrationen sollen unerwartete Zustände sichtbar machen.

Zu vermeiden, wenn Drift sichtbar bleiben soll:

```sql
CREATE TABLE IF NOT EXISTS ...
DROP TABLE IF EXISTS ...
```

### 3.4 Offline-Pfad erhalten

Tests ohne Datenbank müssen weiter funktionieren.

### 3.5 Diagnosekommandos repo-konform halten

Für breite Repo-Suchen `rg` verwenden. `grep -R` ist im Agentenpfad zu vermeiden,
weil es in großen Codebasen langsam ist.

---

## 4. Gesamtstrategie

| Schritt | PR | Zweck |
|---|---|---|
| 1 | `chore(db): prove SQLx migration and PgBouncer runtime path` | Runtime-Pfad belegen, keine Auth-Feature-Arbeit |
| 2 | `feat(auth): implement Postgres-backed sessions` oder `refactor(auth): introduce SessionBackend abstraction` | Persistenz oder vorbereitende Abstraktion |

Regel: Mehr Phasen nur, wenn PR 1 echte Hindernisse zeigt.

---

## 5. PR 1 — Runtime-Proof

### Titel

`chore(db): prove SQLx migration and PgBouncer runtime path`

### Ziel

Beweisen, dass die vorhandene `sessions`-Migration und ein minimaler SQLx-Zugriff
gegen den echten DB-Pfad funktionieren.

### Nicht tun

- Kein `DbSessionStore`.
- Keine `SessionBackend`-Abstraktion.
- Keine Auth-Middleware ändern.
- Keine Auth-Routen ändern.
- Keine PgBouncer-Konfig ändern ohne Fehlerbeleg.
- Kein Redis.
- Keine Startup-Migration.

### Diagnose

Ausführen und dokumentieren:

```bash
git status --short
rg -n "sqlx" apps/api/Cargo.toml
sqlx --version
rg -n "pgbouncer|POOL_MODE|6432|DATABASE_URL" \
  infra .env.example docker-compose* compose* docs apps/api 2>/dev/null | head -160
```

### Sicherheitsregel für `revert`

`sqlx migrate revert` darf ausschließlich gegen eine frische lokale
Wegwerf-Datenbank oder ein isoliertes Test-Fixture laufen. Gegen Shared Dev,
Staging oder Produktion ist `revert` verboten, weil die Down-Migration
`DROP TABLE sessions;` ausführt.

Vor jedem Migrationsbeweis muss die Ziel-DB-Klasse dokumentiert werden:
`disposable-local`, `shared-dev`, `staging` oder `prod`.

- `disposable-local`: `run → revert → run` erlaubt.
- `shared-dev`, `staging`, `prod`: nur `run` erlaubt.

### Migration direkt gegen PostgreSQL

```bash
export DATABASE_URL=<direkte-postgres-url>
# Nur bei Ziel-DB-Klasse disposable-local:
sqlx migrate run --source apps/api/migrations
sqlx migrate revert --source apps/api/migrations
sqlx migrate run --source apps/api/migrations
# Bei shared-dev/staging/prod:
sqlx migrate run --source apps/api/migrations
```

### Migration gegen PgBouncer

Nur ausführen, wenn PgBouncer im Stack aktiv ist.

```bash
export DATABASE_URL=<pgbouncer-url>
# Nur bei Ziel-DB-Klasse disposable-local:
sqlx migrate run --source apps/api/migrations
sqlx migrate revert --source apps/api/migrations
sqlx migrate run --source apps/api/migrations
# Bei shared-dev/staging/prod:
sqlx migrate run --source apps/api/migrations
```

### Minimaler SQLx-CRUD-Smoke

Gegen Tabelle `sessions` prüfen:

- `INSERT`
- `SELECT`
- `UPDATE last_active`
- `DELETE`

Der Smoke darf Script oder Integrationstest sein. Er darf keinen Auth-Code
umbauen.

### Offline-Test

```bash
cargo test --locked -p weltgewebe-api
```

### Ergebnislogik

| Ergebnis | Folge |
|---|---|
| PostgreSQL + PgBouncer + CRUD grün | Weiter zu PR 2 |
| PostgreSQL grün, PgBouncer scheitert | Gezielte Mitigation |
| CRUD scheitert | Ursache isolieren |
| DB nicht verfügbar | Umgebung herstellen oder Nebenpfad dokumentieren |
| Offline-Tests scheitern | Stoppen, kein Auth-Umbau |

---

## 6. Mitigation bei Fehlschlag

Nur bei belegtem Fehler.

### Option A — PgBouncer aktualisieren

- PgBouncer auf Version `>= 1.21` aktualisieren.
- `max_prepared_statements` explizit setzen.

### Option B — SQLx Statement Cache entschärfen

Nur anwenden, wenn PgBouncer-/Prepared-Statement-Fehler belegt sind.

### Option C — API direkt gegen PostgreSQL

Nur wählen, wenn PgBouncer bewusst nicht Zielpfad ist.

Regel: Keine Infrastrukturänderung ohne reproduzierten Fehler.

---

## 7. PR 2 — Persistenz-Implementierung

### Entscheidung vor PR 2

Aufrufstellen messen:

```bash
rg -n "sessions\.(create|get|delete|touch|list_by_account|delete_by_device|delete_all_by_account)" \
  apps/api/src apps/api/tests
```

### Pfad A — Kombinierter PR

Wählen, wenn Änderungsfläche klein bleibt.

PR-Titel:

`feat(auth): implement Postgres-backed sessions`

Scope:

- `SessionBackend` oder `SessionOps`
- `DbSessionStore`
- Backend-Auswahl im `ApiState`
- Middleware/Routen async anpassen
- DB-Integrationstests
- Offline-Tests bleiben grün

### Pfad B — Erst Abstraktion

Wählen, wenn Änderungsfläche breit wird.

PR-Titel:

`refactor(auth): introduce SessionBackend abstraction`

Scope:

- Nur Abstraktion.
- In-Memory-Verhalten bleibt identisch.
- Keine DB-Nutzung.
- Keine Runtime-Semantikänderung.

Danach folgt ein eigener PR für `DbSessionStore`.

---

## 8. Backend-Regel

| Zustand | Backend-Verhalten |
|---|---|
| DB konfiguriert + Pool vorhanden | `DbSessionStore` |
| DB konfiguriert + Pool fehlt | Fehler |
| DB nicht konfiguriert | In-Memory nur für Dev/Test/Single-Instance |

---

## 9. `DbSessionStore`-Anforderungen

Methoden:

- `create`
- `get`
- `delete`
- `touch`
- `list_by_account`
- `delete_by_device`
- `delete_all_by_account`

Regeln:

- `get` gibt abgelaufene Sessions nicht zurück.
- `list_by_account` gibt nur nicht-abgelaufene Sessions zurück.
- `touch` aktualisiert `last_active`.
- `delete_by_device` löscht scoped.
- `delete_all_by_account` löscht scoped.

Tests:

- Session nach Store-Neuerzeugung abrufbar.
- Abgelaufene Session nicht abrufbar.
- `delete_by_device` scoped korrekt.
- `delete_all_by_account` scoped korrekt.
- `touch` aktualisiert `last_active`.
- Offline-Tests ohne Datenbank bleiben grün.

---

## 10. Deploy-/CI-Migrationsstrategie

Nicht automatisch vermischen.

Bevorzugt:

- Migration vor API-Start im Deploy-/CI-Pfad.

Nur bewusst und nach Proof:

- Startup-Migration in der API.

Manuell nur für Dev:

```bash
just db-migrate
```

---

## 11. Statuslogik

Nach PR 1:

- `OPT-API-003` bleibt `partial`, aber mit stärkerem Runtime-Nachweis.

Nach PR 2 mit `DbSessionStore`, aber ohne vollständigen CI-/Deploy-Beweis:

- `OPT-API-002` = `partial`.

Erst bei geschlossenem Runtime-, CI-, Deploy- und Restlückenbeweis:

- `OPT-API-002` = `done`.

---

## 12. Alternativpfade

### Wenn DB/PgBouncer blockiert

`OPT-INF-001`: Trivy Image Scanning.

### Wenn Runtime-Proof blockiert, aber Code-Fortschritt nötig ist

`refactor(auth): introduce SessionBackend abstraction`

Nur ohne DB-Nutzung.

---

## 13. Agentenauftrag für den nächsten PR

Arbeite diagnose-first. Ziel ist ein Runtime-Proof-PR, kein Auth-Feature.

PR-Titel:

`chore(db): prove SQLx migration and PgBouncer runtime path`

Aufgabe:

Beweise, dass die bestehende `sessions`-Migration und ein minimaler SQLx-CRUD-Pfad
gegen PostgreSQL und, falls im Stack vorgesehen, gegen PgBouncer funktionieren.

Nicht tun:

- Kein `DbSessionStore`.
- Keine `SessionBackend`-Abstraktion.
- Keine Auth-Middleware ändern.
- Keine Auth-Routen ändern.
- Keine PgBouncer-Konfig ändern, bevor ein Fehler belegt ist.
- Kein Redis.
- Keine Startup-Migration.

Diagnose und Runtime-Proof:

- Führe die Diagnose aus Abschnitt 5 aus.
- Beachte zwingend die Sicherheitsregel für `sqlx migrate revert`.
- Dokumentiere vor jedem Migrationsbefehl die Ziel-DB-Klasse.
- Führe den direkten PostgreSQL-Proof aus.
- Führe den PgBouncer-Proof nur aus, wenn PgBouncer im aktiven Stack vorgesehen ist.
- Erstelle den kleinsten reproduzierbaren CRUD-Smoke gegen `sessions`.
- Führe `cargo test --locked -p weltgewebe-api` aus.

Patch-Regel:

- Wenn nur Dokumentation/Script nötig ist, klein halten.
- Wenn PgBouncer scheitert, Fehlerausgabe dokumentieren und keine große Mitigation ohne Rücksprache.
- Keine Konfigänderung ohne belegten Fehler.

Lieferung:

1. Belegter Ist-Zustand.
2. Runtime-Ausgaben.
3. Patch-Zusammenfassung.
4. Entscheidung: Weiter zu `DbSessionStore`, erst `SessionBackend`, oder Mitigation?
5. Restlücken.

---

## 14. Essenz

Hebel: Erst DB-Runtime beweisen, dann Auth umbauen.

Entscheidung: Zwei PRs: Runtime-Proof → Persistenz.

Nächste Aktion: Agentenauftrag für
`chore(db): prove SQLx migration and PgBouncer runtime path`.

Unsicherheitsgrad: `0.12` — lokale Runtime-Ausgaben fehlen.

Interpolationsgrad: `0.06` — Annahme: aktueller Branch entspricht dem besprochenen
Stand.
