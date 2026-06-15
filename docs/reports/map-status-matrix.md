---
id: map-status-matrix
title: Map Status Matrix
doc_type: status-matrix
status: active
summary: Repo-wahre Statusmatrix fuer die aktuelle Kartenimplementierung.
relations:
  - type: relates_to
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
  - type: relates_to
    target: docs/blueprints/ui-interaction-doctrine.md
---

Dieses Dokument beschreibt den belegbaren Ist-Zustand der aktuellen
Kartenimplementierung. Massgeblich sind nur Dateien, die im aktuellen
Repo-Stand tatsaechlich vorhanden sind.

## 1. Kartendatenquelle

- **Soll**: Expliziter Route-Contract fuer Kartenressourcen.
- **Ist**: `apps/web/src/routes/map/+page.ts` laedt `/api/nodes`, `/api/accounts` und `/api/edges`, klassifiziert Fehler pro Ressource und gibt `loadState` sowie `resourceStatus` explizit an die UI weiter.
- **Status**: Erledigt
- **Nachweis**: `apps/web/src/routes/map/+page.ts`, `apps/web/src/lib/map/scene.ts`, `apps/web/tests/map-load-fallback.spec.ts`

## 2. Interaktion und Panel

- **Soll**: Marker-Auswahl oeffnet nachvollziehbar den Informationsbereich; Auswahl-, Marker- und Paneldaten liegen nicht alle in der Routendatei.
- **Ist**: Marker-Klick setzt die Auswahl, oeffnet den Kontextbereich und laesst sich per Escape bzw. Karteninteraktion wieder schliessen. Kartenklarheit Phase 2 hat Auswahlzustand, Markerbeschreibung und Paneldaten aus der Route entkoppelt: `selectMapEntity(...)` (in `mapView.ts`) delegiert die Selektion ueber `toMapSelection(...)` an `enterFokus(...)` (in `uiView.ts`); die Presentation-Ableitungen (`deriveMarkerCounts`, `deriveFilteredMarkers`, `deriveAvailableFilterTypes`, `deriveSearchResults`, `deriveSearchMatchIds`, `deriveVisibleEdges`) sind reine Funktionen in `mapView.ts`. Die Route baut die request-bezogene Szene lokal (`buildMapScene`) und speist sie zusammen mit dem fluechtigen UI-Zustand (Filter, Suche) in diese reinen Funktionen; sie haelt nur noch den imperativen MapLibre-/Overlay-Lebenszyklus und die `flyTo`-Verdrahtung. Bewusst ohne modulglobalen Szenen-Store: request-spezifische Kartendaten bleiben in der Komponenten-Instanz und werden nicht in geteilten Modulzustand geschrieben (SSR-sicher; die App liefert ueberdies als statische SPA via `adapter-static` ohne Laufzeit-SSR-Server aus).
- **Status**: Erledigt
- **Nachweis**: `apps/web/src/lib/stores/mapView.ts`, `apps/web/src/lib/stores/uiView.ts`, `apps/web/src/lib/stores/mapView.test.ts`, `apps/web/tests/map-interaction.spec.ts`

## 3. Basemap-Abhaengigkeit

- **Soll**: Dokumentierte und bewusst entschiedene Basemap-Strategie.
- **Ist**: `resolveBasemapMode()` schaltet in dev/test standardmaessig auf `local-sovereign` und in Produktion standardmaessig auf `remote-style`; `PUBLIC_BASEMAP_MODE` kann die Produktionswahl explizit ueberschreiben.
- **Status**: Teil
- **Nachweis**: `apps/web/src/lib/map/config/basemap.current.ts`, `apps/web/src/lib/map/basemap.ts`, `apps/web/tests/basemap.spec.ts`
- **Fehlend**: Klare Produktentscheidung, ob `remote-style` nur Fallback bleiben oder `local-sovereign` produktiv erzwungen werden soll.

## 4. Infrastruktur-Kopplung

- **Soll**: Web-Runtime, Caddy-Proxy und Kartenabhaengigkeiten passen dokumentiert zusammen.
- **Ist**: `infra/caddy/Caddyfile` und `infra/caddy/Caddyfile.heim` bedienen den oeffentlichen `/local-basemap/`-Contract; `scripts/guard/caddy-basemap-route-guard.sh` validiert diese deploy-relevanten Caddyfiles. In dev wird `/local-basemap/` ueber die Vite-Middleware statt ueber Caddy bereitgestellt.
- **Status**: Teil
- **Nachweis**: `infra/caddy/Caddyfile`, `infra/caddy/Caddyfile.heim`, `scripts/guard/caddy-basemap-route-guard.sh`, `apps/web/vite.config.ts`
- **Fehlend**: Durchgehender Live-Nachweis mit echtem PMTiles-Artefakt und laufendem Caddy-Stack.

