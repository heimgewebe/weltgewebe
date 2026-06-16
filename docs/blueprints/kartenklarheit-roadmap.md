---
id: docs.blueprints.kartenklarheit-roadmap
title: Roadmap - Kartenklarheit
doc_type: roadmap
status: active
relations:
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
summary: Roadmap fuer den Uebergang von der aktuellen Demo-Karte zu einer belastbaren, nachvollziehbaren Kartenarchitektur.
---

Statuslegende: `[ ] offen`, `[~] in Arbeit`, `[x] erledigt`

## Ziel

Die Kartenroute soll von einem lokal verdrahteten Demo-Stand zu einer klar
dokumentierten, testbaren und spaeter produktionsfaehigen
Kartenimplementierung weiterentwickelt werden.

## Gesicherte Ausgangslage

- [x] Kartenroute ist als Loader-/UI-Paar vorhanden (`apps/web/src/routes/map/+page.ts`, `apps/web/src/routes/map/+page.svelte`).
- [x] Kartendaten werden in `+page.ts` aus `/api/nodes`, `/api/accounts` und `/api/edges` geladen; `loadState` und `resourceStatus` werden explizit zur UI durchgereicht.
- [x] `buildMapScene(...)` transformiert Route-Daten in ein explizites Kartenmodell (`apps/web/src/lib/map/scene.ts`).
- [x] Marker-Interaktion und Kontextbereich sind durch `apps/web/tests/map-interaction.spec.ts` belegt.
- [x] Degradierte Ladezustaende sind durch `apps/web/tests/map-load-fallback.spec.ts` belegt.
- [x] Basemap-Modus ist explizit: lokal/test standardmaessig `local-sovereign`, Produktion standardmaessig `remote-style`, optional via `PUBLIC_BASEMAP_MODE` ueberschreibbar.

---

## Phase 0 - Ist-Zustand sichern

### Ziel der Phase 0

Den aktuellen Demo-Stand explizit benennen, damit spaetere Verbesserungen
gegen einen klaren Referenzpunkt bewertet werden koennen.

### Arbeitspakete der Phase 0

- [x] Relevante Einstiegspfade benannt:
  - `apps/web/src/routes/map/+page.ts`
  - `apps/web/src/routes/map/+page.svelte`
  - `apps/web/src/lib/map/scene.ts`
  - `apps/web/src/lib/map/types.ts`
  - `apps/web/src/lib/map/config/basemap.current.ts`
  - `apps/web/src/lib/map/basemap.ts`
- [x] Relevante Tests benannt:
  - `apps/web/tests/map-interaction.spec.ts`
  - `apps/web/tests/map-load-fallback.spec.ts`
  - `apps/web/tests/basemap.spec.ts`
  - `apps/web/tests/basemap-client-integration.spec.ts`
  - `apps/web/tests/basemap-sovereignty-testbuild.spec.ts`
- [x] Ist-Notiz festgehalten:
  - Loader laedt API-Ressourcen mit explizitem `loadState` und `resourceStatus`
  - `buildMapScene(...)` ist der zentrale Transformationspunkt zwischen Loader und Rendering
  - `MapEntityViewModel` ist der aktuelle Kartencontract; `MapPoint` lebt nur noch als Deprecated-Alias
  - Basemap laeuft in dev/test standardmaessig `local-sovereign`, in Produktion standardmaessig `remote-style`

### Stop-Kriterium der Phase 0

- [x] Der Demo-Stand ist so dokumentiert, dass spaetere Architekturbehauptungen daran messbar sind.

---

## Phase 1 - Datenquelle explizit machen

### Ziel der Phase 1

Die Kartenroute soll nicht dauerhaft direkt auf Demo-Daten verdrahtet bleiben.

### Arbeitspakete der Phase 1

- [x] Datenbeschaffung aus `+page.svelte` herausloesen.
- [x] Route auf einen expliziten API-/Loader-Contract umstellen (`+page.ts`).
- [x] Zwischen "keine Daten", "Laden" und degradierten Fehlerzustaenden unterscheiden.
- [x] Den frueher lokalen Kartentyp durch `MapEntityViewModel` und `MapSceneModel` ersetzen.

### Verifikation der Phase 1

- [x] Partielle und komplette API-Fehler werden in `apps/web/tests/map-load-fallback.spec.ts` geprueft.
- [x] Sichtbarer Fehlerzustand statt stiller Leere ist ueber `load-state-partial` und `load-state-failed` belegt.

