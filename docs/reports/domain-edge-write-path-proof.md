---
id: reports.domain-edge-write-path-proof
title: "Domain Edge Write Path Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: OPT-ARC-001
review_after: 2026-07-16
canonicality: evidence
created: 2026-06-12
lang: de
summary: >
  Proof-Bericht für OPT-ARC-001 Phase E-C: optionaler PostgreSQL-Schreibpfad
  ausschließlich für `POST /edges` hinter explizitem Write-Gate.
  JSONL bleibt Default; kein Dual-Write; Account-, Node-, Step-up-E-Mail-
  und WebAuthn-Writeback-Persistenz bleiben unverändert.
relations:
  - type: supersedes
    target: docs/reports/domain-edge-create-semantics-preflight.md
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/reports/domain-node-write-path-proof.md
  - type: relates_to
    target: docs/reports/domain-account-write-path-proof.md
  - type: relates_to
    target: docs/reports/domain-read-path-proof.md
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
---

# Domain Edge Write Path Proof

Task: OPT-ARC-001 Phase E-C.

## Problem

Edge-Writes waren im PostgreSQL-Cutover offen: `POST /edges` schrieb
ausschließlich JSONL und wurde unter `WELTGEWEBE_DOMAIN_READ_SOURCE=postgres`
pauschal mit 409 blockiert. Damit blieb der dritte Domain-Schreibpfad (nach
Account-Create E-A und Node-Patch E-B) ohne PostgreSQL-Persistenz.

## Lifecycle

- Zweck: Belegt den OPT-ARC-001 PostgreSQL-Teilpfad für den Edge-Schreibpfad `POST /edges` im dokumentierten Scope.
- Bereitet vor: Fortlaufende OPT-ARC-001 Cutover- und Proof-Matrix-Entscheidungen.
- Gültig bis: Review am 2026-07-16 oder bis ein neuerer Proof diesen Bericht ersetzt.
- Wird abgelöst durch: Noch offen; mögliche spätere Runtime-/Cutover-Proofs oder aktualisierte Proof-Matrix-Artefakte.

## Implementierte Semantik

### Konfigurationsmatrix

| `domain_read_source` | `domain_edge_write_source` | Verhalten |
|---|---|---|
| `jsonl` | `jsonl` | erlaubt — bestehender JSONL-Append-Pfad (Default) |
| `postgres` | `jsonl` | Config lädt; Route blockt mit 409 `DOMAIN_READ_SOURCE_READ_ONLY` |
| `postgres` | `postgres` | erlaubt — PostgreSQL-Insert-Pfad |
| `jsonl` | `postgres` | Config-Load hard fail; defensiv blockt die Route manuell konstruierte States mit 500 `INVALID_DOMAIN_WRITE_CONFIG` |

Neue Konfiguration: `DomainEdgeWriteSource`
(`WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE`, Config-Key
`domain_edge_write_source`, Default `jsonl`, Aliase wie Account/Node:
`file`/`files`, `pg`/`db`). Startup verlangt bei `postgres` zusätzlich einen
verfügbaren Pool (`apps/api/src/lib.rs`), sonst Startabbruch — kein stiller
Downgrade auf JSONL.

### `POST /edges` je Read-/Write-Source

- Write-Gate (`reject_edge_create_unless_writable`) läuft vor der
  Payload-Validierung; danach unveränderte PR-1-Request-Validierung,
  server-eigene `id`/`created_at`, canonical `build_edge_record`.
- JSONL-Modus: bestehender Pfad unverändert (Persist-Lock,
  `inspect_edge_persistence_for_create`, Boundary-/Limit-/Suffix-Safety,
  `append_edge_line` mit fsync).
- PostgreSQL-Modus: kein JSONL-Append, keine JSONL-Inspection;
  `insert_domain_edge` nutzt eine serialisierte Transaktion mit
  `LOCK TABLE domain_edges IN EXCLUSIVE MODE`, Duplicate-Precheck via `SELECT EXISTS`,
  `COUNT(*) >= MAX_EDGES_CACHE`-Prüfung und finalem Insert. Fehlender Pool → 500,
  kein JSONL-Fallback.
- Routing/Auth unverändert: `POST /edges` bleibt `require_write`;
  `GET /edges` und `GET /edges/{id}` bleiben lesbar wie bisher.

### PostgreSQL-Spalten-/Payload-Mapping

| Spalte | Quelle |
|---|---|
| `domain_edges.id` | `edge.id` (server- oder client-UUID) |
| `domain_edges.source_id` | `edge.source_id` |
| `domain_edges.target_id` | `edge.target_id` |
| `domain_edges.edge_kind` | `edge.edge_kind` |
| `domain_edges.created_at` | server-eigenes `edge.created_at` (RFC3339 → `TIMESTAMPTZ`; nicht parsebar → 500, kein Insert, kein Cache) |
| `domain_edges.payload` | JSONB mit `source_type`, `target_type`, `note` (nur wenn vorhanden; kein `note: null`) |

