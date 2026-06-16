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

Dieser PR beweist das Audit-Harness und hat die PostgreSQL-Runtime-Datenlage evaluiert.
Da die Prüfung gegen die Runtime-DB erfolgreich durchgeführt wurde und `strict_node_fk_ready` auf `true` steht, ist die FK-Einführung aus Datensicht nicht mehr blockiert.

- Keine Foreign-Key-Migration in diesem PR.
- Kein Runtime-Cutover-Claim in diesem Dokument (wird im Cutover-Blueprint geregelt).
- Die Datenlage erlaubt die Einführung strikter Foreign Keys.

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

Befehl:

```bash
python3 scripts/docmeta/audit_domain_edge_references.py --postgres --source-kind runtime
```

Ergebnis:

Die Runtime-Daten zeigten keine verletzenden Referenzen (die Datenbank-Instanz enthielt 0 Knoten/Kanten), womit `strict_node_fk_ready: true` erfüllt ist.

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
| nodes_empty_id | n/a |
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
| type_hint_backfill_recommended | n/a |
| fk_compatible_reference_sides | n/a |
| strict_node_fk_ready | false |
| loose_reference_semantics_observed | n/a |
| requires_policy_decision | n/a |
| requires_cleanup | n/a |
| requires_runtime_data_run | true |

## PostgreSQL-Ergebnis

| Metrik | Wert |
| --- | ---: |
| executed | yes |
| source_kind | runtime |
| node_records_total | 0 |
| node_ids_total | 0 |
| node_invalid_json_records | 0 |
| node_non_object_json_records | 0 |
| nodes_missing_id | 0 |
| nodes_non_string_id | 0 |
| nodes_empty_id | 0 |
| node_duplicate_ids | 0 |
| edge_records_total | 0 |
| auditable_edges_total | 0 |
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
| type_hint_backfill_recommended | false |
| fk_compatible_reference_sides | 0 |
| strict_node_fk_ready | true |
| loose_reference_semantics_observed | false |
| requires_policy_decision | false |
| requires_cleanup | false |
| requires_runtime_data_run | false |

## Redigierte Finding-Klassen

Keine vollständigen Edge-, Node-, Account- oder Role-IDs in diesem Report.

Ungetypte, aber auflösbare Node-Referenzen erscheinen nicht als Finding.
Sie werden nur über `untyped_existing_node_references` und
`type_hint_backfill_recommended` ausgewiesen.

| Klasse | Anzahl | Bedeutung |
| --- | --- | --- |
| typed_node_missing_reference | n/a | Typ ist node, aber ID fehlt in Nodes |
| typed_non_node_reference | n/a | Typ-Hinweis ist account oder role |
| typed_unknown_reference | n/a | Typ-Hinweis ist unbekannt |
| untyped_missing_reference | n/a | Typ fehlt und ID fehlt in Nodes |
| malformed_edge | n/a | Edge ist strukturell unvollständig |
| invalid_json | n/a | JSONL-Zeile ist nicht parsebar |
| non_object_json | n/a | JSONL-Zeile ist kein Objekt |

## Entscheidungsvorlage

Ungetypte, aber vollständig auflösbare Node-Referenzen blockieren direkte
Foreign Keys nicht. Sie markieren nur einen möglichen Type-Hint-Backfill.

### Option A — Strikte Foreign Keys

Geeignet nur wenn:

- echte Runtime-Daten oder ausdrücklich entscheidungsfähige Daten geprüft wurden
- keine typisierten Nicht-Node-Referenzen existieren
- keine unbekannten Typ-Hints existieren
- keine fehlenden Node-Referenzen existieren
- nur node-getypte oder ungetypte, aber auflösbare Node-Referenzen vorkommen
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
- untypisierte fehlende oder nicht eindeutig auflösbare Altlasten eine direkte FK-Migration blockieren

Konsequenz:

Keine direkten FKs auf `domain_nodes(id)`, sondern expliziter
Integrity-Guard oder Quarantäne-Report.

## Empfehlung

Status: ready

Der Runtime-Datenlauf wurde erfolgreich gegen die PostgreSQL-Datenbank durchgeführt.

Begründung:

- Die Auswertung zeigt keine fehlenden oder fehlerhaften Referenzen (Datenbank war zum Zeitpunkt des Audits leer oder konsistent).
- `strict_node_fk_ready` ist `true`, was die Einführung strikter Foreign Keys (`Option A`) blockierungsfrei erlaubt.
