---
id: reports.auth-persistence-runtime-target-reconciliation
title: "Auth-Persistenz — Runtime-Zielarchitektur-Abgleich (PgBouncer vs. direkter Postgres)"
doc_type: report
status: active
lifecycle_state: active
lifecycle: audit
owner_task: OPT-API-002
review_after: 2026-07-17
created: 2026-05-13
lang: de
summary: >
  Diagnose- und Kanonisierungsbericht. Klärt den Auth-Persistenzpfad für
  Produktion: direkter PostgreSQL-Zugriff via DATABASE_URL ist durch ADR-0007
  entschieden. PgBouncer bleibt Dev-/Spezialpfad und kein Produktions-Gate.
  Keine Implementierung.
depends_on:
  - docs/adr/ADR-0007__auth-persistence-production-db-path.md
  - docs/reports/auth-persistence-runtime-proof.md
  - docs/proofs/sqlx-pgbouncer-session-crud-proof.md
relations:
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
  - type: relates_to
    target: docs/reports/auth-persistence-runtime-proof.md
  - type: relates_to
    target: docs/proofs/sqlx-pgbouncer-session-crud-proof.md
  - type: relates_to
    target: docs/blueprints/auth-persistence-runtime-proof.md
  - type: relates_to
    target: docs/roadmap.md
---

# Auth-Persistenz — Runtime-Zielarchitektur-Abgleich

> **Zweck:** Diagnose und Kanonisierung. Dieses Dokument hält den Abgleich zwischen
> Dev-Stack, Prod-Stack, Runtime-Befund und Proof-Dokumenten fest.
>
> **Ergebnis:** ADR-0007 entscheidet den Produktionspfad: Auth-Persistenz läuft in
> Produktion direkt über PostgreSQL via `DATABASE_URL`. PgBouncer ist
> Dev-/Spezialpfad und kein Produktions-Gate für `DbSessionStore`.
>
> **Kein Produktionscode. Kein CI-Job. Keine Session-Persistenz. Keine Compose-Änderung.**
>
> Aussagen sind als **PROVEN / NOT_PROVEN / CONFLICT_RESOLVED / DECIDED** markiert.

## Lifecycle

- **Lifecycle-State:** active
- **Lifecycle:** audit
- **Owner-Task:** OPT-API-002
- **Review after:** 2026-07-17
- **Bewertung:** Weiterhin aktiver Architekturabgleich zur Produktionsentscheidung
  direkter PostgreSQL-Pfad vs. PgBouncer-Dev-/Spezialpfad. Keine neue
  Runtime-Aussage in diesem PR.

---

## 1. Zweck

Der gemergte SQLx/PgBouncer-Proof (`docs/proofs/sqlx-pgbouncer-session-crud-proof.md`)
ist als `READY_FOR_PROOF` markiert — compiliertes Testgerüst, kein ausgeführter
Runtime-Beweis. Der belegte Heimserver-Zustand zeigt: API und Postgres laufen,
aber kein PgBouncer-Service, keine Rust/Cargo-Toolchain auf dem Runtime-Host.

Die vormals offene Frage war: Soll Auth-Persistenz produktiv über
`API → PgBouncer → Postgres` laufen, oder ist PgBouncer nur Dev-/Spezial-
Infrastruktur?

**Antwort:** ADR-0007 entscheidet den Produktionspfad auf direkten PostgreSQL-Zugriff
via `DATABASE_URL`. Der nächste Architekturpfad für `DbSessionStore` ist daher der
direkte SQLx/Postgres-Persistenzpfad, nicht ein PgBouncer-Produktions-Gate.

---

## 2. Befundmatrix

