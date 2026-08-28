---
id: specs.ui-state-machine
title: UI-Zustandsmaschine
summary: Verbindlicher Vertrag für die drei globalen Zustände Navigation, Fokus und Komposition.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product-ui
owner: product-ui
last_reviewed: 2026-07-11
review_after: 2026-10-11
depends_on: []
relations:
  - type: supersedes
    target: docs/blueprints/ui-state-machine.md
verifies_with:
  - apps/web/src/lib/stores/uiView.ts
  - apps/web/src/lib/stores/uiInvariants.ts
  - apps/web/src/lib/stores/uiInvariants.test.ts
attention_source_status: none
attention_source_rationale: "Beschreibt UI-Zustände und Navigation, erzeugt aber keine kanonischen persönlichen Fachfakten."
---
# UI-Zustandsmaschine

## Zweck

Die Zustandsmaschine verhindert, dass Karte, Auswahl und Erstellungsformular gleichzeitig widersprüchliche Wahrheiten anzeigen. Sie beschreibt nur globale Zustände. Suche, Filter, Tabs, Hover und Vorschauen bleiben lokale Modi.

## Globale Zustände

```text
navigation
fokus
komposition
```

| Zustand | Bedeutung | Erforderliche Daten |
|---|---|---|
| `navigation` | Karte betrachten, bewegen und durchsuchen | keine Auswahl, kein Entwurf |
| `fokus` | genau ein bestehendes Objekt untersuchen oder bearbeiten | genau eine Auswahl |
| `komposition` | etwas Neues ins Gewebe setzen | genau ein Kompositionsentwurf |

## Invarianten

1. Auswahl und Kompositionsentwurf dürfen nie gleichzeitig gesetzt sein.
2. `fokus` verlangt eine Auswahl.
3. `komposition` verlangt einen Kompositionsentwurf.
4. `navigation` verlangt, dass Auswahl und Entwurf leer sind.
5. Das Fokuspanel ist genau dann geöffnet, wenn der Zustand nicht `navigation` ist.
6. Suche und Filter verändern den globalen Zustand nicht.

## Übergänge

```text
navigation -- Objekt wählen -----------------> fokus
navigation -- Komposition beginnen ----------> komposition
fokus ------ anderes Objekt wählen ----------> fokus
fokus ------ schließen / Karte wählen -------> navigation
fokus ------ neue Webung beginnen -----------> komposition
komposition - erfolgreich speichern ----------> fokus oder navigation
komposition - abbrechen ----------------------> navigation
```

Nach erfolgreichem Knotenweben darf die neue Entität fokussiert werden, sobald sie in der neu geladenen Szene vorhanden ist. Ein fehlgeschlagener Schreibvorgang verlässt die Komposition nicht stillschweigend.

## Lokale Modi

Folgende Zustände sind keine globalen Zustände:

- Suche offen oder geschlossen;
- Filter offen oder geschlossen;
- aktiver Panel-Tab;
- Hover und Tastaturfokus;
- Kartenbewegung und Kameraposition;
- Lade-, Fehler- und Degradationsanzeige.

Suche und Filter schließen sich gegenseitig. Escape schließt zuerst den lokal vordersten Raum und erst danach das Fokuspanel.

## Eigentum der Zustände

- `uiView.ts` besitzt globalen Zustand, Auswahl und Kompositionsentwurf.
- `searchStore.ts` besitzt die Suchlinse.
- `filterStore.ts` besitzt die Filterlinse.
- MapLibre besitzt Mittelpunkt, Zoom, Neigung und Drehung.
- Panel-Komponenten besitzen ihre lokalen Tabs, bis ein eigener URL-Vertrag eingeführt wird.

## Nicht erlaubt

- ein vierter globaler Zustand für Suche oder Filter;
- gleichzeitig geöffnete Auswahl und Komposition;
- ein zweiter Detail-Drawer neben dem Fokuspanel;
- direkte Store-Mutationen, die die Übergangsfunktionen umgehen;
- URL-Parameter als zweite, widersprechende Zustandsquelle.

## Definition von fertig

Eine Änderung an der Hauptinteraktion ist nur fertig, wenn:

- die Invarianten weiterhin gelten;
- Tastatur- und Escape-Verhalten geprüft sind;
- Fokus nach dem Schließen sinnvoll zurückkehrt;
- Browser- und Storetests den neuen Übergang belegen.