## 5. Testabdeckung

- **Soll**: Kerninteraktion und Fehlerpfade der Karte sind testseitig belegt.
- **Ist**: `map-interaction.spec.ts` deckt Kerninteraktion und Panel-Verhalten ab; `map-load-fallback.spec.ts` deckt partielle und komplette API-Fehler ab; `basemap.spec.ts`, `basemap-client-integration.spec.ts` und `basemap-sovereignty-testbuild.spec.ts` decken Basemap-Modi und den clientseitigen lokalen Pfad ab. `mapView.test.ts` deckt die entkoppelten Presentation-Ableitungen (reine Funktionen fuer Filter, Suche, Kantenfilter, Selektion) als Unit-Tests ab. `urlState.test.ts` und `map-url-state.spec.ts` decken die URL-Adressierung (`focus`, `lens`, `compose`) als Parser-Unit- und Browser-Tests ab.
- **Status**: Teil
- **Nachweis**: `apps/web/src/lib/stores/mapView.test.ts`, `apps/web/src/lib/map/urlState.test.ts`, `apps/web/tests/map-url-state.spec.ts`, `apps/web/tests/map-interaction.spec.ts`, `apps/web/tests/map-load-fallback.spec.ts`, `apps/web/tests/basemap.spec.ts`, `apps/web/tests/basemap-client-integration.spec.ts`, `apps/web/tests/basemap-sovereignty-testbuild.spec.ts`
- **Fehlend**: Visuelle Abnahme und echter Live-Runtime-Beweis gegen Caddy plus Artefakt; die initiale URL-Adressierung ist fuer `focus` / `lens` / `compose` abgedeckt, die Tab-Adressierung bleibt offen.

## 6. Runtime-Integration

