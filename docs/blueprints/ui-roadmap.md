---
id: ui-roadmap
title: Weltgewebe UI Roadmap
doc_type: blueprint
status: canonical
canonicality: This document is the canonical source of truth for the UI implementation roadmap.
summary: Konkrete Priorisierung und Meilensteinplanung für den Ausbau der Weltgewebe UI.
---

# Weltgewebe UI Roadmap

Diese Blaupause beschreibt die konkrete, priorisierte Implementierungsfolge für die noch offenen UI-Arbeiten, abgeleitet aus der kanonischen State Machine und der UI-Blaupause.

⸻

## Phase 1 — Jetzt: Komposition wirklich fertig machen

Der Fokus liegt auf dem produktiven Hebel: Der Kompositionsfluss muss aus dem reinen Statusanzeige-Zustand in einen echten Editor überführt werden.

### [x] Roadmap PR 1 — Kompositionseditor vollenden

- [x] KompositionPanel von Statusanzeige zu echtem Editor ausbauen
- [x] Knotentyp-Auswahl ergänzen
- [x] Titel/Beschreibung ergänzen
- [x] lokale Schrittlogik im Panel definieren
- [x] Validierung für Pflichtfelder ergänzen
- [x] Cancel-Flow sauber definieren
- [x] Submit-Flow implementieren
- [x] Erfolgspfad für erfolgreichen Submit entscheiden und dokumentieren:
  - Option A wurde gewählt: `komposition -> navigation`

### [x] Roadmap PR 1a — Kompositions-Tests ergänzen

- [x] Test für erfolgreichen Submit ergänzen
- [x] Test für Validation Error ergänzen
- [x] Test für Cancel während Komposition ergänzen
- [x] Test für „Ort ändern“ ergänzen, falls unterstützt
- [x] Test für Draft-Cleanup nach Close/Success ergänzen

⸻

## Phase 2 — Danach: Guard und Invarianten schärfen

Der aktuelle State-Watcher meldet Verstöße nur; der Unterschied zwischen Warnung und Schranke muss ontologisch durchgesetzt werden.

### [x] Roadmap PR 2 — Zustandsdurchsetzung härten

- [x] Entscheiden, ob der dev/test-Invariant-Watcher weiter nur loggt oder hart werfen soll
- [x] Falls Throw gewünscht:
  - [x] `assertUiStateInvariant()` oder gleichwertige Schicht ergänzen
  - [x] Nutzung im Dev/Test-Modus klar einbauen
- [x] Explizite Ausschlussregel festhalten: `selection !== null` und `kompositionDraft !== null` dürfen nie gleichzeitig gelten
- [x] Optional: separaten Unit-Test für ungültige Zustandskombinationen ergänzen

### [x] Roadmap PR 2a — Store-nahe Tests ergänzen

- [x] Explizit prüfen, dass `enterFokus(...)` `selection !== null` ergibt
- [x] Explizit prüfen, dass `enterKomposition(...)` `selection === null` setzt
- [x] Explizit prüfen, dass `leaveToNavigation()` `selection === null` und `kompositionDraft === null` herstellt
- [x] Sofern sinnvoll: `contextPanelOpen` indirekt oder direkt derived prüfen

⸻

## Phase 3 — Danach: Fokus-Panels inhaltlich aufladen

Die Struktur der Panels steht, nun müssen echte Domänendaten aus der Blaupause einziehen.

### [x] Roadmap PR 3 — NodePanel mit echten Inhalten ausbauen

> Aktueller Stand: Fokus-Panels wurden inhaltlich auf geladene Domänendaten umgestellt. Die Anbindung erfolgt zur Vermeidung von Build-Konflikten lokal dynamisch via `/api/node/[id]` und remote gegen das reguläre Listen-Backend via `/api/nodes/[id]`. Diese laden die echten Teilnehmer und den korrekten Verlauf in die Panel-Ansicht. Die "Gespräch"- und "Anträge"-Tabs wurden explizit als Scaffold belassen, um Feature Creep zu vermeiden (diese benötigen noch komplexere Backend-Integrationen in zukünftigen Schritten).

