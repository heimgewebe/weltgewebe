---
id: docs.blueprints.kartenklarheit-roadmap
title: Roadmap – Kartenklarheit
doc_type: roadmap
status: active
relations:
  - type: relates_to
    target: docs/blueprints/kartenklarheit.md
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
  - type: relates_to
    target: docs/blueprints/map-roadmap.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
summary: Abhakbare Umsetzungsroadmap zur Optimierung der Kartenarchitektur von stiller Leere zu expliziter Szene.
---

# Roadmap – Kartenklarheit

Statuslegende: `[ ] offen`, `[~] in Arbeit`, `[x] erledigt`

## Ziel

Die Karte soll von einer impliziten Orchestrierung zu einer expliziten, fehlertoleranten, testbaren und erweiterbaren Kartenarchitektur weiterentwickelt werden.

## Erfolgskriterien auf oberster Ebene

- [x] API-Fehler erzeugen keinen still normalen Leerzustand mehr.
- [x] Die Kartenroute liefert ein explizites Route-Modell mit Ladezustand.
- [x] Die Karten-UI konsumiert eine Szene statt lose Rohdatenlogik.
- [x] Map-Entitäten sind typseitig diskriminiert statt weich optional.
- [x] API-Modus und Basemap-Modus sind separat sichtbar.
- [~] Neue Overlays können ergänzt werden, ohne dass `apps/web/src/routes/map/+page.svelte` erneut unsichtbar Verantwortung aufsammelt. → Strukturelle Voraussetzungen (scene.ts, NodesOverlay, edges.ts) sind geschaffen; dies ist eine Architekturfolgebehauptung, kein direkt beweisbares Ergebnis.

---

## Phase 0 – Ausgangslage sichern

### Ziel der Phase 0

Vor jeder Änderung die aktuelle Map-Schiene, ihre Pfade und ihre Tests als Referenz sichern.

### Arbeitspakete für Phase 0

- [x] Relevante Einstiegspfade dokumentieren:
  - `apps/web/src/routes/map/+page.ts`
  - `apps/web/src/routes/map/+page.svelte`
  - `apps/web/src/lib/map/types.ts`
  - `apps/web/src/lib/map/overlay/nodes.ts`
  - `apps/web/src/lib/map/config/basemap.current.ts`
- [x] Relevante vorhandene Tests sammeln:
  - `apps/web/tests/map-load-fallback.spec.ts`
  - `apps/web/tests/map-interaction.spec.ts`
  - `apps/web/tests/komposition.spec.ts`
  - `apps/web/tests/edge-visibility.spec.ts`
  - `apps/web/tests/basemap-client-integration.spec.ts`
- [x] Vorher-Zustand kurz als Ist-Notiz festhalten:
  - Loader schluckt Fehler per Fallback
  - Route und UI sind eng gekoppelt
  - Szenenmodell fehlt
  - Debug-Semantik ist nur teilweise getrennt

### Stop-Kriterium für Phase 0

- [x] Die betroffenen Dateien und Tests sind eindeutig benannt.
- [x] Es gibt eine kurze Ist-Notiz als Ausgangsbasis für spätere Reviews.

---

## Phase 1 – Laufzeitwahrheit einziehen

### Ziel der Phase 1

Aus stiller Fehlerverdeckung wird explizite Kartenwahrheit.

### Arbeitspakete für Phase 1

- [x] `MapLoadState` definieren (`ok | partial | failed`).
- [x] `MapResourceStatus` definieren.
- [x] `apps/web/src/routes/map/+page.ts` so erweitern, dass die Route nicht nur `nodes`, `accounts`, `edges`, sondern auch `loadState` und `resourceStatus` zurückgibt.
- [x] Fehler je Ressource klassifizieren statt nur implizit auf Fallback-Arrays zu reduzieren.
- [x] Für degradierte Zustände klare Regeln definieren:
  - [x] Wann gilt `partial`? → Wenn mindestens eine Ressource fehlschlägt, aber nicht alle.
  - [x] Wann gilt `failed`? → Wenn alle Ressourcen fehlschlagen.
- [x] `apps/web/src/routes/map/+page.svelte` so anpassen, dass `partial` sichtbar kommuniziert wird.
- [x] `apps/web/src/routes/map/+page.svelte` so anpassen, dass `failed` nicht wie normale Leere aussieht.
- [x] UI-Texte für degradierte Zustände knapp und eindeutig formulieren.

### Verifikation für Phase 1

