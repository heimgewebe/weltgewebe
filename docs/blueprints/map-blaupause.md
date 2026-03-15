---
id: map-blaupause
title: Basemap Architecture Blueprint
doc_type: blueprint
status: draft
canonicality: canonical
summary: >
  Architecture blueprint for a sovereign basemap stack based on
  MapLibre, PMTiles and a reproducible tile generation pipeline
  for Weltgewebe overlays.
---

# Basemap Architecture Blueprint

## Context

Wenn die Karte der Kern des Systems ist, sollte sie vollständig souverän betrieben werden:
eigene Daten → eigenes Tile-Artefakt → eigener Stil → eigener Hosting-Pfad.
Das führt zu einer Architektur MapLibre + PMTiles + eigener Pipeline.
Die Karte wird als Kerninfrastruktur und nicht als UI-Service betrachtet.

## Current State

The current implementation uses MapLibre with an external basemap style.
The basemap is currently treated as an external dependency.
This blueprint defines the target architecture for replacing that dependency
with a sovereign PMTiles-based basemap pipeline.

## Trade-offs

Zu frühe Souveränität kann operative Komplexität erzeugen:
Tile-Builds, OSM-Updates, Style-Assets, CDN-Konfiguration.
Viele Projekte verlieren hier Geschwindigkeit, was bei selbst gehosteten Basemaps bedacht werden muss.

## Design Principles

Die ideale Blaupause ist souverän, aber modular:

- Basemap is an artifact, not a service
- Hosting can be serverless (PMTiles)
- Pipeline must be reproducible
- MapLibre is only the rendering engine
- Overlays remain fully decoupled

Damit erhält man Souveränität ohne Architekturbruch.

---

## 1. Systemarchitektur

```text
               OSM Daten
                   │
                   ▼
            Tile Generation
         (planetiler / tilemaker)
                   │
                   ▼
               PMTiles
          basemap-vX.pmtiles
                   │
                   ▼
                Storage
       (S3 / R2 / Heimserver / CDN)
                   │
                   ▼
                MapLibre
                   │
        ┌──────────┼───────────┐
        ▼          ▼           ▼
      Edges      Nodes      Activity
      Overlay    Overlay    Overlay
```

### Prinzip

Basemap = Infrastruktur
Overlay = Weltgewebe

---

## 2. Komponenten

### 2.1 Rendering Engine

MapLibre GL

Vorteile:

- Open Source
- Mapbox-Style kompatibel
- PMTiles kompatibel
- keine Vendorbindung

---

### 2.2 Tile-Format

PMTiles

Eigenschaften:

- Single-File Tileset
- Range Requests
- CDN-freundlich
- offlinefähig

Beispiel:

`basemap-europe-v1.pmtiles`

---

### 2.3 Tile-Generierung

Empfohlenes Tool:

planetiler

Vorteile:

- extrem schnell
- gute OSM-Pipeline
- aktiv entwickelt

Alternativen:

- tilemaker
- openmaptiles

---

### 2.4 Datenquelle

OpenStreetMap

Regionen:

- planet
- europe
- germany
- hamburg

Start sinnvoll:

europe

---

### 2.5 Hosting

Optionen:

Cloud

- Cloudflare R2
- S3
- Backblaze

Heimserver

`tiles.weltgewebe.org`

CDN

optional:

Cloudflare CDN

---

## 3. Repositories (empfohlene Struktur)

Im Heimgewebe-Kosmos ist eine Trennung sinnvoll:

- weltgewebe-basemap
- weltgewebe-map-style
- weltgewebe-web

---

### 3.1 basemap repo

```text
weltgewebe-basemap
 ├─ data/
 ├─ build/
 ├─ scripts/
 │   ├─ fetch-osm.sh
 │   ├─ build-tiles.sh
 │   └─ build-pmtiles.sh
 ├─ basemap.pmtiles
 └─ basemap.meta.json
```

---

### 3.2 map-style repo

```text
weltgewebe-map-style
 ├─ style.json
 ├─ sprites/
 ├─ glyphs/
 └─ colors.json
```

---

### 3.3 weltgewebe-web

hier lebt:

- MapLibre
- Overlay
- Nodes
- Edges
- Activity

---

## 4. Tile-Pipeline

### Schritt 1

OSM Download

```bash
wget https://download.geofabrik.de/europe-latest.osm.pbf
```

---

### Schritt 2

Tiles generieren

```bash
planetiler \
  --osm-path=europe.osm.pbf \
  --output=basemap.mbtiles
```

---

### Schritt 3

PMTiles erzeugen

```bash
pmtiles convert basemap.mbtiles basemap.pmtiles
```

---

### Schritt 4

Deploy

upload basemap.pmtiles

z. B.

`tiles.weltgewebe.org/basemap.pmtiles`

---

## 5. MapLibre Integration

```javascript
import { Protocol } from "pmtiles";

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

const map = new maplibregl.Map({
  container: "map",
  style: "/style.json"
});
```

---

Style:

```json
{
 "sources": {
   "basemap": {
     "type": "vector",
     "url": "pmtiles://tiles.weltgewebe.org/basemap.pmtiles"
   }
 }
}
```

---

## 6. Overlay-Philosophie

Basemap enthält nur:

- roads
- water
- landuse
- labels

Weltgewebe enthält:

- nodes
- edges
- activity
- focus
- komposition

Strikte Trennung.

---

## 7. Versionierung

Basemap ist Artefakt.

`basemap-v1.pmtiles`
`basemap-v2.pmtiles`

Deploy-Strategie:

`/tiles/basemap-current.pmtiles`

---

## 8. Update-Strategie

OSM Updatezyklus:

monatlich

Pipeline:

cron → rebuild tiles → publish artifact

---

## 9. Performance

PMTiles Vorteile:

- weniger HTTP Requests
- CDN Cache
- Streaming Tiles

Typischer Ladevorgang:

\<100 requests

statt tausender Tiles.

---

## 10. Erweiterungen

Später möglich:

Activity Heatmap

MapLibre heatmap layer

Regionale Tiles

`germany.pmtiles`
`europe.pmtiles`

Offline Mode

local pmtiles

---

## 11. Alternative Sinnachse

Langfristig könnte Weltgewebe mehrere Kartenprojektionen haben:

- Geographie
- Netzwerk
- Themenraum
- Zeit

Die Basemap ist dann nur eine Projektion des Wissensraums.

---

## Essenz

Die ideale Basemap-Architektur für das System ist:

MapLibre
   +
PMTiles
   +
planetiler
   +
OpenStreetMap
   +
eigener Style

Das liefert:

- maximale Souveränität
- langfristige Kontrolle
- minimale Anbieterabhängigkeit
- hohe Performance

---

## Risks

- Tile generation pipeline complexity
- OSM update management
- Storage size of regional tilesets (Europa Tileset: 10-20 GB)
- Buildzeit (Planet: mehrere Stunden)

---

## Assumptions

- Long-term platform ownership of the basemap
- Integration with Heimserver infrastructure
- MapLibre remains the rendering engine
