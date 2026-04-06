# Architekturkritik: Map-Schiene (v4)

> Stand: 2026-04-06 · Format: weltgewebe.architecture.critique.v4
> Analysierte Revision: Gate A, 18 Testdateien

---

## These

Die Map-Schiene funktioniert. Gate A ist erreicht. Die UX-Grundstruktur Navigation / Fokus / Komposition ist kohärent. 18 Playwright-Tests sind grün, darunter ein dedizierter Guard-Test (`no-activity-heatmap.spec.ts`), der das frühere Bereinigen des Activity-Overlays absichert.

Gleichzeitig trägt `apps/web/src/routes/map/+page.svelte` mindestens acht Verantwortlichkeiten gleichzeitig. Suchalgorithmus und Filter-Derivation liegen nicht in ihren zugehörigen Stores, sondern direkt im Orchestrator. Vier Overlays folgen vier verschiedenen API-Patterns. Die Detail-Panels lesen aus zwei Quellen gleichzeitig. Zustandsinvarianten werden zur Laufzeit bewacht statt durch das Typsystem erzwungen.

Das sind keine Geschmacksfragen. Das sind Stellen, an denen jede neue Funktion in Gate B mit vorhersehbarem Mehraufwand kämpfen wird.

---

## Antithese

Ein Teil der Kritik ist ungenau oder zu stark formuliert.

**`overlayManager.ts` ist kein toter Code.** Die Datei exportiert `toggleSearchExclusive()` und `toggleFilterExclusive()` und wird in `apps/web/src/lib/components/ActionBar.svelte` (L5) importiert und verwendet. Das eigentliche Problem ist ein Namens- und Abstraktionsproblem: Die Datei heißt `overlayManager`, verwaltet aber keine Map-Overlays, sondern die gegenseitige Exklusivität von Search- und Filter-UI-Panels. Der Name suggeriert Verantwortlichkeit, die sie nicht hat.

**Das Activity-Overlay ist kein offener Befund.** `apps/web/src/lib/map/overlay/activity.ts` existiert nicht. Es wurde bereits entfernt. Der Test `no-activity-heatmap.spec.ts` sichert diese Bereinigung dauerhaft ab. Hier gibt es nichts zu korrigieren.

**`O(n)`-Suche ist für den aktuellen Kontext ein vernünftiger MVP-Tradeoff.** Das Skalierungsproblem ist real, aber kein Gate-A-Fehler.

**Die God-Component-Diagnose ist richtig, aber die Wertung bedarf einer Gegenfrage:** Ist `+page.svelte` eine God Component im pathologischen Sinn, oder ist sie ein ehrlicher Orchestrator-Knoten des Kartenmodus? Der Unterschied liegt nicht in der Zeilenzahl, sondern darin, ob Änderungen unbeherrschbar werden. Das ist bisher noch nicht eingetreten – aber das Risiko steigt mit jedem Gate.

---

## Synthese

Die Strukturdiagnose stimmt überwiegend. Die Schlussfolgerungen sind überwiegend tragfähig. Drei Befunde der v1-Kritik müssen korrigiert werden.

### Befunde: belegt

Direkt im Code nachweisbar, keine Interpolation nötig.

| ID | Befund | Nachweis |
|---|---|---|
| **B1** | Suchalgorithmus sitzt in `+page.svelte`, nicht in `searchStore` | L87–104: reaktiver Block mit `searchBaseData.filter(...).slice(0,10)`; `searchStore.ts` enthält nur `isSearchOpen` / `searchQuery` |
| **B2** | Filter-Typderivation sitzt in `+page.svelte`, nicht in `filterStore` | L116–135: `availableFilterTypes`-IIFE; `filterStore.ts` enthält nur Toggles |
| **B3** | Loader validiert API-Antworten nicht zur Laufzeit | `+page.ts`: `return await res.json()` via Generic `<T>` ohne Guard |
| **B4** | Panels lesen aus zwei Quellen (Dual-Sources) | `EdgePanel.svelte`: `edgeDetails?.edge_kind \|\| $selection?.data?.edge_kind \|\| 'Faden'` |
| **B5** | Invarianten-Watcher statt Typsystem | `uiInvariants.ts`: `assertUiStateInvariant()` + `setupUiInvariantWatcher()` |
| **B6** | Impliziter DOM-Vertrag `.map-marker` + `data-id` | `nodes.ts`: `element.dataset.id = item.id`; `+page.svelte` L279: Click-Delegation auf `.map-marker` |
| **B7** | Vier inkonsistente Overlay-APIs | `NodesOverlay` (Klasse), `updateEdges` (Funktion), `setupKompositionInteraction` (Setup+Cleanup), `setupFocusInteraction` (Setup+Callback) |
| **B8** | Fäden-Styling hard-coded | `edges.ts` L88–90: `#ffffff` (Halo), `#888` (Hauptlinie), `[2,1]` Dash, keine CSS-Custom-Properties |
| **B9** | `overlayManager.ts` falsch benannt | Datei heißt Map-Overlay-Manager, verwaltet aber UI-Panel-Exklusivität; importiert in `ActionBar.svelte` L5 |
| **B10** | `MapPoint` in `types.ts` ungenutzt | Interface mit `lng` (nicht `lon`) definiert; `RenderableMapPoint` (mit `lon`) wird verwendet |

### Befunde: plausibel

Logisch aus dem Code ableitbar, vollständige Beweiskette fehlt.

