---
id: specs.privacy-ui
title: Privacy Ui
doc_type: reference
status: active
canonicality: derived
summary: Automatisch hinzugefügtes Frontmatter.
---
# Privacy UI (ADR-0003)

Slider (r Meter) für verortete Garnrollen.

## Startzustand

Beim Einstieg befindet sich der Nutzer im RoN-Startmodus.

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

Texte: Transparenz = Standard.
Vorschau public_pos.