### Stop-Kriterium der Phase 1

- [x] Die Kartenroute hat eine explizite Datenquelle und einen nachvollziehbaren Ladezustand.

---

## Phase 2 - Zustands- und Szenengrenzen klaeren

### Ziel der Phase 2

Kartenlogik, Markerzustand und Drawer-Zustand sollen nicht dauerhaft in einer einzelnen Routendatei zusammenliegen.

### Arbeitspakete der Phase 2

- [x] Auswahlzustand, Markerbeschreibung und Paneldaten aus `+page.svelte` entkoppeln.
  - Auswahlzustand: `selectMapEntity(...)` in `apps/web/src/lib/stores/mapView.ts`
    delegiert ueber `toMapSelection(...)` an `enterFokus(...)` in
    `apps/web/src/lib/stores/uiView.ts`; die Route behaelt nur noch die
    kartenseitige `flyTo`-Verdrahtung.
  - Markerbeschreibung: `deriveMarkerCounts`, `deriveFilteredMarkers`,
    `deriveAvailableFilterTypes`, `deriveSearchResults`, `deriveSearchMatchIds`
    und `deriveVisibleEdges` sind reine Funktionen in
    `apps/web/src/lib/stores/mapView.ts`. Die Route baut die request-bezogene
    Szene lokal (`buildMapScene`) und speist sie samt UI-Zustand (Filter, Suche)
    in diese Funktionen; ein modulglobaler Szenen-Store wurde bewusst vermieden,
    damit request-spezifische Kartendaten nicht in geteilten Modulzustand
    geschrieben werden (SSR-sicher; zusaetzlich statische SPA via
    `adapter-static` ohne Laufzeit-SSR-Server).
  - Paneldaten: Das selektierte Entity reist als `selection.data` ueber `uiView`;
    der `ContextPanel` liest es direkt aus dem Store statt aus der Route.
- [x] Ein kleines Karten-View-Model oder Szenenmodell definieren.
- [x] Query-Parameter-Zustand (`l`, `r`, `t`) und Kartenzustand getrennt dokumentieren.
  - Dokumentiert in `docs/reports/map-status-matrix.md`, Abschnitt
    „Query-Parameter-Zustand vs. Kartenzustand".

### Verifikation der Phase 2

- [x] `apps/web/src/lib/map/scene.test.ts` prueft das Szenenmodell als reine Transformation.
- [x] `apps/web/src/lib/stores/mapView.test.ts` prueft die entkoppelten
  Presentation-Ableitungen (reine Funktionen fuer Filter, Suche, Kantenfilter,
  Selektion) als Unit-Tests.

### Stop-Kriterium der Phase 2

- [x] Auswahlzustand (uiView), Markerbeschreibung (reine Ableitungsfunktionen in
  `mapView`) und Paneldaten (`selection.data`) sind aus der Route entkoppelt; die
  Route haelt nur noch die request-lokale Szene plus die imperative
  MapLibre-/Overlay-Lebenszyklus-Orchestrierung. Die URL-Parameter-Schicht
  (`l`, `r`, `t`) ist dokumentarisch vom Kartenzustand getrennt; die
  tatsaechliche Query-Parameter-Navigation bleibt als Arbeitspaket in Phase 4
  offen.

---

## Phase 3 - Basemap-Abhaengigkeit ehrlich machen

### Ziel der Phase 3

Die Basemap-Strategie soll dem tatsaechlichen Runtime-Verhalten entsprechen.

### Arbeitspakete der Phase 3

- [~] Hybridmodus explizit halten: `local-sovereign` fuer dev/test, `remote-style` als Produktionsdefault, optional ueberschreibbar.
- [~] Style-, Asset- und Tile-Strategie fuer `local-sovereign` dokumentieren und gegen Deploy-Realitaet halten.
- [~] CSP- und Caddy-Konfiguration mit dem `/local-basemap/`-Contract abgleichen; echter Runtime-Beweis bleibt offen.

### Verifikation der Phase 3

- [x] `apps/web/tests/basemap.spec.ts` prueft Modus- und Style-Aufloesung.
- [x] `apps/web/tests/basemap-client-integration.spec.ts` und `apps/web/tests/basemap-sovereignty-testbuild.spec.ts` belegen den clientseitigen lokalen Modus im Testkontext.

### Stop-Kriterium der Phase 3

