---
id: ui-state-machine
title: Weltgewebe UI State Machine
doc_type: blueprint
status: canonical
summary: Kanonische Zustandsmaschine der Weltgewebe-UI und verbindliche Implementierungsregeln.
---



## # 1 Ziel

Die UI besitzt eine einzige globale Interaktionslogik.

Ziele:

- widerspruchsfreie UI-Zustände
- deterministische Interaktionen
- testbare Übergänge
- Vermeidung von UI-Drift

Die State Machine beschreibt nur Frontend-Interaktion, nicht Backend-Logik.

## # 2 Kanonische Zustände

Die UI kennt genau drei globale Zustände:

- `navigation`
- `fokus`
- `komposition`

Kein weiterer globaler Zustand darf eingeführt werden ohne Anpassung dieses Dokuments.

## # 3 State-Machine-Diagramm

```text
navigation
   │
   │ marker click
   ▼
fokus
   │
   │ close / empty map click
   ▼
navigation


navigation
   │
   │ action bar / longpress
   ▼
komposition
   │
   │ cancel / close
   ▼
navigation
```

## # 4 Kanonische Zustandsdaten

### `systemState`

```typescript
type SystemState =
  | "navigation"
  | "fokus"
  | "komposition"
```

Diese Variable ist die einzige globale Zustandsquelle.

### `selection`

```typescript
type Selection =
  | {
      type: "node" | "edge" | "account" | "garnrolle"
      id: string
      data?: unknown
    }
  | null
```

#### Selection Invarianten

- `systemState === "fokus"` → `selection !== null`
- `systemState === "navigation"` → `selection === null`
- `systemState === "komposition"` → `selection === null`

### `kompositionDraft`

```typescript
type KompositionDraft =
  | {
      mode: "new-knoten"
      lngLat?: [number, number]
      source: "action-bar" | "map-longpress"
    }
  | null
```

#### KompositionDraft Invarianten

- `systemState === "komposition"` → `kompositionDraft !== null`
- `systemState !== "komposition"` → `kompositionDraft === null`

### `contextPanelOpen`

**Derived state:**
`contextPanelOpen = systemState !== "navigation"`

Es darf keine zweite Open-State-Quelle existieren.

## # 5 Erlaubte Übergänge

### navigation → fokus

- Trigger: Marker-Klick, Objekt-Klick
- Effekt: `selection = { ... }`, `systemState = "fokus"`

### navigation → komposition

- Trigger: ActionBar → Neuer Knoten, Longpress auf Karte
- Effekt: `kompositionDraft = { ... }`, `systemState = "komposition"`

### fokus → navigation

- Trigger: empty map click, panel close
- Effekt: `selection = null`, `systemState = "navigation"`

### fokus → fokus

- Trigger: click anderes Objekt
- Effekt: selection wechseln, Tabs reset

### komposition → navigation

- Trigger: cancel, panel close, submit success
- Effekt: `kompositionDraft = null`, `systemState = "navigation"`

## # 6 Verbotene Zustände

Diese Zustände dürfen nie auftreten:

- `systemState === "fokus"` AND `selection === null`
- `systemState === "komposition"` AND `kompositionDraft === null`
- `systemState === "navigation"` AND `contextPanelOpen === true`

## # 7 Implementierungsanweisungen

### 7.1 State-Store

Datei: `apps/web/src/state/uiView.ts`

- Pflicht: `export const systemState`, `export const selection`, `export const kompositionDraft`
- Derived: `contextPanelOpen`

### 7.2 ContextPanel

Datei: `components/ContextPanel.svelte`

- Regel:
  - `if systemState === "komposition"` render KompositionView
  - `if systemState === "fokus"` render ObjektView
- Beide dürfen niemals gleichzeitig sichtbar sein.

### 7.3 Map-Interaktionen

Datei: `routes/map/+page.svelte`

- Implementieren:
  - marker click → fokus
  - empty map click → navigation
  - longpress → komposition

### 7.4 ActionBar

Datei: `components/ActionBar.svelte`

- Pflichtaktion: Neuer Knoten → navigation → komposition

## # 8 Testpflicht (Playwright)

Jeder Zustandsübergang benötigt einen Test.
Tests: `tests/map-interaction.spec.ts`

Pflichtfälle:

- **navigation:** initial state, panel closed
- **fokus:** marker click, panel open, selection gesetzt
- **fokus verlassen:** empty map click, panel closed, selection null
- **komposition:** action bar click, draft created, panel open
- **longpress:** map longpress, draft.lngLat gesetzt
- **kompositionsschutz:** empty map click, komposition bleibt aktiv

## # 9 CI-Guard gegen Zustandsdrift

Empfehlung: Unit-Test `expectInvalidState()`
Beispiel:

```typescript
if (systemState === "fokus" && !selection)
   throw Error("invalid ui state")
```

Ziel: UI-Bugs sofort sichtbar machen.

## # 10 Erweiterungsregel

Neue Zustände dürfen nicht einfach ergänzt werden.
Vor Einführung prüfen:

1. Globaler Zustand nötig?
2. Panel-Submodus ausreichend?
3. Lokaler Zustand ausreichend?

Beispiele:

- search → Panelmodus
- filter → Panelmodus
- auth → globaler Zustand

---

## Konkrete PR-Serie (Umsetzungsroadmap)

Die Umsetzung erfolgt idealerweise als gestaffelte PR-Serie.

### [ ] PR 1 — State Contract kanonisieren

**Ziel:** Die drei Hauptzustände als einzige globale Wahrheit technisch fixieren.

- [ ] Typen und Stores sauber trennen in `uiView.ts`
  (nur noch systemState, selection, kompositionDraft, contextPanelOpen).
- [ ] Invarianten zentral prüfen (z.B. Hilfsfunktion `assertUiStateInvariant`).
- [ ] Dev-only invariant watcher einbauen.

### [ ] PR 2 — ContextPanel als strikt exklusiver Detailraum

**Ziel:** Das Panel zeigt entweder Fokus oder Komposition, nie beides und nie „irgendwas“.

- [ ] `ContextPanel.svelte` zerlegen
  (Sub-Komponenten für KompositionPanel, NodePanel, etc.).
- [ ] Tab-Reset explizit machen (Standardtab beim Wechsel neu setzen).
- [ ] Komposition hart gegen Fokus entkoppeln
  (beim Eintritt in Komposition `selection` null setzen).

### [ ] PR 3 — Map-Interaktionen härten

**Ziel:** Kartenlogik robust machen.

- [ ] Zustandsübergänge in kleine Funktionen ziehen (`enterFokus`, `enterKomposition`, `leaveToNavigation`).
- [ ] Longpress-Schutz vervollständigen (Distanz prüfen, nicht auf Marker feuern).
- [ ] Fokus-Restore robuster machen.

### [ ] PR 4 — Testmatrix aus dem Dokument erzwingen

**Ziel:** Die Blaupause durch Tests beweisen.

- [ ] Stabile, testbare Leerklick-Zone bestimmen.
- [ ] Harte Tab-Assertions statt weicher Negation.
- [ ] Neue Pflichttests ergänzen (z.B. Tab-Resets, Kompositionsschutz).