- [x] `apps/web/tests/map-load-fallback.spec.ts` auf neuen Route-/UI-Zustand anpassen.
- [x] Neuer Testfall für `partial` ergänzt.
- [x] Neuer Testfall für `failed` ergänzt.
- [x] Manuell geprüft: Leere Karte ist nicht mehr semantisch doppeldeutig.

### Stop-Kriterium für Phase 1

- [x] Ein API-Ausfall ist im UI als degradierter Zustand erkennbar.
- [x] Die Route hat einen expliziten Ladezustand.

---

## Phase 2 – Explizites Karten-Szenenmodell einziehen

### Ziel der Phase 2

Rohdaten und sichtbare Kartenwirklichkeit trennen.

### Arbeitspakete für Phase 2

- [x] Neues Modul einführen: `apps/web/src/lib/map/scene.ts`
- [x] `MapRouteData` definieren. → Realisiert als `MapSceneInput`.
- [x] `MapSceneModel` definieren.
- [x] Zentrale Funktion bauen, z. B. `buildMapScene(...)`.
- [x] Transformation aus `nodes/accounts/edges + loadState` in `MapSceneModel` implementieren.
- [x] Diagnostikdaten in die Szene integrieren.
- [x] `apps/web/src/routes/map/+page.svelte` auf Szenenverbrauch umstellen.
- [x] Bestehende UI-Logik prüfen:
  - [x] Suchlogik → arbeitet auf scene.entities
  - [x] Filterlogik → arbeitet auf scene.entities
  - [x] Fokuslogik → unverändert in focus.ts/uiView.ts
  - [x] Panel-Öffnung → unverändert in uiView.ts
- [x] Nur die Logik in der Route belassen, die wirklich View-spezifisch ist.

### Verifikation für Phase 2

- [x] Szene kann unabhängig von der Route gebaut und geprüft werden.
- [x] Mindestens ein Test für `buildMapScene(...)` ergänzt. → 10 Unit-Tests in scene.test.ts.
- [x] `+page.svelte` konsumiert Szene statt selbst Rohdaten zusammenzusetzen.
- [x] Keine Funktionsverluste in bestehenden Map-Interaktionstests.

### Stop-Kriterium für Phase 2

- [x] Die Karte lässt sich logisch beschreiben als: „Route lädt Daten, Szene beschreibt Sichtbarkeit.“

---

## Phase 3 – Entitäts-Contracts härten

### Ziel der Phase 3

`RenderableMapPoint` von einem weichen Sammeltyp zu einem klaren Entitätssystem entwickeln.

### Arbeitspakete für Phase 3

- [x] Ist-Zustand von `RenderableMapPoint` dokumentieren:
  - [x] Welche Felder sind optional? → `type`, `kind`, `tags`, `weight`, `info`, `modules`, `created_at`, `updated_at`
  - [x] Welche Felder werden real genutzt? → `id`, `title`, `lat`, `lon`, `type`, `summary`, `kind`, `modules`
- [x] Zielmodell für diskriminierte Union entwerfen.
- [x] Varianten definieren:
  - [x] `node` → `MapEntityNode` (type: "node")
  - [x] `garnrolle` → `MapEntityGarnrolle` (type: "garnrolle")
  - [x] `ron` → Ausgeschlossen: hat keine Position, nicht kartenrelevant
  - [x] `account` → Vereinheitlicht als `garnrolle` (einziger kartenfähiger Account-Typ)
- [x] `MapEntityViewModel` oder Nachfolger sauber typisieren. → `MapEntityViewModel = MapEntityNode | MapEntityGarnrolle`
- [x] `apps/web/src/lib/map/overlay/nodes.ts` auf echte Varianten umstellen.
- [x] Marker-Kategorisierung nicht mehr über lose String-Vermischung laufen lassen.
- [x] Genau eine Koordinatenkonvention festlegen. → lat/lon (nicht lat/lng).
- [x] Repo-weite Prüfung durchführen, ob `MapPoint` noch gebraucht wird. → Nein, nur in Definition und einem Kommentar.
- [x] `MapPoint` nur dann entfernen oder entwerten, wenn seine tatsächliche Nutzung belegt ausgeschlossen ist. → Deprecated mit JSDoc.

### Verifikation für Phase 3

- [x] Typsystem erzwingt Entitätsvarianten explizit.
- [x] Marker-/Overlay-Logik arbeitet ohne semantische Ratespiele.
- [x] Mindestens ein Test deckt die Variantenlogik ab. → scene.test.ts testet Entity-Transformation.
- [x] Keine implizite Gleichsetzung von `account` und `garnrolle` mehr ohne explizite Entscheidung.

