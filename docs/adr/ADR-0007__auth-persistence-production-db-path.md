---
id: adr.ADR-0007-auth-persistence-production-db-path
title: "ADR-0007 — Auth-Persistenz Produktionspfad: Direkter PostgreSQL-Zugriff statt PgBouncer"
doc_type: reference
status: accepted
summary: >
  Kanonisiert den Produktionspfad für Auth-Persistenz: direkter PostgreSQL-Zugriff
  via DATABASE_URL. PgBouncer bleibt Dev-/Spezialpfad und ist keine
  Produktionsvoraussetzung für DbSessionStore.
relations:
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
  - type: relates_to
    target: docs/reports/auth-persistence-runtime-target-reconciliation.md
  - type: relates_to
    target: docs/reports/auth-persistence-runtime-proof.md
  - type: relates_to
    target: docs/proofs/sqlx-pgbouncer-session-crud-proof.md
---

# ADR-0007 — Auth-Persistenz Produktionspfad: Direkter PostgreSQL-Zugriff statt PgBouncer

## Status

accepted

## Kontext

- Der Dev-Stack enthält PgBouncer (`compose.core.yml`, Port 6432, transaction mode).
- Der Prod-Stack enthält keinen PgBouncer (`compose.prod.yml`).
- Die Heimserver-Runtime zeigt keinen PgBouncer-Service.
- `.env.example` setzt `DATABASE_URL` auf direkten Postgres-Port 5432.
- Die API liest ausschließlich `DATABASE_URL`.
- Der SQLx/PgBouncer-Test ist nur `READY_FOR_PROOF` und kein Runtime-Beweis.
- PgBouncer als Produktionsvoraussetzung ist dokumentarisch angenommen, aber runtime-seitig nicht kanonisch.

## Entscheidung

Die produktive Auth-Persistenz nutzt direkten PostgreSQL-Zugriff über `DATABASE_URL`.

PgBouncer ist Dev-/Spezialinfrastruktur und kein erforderlicher Produktionspfad.

## Begründung

- Geringere Betriebs- und Debug-Komplexität.
- Weniger Failure Surfaces.
- Der bestehende Prod-Stack entspricht bereits diesem Modell.
- Kein nachgewiesener Lastdruck für Connection-Pooling.
- PgBouncer transaction mode erzeugt zusätzliche SQLx-/Prepared-Statement-Komplexität.

## Konsequenzen

- `DbSessionStore` darf gegen den direkten PostgreSQL-Pfad geplant werden.
- Der PgBouncer-SQLx-Proof ist ein optionaler Spezialpfad, kein Persistenz-Gate.
- Dokumentation muss Dev-vs-Prod sauber trennen.
- Eine spätere Rückkehr zu PgBouncer als Produktionspfad erfordert ein neues ADR.

## Nicht-Ziele

- Keine Compose-Änderung.
- Kein Runtime-Proof.
- Kein CI-PgBouncer-Job.
- Keine Persistenzimplementierung.
