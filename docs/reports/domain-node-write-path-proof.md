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
  für `POST /nodes`, `PATCH /nodes`, `PUT /nodes/{id}` und
  `DELETE /nodes/{id}` hinter explizitem Write-Gate.
  JSONL bleibt Default; kein Dual-Write; keine öffentlichen Edge-CRUD-Routen;
  Account-, Step-up-E-Mail- und WebAuthn-Writeback-Persistenz bleiben
  unverändert.
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

OPT-ARC-001 Phase E-B implementiert PostgreSQL-Write-Paths für
`POST /nodes`, `PATCH /nodes/{id}`, `PUT /nodes/{id}` und
`DELETE /nodes/{id}`. `DELETE /nodes/{id}` entfernt betroffene
Fadenprojektionen ausschließlich als serverseitige Cascade-Folge der
Knotenlöschung; es entsteht kein öffentlicher Edge-Delete-Pfad.

## Nicht-Ziele

- kein öffentlicher Edge-CRUD-Pfad
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
- `PUT /nodes/{id}` ersetzt die fachlichen Felder vollständig, behält `id` und
  `created_at` bei und persistiert in PostgreSQL über `UPDATE domain_nodes`.
- `DELETE /nodes/{id}` verlangt kohärente Node-/Edge-Write-Quellen. Gemischte
  JSONL/PostgreSQL-Schreibquellen werden vor Mutation mit 409 abgelehnt.
- PostgreSQL-Delete läuft in einer Transaktion, hält den bestehenden
  `domain_edges`-Lock, sperrt die Ziel-Node mit `FOR UPDATE`, validiert
  Edge-Endpunkte vor jeder Mutation und löscht anschließend Node plus
  node-typisierte bzw. eindeutig legacy-untypisierte Fadenprojektionen
  atomar. Explizite `account`-/`role`-Endpunkte bleiben erhalten.
- Legacy-Edges ohne `source_type`/`target_type` werden beim Delete als
  Node-Endpunkt klassifiziert, wenn für dieselbe ID weder ein Account noch ein
  Role-Kollisionsbeleg existiert. Account-/Role-Kollisionen und unbekannte oder
  ungültige Typen blockieren fail-closed ohne Teilmutation.
- JSONL-Delete verwendet eine gemeinsame Journal-Transaktion im bestehenden
  Gewebe-Datenverzeichnis: neue vollständige Node-/Edge-Dateien werden
  vorbereitet und fsync't, Originale als Backups gehalten, Phasen ins Journal
  geschrieben und fsync't, Zielpfade geswappt, der Verzeichniszustand fsync't
  und erst danach Backups/Journal entfernt.
- JSONL-Startup-Recovery läuft vor dem Laden von Nodes/Edges. Bis einschließlich
  `edge_swapped` rollt sie beide Projektionen auf den Originalstand zurück. Erst
  der dauerhaft gespeicherte Marker `node_swapped` gilt als Commit; danach wird
  ausschließlich die verbliebene Transaktionsbereinigung abgeschlossen.
- Nicht parsebare Edge-JSONL-Zeilen blockieren die destruktive Operation ohne
  Teilmutation, weil ihre Beziehung zum Zielknoten nicht sicher bestimmbar ist.

## Payload-Semantik `info: Some(None)` — Option B

Der PostgreSQL-Pfad entfernt den `info`-Key aus dem Payload (`obj.remove("info")`).
Der JSONL-Pfad setzt `info` auf JSON null. Beide Pfade liefern dieselbe öffentliche
`Node`-Projektion (`node.info == None`), unterscheiden sich aber in der
DB-Payload-Shape. Dies ist dokumentiert und akzeptiert.

## Proofs

- `apps/api/tests/db_domain_node_write_path.rs` (PostgreSQL-Proofs,
  `#[ignore]`): Node-Create/Patch/Replace/Delete, Cascade-Atomizität,
  eindeutige untypisierte Legacy-Edges, Account-/Role-Kollisionen und
  ungültige Typen.
- `apps/api/tests/api_collective_mutations.rs`: JSONL-Route-Proofs für
  direkte PUT/DELETE-Webprozesse, kohärente Write-Source-Gates,
  Legacy-untypisierte Cascade-Löschung, Account-/Role-Kollisionen und
  ungültige Typen ohne Teilmutation.
- `apps/api/src/routes/nodes.rs` Unit-Tests `node_delete_journal_tests`:
  Fehler-Injection/Rollback vor dem Commit-Marker, Recovery nach simuliertem
  Prozessabbruch zwischen Edge- und Node-Swap, aufgeschobene Bereinigung nach
  dauerhaftem Commit sowie Fail-Closed-Verhalten bei kaputten Edge-Zeilen.
- CI-Job: `db-domain-node-write-path-proof` in `.github/workflows/api.yml`

## Status

Phase E-B ist implementiert. OPT-ARC-001 bleibt `partial`.

Offen bleiben:

- öffentliche Edge-Writes bleiben Nicht-Ziel; Fadenprojektionen werden nur als
  serverseitige Folge erfolgreicher Webungsaktionen geschrieben oder gelöscht
- Step-up-E-Mail-Persistenz
- WebAuthn-User-ID-Writeback
- Runtime-Smoke / vollständiger Cutover-Beweis
- JSONL-Demontage
