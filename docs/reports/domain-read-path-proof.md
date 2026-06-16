---
id: reports.domain-read-path-proof
title: "Domain Read Path Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: OPT-ARC-001
review_after: 2026-07-16
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
    target: docs/reports/domain-account-write-path-proof.md
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
- Write-Paths werden in Phase D nicht auf PostgreSQL umgestellt.
- Mutierende Domänen-Endpunkte werden bei `WELTGEWEBE_DOMAIN_READ_SOURCE=postgres`
  mit `409 CONFLICT` / `DOMAIN_READ_SOURCE_READ_ONLY` blockiert.

> **Folge-Slice Phase E-A:** Aufbauend auf diesem Read-Path implementiert
> Phase E-A einen engen, opt-in PostgreSQL-Schreibpfad **nur** für
> `POST /accounts` hinter dem getrennten Gate
> `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE`. Im Postgres-Read-Modus ist
> Account-Create damit nicht mehr pauschal blockiert, sondern nur dann, wenn der
> Account-Write-Source weiterhin `jsonl` ist. Knoten-, Kanten-, Step-up-E-Mail-
> und WebAuthn-Writeback-Mutationen bleiben blockiert bzw. unverändert. Details:
> `docs/reports/domain-account-write-path-proof.md`.

## Lifecycle

- Zweck: Belegt den OPT-ARC-001 PostgreSQL-Teilpfad für den optionalen PostgreSQL-Read-Path im dokumentierten Scope.
- Bereitet vor: Fortlaufende OPT-ARC-001 Cutover- und Proof-Matrix-Entscheidungen.
- Gültig bis: Review am 2026-07-16 oder bis ein neuerer Proof diesen Bericht ersetzt.
- Wird abgelöst durch: Noch offen; mögliche spätere Runtime-/Cutover-Proofs oder aktualisierte Proof-Matrix-Artefakte.

## Implementierte Belege

- `apps/api/src/config.rs`: `DomainReadSource` mit Default `Jsonl` und
  explizitem `Postgres`-Opt-in.
- `apps/api/src/domain_db.rs`: read-only Loader für `domain_nodes`,
  `domain_edges` und `domain_accounts`.
- `apps/api/src/lib.rs`: Start-up-Wiring, das bei `Postgres` einen
  konfigurierten PostgreSQL-Pool verlangt.
- `apps/api/src/routes/domain_write_guard.rs`: Guard gegen JSONL-only
  Domänenmutationen im PostgreSQL-Read-Modus.
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
- Kein PostgreSQL-Write-Path und kein Dual-Write; Domänenmutationen sind im
  PostgreSQL-Read-Modus bewusst blockiert.
- Kein Abschalten oder Entfernen von JSONL.
- Kein Produktions-Cutover.
- Kein grüner PR-CI-Laufbeleg für den neuen Read-Path-Job in diesem Dokument.

## JSONL/PostgreSQL List Parity Diagnostic

Status: diagnostic_gap / prepared for CI.

This diagnostic checks the loader/cache order that the legacy list endpoints
paginate with `offset` / `limit` before any PostgreSQL runtime cutover.
It is not a full HTTP route-level parity proof.

### Current contract anchors

- Legacy `/nodes` uses cache insertion order with `offset` / `limit`.
- Legacy `/edges` uses cache insertion order with `offset` / `limit`.
- Legacy `/accounts` uses account-id order through `AccountStore`.
- Cursor mode uses stable id-ascending order for all domains.

### Diagnostic result

The test operates at loader/cache level. This is sufficient for the current
legacy-order diagnostic because the legacy `/nodes` and `/edges` endpoints
paginate `cache.iter_in_order()` directly, while `/accounts` iterates the
`AccountStore` in id order.

With deliberately non-id-sorted fixture data (`c, a, b`):

| Domain | Legacy JSONL order | PostgreSQL loader order | Result |
| --- | --- | --- | --- |
| nodes | `c, a, b` | `a, b, c` | gap |
| edges | `c, a, b` | `a, b, c` | gap |
| accounts | `a, b, c` | `a, b, c` | parity |

Cursor mode remains id-ascending by contract and is not the source of the
legacy mismatch.

### Consequence

TODO 3 final parity proof remains open. This PR records the current gap; it does
not decide or revise the canonical target ordering.

The current blueprint requires PostgreSQL read cutover parity to preserve:

- legacy `/nodes` order as the existing insertion/file order
- legacy `/edges` order as the existing insertion/file order
- legacy `/accounts` order as the existing id order
- cursor order as stable id-ascending order for all three domains

Therefore the nodes/edges legacy mismatch is a blocker for PostgreSQL read
cutover until a follow-up PR implements order preservation or explicitly revises
the blueprint first.

Required follow-up outcome:

- preserve legacy nodes/edges order in PostgreSQL, likely via an explicit
  ordinal/position captured during JSONL backfill/import; or
- first revise `docs/blueprints/domain-data-postgres-cutover.md` in a separate
  API-contract decision PR before changing the target order.

This diagnostic PR does neither.

### Non-goals

- no runtime cutover
- no default-source change
- no JSONL removal
- no migration
- no ORDER BY fix
- no Step-up or WebAuthn claim
