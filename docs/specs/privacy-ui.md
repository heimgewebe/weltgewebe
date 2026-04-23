---
id: specs.privacy-ui
title: Privacy UI
doc_type: reference
status: active
summary: UI-Spezifikation für datenschutzrelevante Oberflächen und Interaktionen.
relations:
  - type: relates_to
    target: docs/specs/privacy-api.md
  - type: relates_to
    target: docs/konzepte/garnrolle-und-verortung.md
---
# Privacy UI (ADR-0003)

Slider (r Meter) für verortete Garnrollen.

## Startzustand

Beim ersten Einstieg (Onboarding neuer Accounts) befindet sich der Nutzer im RoN-Startmodus.

Die UI muss sichtbar machen:

- aktuellen Zustand (RoN)
- Bedeutung dieses Zustands
- Möglichkeit zur Verortung

## Übergang

Die Verortung wird angeboten als:

→ „Verortete Garnrolle erstellen“

Dabei wird erklärt:

- welche Daten benötigt werden
- wie der Ungenauigkeitsradius wirkt
- dass die interne Verortung exakt bleibt

## Nicht erlaubt

- versteckte Defaults ohne Anzeige
- nachträglicher RoN-Toggle
- Vermischung von Identität und Sichtbarkeit

Texte: Sicherer Einstieg im RoN-Startzustand ist Standard; Verortung ist optional und bewusst.
Vorschau public_pos.
