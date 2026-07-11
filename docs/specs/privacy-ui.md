---
id: specs.privacy-ui
title: Garnrollen-Sichtbarkeit UI
doc_type: reference
status: deprecated
summary: UI-Zielbild für Profil, Verortung und öffentliche Sichtbarkeit der eigenen Garnrolle.
relations:
  - type: relates_to
    target: docs/specs/privacy-api.md
  - type: relates_to
    target: docs/konzepte/garnrolle-und-verortung.md
  - type: relates_to
    target: docs/adr/ADR-0009__garnrolle-verortung-sichtbarkeit.md
---
> **Historischer Stand:** Dieses Dokument ist nicht mehr normativ. Maßgeblich ist `docs/specs/garnrolle-knoten-faden.md`.


# Garnrollen-Sichtbarkeit UI

Diese UI-Spezifikation ersetzt die frühere Privacy-Modus-Sprache durch eine
Garnrollen-Handlung:

> Garnrolle auf die Karte setzen.

## Start nach Login

Nach dem Login sieht der Nutzer seine Garnrolle.

Empfohlener Text:

```text
Deine Garnrolle ist angelegt.
Sie steht noch nicht auf der Karte.
```

Primäre Aktionen:

- Garnrolle beschreiben
- Garnrolle auf Karte setzen
- später: ersten Knoten weben

## Garnrolle beschreiben

Felder:

- Anzeigename
- Kurzbeschreibung
- Fähigkeiten
- Güter
- Interessen
- Tags

Die Beschreibung ist zuerst ein Profilakt, keine Kartenentscheidung.

## Garnrolle auf Karte setzen

Die UI fragt nach:

- Adresse
- Koordinate oder Adressauflösung
- Sichtbarkeit

Sichtbarkeitsauswahl:

```text
[ ] Noch nicht auf der Karte
[x] Exakt sichtbar
[ ] Im Umkreis sichtbar
```

Nur bei "Im Umkreis sichtbar" wird ein Radiusfeld angezeigt.

## Exakte Sichtbarkeit

Exakte Sichtbarkeit ist positiv zu formulieren:

```text
Deine Garnrolle wird an dieser Adresse sichtbar. Menschen in der Nähe können
sehen, wo du im Gewebe ansprechbar bist.
```

Nicht als Warntext formulieren.

## Nicht erlaubt

- Identitätsmodus-Auswahl im Onboarding
- Privacy-Toggle als Accountart
- technische Feldnamen in der Haupt-UI
- Standardwarnung gegen exakte Sichtbarkeit
- Kanten- oder Edge-Sprache in Nutzertexten

## Nächster Schritt

Nach einer gesetzten Garnrolle wird der erste produktive Call-to-Action:

```text
Ersten Knoten weben
```
