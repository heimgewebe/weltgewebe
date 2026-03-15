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

### [ ] Roadmap PR 3 — NodePanel mit echten Inhalten ausbauen

*(Aktueller Stand: UI-Strukturen und Tabs wurden als Scaffold vorbereitet, Modul-Labels synchronisiert. Die Anbindung an echte Domain-Objekte und Backend-APIs im Fokuspfad ist noch offen.)*

- [ ] Übersicht mit Beschreibung/Beteiligten/Aktivität (echte Daten)
- [ ] Gesprächs-Tab mit echter Gesprächsansicht
- [ ] Anträge-Tab mit Vorschlägen/Abstimmungen
- [ ] Verlauf-Tab mit Timeline/Chronik
- [ ] Relevante Datenquellen/API-Pfade klären

### [ ] Roadmap PR 4 — AccountPanel mit echten Inhalten ausbauen

- [ ] Profil mit Kompetenzen/Interessen/Gütern
- [ ] Aktivität mit Beiträgen/Teilnahmen
- [ ] Knotenliste mit echten Verknüpfungen

### [ ] Roadmap PR 5 — EdgePanel ausbauen

- [ ] Typ und Beschreibung ergänzen
- [ ] Zeitlichkeit konkretisieren
- [ ] Beteiligte Garnrollen ergänzen
- [ ] Quelle/Ziel sauber modellieren

⸻

## Phase 4 — Mittelfristig: Suche, Filter, Bedienbarkeit

### [ ] Roadmap PR 6 — Suche als Panel-Modus umsetzen

- [ ] Suchfeld in ActionBar/TopBar einziehen
- [ ] Ergebnisse im Kontextpanel rendern
- [ ] Treffer auf der Karte markieren
- [ ] *Search als Panel-/lokalen Modus halten, nicht als vierten Global-State modellieren*

### [ ] Roadmap PR 7 — Filter als Panel-/lokalen Modus umsetzen

- [ ] Filter-UI ergänzen
- [ ] Karten-/Treffer-Filterung anbinden
- [ ] *Keine neue globale Hauptzustandsklasse einführen*

### [ ] Roadmap PR 8 — A11y und Keyboard-Navigation

- [ ] Keyboard-Navigation für Tabs ergänzen
- [ ] Escape-Verhalten definieren
- [ ] Fokusmanagement bei Markerwechsel weiter härten
- [ ] `aria-*` für Panel/Tabs/Toolbar prüfen
- [ ] Screenreader-taugliche Rollen nachziehen

⸻

## Phase 5 — Später / optional: Doku- und Strukturpflege

Diese Punkte sind keine Blocker für den produktiven Fortschritt, aber wichtig für die langfristige Gesundheit.

### [ ] Doku-Pflege

- [ ] `ui-state-machine.md` besser in die Doku-Navigation einhängen
- [ ] Alte/veraltete Pfadangaben in Nebenquellen vermeiden
- [ ] Fokus-Restore als UX-Regel statt fachlicher Kerninvariante markieren

### [ ] Strukturpflege

- [ ] `+page.svelte` weiter entlasten, falls wieder zu schwer
- [ ] Gemeinsame Tab-/Panel-Styling-Bausteine prüfen
- [ ] Optional `uiInvariants.ts` oder ähnliche Trennung einführen, falls Guard komplexer wird
