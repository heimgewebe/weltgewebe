---
id: reports.auth-persistence-direct-proof-diagnose-audit
title: "Auth-Persistenz - Diagnose-Audit zum Direct-Postgres-Proof"
doc_type: report
status: deprecated
lifecycle_state: superseded
lifecycle: audit
owner_task: OPT-API-002
superseded_by: docs/reports/optimierungsstatus.md
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

## Lifecycle
- **Lifecycle-State:** superseded
- **Lifecycle:** audit
- **Owner-Task:** OPT-API-002
- **Superseded by:** `docs/reports/optimierungsstatus.md`
- **Bewertung:** Historisches Diagnose-Audit zur korrekten Lesart des Direct-Postgres-Proofs. Die damalige Warnung vor einer Überdeutung bleibt als Kontext nützlich, ist aber durch die spätere implementierte und CI-belegte Session-Persistenz nicht mehr handlungsleitend.

## Urteil

mergebar.

Begründung: Das Proof-Dokument behauptet überwiegend korrekt nur den direkten
SQLx/Postgres-CRUD-Pfad. Es grenzt explizit aus, dass kein `DbSessionStore`,
kein Auth-Umbau und keine produktive Session-Persistenz-Verdrahtung bewiesen
sind. Damit ist es als Runtime-Proof-Baustein valide.

Einschränkung: Das Label `PROVEN` im Dokument darf ausschließlich als
`PROVEN für den direkten SQLx/Postgres-CRUD-Pfad` gelesen werden, nicht als
`PROVEN für produktive Auth-Session-Persistenz`.

## Was wirklich bewiesen ist

- Direkte DB-Verbindung via `PG_DIRECT_URL` ist runtime-seitig bewiesen;
  `DATABASE_URL` ist im Testcode nur als Fallback akzeptiert.
- SQLx-CRUD auf sessions-spaltenkompatiblem Proof-Fixture funktioniert:
  INSERT, SELECT, UPDATE `last_active`, DELETE, COUNT.
- Der Test failt hart bei fehlender URL (kein stilles Skippen).
- Der Test failt hart, wenn Port 6432 (PgBouncer) verwendet wird.
- Offline-Testverhalten bleibt intakt (ignored Integrationstest).

## Was explizit NICHT bewiesen ist

- Keine produktive Persistenz der realen Auth-Sessions aus Middleware/Routes.
- Keine Nutzung durch `SessionStore` in `apps/api/src/auth/session.rs`
  (weiterhin in-memory `RwLock<HashMap<...>>`).
- Keine Auth-Routen-/Middleware-Pfade über DB (`state.sessions.*` bleibt
  in-memory in `apps/api/src/routes/auth.rs` und `apps/api/src/middleware/auth.rs`).
- Keine Startup-Migration als verpflichtender Runtime-Pfad in `apps/api/src/lib.rs`.
- Kein CI-Gate, das Auth-Session-Persistenz über API-Runtime beweist.

## Versteckte Risiken

- Semantisches Risiko: `PROVEN` kann organisatorisch als
  `Persistenzproblem gelöst` fehlgelesen werden.
- Integrationsrisiko: Solange `SessionStore` in-memory bleibt, gehen Sessions bei
  API-Restart verloren, obwohl DB-CRUD isoliert bewiesen ist.
- Betriebsrisiko: Ohne Startup-/CI-Migrationsgate kann eine DB-basiert gedachte
  Persistenz in Runtime-Umgebungen uneinheitlich sein.
- Scope-Risiko: Der Proof läuft auf isoliertem Fixture, nicht auf der realen
  SessionStore-Laufzeitverkabelung.

## Minimaler nächster Folge-PR

Der unmittelbar nächste konkrete PR ist **ausschließlich Phase A** (Abstraktions-PR).
Phase B ist ein späterer, separater PR. Phase A führt keine DB-Runtime-Verdrahtung durch.

Kleinstes sinnvolles Architektur-Gate Richtung echter Persistenz in zwei Phasen:

A) `refactor(auth): introduce SessionBackend abstraction without changing runtime behavior`

- Ziel: Backend-Naht für Session-Operationen einführen.
- In-Memory bleibt aktiv.
- Kein Runtime-Verhalten ändern.
- Kein DbSessionStore.
- Als Abstraktions-Gate abgeschlossen erst, wenn bestehende Offline-Tests grün
  bleiben und Auth-Verhalten identisch bleibt.

B) `feat(auth): add DbSessionStore and prove restart-stable sessions`

- Ziel: DB-Backend für Sessions implementieren und verdrahten.
- Runtime-/CI-Proof für echte Session-Persistenz.
- PROVEN erst mit Restart-Stabilität, DB-Integrationstest und weiterhin
  grünem Offline-Pfad.

Nicht in diesen Folge-PR ziehen: Redis, Token-/Challenge-Store-Persistenz,
Passkey-Store-Umbau, große Auth-Refactors.

## Stop-Kriterium

**Phase A ist eine reine Abstraktions-Naht und macht Auth-Persistenz NICHT lauffähig.**

Phase A gilt erst dann als abgeschlossenes Abstraktions-Gate, wenn:

1. alle bestehenden Offline-Tests grün bleiben,
2. Auth-Verhalten unverändert bleibt,
3. keine Runtime-Verdrahtung auf DB erfolgt.

Phase A macht ausschließlich die Abstraktionsnaht belastbar; Auth-Session-Persistenz bleibt danach weiterhin NOT_PROVEN.

**Auth-Session-Persistenz wird ausschließlich in Phase B PROVEN.**

Phase B ist erst dann `PROVEN`, wenn:

1. Runtime-Beweis: API erzeugt Session, API wird neu gestartet,
   Session bleibt gültig (kein Logout durch Restart).
2. Runtime-Beweis: `logout`, `logout_all`, `remove_device`, `session_refresh`
   wirken über den DB-basierten Session-Pfad korrekt.
3. CI-Beweis: ein DB-gebundener Integrationstest läuft automatisch und scheitert,
   wenn der Session-Persistenzpfad nicht funktioniert.
4. Offline-Beweis: bestehende Offline-Test-Suites bleiben ohne DB grün.

## PR-Titelkandidaten für Phase A (Abstraktions-PR)

1. `refactor(auth): extract session store abstraction without changing runtime wiring`
2. `refactor(api): introduce auth session persistence interface for future DB backend`
3. `test(auth): lock in current session behavior during store abstraction refactor`
