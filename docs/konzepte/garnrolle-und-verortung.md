---
id: konzepte.garnrolle-und-verortung
title: "Weltgewebe – Garnrolle, Verortung und Sichtbarkeit"
doc_type: concept
status: deprecated
summary: >
  Kanonisches Konzept für Garnrolle, Verortung, öffentliche Sichtbarkeit,
  Knotenweben und Fäden im Weltgewebe.
relations:
  - type: relates_to
    target: docs/adr/ADR-0009__garnrolle-verortung-sichtbarkeit.md
  - type: relates_to
    target: docs/konzepte/garnrolle.md
  - type: supersedes
    target: docs/konzepte/garnrolle.md
---
> **Historischer Stand:** Dieses Dokument ist nicht mehr normativ. Maßgeblich ist `docs/specs/garnrolle-knoten-faden.md`.


# Weltgewebe – Garnrolle, Verortung und Sichtbarkeit

## 1. Grundsatz

Jeder Account hat genau eine Garnrolle.

Die Garnrolle ist die Rolle, von der aus ein Mensch oder Akteur im Weltgewebe
sichtbar wird, Knoten webt und Fäden zieht. Sie ist keine bloße Profilseite,
sondern die handelnde Spule des Gewebes.

Verortung und Sichtbarkeit sind Eigenschaften dieser Garnrolle. Sie sind kein
Identitätsmodus und keine zweite Accountart.

## 2. Begriffe

### Garnrolle

Eine Garnrolle ist der dauerhafte Ursprung von Handlungen im Weltgewebe.

Sie bündelt:

- Anzeigename
- Beschreibung
- Fähigkeiten
- Güter
- Interessen
- optional eine Kartenposition
- die von ihr gewobenen Knoten
- die von ihr ausgehenden Fäden

### Verortung

Verortung bedeutet: Eine Garnrolle wird an einen realen Ort gebunden.

Für Menschen ist das in der Regel der Wohnsitz. Für Gruppen oder Projekte kann
es ein anderer verantworteter Ort sein. Die Verortung ist eine bewusste Handlung
und wird in der UI als **Garnrolle auf Karte setzen** geführt.

### Sichtbarkeit

Sichtbarkeit beschreibt, wie die Garnrolle öffentlich auf der Karte erscheint.

| Sichtbarkeit | Bedeutung |
|---|---|
| Noch nicht auf der Karte | Keine öffentliche Position. |
| Exakt sichtbar | Die öffentliche Position entspricht der angegebenen Position. |
| Im Umkreis sichtbar | Die öffentliche Position wird nur ungefähr angezeigt. |

Exakte Sichtbarkeit ist ein regulärer Fall. Sie ist kein Fehler, keine Bürde und
kein Warnzustand. Im Weltgewebe ist Sichtbarkeit häufig ein Gemeingut, weil sie
Auffindbarkeit, Verantwortung und lokale Anschlussfähigkeit ermöglicht.

### Knoten

Ein Knoten ist ein Bündel im Gewebe. Er kann ein Ort, Projekt, Bedarf, Angebot,
Werkzeug, Ereignis, Commons, Gespräch oder Beschlussgegenstand sein.

Knoten können verortet sein, müssen es aber nicht immer. Eine Fairschenkbox ist
ein verorteter Knoten.

### Faden

Ein Faden ist eine Beziehung oder Handlung zwischen Garnrollen und Knoten oder
zwischen Knoten untereinander.

Fäden ersetzen in der Produktsprache Begriffe wie Kante oder Edge.

Beispiele:

- gebaut von
- betreut von
- vorgeschlagen von
- nutzt
- bietet an
- braucht
- gehört zu
- antwortet auf
- entscheidet über

Ein Faden kann kurzlebig sein. Wenn er dauerhaft tragend wird, kann daraus Garn
werden.

## 3. Nutzerfluss

Der ideale erste Fluss ist organisch:

1. Account anlegen.
2. Eigene Garnrolle sehen.
3. Garnrolle beschreiben.
4. Garnrolle auf die Karte setzen.
5. Ersten Knoten weben.
6. Faden zwischen Garnrolle und Knoten erzeugen.
7. Knoten auf der Karte und im Detailpanel sichtbar machen.

Die UI soll diesen Fluss nicht als Verwaltung von Privacy- oder
Identitätsmodi darstellen, sondern als Weben.

## 4. Beispiel: Alexander und die Fairschenkbox

Alexander wohnt am Poelsweg 2. Er setzt seine Garnrolle exakt sichtbar auf diese
Adresse.

Danach webt er den ersten Knoten:

```text
Titel: Fairschenkbox Caspar-Voght-Straße
Art: Fairschenkbox / Commons-Ort
Position: 53.55891074587864, 10.060308873653412
Status: aktiv
Beschreibung: Öffentlich zugängliche Box zum fairen Teilen brauchbarer Dinge.
```

Beim Speichern entsteht ein Gestaltungsfaden:

```text
Alexander Garnrolle -- gebaut von / betreut von --> Fairschenkbox Caspar-Voght-Straße
```

Damit wird die Box nicht als Demo-Datum von außen eingefügt. Sie entsteht aus
der Handlung einer Garnrolle heraus.

## 5. Datenmodell-Ziel

Das Zielmodell braucht keine getrennten Identitätsmodi. Eine Garnrolle hat
stattdessen optional eine Location-Struktur.

```text
garnrolle.location = null
```

oder:

```text
garnrolle.location = {
  address,
  coordinates,
  public_visibility: "exact" | "radius",
  radius_m
}
```

Alternativ kann die UI mit einem abgeleiteten Kartenzustand arbeiten:

```text
garnrolle.map_state = "not_on_map" | "exact" | "radius"
```

Die entscheidende Semantik bleibt: Eine Garnrolle ist immer dieselbe Rolle;
Kartenposition und Sichtbarkeit ändern nur, wie sie sichtbar wird.

## 6. Produktregeln

- Jeder eingeloggte Account hat eine Garnrolle.
- Eine Garnrolle kann ohne öffentliche Position existieren.
- Eine Garnrolle kann exakt sichtbar sein.
- Eine Garnrolle kann im Umkreis sichtbar sein.
- Eine exakte öffentliche Adresse ist zulässig und positiv formulierbar.
- Knoten werden aus Garnrollen heraus gewoben.
- Fäden beschreiben Beziehungen, Verantwortungen und Handlungen.
- Nutzertexte verwenden Garnrolle, Knoten, Faden, weben und Sichtbarkeit.

## 7. Nicht-Ziele

- Keine Trust-Scores.
- Keine Pflichtverifikation für den Einstieg.
- Kein Privacy-Modus als Accountart.
- Kein anonymer Alternativaccount neben der Garnrolle.
- Keine Seed-Inhalte als Ersatz für organisches Weben.
