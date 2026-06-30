---
id: reports.domain-edge-cache-limit-design
title: "Domain Edge Cache-Limit Design — DOMAIN-PG-003"
doc_type: report
status: active
lifecycle_state: active
lifecycle: decision-prep
owner_task: DOMAIN-PG-003
review_after: 2026-09-29
created: 2026-06-29
lang: de
summary: >
  Designentscheidung zu DOMAIN-PG-003: Der aktuelle PostgreSQL-Edge-Write-Pfad
  bleibt vorerst korrektheitsorientiert. Ein Umbau der Limitprüfung wird erst
  nach Messung und unter Erhalt der Duplicate-vor-Limit-Semantik umgesetzt.
relations:
  - type: relates_to
    target: apps/api/src/domain_db.rs
  - type: relates_to
    target: apps/api/src/routes/edges.rs
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
---

# Domain Edge Cache-Limit Design — DOMAIN-PG-003

## Entscheidung

DOMAIN-PG-003 wird als Design- und Mess-Gate abgeschlossen. Es gibt in diesem Slice keine Runtime-Aenderung.

Der aktuelle PostgreSQL-Write-Pfad bleibt vorerst bestehen. Er prueft Duplicate-ID vor Cache-Limit und serialisiert die Persistenz so, dass parallele Inserts die sichtbare API-Semantik nicht unterlaufen.

## Beizubehaltende Semantik

Jeder spaetere Umbau muss diese Semantik erhalten oder ausdruecklich aendern:

- Duplicate-ID liefert weiter `409 duplicate edge id`.
- Duplicate-ID wird vor Cache-Limit entschieden.
- Cache-Limit liefert weiter `409 edge cache limit reached`.
- Race-Sicherheit bleibt erhalten.
- JSONL- und PostgreSQL-Pfade bleiben semantisch nachvollziehbar vergleichbar.

## Bewertete Optionen

| Option | Beschreibung | Vorteil | Risiko | Entscheidung |
|---|---|---|---|---|
| A — Status quo | serialisierte Pruefung plus Count und Insert | einfach, korrekt, Race-sicher | skaliert schlecht bei hoher Insert-Last | bleibt bis Messpunkt |
| B — Counter-Tabelle | eigene Zaehlertabelle mit Row-Lock | O(1)-Limitpruefung | zusaetzliche Konsistenzflaeche | nur nach Messung |
| C — Deferred Guard | Insert zuerst, periodische Korrektur | hohe Write-Performance | aendert Limit-Semantik | nicht fuer Stage A |
| D — Advisory Lock + Count | weniger harte Serialisierung | potenziell weniger Sperrwirkung | Semantik schwerer zu beweisen | nur mit Concurrency-Test |
| E — Limit entfernen | PostgreSQL ohne Cache-Limit | einfachster DB-Pfad | bricht bestehende API-Grenze | nicht ohne Produktentscheidung |

## Mess-Gate vor Umbau

Ein spaeterer Implementierungs-PR muss vor dem Umbau mindestens dokumentieren:

- erwartete Insert-Rate fuer `POST /edges`,
- gemessene Latenz des aktuellen Pfads bei repraesentativem Datenstand,
- Verhalten bei parallelen Inserts mit gleicher ID,
- Verhalten bei parallelen Inserts knapp unter oder ueber dem Limit,
- gewuenschte Semantik bei Limit-Erreichen.

## Minimaler Testumfang fuer einen spaeteren Umbau

- Duplicate-vor-Limit-Test,
- paralleler Insert-Test gegen Limitgrenze,
- eindeutige Zuordnung von DB-Fehlern zu HTTP-409-Varianten,
- Regressionstest fuer JSONL-/PostgreSQL-Paritaet der sichtbaren API-Semantik.

## Ergebnis

DOMAIN-PG-003 entscheidet nicht, dass der aktuelle Pfad dauerhaft ideal ist. Es entscheidet, dass ein Ersatz ohne Messung und ohne Semantikbeweis nicht eingefuehrt wird. Damit ist der naechste Schritt klar: messen, dann umbauen.
