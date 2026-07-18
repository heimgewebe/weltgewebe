---
id: specs.privacy-api
title: Garnrollen-Sichtbarkeit API
doc_type: reference
status: active
summary: API-Zielbild für Verortung und öffentliche Sichtbarkeit einer Garnrolle.
relations:
  - type: relates_to
    target: docs/specs/garnrolle-knoten-faden.md
  - type: relates_to
    target: docs/adr/ADR-0009__garnrolle-verortung-sichtbarkeit.md
---

# Garnrollen-Sichtbarkeit API

Diese Spezifikation beschreibt das Zielbild für die API rund um Verortung und
öffentliche Sichtbarkeit einer Garnrolle.

Der Pfadname bleibt vorerst aus Kompatibilitätsgründen bestehen. Fachlich geht
es nicht um einen Privacy-Modus, sondern um eine klare Sichtbarkeitsentscheidung
für eine Garnrolle.

## Zielzustand

Ein Account hat genau eine Garnrolle. Diese Garnrolle kann ohne öffentliche
Position existieren oder auf die Karte gesetzt werden.

Zielstruktur:

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

## Öffentliche Projektion

Die öffentliche Ansicht darf nur die gewählte Sichtbarkeit zeigen:

| Sichtbarkeit | Öffentliche Projektion |
|---|---|
| keine Position | keine `public_pos` |
| exakt sichtbar | `public_pos = coordinates` |
| im Umkreis sichtbar | `public_pos` aus Radius-Projektion |

Die interne Adresse und die exakten Koordinaten bleiben getrennt von der
öffentlichen Projektion, sofern nicht exakt sichtbare Anzeige gewählt wurde.

Für `radius` erzeugt der Server einmalig einen kryptografisch zufälligen Punkt
innerhalb eines echten geodätischen Kreises von 50 bis 5.000 Metern. Die dazu
gehörige Bindung wird ausschließlich privat persistiert. Sie bleibt bei
unverändertem Ort und Radius auch nach zeitweisem Ausblenden stabil, damit kein
neuer Punkt eine Schnittmengenattacke ermöglicht. Erst eine Änderung des
privaten Orts oder Radius erzeugt eine neue Bindung. Fehlt eine gültige Bindung,
wird die Garnrolle ohne öffentliche Position als `not_on_map` behandelt.

## Zielendpunkte

Die endgültigen Namen sind noch offen. Semantisch braucht das System:

```text
GET /me/garnrolle
PUT /me/garnrolle/profile
PUT /me/garnrolle/location
DELETE /me/garnrolle/location
```

`PUT /me/garnrolle/location` setzt die Garnrolle auf die Karte oder ändert ihre
Sichtbarkeit.

Beispiel exakt sichtbar:

```json
{
  "address": "Poelsweg 2, Hamburg",
  "coordinates": { "lat": 53.558..., "lon": 10.060... },
  "public_visibility": "exact"
}
```

Beispiel im Umkreis sichtbar:

```json
{
  "address": "Poelsweg 2, Hamburg",
  "coordinates": { "lat": 53.558..., "lon": 10.060... },
  "public_visibility": "radius",
  "radius_m": 250
}
```

## Übergangsnotiz

Bestehende technische Felder in API, Datenbank oder Fixtures dürfen bis zur
Migration weiter gelesen werden. Neue Zielsemantik darf daraus aber keine
zweite Accountart ableiten. Sie projiziert die Daten in eine Garnrolle mit
Sichtbarkeitszustand.
