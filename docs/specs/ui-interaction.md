---
id: specs.ui-interaction
title: UI-Interaktionsvertrag
summary: Kanonischer Vertrag für Karte, Fokuspanel, Werkzeugfächer, Aufmerksamkeit, Kartenlinsen, Farbschema, Komposition und Zugänglichkeit.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-ui
owner: product-ui
last_reviewed: 2026-08-17
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
  - apps/web/src/lib/components/AttentionBubbles.svelte
  - apps/web/src/lib/accountAttentionRuntime.ts
  - apps/web/src/app.html
  - apps/web/static/theme-init.js
  - apps/web/src/lib/styles/tokens.css
  - apps/web/src/lib/components/TopBarAuth.svelte
  - apps/web/src/routes/settings/+page.svelte
  - apps/web/src/lib/stores/mapChrome.ts
  - apps/web/src/lib/components/SearchOverlay.svelte
  - apps/web/src/lib/components/FilterOverlay.svelte
  - apps/web/tests/attention-bubbles.spec.ts
  - apps/web/tests/map-interaction.spec.ts
  - apps/web/tests/ui-filter.spec.ts
  - apps/web/tests/ui-search.spec.ts
  - apps/web/tests/tool-fan-layout.spec.ts
  - apps/web/tests/context-panel-sheet.spec.ts
  - apps/web/tests/theme.spec.ts
---

# UI-Interaktionsvertrag

## Leitidee

Weltgewebe ist ein kartenbasiertes Koordinationsinterface. Die Karte ist der öffentliche Wahrnehmungsraum; Details und Handlungen werden nicht in parallelen Dashboards verteilt, sondern in einem einzigen kontextbezogenen Arbeitsraum gebündelt.

## Drei Hauptflächen

| Fläche         | Verantwortung                                       |
| -------------- | --------------------------------------------------- |
| Karte          | räumlicher Überblick, Auswahl und sichtbares Gewebe |
| Fokuspanel     | Details, Gespräche, Entscheidungen und Handlungen   |
| Werkzeugfächer | Finden, Karteninhalt und Webungsaktionen            |

Aktuelle Aufmerksamkeit ist keine vierte Hauptfläche. Sie erscheint als kompakte, nichtmodale Orientierung in der Kartenleiste und führt in die bereits vorhandenen Fachräume.

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

## Aufmerksamkeit und Governance

Die Kartenleiste zeigt oben links kleine Aufmerksamkeitsblasen für aktuell offene, für den angemeldeten Account relevante Sachverhalte. Diese Blasen sind keine Ereignishistorie, kein Benachrichtigungsarchiv und keine zweite Fachwahrheit. Sie werden aus den kanonischen Fach-APIs abgeleitet; ein Invalidierungssignal fordert lediglich eine erneute Lesung dieser Wahrheit an.

Regeln:

- eine zugrunde liegende Sache erzeugt höchstens eine sichtbare Aufmerksamkeitseinheit; insbesondere gilt eine Direktunterhaltung als eine Einheit und ein Antrag als eine Einheit;
- die neueste Einheit steht ganz links und schiebt ältere Einheiten nach rechts; die Reihenfolge folgt ausschließlich realen Quellzeitpunkten, nicht einer verdeckten Prioritätswertung;
- Bedeutung oder persönliche Nähe dürfen über Symbol, Form oder Umrandung sichtbar werden, ohne die zeitliche Reihenfolge zu verändern;
- auf schmalen Ansichten bleibt nur eine begrenzte Zahl von Blasen sichtbar; weitere Einheiten bleiben über einen berührbaren `+N`-Überlauf erreichbar;
- jede direkte Bedienfläche besitzt mindestens 44 × 44 Pixel;
- neue Aufmerksamkeit darf die Kartenkamera niemals selbständig bewegen;
- das Öffnen einer Blase hält die Karte zunächst offen und zeigt eine kompakte, nichtmodale Aufmerksamkeitskarte mit Grund und genau einer Hauptaktion; erst diese Aktion führt in die bestehende kanonische Fachansicht, etwa die konkrete Direktunterhaltung oder den konkreten Antrag;
- reduzierte Bewegung verhindert nicht die Zustandsänderung, sondern nur deren dekorative Animation.

