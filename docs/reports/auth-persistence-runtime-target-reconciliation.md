---
id: reports.auth-persistence-runtime-target-reconciliation
title: "Auth-Persistenz — Runtime-Zielarchitektur-Abgleich (PgBouncer vs. direkter Postgres)"
doc_type: report
status: active
created: 2026-05-13
lang: de
summary: >
  Diagnose- und Kanonisierungsbericht. Klärt, ob PgBouncer im Auth-Persistenzpfad
  weiterhin kanonische Zielarchitektur ist oder ob der belegte Runtime-Zustand davon
  abweicht. Befundmatrix, Kontrastprüfung, offene Entscheidung und Stop-Regeln.
  Keine Implementierung.
depends_on:
  - docs/reports/auth-persistence-runtime-proof.md
  - docs/proofs/sqlx-pgbouncer-session-crud-proof.md
relations:
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

> **Zweck:** Diagnose und Kanonisierung. Klärt, ob `API → PgBouncer → Postgres`
> wirklich Zielarchitektur ist oder ob PgBouncer nur noch Doku-/Config-Rest ist.
>
> **Kein Produktionscode. Kein CI-Job. Keine Session-Persistenz. Keine Compose-Änderung.**
>
> Alle Aussagen sind als **PROVEN / NOT_PROVEN / CONFLICT / OPEN_DECISION** markiert.

---

## 1. Zweck

Der gemergte SQLx/PgBouncer-Proof (`docs/proofs/sqlx-pgbouncer-session-crud-proof.md`)
ist als `READY_FOR_PROOF` markiert — compiliertes Testgerüst, kein ausgeführter
Runtime-Beweis. Der belegte Heimserver-Zustand zeigt: API und Postgres laufen,
aber kein PgBouncer-Service, keine Rust/Cargo-Toolchain auf dem Runtime-Host.

Damit ist offen: Ist `API → PgBouncer → Postgres` wirklich der Zielpfad für
Auth-Persistenz in der Produktion — oder ist PgBouncer nur Dev-Infrastruktur?

Diese Frage entscheidet, ob der nächste Schritt ein CI-PgBouncer-Proof ist
oder ob der Persistenzpfad direkt auf Postgres geht.

---

## 2. Befundmatrix

| Quelle | Aussage | Status | Konsequenz |
|---|---|---|---|
| `infra/compose/compose.core.yml` (dev-Profil) | PgBouncer-Service vorhanden: `edoburu/pgbouncer:1.20`, `POOL_MODE: transaction`, Port 6432. API-Container verbindet explizit via `DATABASE_URL: postgres://...@pgbouncer:6432/...` | **PROVEN** | PgBouncer ist im Dev-Stack kanonisch verdrahtet. |
| `infra/compose/compose.prod.yml` | Kein PgBouncer-Service. API nutzt `DATABASE_URL: ${DATABASE_URL}` (env-injected). | **PROVEN** | Produktionsdefinition enthält keinen PgBouncer-Service. |
| `infra/compose/compose.prod.override.yml` | Kein PgBouncer. Nur API- und Caddy-Overrides. | **PROVEN** | Prod-Override ergänzt keinen PgBouncer. |
| `infra/compose/compose.heimserver.override.yml` | Kein PgBouncer. Nur API-Seed und Caddy-Overrides. | **PROVEN** | Heimserver-Override ergänzt keinen PgBouncer. |
| `.env.example` | `DATABASE_URL` → Port 5432 (direkt). `PGBOUNCER_URL` existiert als separater Eintrag, wird aber nicht als `DATABASE_URL` gesetzt. | **CONFLICT** | `.env.example` dokumentiert PgBouncer-URL, setzt aber `DATABASE_URL` auf direkten Postgres. |
| `apps/api/src/lib.rs` + `state.rs` | API liest `DATABASE_URL` und erstellt `sqlx::PgPool`. Kein expliziter PgBouncer-Pfad im Produktionscode. `db_pool` wird aktuell nur für Health-Checks genutzt. | **PROVEN** | API verbindet gegen was auch immer in `DATABASE_URL` steht. Kein Auth-Pfad nutzt den Pool. |
| Runtime-Dump Heimserver (externe Evidenz) | `docker compose ps`: `weltgewebe-api-1` healthy, `weltgewebe-db-1` healthy, `weltgewebe-nats-1` healthy — **kein PgBouncer-Service**. Port 6432 nicht sichtbar. Kein `rustc`, kein `cargo` im API-Container. | **PROVEN** | Produktiver Heimserver läuft ohne PgBouncer. |
| `docs/reports/auth-persistence-runtime-proof.md` §2 | „API-Container verbindet über PgBouncer (Port 6432), nicht direkt gegen Postgres" | **CONFLICT** | Diese Aussage gilt für den Dev-Stack (`compose.core.yml`). Für den Prod-Stack ist sie falsch. Die Quelle dokumentiert einen Dev-Befund, nicht den Prod-Zustand. |
| `docs/blueprints/auth-persistence-runtime-proof.md` §5 | Behandelt PgBouncer als Ziel des Runtime-Proof-PR. | **NOT_PROVEN** | PgBouncer ist im Blueprint als Proof-Ziel gesetzt, ohne dass Prod-Stack diesen Pfad enthält. |
| `docs/proofs/sqlx-pgbouncer-session-crud-proof.md` | Test ist `#[ignore]`, Status `READY_FOR_PROOF`. Kein Runtime-Beweis. | **PROVEN** | Proof-Harness vorhanden; Runtime-Ausführung ausstehend. |
| `docs/roadmap.md` Phase 4 | „SQLx/PgBouncer-CRUD-Smoke belegt; SQLx-via-PgBouncer-Rust-Proof offen" | **CONFLICT** | Phase 4 spiegelt nicht wider, dass die PgBouncer-Zielentscheidung für Produktion offen ist. |