- [~] Die Basemap-Abhaengigkeit ist expliziter geworden, aber die Produktionsentscheidung und der Live-Runtime-Beweis bleiben offen.

---

## Phase 4 - Regressionen gezielt absichern

### Ziel der Phase 4

Vorhandene Browser-Tests sollen von Smoke-Absicherung zu gezielter Kartenregression wachsen.

### Arbeitspakete der Phase 4

- [x] Kerninteraktion und Kontextbereich pruefen (`map-interaction.spec.ts`).
- [x] Fehler-, Leere- und Ladezustaende absichern (`map-load-fallback.spec.ts`).
- [x] Basemap-Verhalten separat absichern (`basemap.spec.ts`, `basemap-client-integration.spec.ts`, `basemap-sovereignty-testbuild.spec.ts`).
- [ ] Tastatur- und Query-Parameter-Navigation gezielt absichern.

### Stop-Kriterium der Phase 4

- [~] Kerninteraktion ist testseitig abgedeckt; Daten- und Basemap-Fehlerpfade fehlen noch.

---

## Phase 5 — Souveraene Basemap-Infrastruktur einziehen

### Ziel der Phase 5

Die souveraene Basemap-Infrastruktur (PMTiles-Pipeline, Caddy-Route, Style-Souveraenitaet) ist operational verankert.

### Arbeitspakete der Phase 5

- [x] PMTiles-Pipeline und Build-Skripte vorhanden (`scripts/basemap/`).
- [x] Caddy-Route `/local-basemap/*` in produktionsrelevanten Caddyfiles korrekt konfiguriert.
- [x] Caddy-Route-Guard eingezogen (`scripts/guard/caddy-basemap-route-guard.sh`).
- [x] Souveraenes `style.json` im `map-style`-Verzeichnis vorhanden.
- [x] PMTiles-Protokoll im Frontend registriert; Frontend-Flag (`PUBLIC_BASEMAP_MODE`) vorhanden.

### Stop-Kriterium der Phase 5

- [x] Infrastruktur-Seite ist konfiguriert und statisch verifiziert.
  Echter Runtime-Nachweis (HTTP 206 gegen reales Caddy-Backend) ist noch offen und Thema von Phase 6.

---

## Phase 6 — Wahrheitsbeweis: Basemap Runtime Proof

### Ziel der Phase 6

[~] **In Arbeit** — Vollstaendiger Nachweis ist erst erledigt, wenn HTTP-206-Beweis im CI vorliegt.

Der vollstaendige Abschlussplan fuer Phase 6 ist in
[`docs/blueprints/kartenklarheit-phase6.md`](kartenklarheit-phase6.md) definiert.

### Was in Phase 6 bewiesen werden muss

Nicht:

- „style.json existiert"
- „pmtiles gebaut"
- „Playwright-Test gruenlich"

Sondern:

- Browser / curl → HTTP → Caddy → PMTiles-Byte-Stream → HTTP 206 Partial Content → Rendering

### Arbeitspakete der Phase 6

- [x] Basemap-Runtime-Proof-Guard vorhanden: `scripts/guard/basemap-runtime-proof.sh`
  - Prueft: PMTiles-Artefakt vorhanden, Caddy erreichbar, Range-Request liefert HTTP 206,
    Accept-Ranges/Content-Range-Header vorhanden, kein stiller 200-OK.
  - Unterscheidet explizit zwischen PROVEN und NOT_PROVEN.
- [x] Nicht blockierender Guard-Workflow vorhanden: `.github/workflows/basemap-runtime-proof.yml`
  - Laeuft ohne Artefakt und ohne Caddy; meldet `NOT_PROVEN` — kein falsches Gruen.
  - Startet keinen Docker-Stack, baut kein PMTiles-Artefakt.
