---
id: proofs.weltgewebe-os-v1-t005-two-cell-proof
title: WELTGEWEBE-OS-V1-T005 — Zwei-Zellen-Beweis
doc_type: report
status: active
created: 2026-07-20
lang: de
summary: >
  Belegt den signierten Föderationskern v1 mit zwei logisch unabhängigen Zellen,
  Trennung, kontrollierter Konvergenz, PostgreSQL-Persistenz, Browserprüfung und
  fail-closed Quarantäne ungültiger oder kollidierender Ereignisse.
depends_on:
  - docs/specs/federation-core.md
  - docs/specs/federation-wire-v1.md
relations:
  - type: verifies
    target: docs/specs/federation-core.md
  - type: verifies
    target: docs/specs/federation-wire-v1.md
  - type: relates_to
    target: docs/adr/ADR-0011__foederierte-gewebezellen.md
---

# WELTGEWEBE-OS-V1-T005 – Zwei-Zellen-Beweis

Datum: 2026-07-20
Basis: `3f4d16a3b695530cb4ffbd7184cbf5bf8e94d675` (`origin/main`)
Arbeitszweig: `feat/federation-core-two-cell-v1`

## Ergebnis

Der Föderationskern v1 ist als öffentliche, signierte HTTP-Grenze umgesetzt. Zwei logisch unabhängige Zellen können während einer Trennung lokal weiterarbeiten und danach Knoten, Kanten und einen gemeinsamen Raum kontrolliert austauschen. Ungültige Ereignisse werden nicht angewandt, sondern mit Umschlag-Digest in einer getrennten Quarantäne gesichert.

Dieser Beleg weist den Kernvertrag und den Zwei-Zellen-Pilot nach. Er behauptet noch keinen produktiv aktivierten Dauertransport zwischen realen Betreiberinstanzen.

## Für Nichtprogrammierer

Eine Zelle ist eine eigenständig betriebene Weltgewebe-Instanz. Jede Zelle unterschreibt ihre Nachrichten mit einem eigenen Schlüssel. Die andere Zelle prüft zuerst Absender, Unterschrift, Reichweite und Versionsfolge. Erst dann übernimmt sie den Inhalt. Ist etwas unklar oder manipuliert, landet die Nachricht in einem getrennten Prüfbereich und verändert keine sichtbaren Daten.

## Akzeptanzmatrix

| Kriterium | Beleg | Ergebnis |
| --- | --- | --- |
| Signatur, Version, Replay, Reichweite, Update, Löschung, Quarantäne | `apps/api/src/federation.rs`, `apps/api/tests/api_federation_two_cell.rs` | bestanden |
| Öffentliche Grenze ohne Kubernetes-, Datenbank- oder NATS-Vertrag | `scripts/ci/tests/test_federation_contract.py`, `docs/specs/federation-wire-v1.md` | bestanden |
| Zwei unabhängige Zellen tauschen Knoten, Kante und gemeinsamen Raum | `two_cells_exchange_objects_survive_partition_and_converge` | bestanden |
| Trennung, lokale Weiterarbeit, kontrollierte Konvergenz | derselbe Zwei-Zellen-Test, zwei getrennte In-Memory-Repositories und öffentliche Axum-Router | bestanden |
| Browser- und API-Nachweis | `apps/web/tests/federation-pilot.spec.ts`, API-Integrationstest | bestanden |
| PostgreSQL-Persistenz und Neustart | `apps/api/tests/db_federation_persistence.rs` in isoliertem Wegwerfcontainer | bestanden |
| Historische Schlüssel bleiben nach Rotation prüfbar | Unit-Test `historical_peer_key_remains_valid_after_rotation` | bestanden |

## Belegablauf

### 1. API-Kern und Zwei-Zellen-Pilot

Ausgeführt:

```text
cargo test -p weltgewebe-api federation --lib
cargo test -p weltgewebe-api --test api_federation_two_cell
```

Ergebnis:

```text
3 Unit-Tests bestanden
3 Zwei-Zellen-Integrationstests bestanden
0 fehlgeschlagen
```

Der Pilot simuliert:

1. Zelle A und Zelle B besitzen getrennte Zustände und Schlüssel.
2. Während einer Netztrennung schreibt A einen Knoten, eine Kante und einen gemeinsamen Raum; B schreibt einen eigenen Knoten.
3. Keine Zelle erfindet während der Trennung den Zustand der anderen.
4. Nach Wiederverbindung werden die unveränderten signierten Umschläge über `POST /federation/v1/events` zugestellt.
5. Beide Seiten können globale Objekte über `GET /federation/v1/objects` lesen.
6. Eine erneute identische Zustellung wird als harmloses Duplikat erkannt.
7. Eine zweite Trennung hält B auf Version 1, während A lokal Version 2 schreibt.
8. Nach Zustellung von Version 2 konvergiert B kontrolliert.
9. Eine ursprungsseitige Löschung erzeugt Version 3 als Tombstone; die öffentliche Objektauflösung liefert danach `404`.

Negative Fälle:

- unbekannte Schema-Version;
- lokale, nicht föderierbare Reichweite;
- manipulierte Nutzlast nach Signatur;
- korrekt signierte, aber veraltete Version;
- blockierte Nachbarzelle;
- ausdrücklich inaktiver Schlüssel;
- Event-ID-Kollision mit verändertem Umschlag;
- gleichzeitige gleiche Event-ID bei unterschiedlichen Objektadressen;
- gleichzeitige erste Versionen derselben Adresse;
- Quarantäne-Speicherverstärkung durch mehr als 120 Umschläge je Ursprungszelle und Minute;
- Ursprung-, Objektart- und Versionslücken werden im Kern abgewehrt.

### 2. Statischer Drahtvertrag

