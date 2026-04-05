# Architekturkritik: Map-Schiene

> Stand: 2026-04-05 · Analysierte Revision: Gate A (Click-Dummy vollständig)

---

## Gesamtbewertung

Die Kartenimplementierung ist **funktional solide** – Gate A ist erreicht, alle 18 Playwright-Tests sind grün, die UX-Grundstruktur (Navigation / Fokus / Komposition) ist kohärent durchdacht. Als **architektonische Grundlage für Gate B und darüber hinaus taugt der aktuelle Stand jedoch nur eingeschränkt.** Die zentrale Page-Komponente trägt zu viele Verantwortlichkeiten, Overlays folgen keinem einheitlichen Muster, und mehrere Abstraktionen, die das System skalierbar und testbar machen würden, fehlen vollständig.

| Dimension | Bewertung | Begründung |
|---|---|---|
| Separation of Concerns | 4/10 | Page orchestriert Such-, Filter- und Selektionslogik selbst |
| Kopplung | 4/10 | Direkte Overlay-Instantiierung, implizite DOM-Verträge |
| Abstraktionstiefe | 3/10 | Kein SelectionService, kein MapOverlayManager |
| State-Ownership | 5/10 | Stores klar, aber Panels haben Dual-Sources |
| Testbarkeit | 3/10 | Direkte MapLibre-/API-Aufrufe, kaum Unit-Tests |
| Typsicherheit | 6/10 | TypeScript vorhanden, Invarianten nicht kodiert |
| Dokumentation | 5/10 | Roadmap/Status-Docs gut, Komponentenarchitektur fehlt |

---

## Befunde

### HOCH

---

#### H1 – God Component `+page.svelte` (560 Zeilen, 8+ Verantwortlichkeiten)

**Datei:** `apps/web/src/routes/map/+page.svelte`

Das zentrale Routing-Modul ist eine klassische God Component. Es übernimmt alle der folgenden Aufgaben gleichzeitig:

| Verantwortlichkeit | Zeilen |
|---|---|
| Rohdaten → `RenderableMapPoint` transformieren | 33–66 |
| Suchalgorithmus (Substring-Match, Resultate, Match-IDs) | 87–104 |
| Filter-Typderivation (`availableFilterTypes`) | 116–135 |
| Gefilterte Marker berechnen | 137–139 |
| Kanten nach Markersichtbarkeit filtern | 81–84 |
| Marker-Click-Delegation | 257–270 |
| Karten-Initialisierung (128-zeiliger `onMount`-Block) | 272–400 |
| Overlay-Lifecycle (Init, Update, Cleanup) | 318–370 |
| Fokus-Restauration nach Panel-Schließung | 218–234 |
| DOM-Styling (CSS-Block) | 386–560 |

**Folge:** Jede Änderung – am Suchalgorithmus, am Filter-UI, an einem Overlay – riskiert Regressionen in völlig unverwandten Bereichen. Die Komponente ist in ihrer jetzigen Form kaum isoliert testbar.

**Empfehlung:**
- Suchalgorithmus → `SearchService` oder erweiterten `searchStore`
- Filter-Derivation → `filterStore` als Derived Store
- Overlay-Lifecycle → `MapOverlayManager`-Klasse
- Karten-Init → eigene `createMap()`-Utility oder Sub-Komponente

---

#### H2 – Fehlende Overlay-Abstraktion / vier inkonsistente Patterns

**Dateien:** `overlay/nodes.ts`, `overlay/edges.ts`, `overlay/komposition.ts`, `overlay/focus.ts`

Die vier Overlays haben fundamental unterschiedliche APIs:

| Overlay | Pattern | API |
|---|---|---|
| `NodesOverlay` | Klasse | `constructor(map)` · `update(...)` · `destroy()` |
| `updateEdges` | Reine Funktion | Direkt aufgerufen, kein Lifecycle |
| `setupKompositionInteraction` | Setup + Cleanup-Return | `() => cleanupFn` |
| `setupFocusInteraction` | Setup + Callback | `(map, getStateFn) => cleanupFn` |

Hinzu kommt: `apps/web/src/lib/stores/overlayManager.ts` (20 Zeilen) existiert, wird aber **nirgends importiert** – toter Code, der die ursprüngliche Absicht andeutet, aber nie realisiert wurde.

**Folge:** Wer ein neues Overlay ergänzt, hat keine kanonische Vorlage. Der Lifecycle wird fragmentiert in `onMount`, in reaktiven Blöcken und im Cleanup-Return der Page-Komponente verwaltet.

**Empfehlung:** Einheitliches Interface einführen:

```ts
// apps/web/src/lib/map/overlay/types.ts
export interface MapOverlay {
  initialize(map: MapLibreMap): void;
  update(data: MapOverlayData): void;
  destroy(): void;
}
```

