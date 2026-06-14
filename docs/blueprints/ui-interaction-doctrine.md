---
id: ui-interaction-doctrine
title: Weltgewebe UI Interaction Doctrine
doc_type: blueprint
status: canonical
summary: Kanonischer Interaktionscontract für das Fokuspanel-Modell der Weltgewebe-UI (Karte, Fokuspanel, Aktionsleiste, Kartenlinsen, Komposition, URL-Adressierung).
relations:
  - type: relates_to
    target: docs/blueprints/ui-blaupause.md
  - type: relates_to
    target: docs/blueprints/ui-state-machine.md
  - type: relates_to
    target: docs/blueprints/ui-roadmap.md
  - type: relates_to
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: relates_to
    target: docs/roadmap.md
---

# Weltgewebe UI Interaction Doctrine

## Status

Dieses Dokument ist der kanonische Interaktionscontract für die Weltgewebe-UI.
Es präzisiert und bündelt die Interaktionslogik aus:

- `docs/blueprints/ui-blaupause.md`
- `docs/blueprints/ui-state-machine.md`
- `docs/blueprints/ui-roadmap.md`
- `docs/blueprints/kartenklarheit-roadmap.md`

Es definiert keine neue State Machine und keine Implementierung, sondern legt die
fachliche Bedeutung der Hauptflächen, Zustände und Adressierungsformen fest.

## Zweck

Weltgewebe ist kein generisches Karten-Dashboard.
Weltgewebe ist ein kartenbasiertes Kollektivgüterverwaltungsinterface.

Die UI muss drei Dinge gleichzeitig leisten:

- Orientierung im gemeinsamen Raum
- Fokus auf ein konkretes Objekt oder Anliegen
- Handlung / Komposition im Gewebe

## Kanonische Hauptflächen

Die UI besteht aus drei Hauptflächen: Karte, Fokuspanel und Aktionsleiste.

### Karte

Die Karte ist der öffentliche Lage- und Wahrnehmungsraum.

Sie zeigt:

- Knoten
- Garnrollen
- Fäden
- räumliche Zusammenhänge
- Aktivitätsdichte über Fäden und Objektbeziehungen

### Fokuspanel / ContextPanel

Das Fokuspanel ist der einzige Detail-, Entscheidungs- und Handlungsraum.

`Fokuspanel` ist die fachliche Rolle.
`ContextPanel` ist der technische Komponentenname (`apps/web/src/lib/components/ContextPanel.svelte`).

Das Fokuspanel enthält je nach Zustand:

- Objektfokus
- Beziehungskontext
- Gespräch
- Anträge / Entscheidungen
- Komposition

Die Layoutform ist mobil ein Bottom-Sheet und auf dem Desktop eine rechte
Seitenleiste. Beide sind Layout-Ausprägungen desselben Fokuspanels, kein
eigenständiger rechter Drawer.

### Aktionsleiste

Die Aktionsleiste ist die Intent- und Werkzeugleiste.

Sie öffnet:

- Suche
- Filter / Kartenlinsen
- Komposition
- persönliche Zugänge

## Kanonische globale Zustände

Die UI kennt genau drei globale Zustände:

- `navigation`
- `fokus`
- `komposition`

Diese Zustände sind die globale State-Machine-Wahrheit
(`docs/blueprints/ui-state-machine.md`, implementiert in
`apps/web/src/lib/stores/uiView.ts`). Es darf kein vierter globaler Zustand ohne
Anpassung der State Machine eingeführt werden.

## Lokale Modi und Unterzustände

Lokale Modi sind:

- Suche
- Filter
- Tabs
- Hover
- Vorschau
- temporäre Auswahl

Diese Modi dürfen keine zweite globale State Machine bilden.

## Fokuspanel-Grammatik

Das Fokuspanel folgt einer wiederkehrenden inneren Ordnung:

- Identität
- Beziehungen
- Aktivität
- Handlung
- Verlauf

## Objektarten im Fokuspanel

### Knoten

Typische Tabs:

- Übersicht
- Gespräch
- Anträge
- Verlauf

### Garnrolle

Typische Tabs:

- Profil
- Aktivität
- Knoten
- Güter

### Faden (technisch: Edge)

Typische Tabs:

- Bedeutung
- Quelle / Ziel
- Verlauf
- Handlung

### Antrag / Entscheidungsvorlage (fachlich vorgesehen)

Falls Anträge als eigenständige Fokusobjekte geführt werden, folgen sie
typischerweise dieser Ordnung:

- Anliegen
- Folgen
- Einspruch / Entscheidung
- Frist
- Verlauf

## Komposition

Komposition bedeutet: etwas ins Gewebe setzen.

Beispiele:

- Knoten anlegen
- Faden weben
- Antrag stellen
- Gut anbieten
- Gespräch eröffnen