---

## 3. Kontrastprüfung

### Deutung A: PgBouncer bleibt Zielarchitektur für Produktion

**Belege dafür:**

- `compose.core.yml` (dev) verdrahtet PgBouncer explizit und konfiguriert `POOL_MODE: transaction`.
- `.env.example` enthält `PGBOUNCER_URL` als separaten dokumentierten Eintrag.
- Mehrere Docs (Blueprint, Runtime-Proof-Report, Proof-Doku) behandeln PgBouncer als Ziel.
- SQLx/PgBouncer-Testgerüst (`sqlx_pgbouncer_session_crud.rs`) ist vorbereitet.

**Belege dagegen:**

- `compose.prod.yml` hat keinen PgBouncer-Service — kein auskommentiertes Snippet,
  kein TODO, keine Conditionals.
- `compose.prod.override.yml` und `compose.heimserver.override.yml` ergänzen keinen PgBouncer.
- `.env.example` setzt `DATABASE_URL` auf direkten Postgres (5432), nicht auf Port 6432.
- Heimserver-Runtime zeigt keinen PgBouncer — konsistent mit Prod-Compose-Definition.
- Kein Deploy-Runbook oder CI-Workflow richtet PgBouncer für Produktion ein.

### Deutung B: Direkter Postgres-Pfad ist faktische Runtime-Architektur für Produktion

**Belege dafür:**

- `compose.prod.yml`: kein PgBouncer, `DATABASE_URL` env-injected.
- `.env.example`: `DATABASE_URL` → Port 5432 (direkt).
- Runtime-Dump: kein PgBouncer-Service, kein Port 6432.
- API-Code (`lib.rs`, `state.rs`): verbindet gegen `DATABASE_URL`, kein PgBouncer-spezifischer Pfad.
- PgBouncer in `compose.core.yml` ist in `profiles: ["dev"]` — explizit als Dev-Werkzeug markiert.

**Belege dagegen:**

- Mehrere Docs behandeln PgBouncer als Zielarchitektur und wurden nie zurückgezogen.
- `PGBOUNCER_URL` in `.env.example` deutet auf zumindest geplante Nutzung hin.
- Blueprint und Proof-Dokumente wurden aufgebaut, ohne dass ihre Prämissen (PgBouncer in Prod) formell abgelehnt wurden.

### Gewichtung

Die **Runtime-Konfiguration** (Compose-Dateien, .env.example, Heimserver-Dump) spricht
konsistent für Deutung B: Prod läuft ohne PgBouncer. Die **Dokumentation** spricht für
Deutung A, aber sie wurde auf Basis von Dev-Stack-Beobachtungen geschrieben und spiegelt
den Prod-Stack nicht korrekt wider.

Für diese konkrete Runtime-Frage haben Compose-Konfigurationen, `.env.example`,
API-Code und der Heimserver-Dump höhere Beweiskraft als ältere Reports, weil sie den
aktuell ausführbaren bzw. konfigurierten Verbindungspfad beschreiben. Die Reports
bleiben wichtig als Absichtsdokumente, sind hier aber teilweise mit dem belegten
Prod-/Heimserver-Zustand im Konflikt.

