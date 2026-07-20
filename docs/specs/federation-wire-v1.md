---
id: docs.specs.federation-wire-v1
title: Föderations-Drahtvertrag v1
doc_type: specification
status: canonical
summary: "Definiert die öffentliche, signierte HTTP- und JSON-Grenze zwischen unabhängig betriebenen Weltgewebe-Zellen."
role: norm
organ: platform
canonicality: normative
lifecycle_state: active
owner: platform
review_after: 2026-10-20
last_reviewed: 2026-07-20
depends_on:
  - docs.specs.federation-core
relations:
  - type: relates_to
    target: docs/specs/federation-core.md
  - type: relates_to
    target: docs/adr/ADR-0011__foederierte-gewebezellen.md
---

# Föderations-Drahtvertrag v1

Status: implementiert und durch automatisierte Vertrags-, API-, Browser- und Persistenztests prüfbar.

Dieser Vertrag beschreibt ausschließlich die öffentliche Grenze zwischen unabhängig betriebenen Weltgewebe-Zellen. PostgreSQL, NATS, Kubernetes, interne Tabellen und Betreibergeheimnisse sind keine Bestandteile des Drahtvertrags.

## 1. Grundmodell

Jede Zelle besitzt:

- eine stabile, DNS-ähnliche `cell_id`;
- eine öffentliche HTTPS-Basisadresse;
- mindestens einen Ed25519-Schlüssel mit stabiler `key_id`;
- eine lokale Primärwahrheit für eigene Objekte;
- explizite Beziehungen und Annahmeregeln für fremde Zellen.

Globale Objektadressen sind ursprungsgebunden:

```text
wg://<cell_id>/<node|edge|shared-room>/<object_id>
```

Die Ursprungszelle bleibt alleinige Autorität für Versionen und Löschung ihres Objekts. Eine empfangende Zelle darf ein fremdes Objekt projizieren, aber weder dessen Ursprung noch dessen Art ändern.

## 2. Öffentliche Endpunkte

### `GET /federation/v1/cell`

Liefert die öffentliche Zellbeschreibung:

- Protokollversion;
- Zell-ID;
- öffentliche Basisadresse;
- aktiven Ed25519-Schlüssel;
- unterstützte Fähigkeiten.

Der öffentliche Schlüssel ist base64url ohne Padding codiert. Private Schlüssel werden niemals ausgegeben.

### `POST /federation/v1/events`

Nimmt genau ein signiertes Ereignis entgegen. Maximale Umschlaggröße: 256 KiB.

Antworten:

- `201 Created`: Signatur und Übergang sind gültig; das Ereignis wurde angewandt.
- `200 OK`: derselbe signierte Umschlag wurde bereits angewandt.
- `202 Accepted`: der Umschlag wurde nicht angewandt und getrennt quarantänisiert.
- `400 Bad Request`: der JSON-Umschlag ist syntaktisch oder strukturell nicht als Föderationsereignis lesbar.
- `413 Payload Too Large`: der Umschlag überschreitet 256 KiB.
- `415 Unsupported Media Type`: der Eingang trägt keinen unterstützten `application/json`-Content-Type.
- `429 Too Many Requests`: das feste Prozess- oder authentifizierte Peerfenster ist ausgeschöpft; `Retry-After: 60` begrenzt Quarantäne- und Speicherverstärkung.
- `500 Internal Server Error`: die lokale Persistenz konnte keinen verlässlichen Abschluss liefern.

Der Eingang erlaubt pro Minute höchstens 600 syntaktisch lesbare Umschläge je API-Prozess. Nach erfolgreicher Signaturprüfung gelten zusätzlich höchstens 120 Umschläge je authentifizierter Ursprungszelle. Frei behauptete Zell-IDs bilden keine Vertrauens- oder Rate-Limit-Identität. Ein späterer Auslieferungsworker muss zusätzlich pro Peer mit Backoff und Jitter arbeiten.

`202` bedeutet ausdrücklich nicht Zustimmung. Nur Umschläge mit verifizierter Signatur werden dauerhaft quarantänisiert. Strukturell unlesbare, unbekannte oder falsch signierte Umschläge werden mit demselben fachlichen Ergebnis verworfen, aber nicht persistiert; dadurch kann unauthentifizierter Verkehr die Quarantäne nicht füllen.

### `GET /federation/v1/objects?address=<wg-address>`

Liefert ausschließlich vorhandene, nicht gelöschte Objekte mit Reichweite `global`. Nachbarschaftliche, lokale, private oder gelöschte Objekte ergeben `404 Not Found`.