Der aktuelle belegte Quellensatz umfasst ungelesene Direktunterhaltungen, den eigenen offenen Weberantrag und offene kollektive Governance-Verfahren für Rollen, die an diesen Verfahren teilnehmen können. Die Listenansicht der Governance belegt derzeit nicht, ob eine konkrete Person bereits abgestimmt hat. Die Aufmerksamkeit darf deshalb ein laufendes Abstimmungsverfahren anzeigen, aber nicht behaupten, dass eine persönliche Stimme fehlt.

Allgemeine Governance-Navigation ist keine persönliche Aufmerksamkeit. Die Vollansicht `/antraege` bleibt der kanonische Lese- und Navigationsraum und bietet weiterhin reale Filter für:

- alle Anträge;
- offene Konsentverfahren;
- Anträge mit Veto;
- Gespräche mit tatsächlichen Beiträgen;
- laufende Abstimmungen.

Das Stellen eines Antrags bleibt eine Webungsaktion im Werkzeugfächer beziehungsweise im passenden Fachraum. Ein zusätzlicher Governancefächer in der Kartenmitte ist nicht Teil der kanonischen Chrome.

## Kartenlinsen

Finden und Karteninhalt sind lokale Kartenlinsen:

- sie verändern die sichtbare Szene;
- sie erzeugen keinen neuen globalen Zustand;
- sie schließen sich gegenseitig;
- sie erscheinen kompakt oberhalb der Karte und reservieren keine dauerhafte untere Fläche;
- die Karte bleibt die primäre Trefferfläche; Finden zeigt höchstens sechs automatische Vorschläge, weitere Treffer öffnen nur auf bewusste Anforderung; Sicht zeigt keine automatische Trefferliste, nur Typauswahl, aktive Anzahl und Rücksetzen;
- passende Knoten und Garnrollen werden auf der Karte hervorgehoben;
- liegt ein Treffer außerhalb des nutzbaren Kartenausschnitts, zeigt ein Richtungsmarker am Bildschirmrand zu ihm;
- Richtungsmarker bleiben außerhalb von Topbar, sichtbaren Kartenlinsen, sichtbarer Aufmerksamkeitskarte oder sichtbarem Aufmerksamkeitsüberlauf, Werkzeugfächer und Fokuspanel und besitzen mindestens 44 × 44 Pixel;
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

## Farbschema und visuelle Gewebesprache

Die Oberfläche bietet genau drei Darstellungspräferenzen:

- **System** als Standard; folgt der aktuellen Hell-/Dunkelpräferenz des Geräts und reagiert während der Sitzung auf Änderungen;
- **Hell** als bewusste helle Darstellung;
- **Dunkel** als bewusste dunkle Darstellung.

Die Auswahl liegt im zentralen Einstellungsmenü. Die Kartenleiste führt mit einem einzigen Einstieg dorthin, statt dort parallele Darstellungsschalter zu zeigen. Private Nachrichten bleiben davon getrennt als direkter Arbeitsweg in der Kartenleiste erreichbar; ungelesene Direktunterhaltungen können zusätzlich als aktuelle Aufmerksamkeit erscheinen. Die Farbschema-Auswahl wird ausschließlich lokal im Browser gespeichert; sie gehört weder zum Konto noch zur öffentlichen Garnrolle und wird nicht föderiert.

Farben und Flächen stammen aus gemeinsamen semantischen Darstellungstokens. Komponenten dürfen daher keine dunkle oder helle Grunddarstellung voraussetzen. Status, Auswahl, Warnung und Fehler müssen zusätzlich zu Farbe durch Text, Form, Umrandung oder Symbol verständlich bleiben.

Die Gewebesprache darf Zusammengehörigkeit durch zurückhaltende Fadenlinien, Schichtungen und weiche Übergänge andeuten. Wiederholte Streifenmuster auf Seiten-, Menü- oder Inhaltsflächen sind nicht Teil dieser Sprache. Dekoration darf die Lesbarkeit, den Karteninhalt, den Fokus oder die Bedienziele nicht überlagern. Dekorative Bewegung ist nicht erforderlich und entfällt bei reduzierter Bewegung.

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
- Aufmerksamkeitsblasen als persistente zweite Kopie von Fachzuständen;
- stille API-Fallbacks, die Fehler als Leere darstellen;
- technische Feldnamen in der Nutzerführung;
- ein Kompositionsformular ohne eindeutigen Abbruch- und Erfolgsweg.
