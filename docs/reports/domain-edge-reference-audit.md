---
id: reports.domain-edge-reference-audit
title: "Domain Edge Reference Audit — OPT-ARC-001 TODO 4"
doc_type: report
status: active
created: 2026-06-14
lang: de
summary: >
  Diagnosebericht für OPT-ARC-001 Teilaufgabe 4. Auditiert Edge-Referenzen gegen
  vorhandene Nodes, klassifiziert Orphans, typisierte Nicht-Node-Referenzen und
  unklare Referenzen und bereitet die Entscheidung zwischen strikten
  Foreign Keys und loser Referenzsemantik vor.
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: apps/api/migrations/20260531000002_create_domain_edges.up.sql
  - type: relates_to
    target: contracts/domain/edge.schema.json
  - type: relates_to
    target: scripts/docmeta/audit_domain_edge_references.py
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/reports/opt-arc-001-db-proof-matrix.json
---

# Domain Edge Reference Audit

Task: OPT-ARC-001 TODO 4
Status: diagnostic / decision-prep

## Kurzurteil

- Repositories enthalten keine JSONL-Daten, daher wurde der Audit auf `skipped` gesetzt und es ist ein `runtime_data_run` nötig.

- Keine Foreign-Key-Migration in diesem PR.

- Kein Runtime-Cutover-Claim.

- Ergebnis bereitet nur die spätere Entscheidung vor.

## Scope

Dieses Audit prüft Edge-Referenzen gegen vorhandene Nodes.
Geprüft werden:

- JSONL-Edges gegen JSONL-Nodes

- PostgreSQL `domain_edges` gegen `domain_nodes`, falls `DATABASE_URL` gesetzt ist

- `source_id`

- `target_id`

- optionale `source_type` / `target_type` Hinweise

Nicht geprüft oder nicht geändert:

- keine FK-Migration

- kein Runtime-Code

- keine Edge-Normalisierung

- keine Quarantäne-Mutation

- keine JSONL-Demontage

## Blueprint-Anker

Der Cutover-Blueprint verlangt vor Foreign Keys ein explizites Orphan-/Referenz-Audit.
Strikte FKs auf `domain_nodes(id)` sind nur zulässig, wenn das aktuelle Modell nicht
bewusst externe, fehlende oder entitätsübergreifende Referenzen erlaubt.

## Audit-Methode

- Nodes werden als Menge vorhandener `id`s geladen.

- Jede Edge wird auf `source_id` und `target_id` geprüft.

- Typ-Hints (`source_type`, `target_type`) werden klassifiziert.

- Findings werden redigiert.

- Rohdaten werden nicht committed.

## JSONL-Ergebnis

| Metrik | Wert |
| --- | ---: |
| executed | no |
| source_kind | skipped |
| nodes_total | 0 |
| edges_total | 0 |
| edge_sides_total | 0 |
| typed_node_references | 0 |
| typed_node_missing_references | 0 |
| typed_non_node_references | 0 |
| typed_unknown_references | 0 |
| untyped_existing_node_references | 0 |
| untyped_missing_references | 0 |
| node_reference_sides | 0 |
| missing_node_reference_sides | 0 |
| malformed_edges | 0 |
| invalid_json_records | 0 |
| non_object_json_records | 0 |
| edges_with_any_missing_node_reference | 0 |
| edges_with_both_missing_node_references | 0 |
| strict_node_fk_ready | false |
| loose_reference_semantics_observed | false |
| requires_policy_decision | false |
| requires_cleanup | false |
| requires_runtime_data_run | true |

## PostgreSQL-Ergebnis

| Metrik | Wert |
| --- | ---: |
| executed | no |
| source_kind | skipped |
| nodes_total | 0 |
| edges_total | 0 |
| edge_sides_total | 0 |
| typed_node_references | 0 |
| typed_node_missing_references | 0 |
| typed_non_node_references | 0 |
| typed_unknown_references | 0 |
| untyped_existing_node_references | 0 |
| untyped_missing_references | 0 |
| node_reference_sides | 0 |
| missing_node_reference_sides | 0 |
| malformed_edges | 0 |
| invalid_json_records | 0 |
| non_object_json_records | 0 |
| edges_with_any_missing_node_reference | 0 |
| edges_with_both_missing_node_references | 0 |
| strict_node_fk_ready | false |
| loose_reference_semantics_observed | false |
| requires_policy_decision | false |
| requires_cleanup | false |
| requires_runtime_data_run | true |

PostgreSQL runtime audit skipped: DATABASE_URL not set.

### Redigierte Finding-Klassen

Keine vollständigen Edge-, Node-, Account- oder Role-IDs in diesem Report.

| Klasse | Anzahl | Bedeutung |
| --- | --- | --- |
| typed_node_missing_reference | 0 | Typ ist node, aber ID fehlt in Nodes |
| typed_non_node_reference | 0 | Typ-Hinweis ist account oder role |
| typed_unknown_reference | 0 | Typ-Hinweis ist unbekannt |
| untyped_existing_node_reference | 0 | Typ fehlt, ID existiert aber in Nodes |
| untyped_missing_reference | 0 | Typ fehlt und ID fehlt in Nodes |
| malformed_edge | 0 | Edge ist strukturell unvollständig |
| invalid_json | 0 | JSONL-Zeile ist nicht parsebar |
| non_object_json | 0 | JSONL-Zeile ist kein Objekt |

### Entscheidungsvorlage

#### Option A — Strikte Foreign Keys

Geeignet nur wenn:

- echte Runtime-Daten oder ausdrücklich entscheidungsfähige Daten geprüft wurden

- keine typisierten Nicht-Node-Referenzen existieren

- keine unbekannten Typ-Hints existieren

- keine untypisierten Referenzen offen sind

- keine missing Node references existieren

- keine malformed Edges existieren

Konsequenz:

`source_id REFERENCES domain_nodes(id)`
`target_id REFERENCES domain_nodes(id)`

#### Option B — Lose Referenzsemantik mit Guard/Quarantäne-Report

Geeignet wenn:

- Edges bewusst auf Accounts, Roles oder externe Entitäten zeigen können

- Typ-Hints heterogen sind

- historische Orphans existieren, die nicht still gelöscht werden dürfen

- untypisierte Altlasten eine direkte FK-Migration blockieren

Konsequenz:

Keine direkten FKs auf `domain_nodes(id)`, sondern expliziter Integrity-Guard
oder Quarantäne-Report.

### Empfehlung

Status: needs_runtime_data_run

Begründung:

- Keine lokalen JSONL-Daten für Kanten und Knoten gefunden.

- Keine PostgreSQL DB verfügbar, da DATABASE_URL nicht gesetzt ist.

- Ein Runtime Data Run ist notwendig, um über Foreign Keys zu entscheiden.