Die Payload-Key-Namen entsprechen exakt `load_edges_from_postgres`; der
DB-Integrationstest beweist den Roundtrip. `expires_at`, `payload` und
`metadata` bleiben im Create-Request verboten (`deny_unknown_fields`).

### Cache-Update-Regel

Cache-Insert erst nach erfolgreichem Persistenzschritt (JSONL-Append bzw.
DB-Insert); ein fehlgeschriebener Edge landet nie als Phantom im Cache.
JSONL und PostgreSQL verwenden denselben finalen Edge-Wert für Cache und
Response; `GET /edges/{id}` liefert den Edge im selben Prozess.

### Duplicate-/Limit-/Fehler-Mapping

- Duplicate-ID im PostgreSQL-Modus: transaktionaler Duplicate-Precheck unter
  DB-Lock; Duplicate gewinnt vor Cache-Limit und wird als 409
  „edge id already exists“ gemappt. Eine Unique-Violation bleibt defensiver
  Fallback.
- Cache-Limit im PostgreSQL-Modus: `COUNT(*) >= MAX_EDGES_CACHE` innerhalb
  derselben serialisierten Transaktion; bei erreichtem Limit 409
  „edge cache limit reached“, kein Insert, kein Cache-Eintrag, kein JSONL.
- Andere DB-Fehler → 500 „failed to persist edge“.
- JSONL-Fehlersemantik unverändert.

### JSONL-Regressionsschutz

Alle bestehenden `api_edges`-Tests (PR #1185) bleiben grün, inklusive
Boundary-Schutz bei unterminierter Datei, Cache-Limit-Safety,
Duplicate-Erkennung im ungeladenen Suffix, `MAX_EDGES_CACHE=0` + fehlende
Datei → 409, Cache-after-persist und kein Phantom-Cache bei Persistenzfehler.

## Nicht-Ziele

- kein Cutover
- kein Dual-Write
- keine Foreign Keys / kein Orphan-Audit
- kein `updated_at` für Edges
- kein Step-up-E-Mail-Writeback
- kein WebAuthn-User-ID-Writeback
- kein Edge-Contract-Cleanup
- kein `expires_at`-Create-Feld (bleibt via `deny_unknown_fields` abgelehnt)
- kein `PATCH /edges`, kein `DELETE /edges`, keine UI-Änderungen

## Tests

- API-/Route-Tests: `apps/api/tests/api_edges.rs` (JSONL-Regressionsgate,
  Postgres-Read-Block 409, defensiver Invalid-Config-State 500).
- Guard-/Config-Unit-Tests: `apps/api/src/routes/domain_write_guard.rs`,
  `apps/api/src/config.rs` (Matrix inkl. Hard-Fail beim Config-Load).
- Mapping-Unit-Tests: `apps/api/src/domain_db.rs` (`NewDomainEdgeRow`,
  Loader-kompatible Payload-Keys, `created_at`-Pflicht).
- DB-Integrationstest: `apps/api/tests/db_domain_edge_write_path.rs` —
  drei Persistenz-Ebenen: direkte `domain_edges`-Zeile, Cache/GET im selben
  Prozess, `load_edges_from_postgres`-Roundtrip; zusätzlich Duplicate-409,
  Blockierfälle, kein JSONL-Side-Effect.
- CI-Job: `db-domain-edge-write-path-proof` in `.github/workflows/api.yml`
  (PostgreSQL 16, `--include-ignored --test-threads=1`).

## CI-Evidence

- [GitHub Actions Run 27441828545](https://github.com/heimgewebe/weltgewebe/actions/runs/27441828545) (commit `75ad1eb`)
- Phase E-C implementiert.

## Risiken

- FK-/Orphan-Semantik bleibt offen (Migrationskommentar in `20260531000002_create_domain_edges.up.sql`).
- JSONL bleibt Default-Lesequelle und Write-Truth bis zum Cutover.
- Im JSONL-Modus scannt ein erfolgreicher Create die JSONL-Datei weiterhin O(N)
  (Duplicate-/Limit-Inspection). Der PostgreSQL-Modus vermeidet die
  JSONL-Datei-Inspection, nutzt aktuell aber einen table-level Lock plus
  `COUNT(*)` zur Cache-Limit-Sicherung; diese Serialisierung ist
  korrektheitsorientiert und für Cutover/Skalierung später erneut zu bewerten.
