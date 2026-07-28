---
id: specs.ui-interaction
title: UI-Interaktionsvertrag
summary: Kanonischer Vertrag für Karte, Fokuspanel, Werkzeugfächer, Kartenlinsen, Komposition und Zugänglichkeit.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-ui
owner: product-ui
last_reviewed: 2026-07-27
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
  - apps/web/src/lib/components/ToolFan.svelte
  - apps/web/src/lib/components/GovernanceFan.svelte
  - apps/web/src/lib/stores/mapChrome.ts
  - apps/web/src/lib/components/SearchOverlay.svelte
  - apps/web/src/lib/components/FilterOverlay.svelte
  - apps/web/tests/map-interaction.spec.ts
  - apps/web/tests/ui-filter.spec.ts
  - apps/web/tests/ui-search.spec.ts
  - apps/web/tests/tool-fan-layout.spec.ts
  - apps/web/tests/context-panel-sheet.spec.ts
---

# UI-Interaktionsvertrag

## Leitidee

Weltgewebe ist ein kartenbasiertes Koordinationsinterface. Die Karte ist der öffentliche Wahrnehmungsraum; Details und Handlungen werden nicht in parallelen Dashboards verteilt, sondern in einem einzigen kontextbezogenen Arbeitsraum gebündelt.

## Drei Hauptflächen

| Fläche           | Verantwortung                                       |
| ---------------- | --------------------------------------------------- |
| Karte            | räumlicher Überblick, Auswahl und sichtbares Gewebe |
| Fokuspanel       | Details, Gespräche, Entscheidungen und Handlungen   |
| Werkzeugfächer   | Finden, Karteninhalt und Webungsaktionen            |
| Governancefächer | Anträge und gemeinsame Entscheidungsereignisse      |

Es gibt keinen zweiten Detail-Drawer, kein dauerhaftes Seitenmenü für Objektinhalte und keine frei schwebenden Hauptformulare über der Karte.

## Karte

Die Karte bleibt während Fokus und Komposition sichtbar. Sie darf gedämpft oder teilweise verdeckt werden, verliert aber nicht ihre Rolle als räumlicher Zusammenhang.

Interaktionen:

- Marker oder Faden wählen → Fokus öffnen;
- leere Kartenfläche wählen → Fokus schließen, sofern kein lokaler Dialog Vorrang hat;
- Karte bewegen → kein neuer globaler Zustand;
- neue Webung beginnen → Komposition im Fokuspanel.

Der erste Kartenausschnitt folgt einer eindeutigen Priorität:

1. Ein ausdrücklich per URL adressierter Knoten oder eine Garnrolle wird gezeigt.
2. Sonst startet eine angemeldete Person auf ihrer öffentlich verorteten Garnrolle.
3. Fehlt eine verortete eigene Garnrolle oder eine Anmeldung, gilt der kanonische Fallback-Ausschnitt.

Die Kamera wird möglichst vor dem ersten sichtbaren Kartenbild bestimmt. Ein unnötiger Zwischensprung vom Fallback zur eigenen Garnrolle ist zu vermeiden.

## Fokuspanel

Das Fokuspanel ist der einzige Detail-, Entscheidungs- und Handlungsraum.

Responsive Darstellung:

- mobil als Bottom Sheet mit den Raststufen Vorschau, Halb und Voll;
- auf breiten Bildschirmen als rechtes Seitenpanel.

Fokus startet mobil in der Vorschau und kann bewusst erweitert werden. Komposition öffnet ausreichend groß. Alle Stufen teilen denselben Fachzustand und dieselben Inhalte; sie sind keine zusätzlichen globalen Zustände.

Typische Tabs:

- Knoten: Übersicht, Gespräch, Anträge, Verlauf;
- Garnrolle: Profil, Aktivität, Knoten;
- Faden: Art, beteiligte Endpunkte, Zeit und vorhandene Notiz.

Tabs sind lokal. Sie werden erst Teil der URL, wenn ein eigener verbindlicher Tab-Vertrag existiert.

