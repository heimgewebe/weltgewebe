---
id: specs.garnrolle-knoten-faden
title: Garnrolle, Knoten und Faden
summary: Kanonischer Produktvertrag für Account, Verortung, organisches Weben und Beziehungen im Gewebe.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-domain
owner: product-domain
last_reviewed: 2026-07-13
review_after: 2026-10-11
depends_on: []
relations:
  - type: supersedes
    target: docs/konzepte/garnrolle-und-verortung.md
  - type: supersedes
    target: docs/specs/privacy-ui.md
  - type: relates_to
    target: docs/adr/ADR-0009__garnrolle-verortung-sichtbarkeit.md
  - type: relates_to
    target: docs/domain/vocabulary.md
verifies_with:
  - contracts/domain/account.schema.json
  - contracts/domain/node.schema.json
  - contracts/domain/edge.schema.json
  - apps/web/tests/garnrolle-self-service.spec.ts
  - apps/web/tests/komposition.spec.ts
---
# Garnrolle, Knoten und Faden

## Grundmodell

Jeder Account besitzt genau eine Garnrolle. Die Garnrolle ist der dauerhafte Ausgangspunkt, von dem aus ein Mensch oder Akteur im Weltgewebe sichtbar wird und handelt. Sie ist weder ein Privacy-Modus noch eine zweite Accountart.

| Produktbegriff | technischer Begriff | Bedeutung |
|---|---|---|
| Garnrolle | Account | persönlicher oder verantworteter Ausgangspunkt |
| Knoten | Node | Ort, Commons, Ressource, Vorhaben, Bedarf oder Angebot |
| Faden | Edge | typisierte Beziehung oder Handlung |
| Gesprächsraum | Conversation | eigener Diskussions- oder Entscheidungsraum |
| Beitrag | Message | Inhalt eines Gesprächsraums |

`thread` ist als technischer Sammelbegriff verboten. Eine Graphbeziehung ist ein `edge`, ein Gesprächsraum eine `conversation`.

## Garnrolle

Die Garnrolle kann enthalten:

- Anzeigename und Kurzbeschreibung;
- Fähigkeiten, Güter, Interessen und Tags;
- optional eine interne reale Position;
- optional eine öffentliche Kartenprojektion;
- geknüpfte Knoten und ausgehende Fäden.

Eine Berechtigungsrolle wie `gast`, `weber` oder `admin` regelt technische Rechte. Sie ist nicht die Identität der Person.

## Verortung und Sichtbarkeit

Die Nutzerhandlung lautet:

> Garnrolle auf die Karte setzen

Die öffentliche Darstellung kennt genau drei Zustände:

| Nutzertext | API-Wert | Wirkung |
|---|---|---|
| Noch nicht auf der Karte | `not_on_map` | keine öffentliche Position |
| Exakt sichtbar | `exact` | öffentliche Position entspricht der gewählten Position |
| Im Umkreis sichtbar | `radius` | öffentliche Position wird angenähert dargestellt |

Regeln:

1. Eine Garnrolle kann ohne öffentliche Position bestehen.
2. Exakte Sichtbarkeit ist ein regulärer, positiv formulierter Fall.
3. Nur `radius` verlangt ein Radiusfeld.
4. `not_on_map` darf auch bei intern vorhandener Position keine öffentliche Koordinate ausgeben.
5. Alte RoN- und `mode`-Felder sind nur Migrationskontext und keine Produktsprache.

## Knoten

Ein Knoten ist ein fachlich fassbares Bündel. Er kann verortet oder ortsunabhängig sein. Beispiele:

- Commons-Ort;
- Projekt oder Initiative;
- Werkzeug oder Ressource;
- Angebot oder Bedarf;
- Veranstaltung;
- Idee, Frage oder Beschlussgegenstand.

Knoten werden aus einer angemeldeten Garnrolle heraus geknüpft. Seed- oder Demo-Inhalte dürfen den organischen Produktpfad nicht ersetzen.

## Fäden

Ein Faden beschreibt eine Beziehung oder Handlung. Zulässige Endpunkte ergeben sich aus dem Domain-Contract und können Garnrollen oder Knoten sein.

Wichtige Klarstellung:

- Nutzerhandlungen beginnen in der Regel bei einer Garnrolle.
- Das fachliche Graphmodell darf zusätzlich Beziehungen zwischen Knoten ausdrücken.
- Die ältere Behauptung, Knoten könnten grundsätzlich keine ausgehenden Fäden besitzen, gilt nicht mehr.

Beispiele:

- gebaut von;
- betreut von;
- vorgeschlagen von;
- nutzt;
- bietet an;
- braucht;
- gehört zu;
- antwortet auf.

Ein Faden ist nicht automatisch ein Gespräch. Gespräche besitzen eigene Entitäten.

### Autorisierung, Richtung und öffentliche Notizen

1. Eine reguläre Weberhandlung, die eine Garnrolle beteiligt, muss von der eigenen angemeldeten Garnrolle ausgehen. Ein Weber darf weder eine fremde Garnrolle als Quelle ausgeben noch über `Knoten → fremde Garnrolle` eine fremde Aktivität erzeugen. Die deklarierten Endpunkttypen müssen mit bereits bekannten Entitäten übereinstimmen; eine Garnrollen-ID darf nicht als Knoten-ID ausgegeben werden.
2. Administrative Reparaturen und kontrollierte Importe dürfen eingehende Fäden erzeugen. In der betroffenen Garnrolle werden sie neutral als eingehende Verknüpfung beschrieben, nicht als eigene Handlung.
3. Eine optionale Fadennotiz ist gespeicherte Freitext-Metadaten des Schreibvorgangs. Öffentliche Fadenlisten, Fadendetails und Garnrollenprojektionen geben sie nicht aus. Die authentifizierte Erstellungsantwort darf die gerade übermittelte Notiz zur unmittelbaren Bestätigung zurückgeben.

## Erster organischer Produktfluss

1. Account anmelden oder anlegen.
2. Eigene Garnrolle sehen.
3. Garnrolle beschreiben.
4. Garnrolle optional auf die Karte setzen.
5. Ersten Knoten knüpfen.
6. Beim Speichern einen passenden Faden erzeugen.
7. Knoten und Faden nach Neuladen wiederfinden.

Dieser vertikale Schnitt ist der wichtigste Integrationsbeweis. Er muss ohne Demo-Fallback und mit eindeutigem Persistenzpfad funktionieren.

## Produktsprache

Nutzertexte verwenden Garnrolle, Knoten, Faden, knüpfen, weben, Sichtbarkeit und Gesprächsraum. Interne Begriffe wie Account, Node, Edge, Credential, Token oder WebAuthn erscheinen nicht in der Hauptführung.

## Nicht-Ziele

- kein Trust-Score;
- keine Pflichtverifikation als Einstiegshürde;
- kein anonymer Alternativaccount neben der Garnrolle;
- kein Privacy-Modus als Accountart;
- keine künstliche Währung;
- kein Demo-Datensatz als Ersatz für echte Webhandlungen.
