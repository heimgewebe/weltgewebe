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
- keine gleichzeitige Veröffentlichung in dasselbe Zielverzeichnis.

## Phase 1: Artefakt herstellen und prüfen

`scripts/basemap/prepare-germany-rollout.sh` führt in dieser Reihenfolge aus:

1. reproduzierbaren Build durch `build-germany-pmtiles.sh`;
2. vollständige Traversierung aller erreichbaren PMTiles-Verzeichnisse;
3. deterministische Stichprobe realer MVT-Kacheln gegen
   `map-style/style-germany.json`;
4. Sentinel-, Hash- und Größenprüfung;
5. atomare Veröffentlichung von `basemap-germany.pmtiles` und
   `basemap-germany.meta.json` in ein ausdrücklich angegebenes Ziel.

Die Metadaten tragen bis zur getrennten Produktionsfreigabe
`"activation": "opt-in"`.

## Phase 2: Runtime-Beweis

Vor der Aktivierung müssen mindestens belegt sein:

- HTTP 200 und 206 über den echten Caddy-Pfad;
- `application/octet-stream`, `Accept-Ranges: bytes` und korrektes
  `Content-Range`;
- PMTiles-Signatur und SHA256 des publizierten Artefakts;
- dekodierte und sichtbare Kacheln aus Nord, Süd, Ost, West und Mitte;
- Browserabnahme auf iPad und Desktop;
- keine Requests an externe Kartenanbieter.

Ein erfolgreicher Strukturtest allein beweist weder kartografische
Vollständigkeit noch aktuelle OSM-Daten.

## Phase 3: Aktivierung

Die Aktivierung erfolgt erst nach bestandenem Runtime-Beweis in einem eigenen,
reviewten Deploy. Ein neuer Frontend-Build ist zwingend, weil die Variante eine
Buildzeitentscheidung ist. Das bestehende regionale Artefaktpaar wird nicht
gelöscht.

## Rückfall

Bei Lade-, Darstellungs- oder Range-Fehlern wird ein Frontend-Build mit
`PUBLIC_BASEMAP_VARIANT=regional` veröffentlicht. Die regionalen Aliase bleiben
mindestens 14 Tage verfügbar. Der Deutschland-Alias kann unabhängig davon auf
die vorherige, intakte Version zurückgesetzt werden.

## Noch nicht automatisch erfüllt

- aktuellerer OSM-Snapshot als der gepinnte Stand vom 1. Januar 2026;
- realer Deutschland-Buildbeleg auf dem Heim-PC;
- produktiver Caddy-Readback;
- bundesweite visuelle Abnahme;
- gemessene Artefaktgröße, Builddauer und Bandbreite.

Diese Punkte sind Freigabebedingungen, keine stillschweigend als erfüllt
geltenden Annahmen.