| Quelle | Aussage | Status | Konsequenz |
|---|---|---|---|
| `infra/compose/compose.core.yml` (dev-Profil) | PgBouncer-Service vorhanden: `edoburu/pgbouncer:1.20`, `POOL_MODE: transaction`, Port 6432. API-Container verbindet explizit via `DATABASE_URL: postgres://...@pgbouncer:6432/...` | **PROVEN** | PgBouncer ist im Dev-Stack kanonisch verdrahtet. |
| `infra/compose/compose.prod.yml` | Kein PgBouncer-Service. API nutzt `DATABASE_URL: ${DATABASE_URL}` (env-injected). | **PROVEN** | Produktionsdefinition enthält keinen PgBouncer-Service. |
| `infra/compose/compose.prod.override.yml` | Kein PgBouncer. Nur API- und Caddy-Overrides. | **PROVEN** | Prod-Override ergänzt keinen PgBouncer. |
| `infra/compose/compose.heimserver.override.yml` | Kein PgBouncer. Nur API-Seed und Caddy-Overrides. | **PROVEN** | Heimserver-Override ergänzt keinen PgBouncer. |
| `.env.example` | `DATABASE_URL` → Port 5432 (direkt). `PGBOUNCER_URL` existiert als separater Eintrag, wird aber nicht als `DATABASE_URL` gesetzt. | **PROVEN** | Beispielkonfiguration trennt direkten Produktionspfad und optionalen PgBouncer-Pfad. |
| `apps/api/src/lib.rs` + `state.rs` | API liest `DATABASE_URL` und erstellt `sqlx::PgPool`. Kein expliziter PgBouncer-Pfad im Produktionscode. `db_pool` wird aktuell nur für Health-Checks genutzt. | **PROVEN** | API verbindet gegen was auch immer in `DATABASE_URL` steht; ADR-0007 legt für Produktion den direkten Postgres-Zielwert fest. |
| Runtime-Dump Heimserver (externe Evidenz) | `docker compose ps`: `weltgewebe-api-1` healthy, `weltgewebe-db-1` healthy, `weltgewebe-nats-1` healthy — kein PgBouncer-Service. Port 6432 nicht sichtbar. Kein `rustc`, kein `cargo` im API-Container. | **PROVEN** | Produktiver Heimserver läuft ohne PgBouncer. |
| `docs/reports/auth-persistence-runtime-proof.md` §2 | „API-Container verbindet über PgBouncer (Port 6432), nicht direkt gegen Postgres" | **CONFLICT_RESOLVED** | Diese Aussage wird auf den Dev-Stack (`compose.core.yml`) eingeschränkt. Für Produktion gilt ADR-0007: `DATABASE_URL` → direkter PostgreSQL-Zugriff. |
| `docs/blueprints/auth-persistence-runtime-proof.md` | Behandelt PgBouncer als Proof-Ziel, wenn im aktiven Stack vorgesehen. | **CONFLICT_RESOLVED** | PgBouncer-Proofs bleiben optionaler Dev-/Spezialpfad; sie sind kein Produktions-Gate. |
| `docs/proofs/sqlx-pgbouncer-session-crud-proof.md` | Test ist `#[ignore]`, Status `READY_FOR_PROOF`. Kein Runtime-Beweis. | **PROVEN** | Proof-Harness vorhanden; Runtime-Ausführung optional und nicht blockierend für Produktions-`DbSessionStore`. |
| `docs/adr/ADR-0007__auth-persistence-production-db-path.md` | Die produktive Auth-Persistenz nutzt direkten PostgreSQL-Zugriff über `DATABASE_URL`; PgBouncer ist Dev-/Spezialinfrastruktur und kein erforderlicher Produktionspfad. | **DECIDED** | Die Zielarchitekturentscheidung ist geschlossen. |

---

## 3. Kontrastprüfung

### Deutung A: PgBouncer bleibt Zielarchitektur für Produktion

**Belege dafür:**

- `compose.core.yml` (dev) verdrahtet PgBouncer explizit und konfiguriert `POOL_MODE: transaction`.
- `.env.example` enthält `PGBOUNCER_URL` als separaten dokumentierten Eintrag.
- Ältere Docs (Blueprint, Runtime-Proof-Report, Proof-Doku) behandelten PgBouncer als Proof-Ziel.
- SQLx/PgBouncer-Testgerüst (`sqlx_pgbouncer_session_crud.rs`) ist vorbereitet.

**Belege dagegen:**

- `compose.prod.yml` hat keinen PgBouncer-Service — kein auskommentiertes Snippet,
  kein TODO, keine Conditionals.
- `compose.prod.override.yml` und `compose.heimserver.override.yml` ergänzen keinen PgBouncer.
- `.env.example` setzt `DATABASE_URL` auf direkten Postgres (5432), nicht auf Port 6432.
- Heimserver-Runtime zeigt keinen PgBouncer — konsistent mit Prod-Compose-Definition.
- Kein Deploy-Runbook oder CI-Workflow richtet PgBouncer für Produktion ein.
- ADR-0007 lehnt PgBouncer als Produktionsvoraussetzung für Auth-Persistenz ab.

### Deutung B: Direkter Postgres-Pfad ist Produktionsarchitektur

**Belege dafür:**

- `compose.prod.yml`: kein PgBouncer, `DATABASE_URL` env-injected.
- `.env.example`: `DATABASE_URL` → Port 5432 (direkt).
- Runtime-Dump: kein PgBouncer-Service, kein Port 6432.
- API-Code (`lib.rs`, `state.rs`): verbindet gegen `DATABASE_URL`, kein PgBouncer-spezifischer Pfad.
- PgBouncer in `compose.core.yml` ist in `profiles: ["dev"]` — explizit als Dev-Werkzeug markiert.
- ADR-0007 kanonisiert diesen Pfad.