Ausgeführt:

```text
python3 -m unittest scripts.ci.tests.test_federation_contract
```

Ergebnis:

```text
7 Tests bestanden
0 fehlgeschlagen
```

Geprüft wurden geschlossene JSON-Schemas, vollständige Beispiele, die Trennung von Inbox und Quarantäne, historische Peer-Schlüssel sowie das Verbot interner Infrastrukturbegriffe im öffentlichen Föderationsmodul.

### 3. Browsernachweis

Ausgeführt:

```text
pnpm check
pnpm exec playwright test tests/federation-pilot.spec.ts --reporter=line
```

Ergebnis:

```text
svelte-check: 0 Fehler, 0 Warnungen
Playwright: 3 Tests bestanden
```

Die Browserdiagnose unter `/federation` beweist:

- gültige öffentliche Zellidentität und aktiver Ed25519-Schlüssel;
- Auflösung eines globalen gemeinsamen Raums;
- nachvollziehbarer Zustand bei deaktivierter Föderation;
- keine Anzeige eines nachbarschaftlichen oder nicht vorhandenen Objekts;
- keine Browserfunktion für Vertrauen, Schlüsselrotation oder Quarantänefreigabe.

Der Build meldete den bereits projektweiten Hinweis auf Chunks über 500 KiB. Die neue Diagnoseansicht importiert keine schweren Bibliotheken und fügt keinen eigenen großen Chunk hinzu. Der Hinweis ist daher kein T005-Blocker, bleibt aber als allgemeines Web-Performance-Thema relevant.

### 4. PostgreSQL-Persistenz

Für den Beleg wurde ein eigener loopbackgebundener Wegwerfcontainer mit PostgreSQL 16 und ohne gespeichertes Kennwort gestartet. Bestehende Beweis- und Entwicklungsdatenbanken wurden nicht verwendet.

Ausgeführt:

```text
cargo test -p weltgewebe-api --test db_federation_persistence -- --ignored --nocapture
```

Ergebnis:

```text
1 Persistenztest bestanden
0 fehlgeschlagen
```

Geprüft wurden:

- Anwendung der realen Migrationen auf eine leere Datenbank;
- persistierter Empfang eines signierten fremden Objekts;
- Rekonstruktion des Dienstes aus derselben Datenbank als Neustartbeleg;
- idempotente Duplikaterkennung nach Neustart;
- getrennte, digestgebundene Quarantäne für eine manipulierte Nachricht;
- transaktionale lokale Objekt- und Outbox-Persistenz;
- adressgebundene Serialisierung zweier gleichzeitiger Version-1-Ereignisse;
- Event-ID-gebundene Serialisierung zweier gültiger Umschläge mit unterschiedlichen Objektadressen, sodass genau einer angewandt und der andere quarantänisiert wird statt als Datenbankfehler zu entweichen;
- Widerruf eines zuvor bekannten Schlüssels über `active: false`.

Der Container wurde nach dem Readback entfernt; die zugehörige Grabowski-Lease wurde freigegeben.

## Sicherheits- und Betriebsgrenzen

### Belegt

- Öffentliche Verträge sprechen nur HTTP/JSON und Ed25519.
- Fremde Ereignisse verändern Daten erst nach lokaler Annahmeprüfung.
- `local` und `private` sind extern verboten.
- `neighbourhood` braucht explizites Ziel und lokale Erlaubnis.
- Globales Lesen liefert keine Nachbarschafts- oder Löschdaten.
- Teilkonfiguration oder fehlendes PostgreSQL führt nicht zu einem flüchtigen Ersatzbetrieb.
- Der öffentliche Empfang begrenzt Quarantäne- und Speicherverstärkung mit globalen und ursprungsgebundenen Minutenfenstern.
- Gleichzeitige Übergänge derselben Objektadresse werden in PostgreSQL serialisiert.
- Gleichzeitige Zustellungen derselben Event-ID werden vor Objektübergängen serialisiert; kollidierende Umschläge werden kontrolliert quarantänisiert.
- Ausdrücklich inaktive Schlüssel können keine neuen Zustellungen autorisieren.

### Plausibel, aber noch nicht als realer Mehrhostbetrieb belegt

- Verhalten unter langen WAN-Ausfällen und hohen Zustellmengen.
- operative Schlüsselrotation zwischen zwei tatsächlich getrennten Betreibern.
- Rate-Limits, Retry-Backoff und Dead-Letter-Betrieb eines späteren Auslieferungsworkers.

### Nicht Teil dieses Patches

- automatischer dauerhafter Peer-Auslieferungsworker;
- automatische Peer-Discovery oder Vertrauensbildung;
- föderierte Suche;
- öffentliche Quarantäneverwaltung;
- Chronik-Projektion.

## Bewertung

Nutzen: hoher architektonischer Hebel, weil die öffentliche Grenze jetzt klein, versioniert und testbar ist.
Risiko: mittel, solange die Föderation deaktiviert bleibt; höher erst bei produktiver Schlüssel- und Peer-Konfiguration.
Optimierungsgrad: Kernvertrag hoch, Transportautomatisierung bewusst nicht begonnen.
Nebenwirkung: neue öffentliche Diagnose-Route und optionale API-Routen; ohne vollständige Föderationskonfiguration bleibt das bisherige Laufzeitverhalten unverändert.

Unsicherheit: `0,13`. Ursache: Der Vertrag, Browser und PostgreSQL sind lokal reproduzierbar geprüft; ein echter Zwei-Betreiber-WAN-Pilot fehlt noch.
Interpolationsgrad: `0,08`. Ursache: Fast alle Aussagen beruhen auf ausführbaren Tests und Quellverträgen; nur die erwartete WAN-Übertragbarkeit ist abgeleitet.