Alle Overlays implementieren dieses Interface. `MapOverlayManager` übernimmt Lifecycle-Koordination. `overlayManager.ts` entweder mit Inhalt füllen oder löschen.

---

### MITTEL

---

#### M1 – Suchalgorithmus am falschen Ort

**Datei:** `apps/web/src/routes/map/+page.svelte` L87–104 · `apps/web/src/lib/stores/searchStore.ts`

Der `searchStore` verwaltet nur UI-State (`isSearchOpen`, `searchQuery`). Der eigentliche Suchalgorithmus – inklusive Substring-Matching, Resultateliste und `searchMatchIds` – lebt als reaktiver Block in der Page-Komponente:

```svelte
$: {
  if ($isSearchOpen && $searchQuery.trim().length > 0) {
    const q = $searchQuery.toLowerCase();
    filteredResults = searchBaseData.filter(m => {
      const titleMatch = m.title?.toLowerCase().includes(q);
      const summaryMatch = m.summary?.toLowerCase().includes(q);
      return titleMatch || summaryMatch;
    }).slice(0, 10);
    searchMatchIds = new Set(filteredResults.map(r => r.id));
  }
}
```

`filteredResults` und `searchMatchIds` sind lokaler Component-State. Kein anderes Modul kann die Suchlogik wiederverwenden oder testen.

**Empfehlung:** Suchlogik in `searchStore` oder separaten `SearchService` auslagern. `searchMatchIds` als Derived Store exportieren.

---

#### M2 – Filter-Typderivation am falschen Ort

**Datei:** `apps/web/src/routes/map/+page.svelte` L116–141

`availableFilterTypes` – die Liste der in der Filter-UI angezeigten Typen mit Zählern – wird in jedem Reactive Cycle der Page-Komponente neu berechnet und als Prop an `FilterOverlay` weitergereicht. Die Hilfsfunktion `getFilterTypeKey()` ist zudem zweifach implementiert (L117 und L194 verwenden identische Logik).

`filterStore` managed nur `isFilterOpen` und `activeFilters`. Wer die Datenhoheit für "welche Typen gibt es?" hat, ist unklar.

**Empfehlung:** `availableFilterTypes` als `derived()`-Store in `filterStore.ts` berechnen, mit Memoizing. `getFilterTypeKey()` einmalig als exportierte Utility definieren.

---

#### M3 – Keine Laufzeit-Datenvalidierung im Page Loader

**Datei:** `apps/web/src/routes/map/+page.ts`

```ts
async function fetchResource<T>(resource: string, fallback: T[] = []): Promise<T[]> {
  try {
    const res = await fetch(`${apiUrl}/api/${resource}`);
    if (res.ok) {
      return await res.json(); // ← cast via Generic, keine Laufzeitprüfung
    }
  } catch (e) { ... }
  return fallback;
}
```

TypeScript-Generics sind eine Compile-Time-Aussage. Zur Laufzeit kann `res.json()` beliebige Daten liefern – z. B. `{"error": "DB unavailable"}` statt `Node[]`. Die Komponente crasht dann bei `n.location.lat`.

**Empfehlung:** Schema-Validierung mit `zod` oder einem einfachen Guard am Fetch-Boundary. Unterscheidung zwischen "API nicht erreichbar" (→ Fallback-Array) und "API antwortet mit ungültigem Schema" (→ Fehlermeldung).

---

#### M4 – Dual Data Sources in Panels

**Dateien:** `NodePanel.svelte`, `EdgePanel.svelte`, `AccountPanel.svelte`

Alle Detail-Panels lesen Daten aus zwei Quellen gleichzeitig:

1. `$selection.data` (Store – Schnellanzeige aus dem Lade-Payload)
2. Eigenständiger API-Fetch beim Öffnen (vollständige Detaildaten)

Fallback-Muster:
```ts
{nodeDetails?.title || $selection?.data?.title || $selection?.id}
```

Wenn Store-Daten und API-Daten divergieren (z. B. nach einem Update), zeigt die UI inkonsistente Inhalte. Es gibt keinen definierten API-Vertrag: Ist `.data` eine vollständige Repräsentation oder nur eine Preview?

**Empfehlung:** Klare Entscheidung treffen:
- **Option A:** Orchestrator pre-fetcht Details bei Selektion; Panels bekommen vollständige Daten als Prop (kein eigener Fetch).
- **Option B:** Panels sind alleinige Eigentümer ihres Fetches; `.data` im Selection-Store wird entfernt.

Option A bevorzugt (weniger Netzwerk-Requests, zentrales Error-Handling).

---

#### M5 – Kein einheitlicher Selektions-Einstiegspunkt

**Datei:** `apps/web/src/routes/map/+page.svelte` L164–184