Komposition ist kein loses Formular und kein Drawer.
Komposition ist ein globaler UI-Zustand im Fokuspanel.

## Suche und Filter als Kartenlinsen

Suche und Filter sind Kartenlinsen.
Sie verändern Wahrnehmung, Sichtbarkeit und Auswahl auf der Karte.
Sie erzeugen keinen weiteren globalen UI-Zustand.

Filter ist keine linke Drawer-Fläche.
Suche ist kein vierter Global-State.

Technisch werden Kartenlinsen durch Store- und Presentation-Ableitungen,
kartenbezogene Filterlogik und UI-Overlays umgesetzt. Sie verändern die sichtbare
Perspektive auf die Karte, aber nicht die globale UI-State-Machine.

## URL-Adressierung

URL-State darf bestehende UI-Zustände adressieren.
URL-State darf keine zweite State Machine erzeugen.

Empfohlene Zielsemantik für die spätere Implementierung:

- `focus=<type>:<id>`
- `tab=<tab>`
- `lens=filter|search`
- `compose=<kind>`

Beispiele:

- `/map?focus=node:abc&tab=gespraech`
- `/map?focus=garnrolle:anna&tab=knoten`
- `/map?lens=filter`
- `/map?compose=node`

Identifier in `focus=<type>:<id>` müssen URL-encoded werden. Eine spätere
Implementierung darf die Selection-Referenz nicht durch naives Splitten
ungeprüfter Rohstrings auswerten; sie muss Typ und Identifier kontrolliert
dekodieren und ungültige Werte stabil ignorieren oder bereinigen.

Für nutzerteilbare Links ist die ausgeschriebene Form (`focus`, `tab`, `lens`,
`compose`) vorzuziehen. Eine Kurzform wie `f=<type>:<id>` darf später nur
eingeführt werden, wenn sie einen belegten Nutzen hat und die Lesbarkeit nicht
verschlechtert. Dieser technische Contract wird hier nicht final festgelegt.

Nicht empfohlen als neuer Zielcontract:

- `l = linker Drawer`
- `r = rechter Drawer`

Die bisherige Kurzform `l` / `r` / `t` bleibt nur als historisches Altmodell in
den Statusdokumenten erhalten. Maßgeblich für den aktuellen Umsetzungsstand sind
`docs/reports/map-status-matrix.md` und
`docs/blueprints/kartenklarheit-roadmap.md`.

## Deprecated Begriffe

Veraltet als aktuelle Architekturbegriffe:

- linker Drawer
- rechter Drawer
- Drawer-Zustand
- rechter Slider mit Filterkästchen
- Drawer-/Tab-Deep-Link-Adressierung

Diese Begriffe dürfen nur in historischen Kontexten stehen bleiben oder müssen
ausdrücklich als veraltet markiert werden. Die Desktop-Ausprägung „rechte
Seitenleiste" bleibt erlaubt, aber nur als Layoutform des Fokuspanels.

Nicht betroffen sind fachlich legitime Slider, die nichts mit Drawer-Layout zu
tun haben, etwa der Ungenauigkeitsradius-Slider (Privacy, ADR-0003) oder ein
historischer Zeit-Slider in Fahrplänen.

## Nicht-Ziele

- kein Viewport-Deep-Linking für `center` / `zoom` / `bearing` / `pitch`
- keine zweite Panel-Open-State-Wahrheit (`contextPanelOpen` bleibt abgeleitet)
- keine Layoutfläche als fachlicher Zustand
- keine parallele Drawer-State-Machine
- keine Heatmap als Ersatz für Fäden-Dichte
- keine Implementierung in diesem Dokument

## Konsequenzen für spätere Implementierung

Spätere Query-Navigation soll auf Fokuspanel-/Lens-Semantik aufbauen.
Sie darf bestehende Zustände adressieren:

- Fokus
- Tab
- Linse
- Komposition

Sie darf keine neuen globalen Zustände einführen.

Die URL ist eine Adressierungsschicht, nicht die zweite UI-State-Wahrheit. Bei
Page-Load, Popstate und expliziter Navigation darf sie bestehende Zustände
adressieren. Der kanonische UI-Zustand bleibt in der State Machine (`uiView`).
UI-Aktionen, die später URL-State ändern, müssen über einen deterministischen
Adapter laufen und Rückkopplungsschleifen zwischen Router und Store vermeiden.

Leitsätze:

- Bedeutung vor Layout.
- Fokus statt rechter Drawer.
- Linse statt linker Drawer.
- Tab nur innerhalb eines gültigen Fokuskontexts.

## Weiterführende Dokumente

- [Weltgewebe UI-Blaupause](ui-blaupause.md)
- [Weltgewebe UI State Machine](ui-state-machine.md)
- [Weltgewebe UI Roadmap](ui-roadmap.md)
- [Roadmap – Kartenklarheit](kartenklarheit-roadmap.md)