## Werkzeugfächer

Der Werkzeugfächer formuliert Absichten, ohne der Karte dauerhaft eine Leiste zu entziehen. Sein kompakter Wurzelknopf sitzt unten mittig. Geöffnet besitzt die erste Ebene genau drei stabile Hauptäste:

- **Finden** öffnet die Suchlinse;
- **Karteninhalt** öffnet die Auswahl der sichtbaren Kartenarten;
- **Weben** öffnet eine zweite, höchstens eine Ebene tiefe Auswahl realer Webungsaktionen.

Die Webungsebene trennt die fachliche Kategorie von der konkreten Handlung. Der aktuelle Produktstand bietet dort:

- **Knoten knüpfen** für jeden angemeldeten Account;
- **Antrag stellen** für Gäste als direkter Einstieg in den produktiv vorhandenen Weberantrag.

Gäste können eigene Knoten im Fokuspanel bearbeiten. An fremden oder historisch
eigentümerlosen Knoten bleibt der Bearbeitungstab verborgen; Weber und
Administratoren erhalten dort die gemeinschaftliche Pflegeaktion.

Weitere Antragstypen dürfen erst erscheinen, wenn ihr Serververtrag tatsächlich produktiv ist. Eine deaktivierte oder beschriftete Oberfläche darf keine nicht vorhandene Schreibfähigkeit vortäuschen. Rollenabhängige Berechtigungen dürfen die drei Hauptäste nicht verschieben.

Der Werkzeugfächer schließt durch erneutes Betätigen, Escape, Fokuswechsel nach außen oder Auswahl außerhalb. Er ist kein modaler Dialog und hält den Tastaturfokus daher nicht gefangen. Beim Schließen per Escape kehrt der Fokus zum Wurzelknopf zurück. Animationen verwenden Transformation und Deckkraft und entfallen bei reduzierter Bewegung.

## Governancefächer

Gemeinsame Entscheidungsereignisse besitzen einen getrennten Wurzelknopf oben mittig. Der Governancefächer öffnet nach unten und enthält ausschließlich reale Lese- und Navigationssichten, derzeit:

- alle Anträge;
- offene Konsentverfahren;
- Anträge mit Veto;
- Gespräche mit tatsächlichen Beiträgen;
- laufende Abstimmungen.

Werkzeug- und Governancefächer sind gegenseitig exklusiv. Dadurch konkurrieren nicht zwei offene Menüs um dieselbe Kartenfläche. Das Stellen eines Antrags gehört nicht in den lesenden Governancefächer, sondern als Webungsaktion in die untere Webungsebene.

## Kartenlinsen

Finden und Karteninhalt sind lokale Kartenlinsen:

- sie verändern die sichtbare Szene;
- sie erzeugen keinen neuen globalen Zustand;
- sie schließen sich gegenseitig;
- sie erscheinen kompakt oberhalb der Karte und reservieren keine dauerhafte untere Fläche;
- die Karte bleibt die primäre Trefferfläche; Finden zeigt höchstens sechs automatische Vorschläge, weitere Treffer öffnen nur auf bewusste Anforderung; Sicht zeigt keine automatische Trefferliste, nur Typauswahl, aktive Anzahl und Rücksetzen;
- passende Knoten und Garnrollen werden auf der Karte hervorgehoben;
- liegt ein Treffer außerhalb des nutzbaren Kartenausschnitts, zeigt ein Richtungsmarker am Bildschirmrand zu ihm;
- Richtungsmarker bleiben außerhalb von Topbar, sichtbaren Kartenlinsen, Werkzeugfächer und Fokuspanel und besitzen mindestens 44 × 44 Pixel;
- ein Treffer oder Richtungsmarker kann die Karte fokussieren und das Fokuspanel öffnen;
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
- Finden oder Karteninhalt als globale Hauptzustände;
- stille API-Fallbacks, die Fehler als Leere darstellen;
- technische Feldnamen in der Nutzerführung;
- ein Kompositionsformular ohne eindeutigen Abbruch- und Erfolgsweg.
