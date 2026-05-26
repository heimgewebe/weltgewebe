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

- **Soll**: Marker-Auswahl oeffnet nachvollziehbar den Informationsbereich.
- **Ist**: Marker-Klick setzt die Auswahl, oeffnet den Kontextbereich und laesst sich per Escape bzw. Karteninteraktion wieder schliessen.
- **Status**: Erledigt
- **Nachweis**: `apps/web/tests/map-interaction.spec.ts`

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
- **Ist**: `map-interaction.spec.ts` deckt Kerninteraktion und Panel-Verhalten ab; `map-load-fallback.spec.ts` deckt partielle und komplette API-Fehler ab; `basemap.spec.ts`, `basemap-client-integration.spec.ts` und `basemap-sovereignty-testbuild.spec.ts` decken Basemap-Modi und den clientseitigen lokalen Pfad ab.
- **Status**: Teil
- **Nachweis**: `apps/web/tests/map-interaction.spec.ts`, `apps/web/tests/map-load-fallback.spec.ts`, `apps/web/tests/basemap.spec.ts`, `apps/web/tests/basemap-client-integration.spec.ts`, `apps/web/tests/basemap-sovereignty-testbuild.spec.ts`
- **Fehlend**: Gezielte Query-Parameter-Navigation, visuelle Abnahme und echter Live-Runtime-Beweis gegen Caddy plus Artefakt.

## 6. Runtime-Integration

- **Soll**: Echter HTTP-206-Nachweis, dass Caddy ein reales PMTiles-Artefakt per Range-Request korrekt ausliefert.
- **Ist**: `basemap-client-integration.spec.ts` und `basemap-sovereignty-testbuild.spec.ts` belegen den lokalen clientseitigen Basemap-Pfad im Testkontext. Das Guard-Script `scripts/guard/basemap-runtime-proof.sh` prueft den echten Live-Pfad gegen Caddy plus `.pmtiles`-Datei und unterscheidet explizit zwischen PROVEN und NOT_PROVEN. Der Guard kennt zwei Scopes: `range-delivery` (HTTP-206-Beweis) und `pmtiles-content` (Endpoint + HTTP-206-Range + 7-Byte-Magic `PMTiles` + optionale SHA256-Validierung). Der CI-Workflow betreibt drei Jobs: `basemap-runtime-proof` (skip-Modus, Diagnose), `basemap-range-delivery-proof` (require-Modus + Scope `range-delivery`) und `basemap-pmtiles-content-proof` (require-Modus + Scope `pmtiles-content`). Der Content-Job erzeugt ein echtes PMTiles-Artefakt ueber `scripts/basemap/build-hamburg-pmtiles.sh` (Planetiler-Pinning + verifizierter OSM-Snapshot), startet Caddy und laesst den Guard hart fehlschlagen, sobald Endpoint/206/Magic/SHA nicht stimmen.
- **Status**: Teil (HTTP-206-Range-Delivery: PROVEN — CI-Lauf #25970466659, Commit 14feefd6, Guard-Output `PROVEN: Caddy PMTiles Range delivery verified (scope=range-delivery)`, Response `HTTP/1.1 206 Partial Content`; PMTiles-Content-Proof in GitHub Actions als eigener blockierender Job umgesetzt, visuelle Abnahme weiterhin getrennt)
- **Nachweis**: `apps/web/tests/basemap-client-integration.spec.ts`, `apps/web/tests/basemap-sovereignty-testbuild.spec.ts`, `scripts/guard/basemap-runtime-proof.sh`, `.github/workflows/basemap-runtime-proof.yml`, `infra/caddy/Caddyfile.proof`
- **Fehlend**: Tile-Directory- und strukturelle PMTiles-Validierung bleiben Future Work.
  **Visueller Beweis differenzieren**: Lokale Ausführung (Heimserver, `basemap-real-hamburg-visual.proof.ts`) PROVEN
  (Canvas 1280×720, style_loaded true, direct_range_status 206, zero remote_violations).
  CI-Ausführung des visuellen Proofs: NOT_PROVEN (noch nicht in GitHub Actions). Map-Interaktion und clientseite Fehlerbehandlung sind belegt.
  Produktentscheidung (remote-style vs. local-sovereign im Produktionsbetrieb): ausstehend.

## Essenz

Die Karte besitzt einen expliziten Loader-Contract, ein Szenenmodell und belegte Fehlerpfade.
Der blockierende CI-Job `basemap-range-delivery-proof` fuer HTTP-206-Range-Delivery
ist PROVEN: [CI-Lauf 25970466659](https://github.com/heimgewebe/weltgewebe/actions/runs/25970466659)
(Commit 14feefd6), Guard-Output `PROVEN: Caddy PMTiles Range delivery verified
(scope=range-delivery)`, Response-Header `HTTP/1.1 206 Partial Content`.
Der Scope `pmtiles-content` ist im selben Workflow als eigener blockierender
Proof-Job hinterlegt (`basemap-pmtiles-content-proof`) und prueft Endpoint,
HTTP-206-Range, 7-Byte-Magic `PMTiles` und optionale SHA256 gegen ein echtes
in CI erzeugtes Artefakt. Offen bleiben die Produktionsentscheidung fuer den
Basemap-Modus und die visuelle Kartenabnahme in GitHub Actions.