---

## 4. Entscheidungspunkt

> **OPEN_DECISION:** Soll Auth-Persistenz produktiv über PgBouncer transaction mode laufen?

Diese Frage ist im Repo weder explizit entschieden noch durch einen ADR abgedeckt.

**Auswirkung der Entscheidung:**

| Entscheidung | Konsequenz |
|---|---|
| **JA: PgBouncer in Produktion** | PgBouncer muss in `compose.prod.yml` ergänzt werden. `DATABASE_URL` in Prod muss auf Port 6432 zeigen. Erst dann ist ein CI-/Runtime-Proof mit PgBouncer sinnvoll. SQLx/PgBouncer-Test kann danach ausgeführt werden. |
| **NEIN: Direkter Postgres-Pfad** | Prod-Compose und `.env.example` bleiben wie sie sind. `DATABASE_URL` → direkter Postgres. SQLx/PgBouncer-Proof wird als optionaler Spezialpfad markiert (oder archiviert). `DbSessionStore` wird gegen direkten Postgres geplant. Roadmap/Reports korrigieren. |

---

## 5. Empfohlener nächster Schritt nach Entscheidung

### Wenn JA — PgBouncer bleibt Ziel

1. PgBouncer in `compose.prod.yml` als kanonischen Service ergänzen.
2. `DATABASE_URL` in `.env.example` auf Port 6432 umstellen (oder `PGBOUNCER_URL` als
   primäre DB-URL im Prod-Stack dokumentieren).
3. Heimserver-Deployment anpassen: PgBouncer-Service starten.
4. Erst danach: SQLx/PgBouncer-Test mit `--include-ignored` ausführen (Runtime-Proof).
5. Erst nach bestandenem Runtime-Proof: `DbSessionStore` gegen PgBouncer-Pfad planen.

### Wenn NEIN — direkter Postgres-Pfad

1. `docs/blueprints/auth-persistence-runtime-proof.md` — PgBouncer-Pfad als
   Dev-only / optional kennzeichnen.
2. `docs/reports/auth-persistence-runtime-proof.md` §2 — Klarstellung ergänzen:
   Dev-Stack nutzt PgBouncer, Prod-Stack verbindet direkt gegen Postgres.
3. `docs/proofs/sqlx-pgbouncer-session-crud-proof.md` — Status auf `optional`
   oder `archived` setzen; Scope auf „Dev-/Spezialpfad" eingrenzen.
4. `DbSessionStore` gegen direkten Postgres-Pfad planen (`DATABASE_URL` → Port 5432).
5. Roadmap Phase 4 aktualisieren: PgBouncer-Proof als Dev-Pfad, nicht als
   Prod-Gate.

---

## 6. Stop-Regeln

**Kein `DbSessionStore`**, solange diese OPEN_DECISION nicht explizit aufgelöst ist.

**Kein CI-PgBouncer-Proof**, solange PgBouncer nicht als Prod-Zielarchitektur
bestätigt und in `compose.prod.yml` kanonisch eingetragen ist.

**Kein weiterer Proof-PR**, der PgBouncer als Prod-Prämisse voraussetzt, solange
der Prod-Stack keinen PgBouncer-Service enthält.

---

## 7. Konfliktdokumentation

Die folgenden Stellen in bestehenden Dokumenten sind inhaltlich ungenau und
müssen nach Entscheidung korrigiert werden:

| Dokument | Stelle | Problem |
|---|---|---|
| `docs/reports/auth-persistence-runtime-proof.md` §2 | „API-Container verbindet über PgBouncer (Port 6432)" | Gilt nur für Dev-Stack (`compose.core.yml`). Prod-Stack (`compose.prod.yml`) hat keinen PgBouncer. |
| `docs/blueprints/auth-persistence-runtime-proof.md` | Gesamtblaupause behandelt PgBouncer als Prod-Proof-Ziel | Prod-Stack enthält PgBouncer nicht. Blueprint wurde auf Basis von Dev-Stack-Beobachtungen geschrieben. |
| `docs/roadmap.md` Phase 4 | „SQLx/PgBouncer-CRUD-Smoke belegt" als Gate für `DbSessionStore` | CRUD-Smoke ist belegt, aber Prod-Zielarchitektur für PgBouncer ist OPEN_DECISION. |
