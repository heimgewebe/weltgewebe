---
id: docs.blueprints.domain-scale-foundation
title: Domain Scale Foundation
doc_type: blueprint
status: active
canonicality: planning
summary: Reproduzierbarer PostgreSQL-Prüfstand für große Weltgewebe-Graphen und belegbare Abfragebudgets.
owner: architecture
organ: architecture
role: plan
lifecycle_state: active
relations:
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/datenmodell.md
verifies_with:
  - scripts/tests/test_domain_scale.py
depends_on:
  - apps/api/migrations/20260531000001_create_domain_nodes.up.sql
  - apps/api/migrations/20260531000002_create_domain_edges.up.sql
---

# Domain Scale Foundation

## Zweck

Weltgewebe soll perspektivisch einen großen Graphen mit vielen gleichzeitigen
Lese- und Schreibvorgängen tragen. Vor Änderungen am Laufzeit-Datenpfad braucht
das Projekt deshalb einen reproduzierbaren Prüfstand.

Der Prüfstand beantwortet drei Fragen:

1. Wie verhalten sich die aktuellen PostgreSQL-Tabellen bei großen Datenmengen?
2. Welche Abfragen verwenden Indizes und welche fallen auf vollständige
   Tabellendurchläufe zurück?
3. Verbessert eine spätere Änderung den belegten Zustand oder verschiebt sie
   nur Kosten an eine andere Stelle?

## Begriffe

**Lastprofil** bezeichnet eine festgelegte Datenmenge. Das kleinste Profil
prüft den Mechanismus schnell in CI. Die größeren Profile sind für einen
leistungsfähigen Testrechner oder eine produktionsnahe Datenbank bestimmt.

**Abfrageplan** ist PostgreSQLs Ausführungsweg für eine SQL-Abfrage. Ein
`Index Scan` entspricht grob dem Nachschlagen in einem Register. Ein
`Seq Scan` liest dagegen eine Tabelle vollständig. Ein vollständiger Durchlauf
ist bei kleinen Tabellen oft korrekt, kann bei Millionen Datensätzen aber zum
Engpass werden.

**Kalibrierung** bedeutet, Zeitgrenzen erst auf einer festgelegten Hardware und
mit wiederholten Messungen zu bestimmen. Dieser erste Schnitt erfindet deshalb
keine allgemeingültigen Millisekunden-Budgets.

## Profile

| Profil | Knoten | Fäden | Zweck |
|---|---:|---:|---|
| `smoke` | 1.000 | 5.000 | schneller Funktionsnachweis |
| `ci` | 20.000 | 100.000 | regelmäßiger Integrationslauf |
| `scale_100k` | 100.000 | 500.000 | mittlere Lastmessung |
| `scale_1m` | 1.000.000 | 5.000.000 | produktionsnahe Skalierungsprüfung |

Die Werte liegen in
`configs/performance/domain-scale.v1.json`. Änderungen an Profilen oder
Budgets sind damit überprüfbare Vertragsänderungen und keine versteckten
Skriptparameter.

## Sicherheitsgrenze

Der Loader arbeitet ausschließlich im fest reservierten Schema
`weltgewebe_perf`. Andere Namen – auch weitere scheinbare Testschemas – werden
abgewiesen. Dadurch können weder `public` noch PostgreSQL-Systemschemas als
Löschziel eingeschleust werden.

Er darf:

- dieses Benchmark-Schema verwerfen und neu anlegen,
- die Strukturen der öffentlichen Domänentabellen mit `LIKE ... INCLUDING ALL`
  übernehmen,
- generierte CSV-Dateien dort laden,
- Statistiken mit `ANALYZE` aktualisieren.

Schema-Neuanlage, beide CSV-Importe, Statistikaufbau und Zeilenzählung liegen
in einer Transaktion. Schlägt ein Schritt fehl, stellt PostgreSQL den vorherigen
Benchmark-Zustand wieder her, statt ein halbfertiges Schema zurückzulassen.

Er darf nicht:

- `public.domain_nodes` oder `public.domain_edges` leeren,
- Produktionsdaten überschreiben,
- das Schema `public` verwerfen,
- den Testdatensatz ohne Hashprüfung verwenden.

Die Unit-Tests prüfen diese Grenze statisch. PostgreSQL-Berechtigungen bleiben
die zweite Schutzschicht: Ein Benchmark-Benutzer sollte keine Rechte zum
Verwerfen produktiver Tabellen besitzen.

