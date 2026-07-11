---
id: adr.ADR-0009__garnrolle-verortung-sichtbarkeit
title: ADR-0009 — Garnrolle, Verortung und Sichtbarkeit
doc_type: reference
status: active
summary: >
  Entscheidung zum Zielmodell: Jeder Account hat eine Garnrolle; Verortung und
  Sichtbarkeit sind Eigenschaften dieser Garnrolle, keine getrennten
  Identitätsmodi.
relations:
  - type: supersedes
    target: docs/adr/ADR-0003__privacy-ungenauigkeitsradius-ron.md
  - type: relates_to
    target: docs/specs/garnrolle-knoten-faden.md
  - type: relates_to
    target: docs/specs/privacy-api.md
  - type: relates_to
    target: docs/specs/ui-interaction.md
---

# ADR-0009 — Garnrolle, Verortung und Sichtbarkeit

Datum: 2026-07-09
Status: Accepted

## Entscheidung

Weltgewebe verwendet künftig ein einziges Accountmodell:

> Jeder Account hat genau eine Garnrolle.

Die Garnrolle ist die sichtbare und handelnde Rolle eines Menschen oder Akteurs
im Gewebe. Sie ist der Ursprung von Fäden und kann Knoten weben.

Verortung und öffentliche Sichtbarkeit sind Eigenschaften dieser Garnrolle. Sie
sind kein Identitätsmodus und keine zweite Art von Account.

## Zielmodell

Eine Garnrolle hat einen Profilkern und optional eine Kartenposition.

```text
Garnrolle
├─ Profil
│  ├─ Anzeigename
│  ├─ Beschreibung
│  ├─ Fähigkeiten
│  ├─ Güter
│  └─ Interessen
└─ Kartenposition
   ├─ keine öffentliche Position
   └─ öffentliche Position
      ├─ exakt sichtbar
      └─ im Umkreis sichtbar
```

Die zentrale Nutzerhandlung lautet:

> Garnrolle auf die Karte setzen.

Nicht:

> Identitätsmodus wechseln.

## Sichtbarkeit

Sichtbarkeit ist im Weltgewebe ein positiver Wert. Ein genauer öffentlicher Ort
ist kein Fehlerfall, sondern kann selbst ein Gemeingut sein: Menschen,
Initiativen und Orte werden auffindbar, ansprechbar und anschlussfähig.

Die Nutzerführung kennt drei einfache Zustände:

| Zustand | Bedeutung |
|---|---|
| Noch nicht auf der Karte | Die Garnrolle hat keine öffentliche Kartenposition. |
| Exakt sichtbar | Die angegebene Position wird öffentlich exakt angezeigt. |
| Im Umkreis sichtbar | Die Garnrolle wird öffentlich nur ungefähr angezeigt. |

Die exakte Sichtbarkeit ist der einfache Fall. Die ungefähre Sichtbarkeit ist
eine bewusste Option, nicht der normative Default.

## Knoten und Fäden

Eine Garnrolle webt Knoten.

Ein Knoten ist ein verortetes oder thematisch fassbares Bündel im Gewebe: Ort,
Projekt, Bedarf, Angebot, Werkzeug, Ereignis, Gruppe oder Commons.

Beim Weben eines Knotens entsteht mindestens ein Faden. Ein Faden beschreibt,
was zwischen Garnrolle und Knoten gilt, zum Beispiel:

- gebaut von
- betreut von
- vorgeschlagen von
- nutzt
- braucht
- bietet an
- gehört zu

Die Nutzerführung sagt **Faden** und **Fadenart**. Technische Implementierungen
dürfen intern weiter `edge` oder `edge_kind` verwenden, solange die Produkt- und
Dokumentationssprache konsistent bleibt.

## Beispiel: erstes organisches Weben

1. Alexander legt seinen Account an.
2. Seine Garnrolle entsteht.
3. Er ergänzt Profilinformationen.
4. Er setzt seine Garnrolle exakt sichtbar auf den Poelsweg 2.
5. Er webt den Knoten "Fairschenkbox Caspar-Voght-Straße" an der exakten
   Position der Box.
6. Das System erzeugt einen Gestaltungsfaden:
   "Alexander hat die Fairschenkbox gebaut / betreut sie".

Damit entsteht kein Demo-Datensatz von außen, sondern der erste echte
Weltgewebe-Akt aus einer Garnrolle heraus.

## API-Zielrichtung

Das Zielmodell sollte künftig durch klare Felder ausgedrückt werden:

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

Alternativ ist ein expliziter Kartenzustand möglich:

```text
garnrolle.map_state = "not_on_map" | "exact" | "radius"
```

Die konkrete Migration ist nicht Bestandteil dieser ADR. Wichtig ist die
semantische Richtung: keine separaten Identitätsmodi für dasselbe Nutzerkonto.

## Konsequenzen

- Onboarding beginnt mit "Deine Garnrolle".
- Die erste große Handlung ist "Garnrolle auf Karte setzen".
- Sichtbarkeit wird als positive, verständliche Auswahl geführt.
- Die exakte Adresse ist ein regulärer Fall.
- Das erste echte Produktziel ist organisches Weben aus der eigenen Garnrolle.
- UI, Konzepte und Roadmaps verwenden **Fäden** statt **Kanten/Edges**.
- Alte technische Begriffe bleiben nur als Migrations- oder Implementierungsdetail zulässig.

## Nicht-Ziele

- Kein Trust-Score.
- Keine Pflichtverifikation als Einstiegshürde.
- Kein anonymer Alternativaccount neben der Garnrolle.
- Kein Privacy-Modus als Ersatz für klare Sichtbarkeit.
- Keine seedartige Inhaltseinspielung als Ersatz für organisches Weben.

## Abgelöste Entscheidung

Diese ADR löst ADR-0003 als Zielmodell ab. ADR-0003 bleibt nur als historischer
Migrationskontext erhalten. Neue Produkt- und Konzeptarbeit folgt dieser ADR.
