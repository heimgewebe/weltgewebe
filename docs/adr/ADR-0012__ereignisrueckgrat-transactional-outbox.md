---
id: adr.ADR-0012__ereignisrueckgrat-transactional-outbox
title: ADR-0012 — Ereignisrückgrat mit Transactional Outbox
doc_type: reference
status: active
summary: >
  Entscheidet Transactional Outbox, versionierte Domain-Ereignisse und idempotente Konsumenten als Grundlage für Projektionen, Skalierung und Föderation.
relations:
  - type: relates_to
    target: architecture/weltgewebe-os.md
  - type: relates_to
    target: docs/reports/domain-postgres-instance-coherence-decision.md
  - type: relates_to
    target: docs/blueprints/weltgewebe-os-masterplan.md
---

# ADR-0012 — Ereignisrückgrat mit Transactional Outbox

Datum: 2026-07-15
Status: Accepted

## Kontext

Weltgewebe benötigt künftig mehrere API-Instanzen, abgeleitete Such- und Kartenprojektionen, Benachrichtigungen, Agentenworkloads und föderierte Zustellung. Direkte Best-Effort-Nachrichten nach einer Datenbankänderung können verloren gehen. Prozesslokale Caches und Zwischenzustände verhindern derzeit eine sichere horizontale Skalierung.

## Entscheidung

PostgreSQL bleibt die lokale kanonische Fachwahrheit. Jede Mutation, die andere Komponenten oder Zellen zuverlässig erfahren müssen, schreibt innerhalb derselben Transaktion:

1. den neuen Fachzustand,
2. ein versioniertes Outbox-Ereignis.

Ein getrenntes Relay veröffentlicht bestätigte Outbox-Ereignisse an NATS JetStream. Konsumenten verarbeiten mindestens einmal zugestellte Ereignisse idempotent.

## Ereignisumschlag

Ein Domain-Ereignis enthält mindestens:

- eindeutige Ereignis-ID,
- Ereignistyp,
- Schema-Version,
- Ursprungszelle,
- Akteur oder Systemursprung,
- Objekt-ID,
- Objektversion oder erwartete Vorgängerversion,
- Transaktions- oder Korrelations-ID,
- Erzeugungszeit,
- Reichweite,
- Nutzdaten oder referenzierbare Änderung,
- Deduplikations- und Aufbewahrungsinformationen.

Öffentlich föderierte Ereignisse ergänzen Signatur, Schlüsselreferenz und Protokollversion.

## Zustellungssemantik

Die Plattform verspricht keine globale Exactly-once-Zustellung. Sie verwendet:

- mindestens einmalige Zustellung,
- stabile Ereignis-IDs,
- idempotente Konsumenten,
- atomare Konsumentenfortschritte, wo erforderlich,
- Dead-Letter- oder Quarantänepfade,
- beobachtbare Wiederholungen,
- begrenzte Aufbewahrung und Replay-Verträge.

## Konsumenten

Typische Konsumenten sind:

- Cacheinvalidierung,
- Aktivitätsprojektion,
- Suche,
- Kartenprojektion,
- Benachrichtigung,
- Chronik,
- Föderationsausgang,
- Nachbarschaftsradar,
- Agenten- und Batchaufträge.

Jeder Konsument dokumentiert:

- abonnierte Ereignistypen und Versionen,
- Deduplikationsschlüssel,
- transaktionale Wirkung,
- Retry- und Quarantäneregeln,
- Replay-Verhalten,
- Daten- und Sichtbarkeitsgrenzen.

## Cachevertrag

Caches sind abgeleitete Beschleuniger, keine Primärwahrheit. Ein Cache muss:

- vollständig rekonstruierbar sein,
- eine bekannte Frische- und Invalidierungssemantik besitzen,
- bei unklarem Zustand fail-closed oder direkt gegen die Primärquelle lesen,
- Restart, verspätete Zustellung und Replay vertragen.

## Reihenfolge der Einführung

1. Inventar aller prozesslokalen autoritativen Zustände,
2. Persistenz aller Auth-Zwischenzustände,
3. Outbox-Schema und Relay,
4. versionierter Ereignisvertrag,
5. erster idempotenter Konsument,
6. Multi-API-Kohärenztest,
7. schrittweise Projektionen,
8. spätere Föderationszustellung.

## Nicht-Ziele dieses Beschlusses

- keine sofortige Event-Sourcing-Umstellung aller Fachobjekte,
- keine globale Ereignisreihenfolge,
- keine Entfernung relationaler Primärmodelle,
- keine öffentliche Föderation vor Protokoll- und Sicherheitsbeweisen,
- keine Produktionsreplikation allein aufgrund vorhandener NATS-Infrastruktur; erforderlich bleiben Outbox-, Idempotenz- und Zwei-Instanz-Beweise.

## Alternativen

### Direkte Veröffentlichung nach Commit

Verworfen, weil ein Prozessabsturz zwischen Commit und Veröffentlichung ein dauerhaft fehlendes Ereignis erzeugen kann.

### Dual Write in Datenbank und Broker

Verworfen ohne verteilte Transaktion. Es erzeugt zwei nicht atomare Wahrheiten.

### Vollständiges Event Sourcing ab sofort

Verworfen. Der zusätzliche Modell- und Migrationsaufwand ist nicht durch aktuelle Anforderungen belegt.

## Konsequenzen

- Ereignisse werden zu versionierten Verträgen,
- Mutationen müssen ihre projektionsrelevanten Wirkungen benennen,
- NATS-Verfügbarkeit ist nicht Teil der fachlichen Datenbanktransaktion,
- Backpressure und Relay-Rückstand werden messbar,
- horizontale Skalierung und Föderation erhalten eine gemeinsame Grundlage,
- Datenschutz- und Reichweitenregeln müssen bis in Ereignisse und Konsumenten fortgeführt werden.

## Akzeptanzkriterien für den ersten Implementierungsschnitt

- Outboxzeile und Fachmutation sind atomar,
- Relay kann nach Absturz fortsetzen,
- doppelte Veröffentlichung erzeugt keine doppelte Fachwirkung,
- unveröffentlichte und fehlgeschlagene Ereignisse sind beobachtbar,
- mindestens zwei API-Instanzen sehen nach einer Mutation konsistent denselben Zustand,
- Der vollständige Kohärenzbeweis ersetzt den Single-Instance-Guard durch einen stärkeren Multi-Instance-Guard.