### Stop-Kriterium für Phase 3

- [x] Die Karten-Entitäten sind compile-time-seitig klar unterscheidbar.

---

## Phase 4 – Modus- und Diagnostik-Semantik trennen

### Ziel der Phase 4

API-Herkunft und Basemap-Modus separat sichtbar machen.

### Arbeitspakete für Phase 4

- [x] Diagnostikmodell definieren:
  - [x] `apiMode`
  - [x] `basemapMode`
  - [x] `degraded`
- [x] Bestehenden Debug-Hinweis prüfen und umstellen.
- [x] Begriffe schärfen:
  - [x] API: `remote` / `local`
  - [x] Basemap: `local-sovereign` / `remote-style`
- [x] Optional: `MapDiagnostics.svelte` einführen → Nicht nötig: Diagnostik ist Teil des MapSceneModel und wird im Debug-Badge angezeigt.
- [x] Sichtbarkeitsregel definieren:
  - [x] nur DEV/Test → Ja, wie bisher.

### Verifikation für Phase 4

- [x] Im Debugzustand sind API-Modus und Basemap-Modus getrennt sichtbar.
- [x] Keine trügerische Ein-Modus-Semantik mehr.
- [x] Mindestens ein Test oder Snapshot prüft den Diagnostikzustand. → Test in map-load-fallback.spec.ts.

### Stop-Kriterium für Phase 4

- [x] Ein Entwickler kann auf einen Blick erkennen, woher Daten kommen und wie die Basemap läuft.

---

## Phase 5 – Zustands-Ownership klären

### Ziel der Phase 5

Nicht Dateigröße bekämpfen, sondern Zuständigkeiten explizit machen.

### Arbeitspakete für Phase 5

- [x] Ownership-Matrix schreiben:
  - [x] Was lebt in Stores? → uiView (systemState, selection, kompositionDraft), searchStore, filterStore
  - [x] Was lebt in `+page.svelte`? → Filter-Derivationen, Edge-Filter, Map-Instanz, Overlay-Lifecycle
  - [x] Was lebt implizit in MapLibre? → Canvas, Style, Navigation Controls
  - [x] Was lebt in Overlay-Modulen? → DOM-Markers (NodesOverlay), GeoJSON-Layers (edges.ts)
- [x] Für jede relevante Zustandsklasse eine Quelle-der-Wahrheit festlegen. → Dokumentiert in uiView.ts.
- [x] Nur auf Basis dieser Matrix entscheiden, was aus `+page.svelte` herausgezogen wird.
- [x] Selektive Extraktion nur dort, wo echte semantische Entlastung entsteht:
  - [x] Szenenaufbau → scene.ts (buildMapScene)
  - [x] Diagnostik → MapDiagnostics im Scene-Model
  - [x] Interaktionskoordination → focus.ts, komposition.ts (bereits extrahiert)
  - [x] Overlay-Koordination → NodesOverlay, edges.ts (bereits extrahiert)

### Verifikation für Phase 5

- [x] Es gibt eine explizite Ownership-Matrix. → In uiView.ts als JSDoc.
- [x] Keine rein kosmetische Datei-Zerlegung.
- [x] Extraktion reduziert semantische Last, nicht nur Zeilenanzahl.

### Stop-Kriterium für Phase 5

- [x] Die wichtigsten Zustände haben eine klar benannte Quelle der Wahrheit.

---

## Phase 6 – Härtung und Regression

### Ziel der Phase 6

Die neue Kartenarchitektur gegen Rückfall schützen.

*Hinweis: Geschriebene Tests allein genügen nicht. Phase 6 ist erst abgeschlossen, wenn die Beweisdefinition aus [Kartenklarheit Phase 6](kartenklarheit-phase6.md) systemisch durchgesetzt ist.*

### Arbeitspakete für Phase 6

- [x] Relevante Testsuite vollständig durchlaufen. → 39/39 Unit-Tests (vitest) grün; 22/22 E2E-Tests (Playwright/Chromium) grün (2026-04-23).
- [x] Fehlerszenarien gezielt prüfen. → Playwright-Tests im echten Browser verifiziert:
  - [x] Nodes fehlen → `map-load-fallback.spec.ts` (failed state) grün
  - [x] Accounts fehlen → `map-load-fallback.spec.ts` (partial state) grün
  - [x] Edges fehlen → `map-load-fallback.spec.ts` (partial state) grün
  - [x] mehrere Ressourcen fehlen → `map-load-fallback.spec.ts` (failed state) grün
