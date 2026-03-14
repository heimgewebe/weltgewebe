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

### [ ] PR 1 — Kompositionseditor vollenden

- [ ] KompositionPanel von Statusanzeige zu echtem Editor ausbauen
- [ ] Knotentyp-Auswahl ergänzen
- [ ] Titel/Beschreibung ergänzen
- [ ] lokale Schrittlogik im Panel definieren
- [ ] Validierung für Pflichtfelder ergänzen
- [ ] Cancel-Flow sauber definieren
- [ ] Submit-Flow implementieren
- [ ] Erfolgspfad entscheiden:
  - `komposition -> navigation`
  - oder `komposition -> fokus(neuer Knoten)`

### [ ] PR 1a — Kompositions-Tests ergänzen

- [ ] Test für erfolgreichen Submit ergänzen
- [ ] Test für Validation Error ergänzen
- [ ] Test für Cancel während Komposition ergänzen
- [ ] Test für „Ort ändern“ ergänzen, falls unterstützt
- [ ] Test für Draft-Cleanup nach Close/Success ergänzen

⸻

## Phase 2 — Danach: Guard und Invarianten schärfen

Der aktuelle State-Watcher meldet Verstöße nur; der Unterschied zwischen Warnung und Schranke muss ontologisch durchgesetzt werden.

### [ ] PR 2 — Zustandsdurchsetzung härten

- [ ] Entscheiden, ob der dev/test-Invariant-Watcher weiter nur loggt oder hart werfen soll
- [ ] Falls Throw gewünscht:
  - [ ] `assertUiStateInvariant()` oder gleichwertige Schicht ergänzen
  - [ ] Nutzung im Dev/Test-Modus klar einbauen
- [ ] Explizite Ausschlussregel festhalten: `selection !== null` und `kompositionDraft !== null` dürfen nie gleichzeitig gelten
- [ ] Optional: separaten Unit-Test für ungültige Zustandskombinationen ergänzen

### [ ] PR 2a — Store-nahe Tests ergänzen

- [ ] Explizit prüfen, dass `enterFokus(...)` `selection !== null` ergibt
- [ ] Explizit prüfen, dass `enterKomposition(...)` `selection === null` setzt
- [ ] Explizit prüfen, dass `leaveToNavigation()` `selection === null` und `kompositionDraft === null` herstellt
- [ ] Sofern sinnvoll: `contextPanelOpen` indirekt oder direkt derived prüfen

⸻

## Phase 3 — Danach: Fokus-Panels inhaltlich aufladen

Die Struktur der Panels steht, nun müssen echte Domänendaten aus der Blaupause einziehen.

### [ ] PR 3 — NodePanel mit echten Inhalten ausbauen

- [ ] Übersicht mit Beschreibung/Beteiligten/Aktivität
- [ ] Gesprächs-Tab mit echter Gesprächsansicht
- [ ] Anträge-Tab mit Vorschlägen/Abstimmungen
- [ ] Verlauf-Tab mit Timeline/Chronik
- [ ] Relevante Datenquellen/API-Pfade klären

### [ ] PR 4 — AccountPanel mit echten Inhalten ausbauen

- [ ] Profil mit Kompetenzen/Interessen/Gütern
- [ ] Aktivität mit Beiträgen/Teilnahmen
- [ ] Knotenliste mit echten Verknüpfungen

### [ ] PR 5 — EdgePanel ausbauen

- [ ] Typ und Beschreibung ergänzen
- [ ] Zeitlichkeit konkretisieren
- [ ] Beteiligte Garnrollen ergänzen
- [ ] Quelle/Ziel sauber modellieren

⸻

## Phase 4 — Mittelfristig: Suche, Filter, Bedienbarkeit

### [ ] PR 6 — Suche als Panel-Modus umsetzen

- [ ] Suchfeld in ActionBar/TopBar einziehen
- [ ] Ergebnisse im Kontextpanel rendern
- [ ] Treffer auf der Karte markieren
- [ ] *Search als Panel-/lokalen Modus halten, nicht als vierten Global-State modellieren*

### [ ] PR 7 — Filter als Panel-/lokalen Modus umsetzen

- [ ] Filter-UI ergänzen
- [ ] Karten-/Treffer-Filterung anbinden
- [ ] *Keine neue globale Hauptzustandsklasse einführen*

### [ ] PR 8 — A11y und Keyboard-Navigation

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