## 3. Ereignisfelder

Das JSON-Schema liegt unter `contracts/federation/v1/event.schema.json`.

Wesentliche Felder:

| Feld | Bedeutung |
| --- | --- |
| `protocol_version` | feste Drahtversion `wg-federation/1` |
| `schema_version` | Ereignisschema, aktuell `1` |
| `event_id` | globale UUID für Idempotenz und Kollisionsprüfung |
| `event_type` | `object.upserted` oder `object.deleted` |
| `origin_cell_id` | autoritative Ursprungszelle |
| `actor` | ursprungsseitige Akteurreferenz, keine lokale Berechtigung |
| `object_address` | stabile globale Adresse |
| `object_kind` | `node`, `edge` oder `shared-room` |
| `object_version` | streng monotone Version ab `1` |
| `previous_version` | vorherige Version oder `null` bei Version `1` |
| `created_at` | kanonischer RFC-3339-UTC-Zeitstempel mit `Z`; Sekundenbruchteile fehlen oder haben exakt 3, 6 oder 9 Stellen; maximal fünf Minuten in der Zukunft |
| `scope` | `global` oder `neighbourhood` |
| `neighbourhood_targets` | explizite Zielzellen bei Nachbarschaftsreichweite |
| `payload` | Objektinhalt; bei Löschung zwingend `null` |
| `key_id` | verwendeter Ursprungsschlüssel |
| `signature` | Ed25519-Signatur als base64url ohne Padding |

## 4. Signatur

Signiert werden alle Ereignisfelder außer `signature` als UTF-8-Bytes nach RFC 8785, JSON Canonicalization Scheme (JCS). Schlüssel werden rekursiv lexikografisch sortiert, es gibt keine unbedeutenden Leerzeichen, und `created_at` muss bereits in der kanonischen UTC-Schreibweise mit `Z` sowie 0, 3, 6 oder 9 Nachkommastellen vorliegen. Der Empfänger rekonstruiert exakt diese Bytes und verifiziert sie gegen den öffentlichen Schlüssel aus `(origin_cell_id, key_id)`. Fehlende Pflichtfelder und unbekannte Felder werden vor der Fachlogik als `400 Bad Request` abgewiesen.

Interoperabilitätsvektor für `contracts/federation/v1/examples/event.example.json`:

- Testschlüssel: 32 Bytes mit dem Wert `0x07` ausschließlich als öffentliche Fixture, niemals als Betreibergeheimnis;
- öffentlicher Ed25519-Schlüssel, base64url: `6kpsY-KcUgq-9VB7Ey7F-ZVHdq6-vnuSQh7qaRRG0iw`;
- SHA-256 der kanonischen Signaturbytes: `d0e9fde82180c8e1585f2a3654807853d0b84b8b5dc78ffc741366591b592fb6`;
- Signatur, base64url: `K1oizQlxat51Gqo8kd-vXpbBut7L2wq6eAqaue7d09gd7feuZ8bR1JDx7jSomACnbwjo5kS0nd0WGavP2pNHDQ`.

Folgen:

- Jede Änderung an Nutzlast, Adresse, Version, Reichweite oder Zeitstempel macht die Signatur ungültig.
- Eine aktualisierte Peer-Policy deaktiviert alle zuvor bekannten Schlüssel, die nicht erneut ausdrücklich aufgeführt werden. Verzögert zugestellte historische Ereignisse bleiben nur prüfbar, wenn der alte Schlüssel weiterhin explizit und aktiv enthalten ist.
- `active: false` bedeutet Widerruf: Neue Zustellungen mit diesem Schlüssel werden unabhängig von ihrem behaupteten Zeitstempel quarantänisiert. Ein kompromittierter Schlüssel kann Zeitstempel selbst signieren und darf daher nicht durch Rückdatierung wieder gültig werden.
- Ein unbekannter Schlüssel wird nicht automatisch aus dem Netz übernommen und erzeugt keinen persistenten Quarantäneeintrag.

## 5. Versionen, Replay und Konvergenz

Für jedes Objekt gilt:

1. Die erste beobachtete Version ist `1` und hat kein `previous_version`.
2. Jeder Folgeschritt erhöht die Version exakt um eins.
3. `previous_version` muss der aktuell gespeicherten Version entsprechen.
4. Ursprung und Objektart dürfen sich nicht ändern.
5. Derselbe `event_id` plus derselbe Umschlag ist ein harmloses Duplikat.
6. Derselbe `event_id` mit anderem Umschlag ist eine Kollision und wird quarantänisiert.
7. Veraltete, übersprungene oder anders verzweigte Versionen werden nicht angewandt.
8. Wiederholte Ablehnungen desselben signierten Umschlags erzeugen höchstens einen Quarantäneeintrag.

