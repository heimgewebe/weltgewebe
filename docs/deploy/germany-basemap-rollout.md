---
id: deploy.germany-basemap-rollout
title: Deutschlandweite PMTiles-Basemap ausrollen
doc_type: runbook
status: active
owner: product-map
---
# Deutschlandweite PMTiles-Basemap ausrollen

## Ziel und Sicherheitsgrenze

Die Deutschland-Basemap wird als eigenständiges, versioniertes PMTiles-Artefakt
vorbereitet. Der bestehende Regionalpfad mit Hamburg und Schleswig-Holstein
bleibt Standard und Rückfallpfad.

Der Build oder die Veröffentlichung des stabilen Alias aktiviert Deutschland
**nicht**. Die Clientaktivierung erfordert zusätzlich einen bewusst neu gebauten
Frontend-Build mit:

- `PUBLIC_BASEMAP_MODE=local-sovereign`
- `PUBLIC_BASEMAP_VARIANT=germany`

Ohne `PUBLIC_BASEMAP_VARIANT` bleibt `regional` aktiv.

## Voraussetzungen

- sauberer, aktueller Checkout;
- Docker, Node und pnpm;
- mindestens 64 GiB freier Arbeitsraum, sofern der Grenzwert nicht bewusst
  über `BASEMAP_MIN_FREE_BYTES` angepasst wurde;
- gepinnter OSM-Snapshot mit bekannter SHA256-Prüfsumme;
- vollständige, nicht leere Provenienz aus Dateiname, HTTPS-URL, SHA256 und
  Snapshotdatum;
- keine gleichzeitige Veröffentlichung in dasselbe Zielverzeichnis.

Versionierte Artefakte sind unveränderlich. Existiert eine Version bereits im
Build- oder Zielverzeichnis, muss eine neue `BASEMAP_VERSION` verwendet werden.
Ein Austausch unter demselben Versionsnamen ist nicht zulässig.

## Phase 1: Artefakt herstellen und prüfen

`scripts/basemap/prepare-germany-rollout.sh` führt in dieser Reihenfolge aus:

1. reproduzierbaren Build durch `build-germany-pmtiles.sh` im isolierten
   Staging-Verzeichnis `build/basemap-staging/germany`;
2. vollständige Traversierung aller erreichbaren PMTiles-Verzeichnisse;
3. deterministische Stichprobe realer MVT-Kacheln gegen
   `map-style/style-germany.json`;
4. Sentinel-, Hash- und Größenprüfung;
5. atomare Veröffentlichung von `basemap-germany.pmtiles` und
   `basemap-germany.meta.json` in ein ausdrücklich angegebenes, vom
   Buildverzeichnis verschiedenes Ziel.

Dadurch kann ein vorhandener stabiler Alias zu keinem Zeitpunkt auf neue,
noch nicht validierte Bytes zeigen. Die Metadaten tragen bis zur getrennten
Produktionsfreigabe `"activation": "opt-in"`.

## Phase 2: Runtime- und Gerätebeweis

Vor der Aktivierung müssen mindestens belegt sein:

- aktueller OSM-Snapshot; der Aktivierungsoperator akzeptiert standardmäßig
  höchstens 45 Tage alte Quelldaten;
- HTTP 200 und 206 über den echten Caddy-Pfad;
- `application/octet-stream`, `Accept-Ranges: bytes` und korrektes
  `Content-Range`;
- PMTiles-Signatur, Größe und SHA256 des publizierten Artefakts;
- dekodierte und sichtbare Kacheln aus Nord, Süd, Ost, West und Mitte;
- Browserabnahme auf iPad und Desktop;
- keine Requests an externe Kartenanbieter.

Ein erfolgreicher Strukturtest allein beweist weder kartografische
Vollständigkeit noch aktuelle OSM-Daten.

## Phase 3: Aktivierung

`scripts/basemap/activate-germany-basemap.sh` ist der einzige vorgesehene
Aktivierungspfad. Er verlangt die ausdrückliche Bestätigung
`GERMANY_BASEMAP_ACTIVATION_CONFIRM=deploy-germany-pmtiles` und arbeitet
fail-closed:

1. beide stabilen Aliase müssen exakt auf dasselbe ausgewählte Versionspaar
   zeigen;
2. Sentinel, Hash, Größe, Region, Version und Quelldatenalter werden geprüft;
3. die Tiefenvalidierung wird unmittelbar gegen die aktuellen Artefaktbytes
   wiederholt;
4. ein frischer Frontend-Build mit der Variante `germany` wird erzwungen;
5. der lokale und öffentliche Buildbeleg `/_app/basemap-build.json` muss die
   Germany-Variante exakt ausweisen;
6. öffentlicher Stil, Metadaten und HTTP-206-Range-Vertrag werden gelesen;
7. erst danach wird `.ops/germany-basemap-activation.json` geschrieben.

Das bestehende regionale Artefaktpaar wird nicht gelöscht.

## Rückfall

Scheitert nach dem Germany-Deploy ein Buildidentitäts-, Stil-, Sentinel- oder
Range-Beweis, baut der Aktivierungsoperator das Frontend automatisch erneut mit
`PUBLIC_BASEMAP_VARIANT=regional`. Die ursprünglichen Deploy-Argumente werden
unverändert übernommen. Die regionalen Aliase bleiben mindestens 14 Tage
verfügbar. Der Deutschland-Alias kann unabhängig davon auf die vorherige,
intakte Version zurückgesetzt werden.

## Noch nicht automatisch erfüllt

- aktuellerer OSM-Snapshot als der eingebaute reproduzierbare Teststand vom
  1. Januar 2026;
- realer Deutschland-Buildbeleg auf dem Heim-PC;
- produktiver Caddy-Readback mit dem großen Artefakt;
- bundesweite visuelle Abnahme;
- gemessene Artefaktgröße, Builddauer, Spitzenlast und Bandbreite.

Diese Punkte sind Freigabebedingungen, keine stillschweigend als erfüllt
geltenden Annahmen.
