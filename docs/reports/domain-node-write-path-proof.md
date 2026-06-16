---
id: reports.domain-node-write-path-proof
title: "Domain Node Write Path Proof"
doc_type: report
status: active
lifecycle_state: active
lifecycle: proof
owner_task: OPT-ARC-001
review_after: 2026-07-16
canonicality: evidence
created: 2026-06-05
lang: de
summary: >
  Proof-Bericht für OPT-ARC-001 Phase E-B: optionaler PostgreSQL-Schreibpfad
  ausschließlich für `PATCH /nodes` hinter explizitem Write-Gate.
  JSONL bleibt Default; kein Dual-Write; Account-, Kanten-, Step-up-E-Mail-
  und WebAuthn-Writeback-Persistenz bleiben unverändert.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
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

# Domain Node Write Path Proof

## Scope

OPT-ARC-001 Phase E-B implementiert einen engen PostgreSQL-Write-Path nur für
`PATCH /nodes`. Alle anderen Endpunkte bleiben unverändert.

## Nicht-Ziele

- keine Edge-Writes
- keine Step-up-E-Mail-Persistenz
- kein WebAuthn-User-ID-Writeback
- kein Account-Write-Umbau über Phase E-A hinaus
- kein JSONL-Abbau
- kein Produktions-Cutover
- kein Dual-Write

## Lifecycle

- Zweck: Belegt den OPT-ARC-001 PostgreSQL-Teilpfad für den Node-Schreibpfad `PATCH /nodes` im dokumentierten Scope.
- Bereitet vor: Fortlaufende OPT-ARC-001 Cutover- und Proof-Matrix-Entscheidungen.
- Gültig bis: Review am 2026-07-16 oder bis ein neuerer Proof diesen Bericht ersetzt.
- Wird abgelöst durch: Noch offen; mögliche spätere Runtime-/Cutover-Proofs oder aktualisierte Proof-Matrix-Artefakte.

## Config-Matrix

| Read Source | Node Write Source | Ergebnis |
|---|---|---|
| JSONL | JSONL | erlaubt — bestehender JSONL-Rewrite-Pfad |
| PostgreSQL | PostgreSQL | erlaubt — `domain_nodes` UPDATE in Transaktion |
| PostgreSQL | JSONL | 409 `DOMAIN_READ_SOURCE_READ_ONLY` |
| JSONL | PostgreSQL | 500 `INVALID_DOMAIN_WRITE_CONFIG` |

## Persistenzverhalten

- JSONL bleibt Default (`WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE` nicht gesetzt).
- PostgreSQL ist opt-in via `WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE=postgres`.
- PostgreSQL-Write setzt `domain_read_source=postgres` voraus (Config-Validation
  erzwingt dies hart; kein stiller Fallback).
- Kein Dual-Write.
- Cache-Update erfolgt erst nach erfolgreichem durable Write.
- Timestamp-Semantik folgt bewusst dem aktuellen JSONL-Pfad: Enthält der Patch
  `info`, wird `updated_at` gebumpt, auch wenn die öffentliche Projektion
  unverändert bleibt; `steckbrief`-Cleanup löst ebenfalls einen Timestamp-Bump aus.
- Finale `Node`-Projektion wird **vor** `tx.commit()` validiert: Ein Mapping-
  oder Serialisierungsfehler kann keine persistierte DB-Mutation hinterlassen.
- Serialisierungsfehler werden nicht auf `{}` geglättet; sie propagieren als
  `NodeWriteError::Serialization`.
- Nicht-Objekt-Payloads (Datenbeschädigung in `domain_nodes.payload`) werden vor
  jeder Mutation als `NodeWriteError::Mapping` zurückgewiesen.

## Payload-Semantik `info: Some(None)` — Option B

Der PostgreSQL-Pfad entfernt den `info`-Key aus dem Payload (`obj.remove("info")`).
Der JSONL-Pfad setzt `info` auf JSON null. Beide Pfade liefern dieselbe öffentliche
`Node`-Projektion (`node.info == None`), unterscheiden sich aber in der
DB-Payload-Shape. Dies ist dokumentiert und akzeptiert.

## Proofs

- `apps/api/tests/db_domain_node_write_path.rs` (Tests A–H, `#[ignore]`)
- CI-Job: `db-domain-node-write-path-proof` in `.github/workflows/api.yml`

## Status

Phase E-B ist implementiert. OPT-ARC-001 bleibt `partial`.

Offen bleiben:

- Edge-Writes
- Step-up-E-Mail-Persistenz
- WebAuthn-User-ID-Writeback
- Runtime-Smoke / vollständiger Cutover-Beweis
- JSONL-Demontage