Damit arbeiten Zellen während einer Netztrennung mit ihrer lokalen Wahrheit weiter. Nach Wiederverbindung werden fehlende, lückenlose Ereignisse kontrolliert nachgeliefert. PostgreSQL serialisiert jeden Objektübergang zusätzlich mit einer transaktionsgebundenen Sperre aus der Objektadresse; zwei gleichzeitige erste Versionen können daher nicht beide als angewandt bestätigt werden. Die Implementierung erfindet keine Konfliktauflösung zwischen mehreren Ursprüngen, weil eine globale Adresse genau einer Ursprungszelle gehört.

## 6. Reichweiten

- `global`: darf an vertrauenswürdige Peers zugestellt und öffentlich aufgelöst werden.
- `neighbourhood`: darf nur an explizit genannte Zielzellen zugestellt werden, wenn die lokale Peer-Regel Nachbarschaftsereignisse erlaubt.
- `local` und `private`: sind niemals extern föderierbar und werden am öffentlichen Eingang ohne Persistenz verworfen.

Die Browserdiagnose unter `/federation` zeigt daher nur die öffentliche Zellbeschreibung und globale Objekte.

## 7. Quarantäne

Die Quarantäne ist eine getrennte Tabelle und kein Statuswert in der angewandten Inbox. Jeder Eintrag bindet:

- Ereignis-ID;
- behauptete Ursprungszelle;
- Ablehnungsgrund;
- SHA-256 des vollständigen Umschlags;
- unveränderten JSON-Umschlag;
- Empfangszeitpunkt.

Persistiert werden nur signaturverifizierte Ablehnungen. Typische Gründe:

- blockierte Zelle;
- ausdrücklich inaktiver Schlüssel;
- unzulässige Reichweite oder nicht adressierte Nachbarschaft;
- nicht erlaubter Ereignistyp;
- Version veraltet, lückenhaft oder kollidierend;
- Ursprung oder Objektart wechselt.

Quarantäne erzeugt keine automatische Freigabe und keine Rückschreibung. Die Kombination aus Ereignis-ID, Umschlag-Digest und Ablehnungsgrund ist eindeutig; identische Replays vergrößern die Tabelle nicht. Je Ursprungszelle werden höchstens 1.000 Einträge und nur die letzten 30 Tage aufbewahrt; Bereinigung und Einfügung laufen unter einer zellgebundenen Transaktionssperre.

## 8. Aktivierung

Ohne Föderationsvariablen startet die API unverändert ohne öffentliche Föderationsrouten. Die Aktivierung ist absichtlich vollständig oder gar nicht:

```text
FEDERATION_CELL_ID
FEDERATION_PUBLIC_BASE_URL
FEDERATION_KEY_ID
FEDERATION_SIGNING_KEY_B64
```

`FEDERATION_SIGNING_KEY_B64` muss genau 32 Bytes base64url-codiertes Ed25519-Schlüsselmaterial enthalten. Bei teilweiser Konfiguration oder fehlender PostgreSQL-Verbindung verweigert die API den Start der Föderationsgrenze; ein flüchtiger In-Memory-Fallback ist im Laufzeitpfad verboten.

Peer-Beziehungen können beim Start über `FEDERATION_PEERS_JSON` eingelesen werden. Jeder Eintrag enthält Zell-ID, Zustand `trusted` oder `blocked`, die Nachbarschaftserlaubnis, erlaubte Ereignistypen und einen oder mehrere öffentliche Schlüssel. Das JSON ist Betreiberkonfiguration, kein öffentliches Discovery-Vertrauen.

## 9. Bewusst nicht Teil von v1

Der Kern stellt Persistenz, Verträge, Prüfung und öffentliche Annahme bereit. Nicht enthalten sind:

- ein dauerhafter automatischer HTTP-Auslieferungsworker mit Retry- und Backoff-Politik;
- automatische Vertrauensbildung oder ungeprüfte Schlüsselübernahme;
- föderierte Volltextsuche;
- eine öffentliche Verwaltungs- oder Quarantänefreigabeoberfläche;
- Chronik-Projektion der Zustell- und Wirkungsbelege.

Diese Trennung reduziert das Risiko: Erst ist beweisbar, was angenommen werden darf; anschließend kann der Transport automatisiert werden, ohne die Sicherheitsgrenze neu zu erfinden.