- [x] Übersicht mit Beschreibung/Beteiligten/Aktivität (echte Daten) (Integration im Fokuspfad umgesetzt)
- [x] Verlauf-Tab mit Timeline/Chronik (Echte Daten aus der History eingebunden)
- [x] Relevante Datenquellen/API-Pfade klären (Lokal: `/api/node/[id]` zur Vermeidung von Static-Build-Konflikten, Remote: `/api/nodes/[id]`)
- [ ] Gesprächs-Tab mit echter Gesprächsansicht (Scaffold bewusst erhalten, Integration auf später verschoben)
- [ ] Anträge-Tab mit Vorschlägen/Abstimmungen (Scaffold bewusst erhalten, Integration auf später verschoben)

### [x] Roadmap PR 4 — AccountPanel mit echten Inhalten ausbauen

> Aktueller Stand: Im Demo-/Scaffold-Scope funktional abgeschlossen. Basisdaten, Aktivitäten und Knotenlisten sind demo-basiert integriert, die tiefergehende Domänenintegration bleibt jedoch explizit offen.

- [x] Profil: Basisdaten integriert (Typ, Tags, Erstellungsdatum), tiefergehende Domänenfelder (Kompetenzen/Güter) offen
- [x] Aktivität: demo-/edge-basierte Aktivität integriert, tiefere Fachintegration offen
- [x] Knotenliste: echte Verknüpfungen im Demo-Scope integriert

### [ ] Roadmap PR 5 — EdgePanel ausbauen (teilweise erledigt)

> Aktueller Stand: UI-Fortschritt im EdgePanel ist lokal abgeschlossen (Typ, Beschreibung, Teilnehmer, Zeitlichkeit). Die Remote-Backend-Infrastruktur unterstützt jedoch noch keinen konsistenten Edge-Detailpfad (z.B. `/api/edges/:id`), daher wird die Funktionalität lokal/demo-tauglich gehalten, die Architektur-Parität ist jedoch noch offen.

- [x] Typ und Beschreibung ergänzen
- [x] Zeitlichkeit konkretisieren
- [x] Beteiligte Garnrollen ergänzen
- [x] Quelle/Ziel sauber modellieren
- [ ] Remote-Backend: Echten Edge-Detail-Endpoint (`/api/edges/:id`) implementieren und anbinden

⸻

## Phase 4 — Mittelfristig: Suche, Filter, Bedienbarkeit

### [x] Roadmap PR 6 — Suche als lokaler Modus (ActionBar) umsetzen

- [x] Suchfeld in ActionBar/TopBar einziehen
- [x] Ergebnisse lokal über der ActionBar rendern (ohne Konflikt mit ContextPanel)
- [ ] Treffer auf der Karte markieren
- [x] *Search als lokalen Modus halten, nicht als vierten Global-State modellieren*

### [ ] Roadmap PR 7 — Filter als Panel-/lokalen Modus umsetzen

- [ ] Filter-UI ergänzen
- [ ] Karten-/Treffer-Filterung anbinden
- [ ] *Keine neue globale Hauptzustandsklasse einführen*

### [ ] Roadmap PR 8 — A11y und Keyboard-Navigation

- [x] Keyboard-Navigation für Tabs ergänzen
- [x] Escape-Verhalten definieren
- [ ] Fokusmanagement bei Markerwechsel weiter härten
- [x] `aria-*` für Tabs/Tabpanels grundlegend ergänzt
- [ ] Screenreader-taugliche Rollen vollständig absichern

⸻

## Phase 5 — Später / optional: Doku- und Strukturpflege

Diese Punkte sind keine Blocker für den produktiven Fortschritt, aber wichtig für die langfristige Gesundheit.

### [ ] Doku-Pflege

- [ ] `ui-state-machine.md` besser in die Doku-Navigation einhängen
- [ ] Alte/veraltete Pfadangaben in Nebenquellen vermeiden
- [ ] Fokus-Restore als UX-Regel statt fachlicher Kerninvariante markieren

### [ ] Strukturpflege

- [x] `+page.svelte` weiter entlasten (Suche als eigenes Overlay extrahiert)
- [ ] Gemeinsame Tab-/Panel-Styling-Bausteine prüfen
- [ ] Optional `uiInvariants.ts` oder ähnliche Trennung einführen, falls Guard komplexer wird
