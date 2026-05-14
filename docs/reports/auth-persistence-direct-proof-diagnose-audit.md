---
id: reports.auth-persistence-direct-proof-diagnose-audit
title: "Auth-Persistenz - Diagnose-Audit zum Direct-Postgres-Proof"
doc_type: report
status: active
created: 2026-05-14
lang: de
summary: >
  Diagnose-only Audit des Direct SQLx/Postgres-Proofs mit strikter Trennung
  zwischen bewiesenem DB-CRUD-Pfad und nicht bewiesener produktiver
  Auth-Session-Persistenz. Definiert den kleinsten sinnvollen Folge-PR und
  ein klares PROVEN-Stop-Kriterium.
depends_on:
  - docs/proofs/sqlx-postgres-direct-session-crud-proof.md
  - docs/reports/auth-persistence-next-step.md
  - docs/reports/auth-persistence-readiness.md
  - docs/adr/ADR-0007__auth-persistence-production-db-path.md
relations:
  - type: relates_to
    target: docs/proofs/sqlx-postgres-direct-session-crud-proof.md
  - type: relates_to
    target: docs/reports/auth-persistence-next-step.md
  - type: relates_to
    target: docs/reports/auth-persistence-readiness.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
---

# Auth-Persistenz - Diagnose-Audit zum Direct-Postgres-Proof

Hinweis zur Eingabe: `docs/proofs/auth-postgres-direct-proof.md` ist im Repo nicht vorhanden.
Bewertet wurde stattdessen das vorhandene Dokument
`docs/proofs/sqlx-postgres-direct-session-crud-proof.md`.

## Urteil

mergebar.

Begruendung: Das Proof-Dokument behauptet ueberwiegend korrekt nur den direkten
SQLx/Postgres-CRUD-Pfad. Es grenzt explizit aus, dass kein `DbSessionStore`,
kein Auth-Umbau und keine produktive Session-Persistenz-Verdrahtung bewiesen
sind. Damit ist es als Runtime-Proof-Baustein valide.

Einschraenkung: Das Label `PROVEN` im Dokument darf ausschliesslich als
`PROVEN fuer den direkten SQLx/Postgres-CRUD-Pfad` gelesen werden, nicht als
`PROVEN fuer produktive Auth-Session-Persistenz`.

## Was wirklich bewiesen ist

- Direkte DB-Verbindung via `PG_DIRECT_URL` oder `DATABASE_URL` funktioniert.
- SQLx-CRUD auf sessions-spaltenkompatiblem Proof-Fixture funktioniert:
  INSERT, SELECT, UPDATE `last_active`, DELETE, COUNT.
- Der Test failt hart bei fehlender URL (kein stilles Skippen).
- Der Test failt hart, wenn Port 6432 (PgBouncer) verwendet wird.
- Offline-Testverhalten bleibt intakt (ignored Integrationstest).

## Was explizit NICHT bewiesen ist

- Keine produktive Persistenz der realen Auth-Sessions aus Middleware/Routes.
- Keine Nutzung durch `SessionStore` in `apps/api/src/auth/session.rs`
  (weiterhin in-memory `RwLock<HashMap<...>>`).
- Keine Auth-Routen-/Middleware-Pfade ueber DB (`state.sessions.*` bleibt
  in-memory in `apps/api/src/routes/auth.rs` und `apps/api/src/middleware/auth.rs`).
- Keine Startup-Migration als verpflichtender Runtime-Pfad in `apps/api/src/lib.rs`.
- Kein CI-Gate, das Auth-Session-Persistenz ueber API-Runtime beweist.

## Versteckte Risiken

- Semantisches Risiko: `PROVEN` kann organisatorisch als
  `Persistenzproblem geloest` fehlgelesen werden.
- Integrationsrisiko: Solange `SessionStore` in-memory bleibt, gehen Sessions bei
  API-Restart verloren, obwohl DB-CRUD isoliert bewiesen ist.
- Betriebsrisiko: Ohne Startup-/CI-Migrationsgate kann eine DB-basiert gedachte
  Persistenz in Runtime-Umgebungen uneinheitlich sein.
- Scope-Risiko: Der Proof laeuft auf isoliertem Fixture, nicht auf der realen
  SessionStore-Laufzeitverkabelung.

## Minimaler naechster Folge-PR

Kleinstes sinnvolles Architektur-Gate Richtung echter Persistenz:

1. `DbSessionStore` fuer die bestehende `sessions`-Tabelle implementieren
   (nur Session-Domain, keine anderen Auth-Stores).
2. Einen kleinen async-Backend-Adapter fuer Session-Operationen einfuehren,
   damit `SessionStore`-Aufrufstellen DB oder in-memory nutzen koennen.
3. Runtime-Verdrahtung in `ApiState` + Auth-Middleware/Auth-Routen nur fuer
   Session-Operationen auf den neuen Backend-Pfad umstellen.
4. In-Memory-Fallback fuer Offline-Tests beibehalten.

Nicht in diesen Folge-PR ziehen: Redis, Token-/Challenge-Store-Persistenz,
Passkey-Store-Umbau, grosse Auth-Refactors.

## Stop-Kriterium

Der Folge-PR ist erst dann `PROVEN`, wenn alle Punkte erfuellt sind:

1. Runtime-Beweis: API erzeugt Session, API wird neu gestartet,
   Session bleibt gueltig (kein Logout durch Restart).
2. Runtime-Beweis: `logout`, `logout_all`, `remove_device`, `session_refresh`
   wirken ueber den DB-basierten Session-Pfad korrekt.
3. CI-Beweis: ein DB-gebundener Integrationstest laeuft automatisch und failt,
   wenn Session-Persistenzpfad nicht funktioniert.
4. Offline-Beweis: bestehende Offline-Test-Suites bleiben ohne DB gruen.

## PR-Titelkandidaten (Folge-PR)

1. `feat(auth): wire DbSessionStore for runtime session persistence`
2. `feat(api): switch auth sessions from in-memory to PostgreSQL backend`
3. `test(auth): prove restart-stable session persistence via DbSessionStore`
