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
- **Ist**: `basemap-client-integration.spec.ts` und `basemap-sovereignty-testbuild.spec.ts` belegen den lokalen clientseitigen Basemap-Pfad im Testkontext. Das Guard-Script `scripts/guard/basemap-runtime-proof.sh` prueft den echten Live-Pfad gegen Caddy plus PMTiles-Artefakt und unterscheidet explizit zwischen PROVEN und NOT_PROVEN. Der zugehoerige CI-Workflow bleibt ohne Artefakt und ohne Caddy bewusst bei NOT_PROVEN.
- **Status**: Teil
- **Nachweis**: `apps/web/tests/basemap-client-integration.spec.ts`, `apps/web/tests/basemap-sovereignty-testbuild.spec.ts`, `scripts/guard/basemap-runtime-proof.sh`, `.github/workflows/basemap-runtime-proof.yml`
- **Fehlend**: Echter CI-Nachweis; PMTiles-Artefakt ist im CI aktuell nicht verfuegbar; kein Caddy-Stack im CI.
  Solange kein reales Artefakt und kein laufender Caddy im CI-Stack vorhanden sind, bleibt der HTTP-206-Beweis offen.
  Die clientseitigen Tests sind kein Ersatz fuer den Live-Caddy-Beweis.

## Essenz

Die Karte besitzt einen expliziten Loader-Contract, ein Szenenmodell und belegte Fehlerpfade.
Offen bleiben vor allem die Produktionsentscheidung fuer den Basemap-Modus und der echte HTTP-206-Nachweis gegen laufendes Caddy plus Artefakt.