- **Soll**: Echter HTTP-206-Nachweis, dass Caddy ein reales PMTiles-Artefakt per Range-Request korrekt ausliefert.
- **Ist**: `basemap-client-integration.spec.ts` und `basemap-sovereignty-testbuild.spec.ts` belegen den lokalen clientseitigen Basemap-Pfad im Testkontext. Das Guard-Script `scripts/guard/basemap-runtime-proof.sh` prueft den echten Live-Pfad gegen Caddy plus `.pmtiles`-Datei und unterscheidet explizit zwischen PROVEN und NOT_PROVEN. Der Guard kennt zwei Scopes: `range-delivery` (HTTP-206-Beweis) und `pmtiles-content` (Endpoint + HTTP-206-Range + 7-Byte-Magic `PMTiles` + optionale SHA256-Validierung). Der CI-Workflow betreibt drei Jobs: `basemap-runtime-proof` (skip-Modus, Diagnose), `basemap-range-delivery-proof` (require-Modus + Scope `range-delivery`) und `basemap-pmtiles-content-proof` (require-Modus + Scope `pmtiles-content`). Der Content-Job erzeugt ein echtes PMTiles-Artefakt ueber `scripts/basemap/build-hamburg-pmtiles.sh` (Planetiler-Pinning + verifizierter OSM-Snapshot), startet Caddy und laesst den Guard hart fehlschlagen, sobald Endpoint/206/Magic/SHA nicht stimmen.
- **Status**: Teil (HTTP-206-Range-Delivery: PROVEN — CI-Lauf #25970466659, Commit 14feefd6, Guard-Output `PROVEN: Caddy PMTiles Range delivery verified (scope=range-delivery)`, Response `HTTP/1.1 206 Partial Content`; pmtiles-content: PROVEN (scope=pmtiles-content) — CI-Lauf #26447341921, Job `basemap-pmtiles-content-proof` (#77857000606), Commit 3410c872964669fa27bfee958169ad9ce95594ae, Guard-Output `PROVEN: HTTP-served PMTiles Magic verified` und `PROVEN: Caddy PMTiles content verified (scope=pmtiles-content)`, Artefakt `basemap-hamburg-v0.1.0.pmtiles`, SHA256 `3eea9946f90a1cca425916c5b3272692ae8a1030bf22e700b67908cfafee8eab`, Groesse `23948909` Bytes)
- **Nachweis**: `apps/web/tests/basemap-client-integration.spec.ts`, `apps/web/tests/basemap-sovereignty-testbuild.spec.ts`, `scripts/guard/basemap-runtime-proof.sh`, `.github/workflows/basemap-runtime-proof.yml`, `infra/caddy/Caddyfile.proof`
- **Fehlend**: Tile-Directory- und strukturelle PMTiles-Validierung bleiben Future Work.
  **Visueller Beweis differenzieren**: Lokale Ausführung (Heimserver, `basemap-real-hamburg-visual.proof.ts`) PROVEN
  (Canvas 1280×720, style_loaded true, direct_range_status 206, zero remote_violations).
  CI-Ausführung des visuellen Proofs: READY_FOR_CI_PROOF — Job `basemap-visual-proof` in
  `.github/workflows/basemap-runtime-proof.yml` eingerichtet; kein grüner GitHub-Actions-Lauf liegt noch vor.
  Map-Interaktion und clientseitige Fehlerbehandlung sind belegt.
  Produktentscheidung (remote-style vs. local-sovereign im Produktionsbetrieb): ausstehend.

  **Fresh CI-Evidence pmtiles-content**:
  Run-URL: `https://github.com/heimgewebe/weltgewebe/actions/runs/26447341921`
  Job-URL: `https://github.com/heimgewebe/weltgewebe/actions/runs/26447341921/job/77857000606`
  Event: `pull_request`
  Branch: `chore/api-dockerfile-cargo-build-jobs`

## 7. Query-Parameter-Zustand vs. Kartenzustand

Kartenklarheit Phase 2 trennt zwei Zustandsschichten bewusst und dokumentiert,
damit Laufzeit- und Deep-Link-Zustand nicht ineinander verschwimmen.

### Kartenzustand (fluechtig, NICHT in der URL)

Laufzeitzustand der Karte. Lebt in Stores bzw. in der MapLibre-Instanz und wird
absichtlich nicht in die URL gespiegelt:

- Kartenausschnitt: `center`, `zoom`, `bearing`, `pitch` (MapLibre-Instanz).
- Systemzustand und Selektion: `systemState`, `selection`, `kompositionDraft`
  (`apps/web/src/lib/stores/uiView.ts`).
- Presentation-Ableitungen: aus der request-bezogenen Szene und dem UI-Zustand
  per reiner Funktionen abgeleitet (`deriveFilteredMarkers`,
  `deriveAvailableFilterTypes`, `deriveSearchResults`, `deriveSearchMatchIds`,
  `deriveVisibleEdges` in `apps/web/src/lib/stores/mapView.ts`); die Szene selbst
  bleibt request-lokal in der Route, nicht in einem Modul-Store.
- Filter- und Suchzustand: `activeFilters`, `isSearchOpen`, `searchQuery`
  (`apps/web/src/lib/stores/filterStore.ts`, `searchStore.ts`).

### Query-Parameter-Zustand (URL-eigen, Fokuspanel-/Kartenlinsen-Adressierung)

Eigene, URL-besessene Schicht für die Fokuspanel-/Kartenlinsen-Deep-Link-Adressierung,
getrennt vom flüchtigen Kartenzustand. Aktuelle Zielsemantik gemäß
`docs/blueprints/ui-interaction-doctrine.md`:

- `lens` (bisher grob `l`): Filter / Suche als Kartenlinse.
- `focus` (bisher grob `r`): Fokus-Selection im ContextPanel.
- `tab` (bisher grob `t`): Tab innerhalb eines gültigen Fokuspanel-Kontexts.
- `compose`: optionale spätere Adressierung eines Kompositionsmodus; kein
  direktes Erbe der bisherigen Kurzform `l` / `r` / `t`.

Die Kurzform `l` / `r` / `t` ist das bisherige Altmodell und kein Zielcontract
für neue Implementierung. Spätere URL-Adressierung und optionale Navigation soll
die semantische Zielrichtung `focus` / `tab` / `lens` / `compose` prüfen.

- **Soll**: URL-Parameter und Kartenzustand sind klar getrennt dokumentiert; die
  URL-Schicht beschreibt Fokus-/Linsen-/Tab-Adressierung, nicht den flüchtigen
  Kartenausschnitt.
- **Ist**: Die Trennung ist dokumentiert (dieser Abschnitt sowie der
  Modul-Header in `apps/web/src/lib/stores/mapView.ts`, der die bisherige
  Kurzform `l` / `r` / `t` verwendet). Die URL-Adressierungsschicht ist als
  URL-eigene Schicht definiert und bewusst aus den Presentation-Ableitungen
  herausgehalten. Initiale URL-Adressierung beim Laden der Map ist für
  `focus=node:<id>`, `focus=garnrolle:<id>`, `lens=filter`, `lens=search` und
  `compose=node` implementiert und getestet: `apps/web/src/lib/map/urlState.ts`
  parst die Query rein und ohne Seiteneffekte,
  `apps/web/src/routes/map/+page.svelte` wendet sie als Adressierungsschicht auf
  die bestehenden uiView-/Overlay-Stores an (Priorität `compose` > `focus` >
  Linse; ein gültiger, aber noch nicht auflösbarer `focus` blockiert den
  Linsen-Fallback). Ein Intent-Wechsel über die URL verlässt zuvor gesetzte
  Fokus-/Kompositionszustände, bevor die neue Linse geöffnet wird; doppelte
  bekannte Query-Keys gelten als ungültig. Eine Store→URL-Synchronisation bleibt
  offen; `center` / `zoom` / `bearing` / `pitch` werden bewusst nicht gespiegelt.
  `tab=<tab>` wird parserseitig toleriert, aber noch nicht an ein
  Panel-Tab-Modell gebunden, da Tabs derzeit lokale Panelzustände sind.
- **Status**: Teil
- **Nachweis**: `apps/web/src/lib/map/urlState.ts`, `apps/web/src/lib/map/urlState.test.ts`, `apps/web/src/routes/map/+page.svelte`, `apps/web/tests/map-url-state.spec.ts`, `apps/web/src/lib/stores/mapView.ts`, `apps/web/src/lib/stores/uiView.ts`
- **Fehlend**: Tab-Adressierung an ein adressierbares Panel-Tab-Modell binden
  (`tab=<tab>` derzeit parser-only) und eine Store→URL-Synchronisation, falls
  später gewollt; weitere Fokus- oder Kompositionsarten erst nach eigenem
  Contract (siehe `docs/blueprints/kartenklarheit-roadmap.md`).

## Essenz

Die Karte besitzt einen expliziten Loader-Contract, ein Szenenmodell und belegte Fehlerpfade.
Der blockierende CI-Job `basemap-range-delivery-proof` fuer HTTP-206-Range-Delivery
ist PROVEN: [CI-Lauf 25970466659](https://github.com/heimgewebe/weltgewebe/actions/runs/25970466659)
(Commit 14feefd6), Guard-Output `PROVEN: Caddy PMTiles Range delivery verified
(scope=range-delivery)`, Response-Header `HTTP/1.1 206 Partial Content`.
Der Scope `pmtiles-content` ist im selben Workflow als eigener blockierender
Proof-Job hinterlegt (`basemap-pmtiles-content-proof`) und prueft Endpoint,
HTTP-206-Range, 7-Byte-Magic `PMTiles` und optionale SHA256 gegen ein echtes
in CI erzeugtes Artefakt. Der Guard ist fachlich erweitert um
`PROVEN: HTTP-served PMTiles Magic verified`.
Fuer Scope `pmtiles-content` ist der Proof jetzt PROVEN: [CI-Lauf 26447341921](https://github.com/heimgewebe/weltgewebe/actions/runs/26447341921)
(Job `basemap-pmtiles-content-proof`, [Job 77857000606](https://github.com/heimgewebe/weltgewebe/actions/runs/26447341921/job/77857000606),
Commit 3410c872964669fa27bfee958169ad9ce95594ae), Guard-Output
`PROVEN: HTTP-served PMTiles Magic verified` und
`PROVEN: Caddy PMTiles content verified (scope=pmtiles-content)`, Artefakt
`basemap-hamburg-v0.1.0.pmtiles` mit SHA256
`3eea9946f90a1cca425916c5b3272692ae8a1030bf22e700b67908cfafee8eab` und
Groesse `23948909` Bytes.
Offen bleiben die Produktionsentscheidung fuer den
Basemap-Modus und die visuelle Kartenabnahme in GitHub Actions.