Zwei getrennte Code-Pfade führen zur gleichen Selektion:
- Marker-Klick → `focusAndFlyToPoint()` (L257–270)
- Such-Resultat-Auswahl → ebenfalls `focusAndFlyToPoint()` (L184)

Beide Pfade sind identisch, aber unabhängig verdrahtet. Bei einem zukünftigen dritten Einstiegspunkt (z. B. Deep-Link, Liste) muss erneut dupliziert werden.

**Empfehlung:** `SelectionService` mit einer einzigen `select(item)`-Methode als Einstiegspunkt für alle Selektionspfade.

---

### NIEDRIG

---

#### N1 – Marker-Click per Event-Delegation mit implizitem DOM-Vertrag

**Datei:** `apps/web/src/routes/map/+page.svelte` L257–270 ↔ `overlay/nodes.ts`

Der Click-Handler auf dem Map-Container (`L279`) erwartet Buttons mit CSS-Klasse `.map-marker` und `data-id`-Attribut. Diese werden von `NodesOverlay` erstellt. Der Vertrag ist nirgends dokumentiert – ein Umbenennen der Klasse bricht die Interaktion still.

**Empfehlung:** `NodesOverlay` sollte einen `onMarkerClick`-Callback akzeptieren und die Marker intern verdrahten. Kein globales Event-Delegation auf CSS-Klassen.

---

#### N2 – Zustandsinvarianten via Laufzeit-Watcher statt Typsystem

**Datei:** `apps/web/src/lib/stores/uiView.ts` · `apps/web/src/lib/stores/uiInvariants.ts`

Die Invariante "in `fokus` ist immer eine Selektion gesetzt; in `komposition` immer ein Draft" wird durch einen externen Watcher in `uiInvariants.ts` überwacht, nicht durch das Typsystem erzwungen.

**Empfehlung:** `AppState` als Discriminated Union modellieren:

```ts
export type AppState =
  | { tag: 'navigation' }
  | { tag: 'fokus'; selection: Selection }
  | { tag: 'komposition'; draft: KompositionDraft };
```

Compiler schließt ungültige Kombinationen aus. `uiInvariants.ts` kann entfallen.

---

#### N3 – Fäden-Styling hard-coded, keine `edge_kind`-Differenzierung

**Datei:** `apps/web/src/lib/map/overlay/edges.ts` L88–128

Alle Fäden werden identisch gezeichnet (grau, gestrichelt). Farben und Breiten sind hard-coded (`#ffffff`, `#888`), ohne Referenz auf CSS Custom Properties. Die vier semantischen Typen (`delegation`, `membership`, `ownership`, `reference`) sind visuell nicht unterscheidbar.

**Empfehlung:** `edge_kind` → Farbe/Stil-Mapping in separater Konfigurationsdatei (`edgeStyles.ts`). CSS Custom Properties für Kompatibilität mit Dark Mode.

---

#### N4 – Keine Koordinaten-Validierung in `NodesOverlay`

**Datei:** `apps/web/src/lib/map/overlay/nodes.ts` L74–79

`marker.setLngLat([item.lon, item.lat])` wird ohne Guard aufgerufen. `AccountRon`-Instanzen ohne `public_pos` können mit `undefined`-Koordinaten in den Overlay-Update gelangen. MapLibre ignoriert dies still; der Marker erscheint nicht, ohne dass eine Warnung ausgegeben wird.

**Empfehlung:**

```ts
function isValidCoordinate(lat: number, lon: number): boolean {
  return isFinite(lat) && isFinite(lon) &&
    lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}
```

Ungültige Punkte vor dem Rendering herausfiltern und als Warning loggen.

---

#### N5 – Toter und inkonsistenter Code in `types.ts`

**Datei:** `apps/web/src/lib/map/types.ts`

```ts
// Definiert, aber nie verwendet:
export interface MapPoint {
  id: string;
  lat: number;
  lng: number;  // ← 'lng', nicht 'lon'
  kind: string;
  data: Node | Account | unknown;
}

// Im Einsatz:
export interface RenderableMapPoint {
  lat: number;
  lon: number;  // ← 'lon', nicht 'lng'
  // ...
}
```

`MapPoint` ist Dead Code mit abweichender Feldbezeichnung. `RenderableMapPoint.kind` ist als optional (`kind?`) deklariert, ohne dass definiert wäre, was `kind === undefined` für die Rendering-Logik bedeutet.

**Empfehlung:** `MapPoint` löschen. `kind` entweder als required deklarieren oder den Fallback explizit machen.

---

#### N6 – Imperative Muster in reaktivem Kontext

**Datei:** `apps/web/src/routes/map/+page.svelte` L198–234

Zwei Stellen kämpfen gegen Sveltes Reaktivitätsmodell statt damit zu arbeiten:

