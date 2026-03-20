---
id: map-blaupause
title: Basemap-Architektur-Blaupause
doc_type: blueprint
status: draft
canonicality: canonical
summary: >
  Architektur-Blaupause für einen souveränen Basemap-Stack basierend auf
  MapLibre, PMTiles und einer reproduzierbaren Tile-Generierungs-Pipeline
  für Weltgewebe-Overlays.
---

# Basemap-Architektur-Blaupause

> **Hinweis:** Dies ist das normative Architektur-Dokument. Der exekutive Inkrementpfad dazu befindet sich in der [Basemap-Umsetzungsroadmap](map-roadmap.md). Blueprint und Roadmap sind als Paket zu verstehen.

## Kontext

Wenn die Karte der Kern des Systems ist, sollte sie vollständig souverän betrieben werden:
eigene Daten → eigenes Tile-Artefakt → eigener Stil → eigener Hosting-Pfad.
Das führt zu einer Architektur MapLibre + PMTiles + eigener Pipeline.
Die Karte wird als Kerninfrastruktur und nicht als UI-Service betrachtet.

## Ist-Zustand

Die Implementierung nutzt im lokalen Entwicklungsbetrieb nun standardmäßig die lokale souveräne Basemap-Pipeline (`local-sovereign`).
Die Style- und Asset-Auslieferung ist im Dev-Setup über den lokalen Vite-Server angebunden und verifiziert.
Produktionshosting und vollständige Betriebsreife des finalen PMTiles-Artefakts bleiben davon getrennt zu betrachten und stellen den ausstehenden Teil dieses Blueprints dar.

## Abwägungen

Zu frühe Souveränität kann operative Komplexität erzeugen:
Tile-Builds, OSM-Updates, Style-Assets, CDN-Konfiguration.
Viele Projekte verlieren hier Geschwindigkeit, was bei selbst gehosteten Basemaps bedacht werden muss.

## Entwurfsprinzipien

Die ideale Blaupause ist souverän, aber modular:

- Basemap ist ein Artefakt, kein Service
- Hosting ist serverlos möglich (PMTiles)
- Pipeline ist reproduzierbar
- MapLibre bleibt reine Rendering-Engine
- Overlays bleiben komplett entkoppelt

Damit erhält man Souveränität ohne Architekturbruch.

## Architekturziele

- Volle Basemap-Souveränität
- Anbieterunabhängigkeit
- Reproduzierbare Builds
- Artefaktbasiertes Deployment

## Artefaktfluss

- OpenStreetMap-Daten
- → Tile-Generierung
- → MBTiles
- → PMTiles-Artefakt
- → Hosting
- → MapLibre Rendering
- → Weltgewebe-Overlay-Layer

Ziel: Die Basemap wird als Artefakt erzeugt und verteilt, nicht als externer Kartenservice konsumiert.

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

### Tileset-Strategie

Mögliche Startpunkte:

- `hamburg.pmtiles` – schnelle lokale Iteration, geringste Speicherkosten
- `germany.pmtiles` – guter Mittelweg aus Abdeckung und Build-Dauer
- `europe.pmtiles` – maximale Reichweite, aber höchste Build- und Speicherkosten

Damit wird klar unterschieden zwischen Large Scale und Local Scale.

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

Eine logische und physische Trennung der Repositories ist sinnvoll:

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

MapLibre `style.json` ist Teil des `map-style` repositories.

Style-Ownership ist wichtig, weil:

- Glyphs
- Sprites
- Layer order
- Color palette

sonst wieder fremd kontrolliert werden.

```text
weltgewebe-map-style
 ├─ style.json
 ├─ sprites/
 ├─ glyphs/
 └─ colors.json
```

---

### 3.3 Asset-Compliance & Lizenzierung

Souveränität umfasst nicht nur das Hosting, sondern auch eine lückenlos nachvollziehbare Rechtekette für alle Assets.

- **Karten-Attribution:** Die OSM-/ODbL-Pflichten müssen im Client (MapLibre UI) jederzeit korrekt und sichtbar erfüllt sein.
- **Style-Assets:** Herkunft und Lizenz von Glyphs, Sprites und Fonts müssen im `map-style` Repository dokumentiert sein.
- **Keine stillen Abhängigkeiten:** Das finale Kartenprodukt darf nicht stillschweigend von fremden Diensten oder unklaren Fremdlizenzen abhängen.

---

### 3.4 weltgewebe-web

Hier lebt:

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

Empfohlene Build-Umgebung:

- RAM: 32-64 GB
- Storage: 100 GB
- CPU: multi-core

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

### MapLibre Layer Order

MapLibre Layer Order:

1. Basemap layers
2. Graph edges
3. Activity layers
4. Nodes (DOM markers)
5. Focus / highlight

---

## 6. Overlay-Philosophie

Basemap enthält:

- landcover
- water
- roads
- administrative boundaries
- place labels

Basemap enthält NICHT:

- domain nodes
- graph edges
- activity layers
- semantic overlays

Strikte Trennung. Das verhindert später die Frage: "Packen wir das noch in die Basemap?"

Weltgewebe enthält:

- nodes
- edges
- activity
- focus
- komposition

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

- Weniger HTTP Requests
- CDN Cache
- Streaming Tiles

Typischer Ladevorgang:

PMTiles reduziert typischerweise die Anzahl einzelner Tile-Anfragen, da Tiles aus einem zusammenhängenden Artefakt per HTTP Range Requests gelesen werden.

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

## Risiken

- Komplexität der Tile-Generierungs-Pipeline
- Management von OSM-Updates
- Speichergröße regionaler Tilesets (Europa Tileset: 10-20 GB)
- Buildzeit (Planet: mehrere Stunden)

---

## Annahmen

- Langfristiger Plattformanspruch für die Basemap
- Infrastruktur-Integration (z. B. Heimserver)
- MapLibre bleibt als Rendering-Engine erhalten
