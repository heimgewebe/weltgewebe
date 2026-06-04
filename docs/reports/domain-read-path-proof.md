---
id: reports.domain-read-path-proof
title: "Domain Read Path Proof"
doc_type: report
status: active
created: 2026-06-03
lang: de
summary: >
  Lokaler Proof für OPT-ARC-001 Phase D: optionaler PostgreSQL-Read-Path
  hinter explizitem Config-Gate. JSONL bleibt Default-Lesequelle und
  Write-Truth; PR-CI-Beleg steht aus.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/reports/domain-backfill-proof.md
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/tasks/board.md
---

# Domain Read Path Proof

## Scope

Dieser Proof dokumentiert OPT-ARC-001 Phase D als **optionalen, read-only
PostgreSQL-Read-Path** für Domänendaten.

Geltende Grenzen:

- JSONL bleibt Default-Lesequelle.
- JSONL bleibt Write-Truth.
- PostgreSQL wird nur über `WELTGEWEBE_DOMAIN_READ_SOURCE=postgres` bzw.
  `domain_read_source: postgres` aktiviert.
- Phase E bleibt offen.
- Write-Paths werden nicht geändert.

## Implementierte Belege

- `apps/api/src/config.rs`: `DomainReadSource` mit Default `Jsonl` und
  explizitem `Postgres`-Opt-in.
- `apps/api/src/domain_db.rs`: read-only Loader für `domain_nodes`,
  `domain_edges` und `domain_accounts`.
- `apps/api/src/lib.rs`: Start-up-Wiring, das bei `Postgres` einen
  konfigurierten PostgreSQL-Pool verlangt.
- `.github/workflows/api.yml`: PR-CI-Job `db-domain-read-path-proof`
  vorbereitet.
- `apps/api/tests/db_domain_read_path.rs`: lokale PostgreSQL-Proof-Suite;
  `db_domain_read_path`-Suite als lokaler PostgreSQL-Proof vorbereitet.

## Validierungsstatus

- db_domain_read_path-Suite als lokaler PostgreSQL-Proof vorbereitet; PR-CI-Beleg ausstehend.
- lokaler Loader-Proof berichtet; PR-CI-Beleg ausstehend.
- Kein `done`-Status für OPT-ARC-001.
- Phase E bleibt offen.

## Nicht bewiesen

- Kein Write-Path-Cutover.
- Kein Abschalten oder Entfernen von JSONL.
- Kein Produktions-Cutover.
- Kein grüner PR-CI-Laufbeleg für den neuen Read-Path-Job in diesem Dokument.