| ID | Befund | Begründung der Einschränkung |
|---|---|---|
| **P1** | Koordinaten-NaN-Pfad bei `AccountRon` ohne `public_pos` | `nodes.ts` L74–79 vergleicht `item.lon` numerisch ohne Guard; ob ein `AccountRon` tatsächlich mit `undefined`-Koordinaten bis `update()` gelangt, hängt von der Filterung in `+page.svelte` ab – nicht vollständig geprüft |
| **P2** | Fokus-Restauration fragil bei gefiltertem Marker | `+page.svelte` L218–234 stellt `lastFocusedElement` wieder her; wenn der Marker durch Filter aus dem DOM entfernt wurde, schlägt `focus()` still fehl |
| **P3** | Suche skaliert nicht ab Gate D | Mechanismus klar (O(n) client-seitig), aber konkrete Grenzwerte sind Schätzungen |

### Befunde: zu korrigieren

In v1 falsch oder unvollständig behauptet.

| ID | v1-Behauptung | Korrektur |
|---|---|---|
| **K1** | `overlayManager.ts` = toter Code | Falsch. Importiert in `ActionBar.svelte` L5. Problem ist Namensverwirrung, nicht Nichtverwendung. |
| **K2** | Activity-Overlay als implizit aktiver Befund | Nicht zutreffend. `activity.ts` existiert nicht. `no-activity-heatmap.spec.ts` sichert die Abwesenheit ab. |
| **K3** | „18 Tests, Gate A" ohne Kontext | Stimmt zahlenmäßig (18 `.spec.ts`), aber einer davon (`no-activity-heatmap.spec.ts`) ist ein Regressions-Guard für bereits erledigte Bereinigung – keine Gate-A-Neuleistung. |

---

## Fehlende Abstraktionen

| Abstraktion | Problem, das sie löst | Gate |
|---|---|---|
| `SearchService` | Suchalgorithmus aus `+page.svelte` (B1), testbar, delegierbar | B |
| Derived Filter-Store | Filter-Derivation aus `+page.svelte` (B2), mit Memoizing | B |
| `SelectionService` | Zwei unverbundene Einstiegspunkte (Marker-Klick + Suche) vereinen | B |
| `MapOverlay`-Interface | Einheitliche API für alle Overlays (B7): `initialize / update / destroy` | C |
| `AppState` Discriminated Union | Invarianten-Watcher (B5) durch Typsystem ersetzen | C |

---

## Test-Coverage-Lücken

Die Suite hat keine Unit-Test-Schicht. Der Sprung geht direkt von „keine Tests" zu Playwright E2E. Das macht Logik-Regressions-Tests teuer und langsam.

| Bereich | Lücken |
|---|---|
| Such- / Filterlogik | Unit-Tests fehlen; Logik liegt in Komponente, kein Test-Seam |
| `NodePanel` / `EdgePanel` / `AccountPanel` | Async-Fetch, Request-Abbruch, Stale-Response-Prävention |
| `KompositionPanel` | Formvalidierung, Submit-Flow (funktionales Loch) |
| `NodesOverlay` | Marker-Lifecycle, Koordinaten-Guard |
| `setupFocusInteraction` | State-Transitions, Click-Outside |

---

## Alternative Sinnachse

Die Kritik denkt in klassischer Frontend-Schichtarchitektur: Service hier, Store dort, Manager dort. Das ist sinnvoll. Aber eine andere Lesart wäre: `+page.svelte` ist der ehrliche Orchestrator-Knoten des Kartenmodus – eine Art lokale Regiezentrale, die bewusst alle Fäden hält.

Nicht jede große Komponente ist eine God Component. Manche sind einfach Sammelstellen. Die entscheidende Frage ist nicht „Wieviele Zeilen?", sondern: „Wächst die Änderungsangst schneller als der Nutzen?"

Für Gate A: noch nicht. Für Gate B, wenn KompositionPanel wirklich submittiert, Edge-Typen visuell unterschieden werden und Echtzeit-Updates hinzukommen: dann wird der Orchestrator eng.

---

## Für Dummies

- Die Karte funktioniert, sieht gut aus, ist gut getestet.
- Intern ist aber eine Datei dafür zuständig, was eigentlich vier Dateien sein sollten.
- Die Suchfunktion wohnt am falschen Ort.
- Drei Behauptungen der letzten Kritik waren zu scharf: eine Datei, die als „tot" bezeichnet wurde, wird tatsächlich benutzt; ein Overlay, das als Problem galt, wurde längst entfernt.
- Die Karte ist solide für heute. Für morgen braucht sie mehr Struktur.

---

## Essenz

**Hebel:** Such- und Filterlogik aus `+page.svelte` heraus in testbare Services. Das schafft den größten Gewinn mit dem kleinsten Aufwand – Testbarkeit, klarere Datenhoheit, weniger reaktive Kaskaden.

**Entscheidung:** Diese Kritik ist als Refactoring-Grundlage geeignet, nicht als heilige Schrift. Drei Punkte sind als korrigiert zu markieren (K1–K3).

**Nächste Aktion:** Gate B beginnt mit dem KompositionPanel-Submit – das ist das größte funktionale Loch. Danach: SearchService extrahieren, Filter-Derivation in Store verschieben, Overlay-Interface vereinheitlichen.

---

**Unsicherheitsgrad:** 0.15
Ursachen: Für P1 (Koordinaten-NaN) fehlt der vollständige Datenpfad von AccountRon bis `setLngLat`. Alles andere ist direkt im Code nachweisbar oder durch den User-Review korrigiert.

**Interpolationsgrad:** 0.12
Hauptquelle: P3 (Skalierungsgrenzwerte der Suche) beruht auf allgemeinen Faustregeln, nicht auf Profiling.

---

*Architekturkritik ist wie eine Wetterkarte: Sie zeigt die Fronten korrekt, aber nicht, ob es an genau deiner Haustür regnet. Die Fronten hier sind real.*
