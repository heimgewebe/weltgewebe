---
id: specs.ui-interaction
title: UI-Interaktionsvertrag
summary: Kanonischer Vertrag für Karte, Fokuspanel, Aktionsleiste, Kartenlinsen, Komposition und Zugänglichkeit.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-ui
owner: product-ui
last_reviewed: 2026-07-11
review_after: 2026-10-11
depends_on:
  - specs.ui-state-machine
  - specs.garnrolle-knoten-faden
relations:
  - type: supersedes
    target: docs/blueprints/ui-interaction-doctrine.md
  - type: supersedes
    target: docs/blueprints/ui-blaupause.md
verifies_with:
  - apps/web/src/lib/components/ContextPanel.svelte
  - apps/web/src/lib/components/ActionBar.svelte
  - apps/web/src/lib/components/SearchOverlay.svelte
  - apps/web/src/lib/components/FilterOverlay.svelte
  - apps/web/tests/map-interaction.spec.ts
  - apps/web/tests/ui-filter.spec.ts
---
# UI-Interaktionsvertrag

## Leitidee

Weltgewebe ist ein kartenbasiertes Koordinationsinterface. Die Karte ist der öffentliche Wahrnehmungsraum; Details und Handlungen werden nicht in parallelen Dashboards verteilt, sondern in einem einzigen kontextbezogenen Arbeitsraum gebündelt.

## Drei Hauptflächen

| Fläche | Verantwortung |
|---|---|
| Karte | räumlicher Überblick, Auswahl und sichtbares Gewebe |
| Fokuspanel | Details, Gespräche, Entscheidungen und Handlungen |
| Aktionsleiste | Suche, Filter, Komposition und weitere Absichten |

Es gibt keinen zweiten Detail-Drawer, kein dauerhaftes Seitenmenü für Objektinhalte und keine frei schwebenden Hauptformulare über der Karte.

## Karte

Die Karte bleibt während Fokus und Komposition sichtbar. Sie darf gedämpft oder teilweise verdeckt werden, verliert aber nicht ihre Rolle als räumlicher Zusammenhang.

Interaktionen:

- Marker oder Faden wählen → Fokus öffnen;
- leere Kartenfläche wählen → Fokus schließen, sofern kein lokaler Dialog Vorrang hat;
- Karte bewegen → kein neuer globaler Zustand;
- neue Webung beginnen → Komposition im Fokuspanel.

## Fokuspanel

Das Fokuspanel ist der einzige Detail-, Entscheidungs- und Handlungsraum.

Responsive Darstellung:

- mobil als Bottom Sheet;
- auf breiten Bildschirmen als rechtes Seitenpanel.

Beide Darstellungen teilen denselben Zustand und dieselben Inhalte.

Typische Tabs:

- Knoten: Übersicht, Gespräch, Anträge, Verlauf;
- Garnrolle: Profil, Aktivität, Knoten;
- Faden: Art, beteiligte Endpunkte, Zeit und vorhandene Notiz.

Tabs sind lokal. Sie werden erst Teil der URL, wenn ein eigener verbindlicher Tab-Vertrag existiert.

## Aktionsleiste

Die Aktionsleiste formuliert Absichten und bleibt knapp. Kernhandlungen:

- Suche;
- Filter;
- einen Knoten knüpfen;
- Zugang zur eigenen Garnrolle und zu Kontoeinstellungen.

Seltene oder noch nicht produktive Module gehören nicht als dauerhafte Hauptschaltflächen in die erste Ebene.

## Kartenlinsen

Suche und Filter sind lokale Kartenlinsen:

- sie verändern die sichtbare Szene;
- sie erzeugen keinen neuen globalen Zustand;
- sie schließen sich gegenseitig;
- ein Treffer kann die Karte fokussieren und das Fokuspanel öffnen;
- ein API-Fehler darf nicht wie eine normale leere Ergebnismenge aussehen.

## Komposition

Komposition bedeutet, etwas ins Gewebe zu setzen. Sie läuft im Fokuspanel und besitzt:

- einen klaren Entwurf;
- eine sichtbare Hauptaktion;
- einen Abbruchweg;
- verständliche Validierungsfehler;
- eine eindeutige Reaktion nach erfolgreichem Speichern.

Primäre Kompositionen:

- eigene Garnrolle auf die Karte setzen;
- Knoten knüpfen;
- passenden Faden erzeugen.

## URL-Adressierung

Die URL adressiert fachliche Absichten, nicht die flüchtige Kamera.

Unterstützte Zielrichtung:

```text
?focus=node:<id>
?focus=garnrolle:<id>
?lens=filter
?lens=search
?compose=node
?compose=garnrolle
?tab=<tab>
```

Priorität beim Einstieg:

```text
compose > focus > lens
```

`tab` wird erst wirksam, wenn das gewählte Panel ein adressierbares Tabmodell besitzt. Mittelpunkt, Zoom, Drehung und Neigung bleiben MapLibre-Zustand und werden nicht automatisch in die URL gespiegelt.

## Mobile-First und Zugänglichkeit

Pflichtregeln:

- alle Kernhandlungen per Tastatur erreichbar;
- sichtbarer Fokus;
- Escape schließt den vordersten relevanten Raum;
- Fokus kehrt nach dem Schließen möglichst zum Auslöser zurück;
- Tabs unterstützen Pfeiltasten, Pos1 und Ende;
- Schaltflächen besitzen verständliche Namen;
- Touchziele sind ausreichend groß;
- Formulare verwenden klare Labels und Fehlermeldungen;
- Animationen berücksichtigen reduzierte Bewegung.

## Sprache

Die Hauptführung verwendet Produktbegriffe. Technische Namen bleiben in Diagnose- oder Entwicklungsflächen.

## Nicht erlaubt

- mehrere konkurrierende Detailflächen;
- Suche oder Filter als globale Hauptzustände;
- stille API-Fallbacks, die Fehler als Leere darstellen;
- technische Feldnamen in der Nutzerführung;
- ein Kompositionsformular ohne eindeutigen Abbruch- und Erfolgsweg.