- [x] Interaktionsszenarien erneut prüfen. → `map-interaction.spec.ts` im echten Browser verifiziert:
  - [x] Suche → `map-interaction.spec.ts` grün
  - [x] Filter → `map-interaction.spec.ts` grün
  - [x] Fokus → `map-interaction.spec.ts` grün, kein Regressionrisiko
  - [x] Komposition → `map-interaction.spec.ts` grün, kein Regressionrisiko
- [x] Basemap-/Diagnostik-Szenarien erneut prüfen. → `map-load-fallback.spec.ts` (Debug-Badge), `basemap-sovereignty-testbuild.spec.ts`, `basemap-client-integration.spec.ts` im echten Browser grün.
- [~] Basemap-Runtime-Beweis (Caddy + echtes PMTiles-Artefakt + HTTP 206). → Ausstehend: erfordert vollständigen Docker-Stack mit realem PMTiles-Byte-Stream.
- [x] Dokumentation aktualisieren:
  - [x] `docs/blueprints/kartenklarheit-roadmap.md` → Diese Datei
  - [x] `docs/reports/map-status-matrix.md` → Aktualisiert mit Kartenklarheit-Nachtrag und verifizierten Testständen (2026-04-23)
  - [x] `docs/reports/map-architekturkritik.md` → Nachtrag-Evidenzlage mit E2E-Verifikationsstand ergänzt (2026-04-23)

### Verifikation für Phase 6

- [x] Keine Regression in Kerninteraktionen. → 39/39 Unit-Tests + 22/22 E2E-Tests grün (2026-04-23).
- [x] Dokumentation entspricht dem tatsächlichen Zustand. → Roadmap, map-status-matrix und map-architekturkritik aktualisiert.

### Stop-Kriterium für Phase 6

- [x] Die Karte ist expliziter, testbarer und semantisch klarer als zuvor. → Code, Unit-Tests und E2E-Tests belegen Verbesserung. Einzig ausstehend: Caddy+PMTiles-E2E-Nachweis mit echtem Byte-Stream (infrastruktureller CI-Ausbau).

---

## Minimalpfad, falls Kapazität knapp ist

### Ziel des Minimalpfads

Mit kleinem Eingriff maximalen Wahrheitsgewinn erzielen.

- [x] `MapLoadState` einführen
- [x] `resourceStatus` einführen
- [x] degradiertes UI für `partial` / `failed`
- [x] `apps/web/tests/map-load-fallback.spec.ts` und neue Fehlerfälle anpassen
- [x] API-/Basemap-Modus im Debug-Hinweis trennen

### Minimalpfad erfolgreich, wenn

- [x] Leere Karte nicht mehr still normal wirkt
- [x] zentrale Diagnostik klarer geworden ist
- [x] ohne großen Umbau spürbare Wahrheitsverbesserung erreicht wurde

---

## Nicht-Ziele

- [x] Kein bloß kosmetisches Zerteilen von `+page.svelte` → Eingehalten.
- [x] Kein Stil-Refactoring ohne semantischen Gewinn → Eingehalten.
- [x] Keine voreilige Entfernung von `MapPoint` ohne repo-weiten Nachweis → Deprecated statt entfernt.
- [x] Keine Vermischung von Kartenoptimierung mit Basemap-Souveränitätsprogramm, sofern nicht diagnostisch nötig → Eingehalten.

---

## Abschlusskriterium

Die Roadmap ist erfüllt, wenn:

- [x] die Karte degradierte Zustände explizit zeigt,
- [x] ein Szenenmodell existiert,
- [x] die wichtigsten Karten-Entitäten hart typisiert sind,
- [x] die Diagnostik getrennte Betriebsachsen zeigt,
- [x] Zustands-Ownership nicht mehr implizit im Routenorchestrator verschwindet.

---

## Essenz

**Hebel:** Laufzeitwahrheit → Szenenmodell → Typenhärtung.
**Entscheidung:** Erst explizit machen, dann aufräumen.
**Status:** Phasen 1–6 umgesetzt. 39/39 Unit-Tests + 22/22 E2E-Tests grün (2026-04-23). Dokumentation aktualisiert. Einzig ausstehend: Caddy+PMTiles-E2E-Nachweis mit echtem Byte-Stream.
