---
id: reports.domain-edge-reference-audit
title: "Domain Edge Reference Audit — OPT-ARC-001 Teilaufgabe 4"
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

Task: OPT-ARC-001 Teilaufgabe 4
Status: diagnostic / decision-prep

## Kurzurteil

Dieser PR beweist das Audit-Harness, nicht die Runtime-Datenlage.
Da keine entscheidungsfähige JSONL- oder PostgreSQL-Runtime-Quelle geprüft wurde,
bleibt die FK-Entscheidung blockiert bis zu einem Runtime-Datenlauf.

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
Strikte FKs auf `domain_nodes(id)` sind nur zulässig,
wenn das aktuelle Modell nicht bewusst externe, fehlende oder entitätsübergreifende Referenzen erlaubt.

## Audit-Methode

- Nodes werden als Menge vorhandener `id`s geladen.
- Jede Edge wird auf `source_id` und `target_id` geprüft.

- Typ-Hints (`source_type`, `target_type`) werden klassifiziert.
- Findings werden redigiert.

- Rohdaten werden nicht committed.

## Ausführungsprovenienz

### JSONL-Suche

Befehl:

```bash
find . \
  -path './.git' -prune -o \
  -path './target' -prune -o \
  -path './node_modules' -prune -o \
  -path './apps/web/node_modules' -prune -o \
  -type f \( -name '*nodes*.jsonl' -o -name '*edges*.jsonl' \) \
  -print

```

Ergebnis:

```text
keine Kandidaten

```

### PostgreSQL

DATABASE_URL war nicht gesetzt; PostgreSQL-Audit wurde nicht ausgeführt.

## JSONL-Ergebnis

| Metrik | Wert |
| --- | ---: |
| executed | no |
| source_kind | skipped |
| node_records_total | n/a |
| node_ids_total | n/a |
| node_invalid_json_records | n/a |
| node_non_object_json_records | n/a |
| nodes_missing_id | n/a |
| nodes_non_string_id | n/a |
| node_duplicate_ids | n/a |
| edge_records_total | n/a |
| auditable_edges_total | n/a |
| nodes_total | n/a |
| edges_total | n/a |
| edge_sides_total | n/a |
| typed_node_references | n/a |
| typed_node_missing_references | n/a |
| typed_non_node_references | n/a |
| typed_unknown_references | n/a |
| untyped_existing_node_references | n/a |
| untyped_missing_references | n/a |
| node_reference_sides | n/a |
| missing_node_reference_sides | n/a |
| malformed_edges | n/a |
| invalid_json_records | n/a |
| non_object_json_records | n/a |
| edges_with_any_missing_node_reference | n/a |
| edges_with_both_missing_node_references | n/a |
| strict_node_fk_ready | false |
| loose_reference_semantics_observed | n/a |
| requires_policy_decision | n/a |
| requires_cleanup | n/a |
| requires_runtime_data_run | true |

## PostgreSQL-Ergebnis

| Metrik | Wert |
| --- | ---: |
| executed | no |
| source_kind | skipped |
| node_records_total | n/a |
| node_ids_total | n/a |
| node_invalid_json_records | n/a |
| node_non_object_json_records | n/a |
| nodes_missing_id | n/a |
| nodes_non_string_id | n/a |
| node_duplicate_ids | n/a |
| edge_records_total | n/a |
| auditable_edges_total | n/a |
| nodes_total | n/a |
| edges_total | n/a |
| edge_sides_total | n/a |
| typed_node_references | n/a |
| typed_node_missing_references | n/a |
| typed_non_node_references | n/a |
| typed_unknown_references | n/a |
| untyped_existing_node_references | n/a |
| untyped_missing_references | n/a |
| node_reference_sides | n/a |
| missing_node_reference_sides | n/a |
| malformed_edges | n/a |
| invalid_json_records | n/a |
| non_object_json_records | n/a |
| edges_with_any_missing_node_reference | n/a |
| edges_with_both_missing_node_references | n/a |
| strict_node_fk_ready | false |
| loose_reference_semantics_observed | n/a |
| requires_policy_decision | n/a |
| requires_cleanup | n/a |
| requires_runtime_data_run | true |

## Redigierte Finding-Klassen

Keine vollständigen Edge-, Node-, Account- oder Role-IDs in diesem Report.

| Klasse | Anzahl | Bedeutung |
| --- | --- | --- |
| typed_node_missing_reference | n/a | Typ ist node, aber ID fehlt in Nodes |
| typed_non_node_reference | n/a | Typ-Hinweis ist account oder role |
| typed_unknown_reference | n/a | Typ-Hinweis ist unbekannt |
| untyped_existing_node_reference | n/a | Typ fehlt, ID existiert aber in Nodes |
| untyped_missing_reference | n/a | Typ fehlt und ID fehlt in Nodes |
| malformed_edge | n/a | Edge ist strukturell unvollständig |
| invalid_json | n/a | JSONL-Zeile ist nicht parsebar |
| non_object_json | n/a | JSONL-Zeile ist kein Objekt |

## Entscheidungsvorlage

### Option A — Strikte Foreign Keys

Geeignet nur wenn:

- echte Runtime-Daten oder ausdrücklich entscheidungsfähige Daten geprüft wurden
- keine typisierten Nicht-Node-Referenzen existieren

- keine unbekannten Typ-Hints existieren
- keine untypisierten Referenzen offen sind

- keine missing Node references existieren
- keine malformed Edges existieren

Konsequenz:

```text
source_id REFERENCES domain_nodes(id)
target_id REFERENCES domain_nodes(id)

```

### Option B — Lose Referenzsemantik mit Guard/Quarantäne-Report

Geeignet wenn:

- Edges bewusst auf Accounts, Roles oder externe Entitäten zeigen können
- Typ-Hints heterogen sind

- historische Orphans existieren, die nicht still gelöscht werden dürfen
- untypisierte Altlasten eine direkte FK-Migration blockieren

Konsequenz:

```text
Keine direkten FKs auf `domain_nodes(id)`, sondern expliziter
Integrity-Guard oder Quarantäne-Report.

```

## Empfehlung

Status: needs_runtime_data_run

Begründung:

- Keine lokalen JSONL-Daten für Kanten und Knoten gefunden.
- Keine PostgreSQL DB verfügbar, da DATABASE_URL nicht gesetzt ist.

- Ein Runtime Data Run ist notwendig, um über Foreign Keys zu entscheiden.