- [x] **Blockierender CI-Job fuer HTTP-206-Range-Delivery PROVEN:**
  Job `basemap-range-delivery-proof` startet einen realen Caddy-Container (Image
  `caddy:2.7`, Config `infra/caddy/Caddyfile.proof`), serviert eine `.pmtiles`-Datei
  unter `/local-basemap/*` und der Guard verifiziert HTTP 206 plus
  `Accept-Ranges`/`Content-Range`. Bei Abweichung schlaegt der Job hart fehl.
  **PROVEN:** [CI-Lauf 25970466659](https://github.com/heimgewebe/weltgewebe/actions/runs/25970466659)
  (Commit 14feefd6), Guard-Output `PROVEN: Caddy PMTiles Range delivery verified
  (scope=range-delivery)`, Response `HTTP/1.1 206 Partial Content`.
  - Scope: `BASEMAP_PROOF_SCOPE=range-delivery`. Beweist die
    Range-Auslieferungs-Kette, nicht den PMTiles-Magic-Byte-Check.
  - Das ausgelieferte Artefakt ist im CI ein deterministisches, synthetisches
    64-KiB-Testartefakt — keine echte Karte. Es belegt nur die Caddy-Range-Kette.
- [ ] **PMTiles-Magic-Byte-Check im CI:** Der Guard kennt
  `BASEMAP_PROOF_SCOPE=pmtiles-content` (prueft die PMTiles-Magic-Bytes), wird in
  diesem Scope aber erst ausfuehrbar, sobald ein echtes PMTiles-Artefakt im CI
  produziert oder geladen wird. Hamburg-/Deutschland-Builds bleiben heavy und
  laufen weiterhin nur via `workflow_dispatch`.
- [ ] Visuelle Abnahme: Karte rendert ohne Fallback nach realem Tile-Load.

### Abgrenzung: Was kein Ersatz fuer den Runtime-Beweis ist

- `apps/web/tests/basemap-client-integration.spec.ts` ist ein **gemockter Client-Test**.
  Er validiert MapLibre-Protokoll-Handling ohne echtes HTTP-Backend — kein Runtime-Beweis.
- `scripts/guard/caddy-basemap-route-guard.sh` ist ein **statischer Konfigurations-Check**.
  Er prueft Caddyfile-Struktur ohne reale Auslieferung — kein Runtime-Beweis.

### Stop-Kriterium der Phase 6

- [x] Guard-Script liefert PROVEN (HTTP 206 bestaetigt) in einem reproduzierbaren
  CI-Lauf mit laufendem Caddy-Backend und einer `.pmtiles`-Datei unter
  `/local-basemap/*`. Scope: `range-delivery`. **PROVEN:** CI-Lauf
  [CI-Lauf 25970466659](https://github.com/heimgewebe/weltgewebe/actions/runs/25970466659) (Commit 14feefd6),
  Guard-Output `PROVEN: Caddy PMTiles Range delivery verified (scope=range-delivery)`,
  Response `HTTP/1.1 206 Partial Content`.
- [ ] Guard-Script liefert PROVEN unter Scope `pmtiles-content` gegen ein echtes
  PMTiles-Artefakt (Magic-Byte-Check, 7-Byte-Prefix; Tile-Directory- und
  Strukturvalidierung bleiben Future Work). Steht aus, solange im CI
  kein echtes Artefakt produziert wird.

---

## Minimalpfad

- [x] Aktuellen Demo-Stand wahrheitsgetreu dokumentieren.
- [x] Datenquelle explizit machen.
- [ ] Externe Basemap-Abhaengigkeit klar entscheiden.
- [x] Fehlerpfade testbar machen.
- [x] Basemap-Runtime-Beweis: blockierender CI-Job `basemap-range-delivery-proof`
  PROVEN — [CI-Lauf 25970466659](https://github.com/heimgewebe/weltgewebe/actions/runs/25970466659)
  (Commit 14feefd6). PMTiles-Magic-Byte-Check bleibt offen.

---

## Essenz

**Hebel:** Ehrliche Bestandsaufnahme vor Ausbau.
**Entscheidung:** Route-Contract, Szenenmodell und degradiertes Laufzeitverhalten sind jetzt explizit; offen bleibt vor allem die Produktionswahrheit der Basemap.
**Status:** Loader, Szene, Interaktion, Fehlerbanner und clientseitiger Basemap-Modus sind belegt.
Produktionsdefault, Artefaktverfuegbarkeit und echter HTTP-206-Runtime-Beweis bleiben offen.
Phase 6 (Basemap Runtime Proof): Guard-Script eingezogen, CI-Job nicht blockierend vorhanden,
blockierender Job `basemap-range-delivery-proof` PROVEN (CI-Lauf #25970466659, Commit 14feefd6,
Guard `PROVEN: Caddy PMTiles Range delivery verified (scope=range-delivery)`,
Response `HTTP/1.1 206 Partial Content`).
PMTiles-Magic-Byte-Check bleibt offen; `pmtiles-content`-Scope prueft nur die ersten
7 Magic-Bytes der lokalen Artefaktdatei, keine Tile-Directory-Struktur.