## Determinismus

Jeder Knoten und jeder Faden wird aus folgenden Eingaben abgeleitet:

- festem Seed,
- Profilname,
- Datensatznummer,
- Feldrolle.

Die Ableitung erfolgt über SHA-256. Dadurch sind Reihenfolge, Koordinaten,
Knotenarten und Beziehungen wiederholbar. Die ersten Fäden bilden zusätzlich
einen geschlossenen Ring über alle Knoten. Somit besitzt jeder Knoten garantiert
mindestens eine eingehende und eine ausgehende Verbindung; Nachbarschaftsmessungen
laufen nicht versehentlich gegen einen leeren Fall. Das Manifest enthält
SHA-256-Werte für beide CSV-Dateien. Eine nachträgliche Veränderung wird vor dem
Rendern der SQL-Dateien abgewiesen.

## Gemessene Abfragen

Der erste Kanon umfasst:

- Knoten-Cursor,
- Faden-Cursor,
- geografischen Ausschnitt,
- ausgehende Nachbarschaft,
- eingehende Nachbarschaft,
- Filter nach Knotenart.

Jede Abfrage wird mit
`EXPLAIN (ANALYZE, BUFFERS, WAL, FORMAT JSON)` ausgeführt. PostgreSQL liefert
damit neben dem gewählten Weg auch Pufferzugriffe, temporäre Blöcke,
Schreibaufwand und Zeitwerte in maschinenlesbarer Form.

## Erste Budgets

Der Prüfer blockiert zunächst nur eindeutig schädliche Planformen:

- kein `Seq Scan` für die kanonischen großen Listen- und Suchabfragen,
- kein zusätzlicher `Sort` für die ID-Cursor,
- keine temporären Blöcke.

Die harten Planbudgets gelten nur für `scale_100k` und `scale_1m`. Bei den
kleinen Profilen darf PostgreSQL einen vollständigen Tabellendurchlauf wählen,
falls dieser tatsächlich günstiger ist; dort werden die Pläne nur beobachtet.

Zeitgrenzen bleiben ausdrücklich unkalibriert. Eine allgemeine Grenze ohne
festgelegte Hardware, PostgreSQL-Konfiguration, Warm-up und Wiederholungszahl
wäre Scheingenauigkeit.

## Ausführung

Konfiguration prüfen:

```bash
python3 -B scripts/performance/domain_scale.py validate
```

Deterministische Daten erzeugen:

```bash
python3 -B scripts/performance/domain_scale.py generate \
  --profile smoke \
  --output-dir /tmp/weltgewebe-domain-scale
```

SQL zum sicheren Laden rendern:

```bash
python3 -B scripts/performance/domain_scale.py render-load \
  --manifest /tmp/weltgewebe-domain-scale/manifest.json \
  --output /tmp/weltgewebe-domain-scale/load.sql
```

Messabfragen rendern:

```bash
python3 -B scripts/performance/domain_scale.py render-workload \
  --manifest /tmp/weltgewebe-domain-scale/manifest.json \
  --plan-dir /tmp/weltgewebe-domain-scale/plans \
  --output /tmp/weltgewebe-domain-scale/workload.sql
```

Die beiden SQL-Dateien werden anschließend mit `psql` gegen eine ausdrücklich
bestimmte Benchmark-Datenbank ausgeführt. Danach prüft der folgende Befehl die
JSON-Abfragepläne:

```bash
python3 -B scripts/performance/domain_scale.py check \
  --manifest /tmp/weltgewebe-domain-scale/manifest.json \
  --plan-dir /tmp/weltgewebe-domain-scale/plans \
  --report /tmp/weltgewebe-domain-scale/report.json
```

## Folgeschnitte

Dieser Prüfstand verändert den API-Datenpfad noch nicht. Die nächsten
Laufzeitschritte müssen auf seinen Messungen aufbauen:

1. vollständiges Vorladen aller Knoten entfernen,
2. Kartenabfragen räumlich und begrenzt aus PostgreSQL lesen,
3. Listen per Cursor paginieren,
4. Nachbarschaften begrenzt laden,
5. Speicher-, Verbindungs- und Überlastbudgets messen,
6. erst danach PostGIS oder zusätzliche Indizes einführen.

Die Trennung verhindert, dass eine vermeintliche Optimierung gleichzeitig
Messgrundlage und untersuchten Datenpfad verändert.