**Filter-Tooltip (L198–210):** Manuelles `window.setTimeout` + `window.clearTimeout` + `tick().then()` für einen Animation-Reset-Trick.

**Fokus-Restauration (L218–234):** `tick().then()` mit manuellem Clear-Flag (`lastFocusedElement = null`) um eine Reaktivitätsschleife zu verhindern. Der Kommentar "Clear immediately to prevent loop" ist ein Zeichen dafür, dass das Reaktivitätsmodell hier an seine Grenzen stößt.

**Empfehlung:** Filter-Tooltip in eigene `FilterTooltip.svelte`-Komponente mit eigenem Lifecycle auslagern. Fokus-Restauration als Derived Store oder Action modellieren.

---

#### N7 – Suche skaliert nicht

**Datei:** `apps/web/src/routes/map/+page.svelte` L87–104

Client-seitiges O(n)-Substring-Matching über alle Marker. Kein Backend-Suchendpoint. `slice(0, 10)` hard-coded. Kein Fuzzy-Matching.

Für Gate A (< 100 Datenpunkte) akzeptabel. Ab Gate D (tausende Knoten) ungeeignet.

**Empfehlung:** `/api/nodes/search?q=...&limit=10` Backend-Endpoint (Rust), PostgreSQL `tsvector` oder Meili/Typesense. Client-seitige Suche als Offline-Fallback behalten.

---

## Fehlende Abstraktionen

| Abstraktion | Beschreibung | Dringlichkeit |
|---|---|---|
| `SearchService` | Suchalgorithmus, Highlight-IDs, Backend-Delegation | Gate B |
| `FilterService` | Typderivation, Filter-Anwendung, Memoizing | Gate B |
| `SelectionService` | Einziger Entry-Point für Selektion (Marker, Suche, zukünftig Deep-Link) | Gate B |
| `MapOverlayManager` | Einheitliches Interface (`initialize` / `update` / `destroy`) für alle Overlays | Gate B |
| `AppState` Discriminated Union | `navigation` / `fokus` / `komposition` typsicher als Summentyp | Gate B |

---

## Test-Coverage-Lücken

| Bereich | Aktuell | Lücken |
|---|---|---|
| `+page.svelte` | E2E only | Suchalgorithmus, Filterderviation, Datentransformation |
| `NodePanel` | Keine | Async-Fetch, Request-Abbruch, Stale-Response-Prävention, Tab-Navigation |
| `EdgePanel` | Keine | Fehlerbehandlung, Source/Target-Auflösung |
| `AccountPanel` | Keine | Tab-State, Aktivitätsliste |
| `KompositionPanel` | Integration | Formvalidierung, Submit-Flow, Fehlerfälle |
| `NodesOverlay` | Keine | Marker-Lifecycle, Suchhervorhebung, Koordinaten-Guard |
| `updateEdges` | Strukturell | Tatsächliches Layer-Rendering, GeoJSON-Validierung |
| `setupFocusInteraction` | Keine | State-Transitions, Click-Outside-Verhalten |

Hauptproblem: Es fehlt eine Unit-Test-Schicht. Die Suite springt direkt von "kein Test" zu "Playwright E2E". Logik in Services auslagern (H1, M1, M2) schafft die nötigen Test-Seams.

---

## Empfohlener Refactoring-Pfad

### Sofort (Voraussetzung Gate B)

1. **`SearchService` extrahieren** – Suchalgorithmus aus `+page.svelte` heraus, als testbare Utility
2. **`FilterService` / Derived Store** – Typderivation und Filter-Anwendung in `filterStore.ts`
3. **`KompositionPanel` Submit implementieren** – Größtes funktionales Loch; ohne dies kein Gate B

### Kurzfristig (Gate B)

4. **`SelectionService`** – Einheitlicher Einstiegspunkt für alle Selektionspfade
5. **Datenstrategie in Panels klären** – Dual-Sources auflösen (Empfehlung: Option A, Pre-fetch im Orchestrator)
6. **Unit-Tests für extrahierte Services**

### Mittelfristig (Gate C)

7. **`MapOverlayManager`** – Einheitliches Overlay-Interface, `overlayManager.ts` entweder implementieren oder löschen
8. **`AppState` als Discriminated Union** – `uiInvariants.ts` Watcher ersetzen
9. **Koordinaten-Guard** in `NodesOverlay`
10. **Fäden-Styling konfigurierbar** (`edge_kind` → Farbe/Stil)

### Langfristig (Gate D+)

11. **Backend-Suchendpoint** (`/api/nodes/search`)
12. **SSE / JetStream** für Echtzeit-Updates
13. **Memoizing** für Filter-Derivation bei großen Datensätzen
14. **Laufzeit-Datenvalidierung** im Page Loader (z. B. `zod`)