**Belege dagegen:**

- Vor ADR-0007 behandelten mehrere Dokumente PgBouncer als Ziel- oder Gate-Annahme.
- `PGBOUNCER_URL` in `.env.example` bleibt als optionaler Spezialpfad dokumentiert.

### Gewichtung

Die **Runtime-Konfiguration** (Compose-Dateien, `.env.example`, Heimserver-Dump) spricht
konsistent für den direkten PostgreSQL-Produktionspfad. Die frühere **Dokumentation**
sprach teilweise für PgBouncer als Ziel, beruhte aber auf Dev-Stack-Beobachtungen und
spiegelte den Prod-Stack nicht korrekt wider.

ADR-0007 löst diese Divergenz formal auf: Für Produktion ist der direkte PostgreSQL-Pfad
kanonisch. PgBouncer bleibt als Dev-/Spezialpfad zulässig, aber nicht als
Voraussetzung für produktive Auth-Persistenz.

---

## 4. Entscheidung

> **DECIDED:** Auth-Persistenz läuft produktiv über direkten PostgreSQL-Zugriff via
> `DATABASE_URL`.

Diese Entscheidung ist in `docs/adr/ADR-0007__auth-persistence-production-db-path.md`
formal akzeptiert.

| Entscheidung | Konsequenz |
|---|---|
| Direkter PostgreSQL-Pfad in Produktion | Prod-Compose und `.env.example` bleiben in ihrer Grundrichtung unverändert: `DATABASE_URL` zeigt für Produktion auf PostgreSQL. `DbSessionStore` wird gegen diesen direkten SQLx/Postgres-Pfad geplant. |
| PgBouncer als Dev-/Spezialpfad | SQLx/PgBouncer-Proofs bleiben möglich, sind aber optional und kein Persistenz-Gate für Produktion. |
| Rückkehr zu PgBouncer als Produktionspfad | Nur über neues ADR zulässig; dann wären Prod-Compose, Deployment, `DATABASE_URL` und Proof-Gates neu zu entscheiden. |

---

## 5. Abgeschlossener Folgepfad

1. `docs/reports/auth-persistence-runtime-proof.md` schränkt die Aussage
   „API verbindet über PgBouncer" auf den Dev-Stack ein.
2. `docs/proofs/sqlx-pgbouncer-session-crud-proof.md` markiert den Proof als
   optionalen Dev-/Spezialpfad.
3. `docs/roadmap.md` und `docs/blueprints/auth-roadmap.md` vermerken die
   geschlossene Zielarchitekturentscheidung.
4. Der nächste Architekturpfad für Auth-Persistenz ist ein direkter
   SQLx/Postgres-Nachweis und danach `DbSessionStore` / `SessionBackend` gegen
   den direkten PostgreSQL-Pfad.

---

## 6. Stop-Regeln

**Kein `DbSessionStore`** ohne direkten SQLx/Postgres-Persistenzpfad-Nachweis.

**Kein CI-PgBouncer-Proof** als Produktions-Gate, solange PgBouncer nicht durch ein
neues ADR als Produktionsziel reaktiviert ist.

**Kein weiterer Proof-PR**, der PgBouncer als Prod-Prämisse voraussetzt, solange
der Prod-Stack keinen PgBouncer-Service enthält und ADR-0007 gilt.

---

## 7. Konfliktdokumentation

Die folgenden Stellen in bestehenden Dokumenten wurden oder werden inhaltlich
präzisiert:

| Dokument | Stelle | Korrektur |
|---|---|---|
| `docs/reports/auth-persistence-runtime-proof.md` §2 | „API-Container verbindet über PgBouncer (Port 6432)" | Gilt nur für Dev-Stack (`compose.core.yml`). Prod-Stack (`compose.prod.yml`) hat keinen PgBouncer; Produktionspfad ist `DATABASE_URL` → direkter PostgreSQL-Zugriff. |
| `docs/blueprints/auth-persistence-runtime-proof.md` | Proof-Ziel PgBouncer | PgBouncer-Proof nur, wenn im aktiven Stack vorgesehen; kein Produktions-Gate. |
| `docs/proofs/sqlx-pgbouncer-session-crud-proof.md` | Gate-Formulierungen vor `DbSessionStore` | Optionaler Dev-/Spezialpfad; kein Blocker für produktiven `DbSessionStore` gegen direkten Postgres. |
| `docs/roadmap.md` Phase 4/5 | Offene Entscheidung | Geschlossen: direkter PostgreSQL-Produktionspfad; Phase 5 folgt gegen direkten Pfad. |
