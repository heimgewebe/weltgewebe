# Asset Manifest: Glyphs & Sprites

Dieses Dokument dokumentiert die Herkunft, Lizenzierung und Integration der visuellen Assets (Schriften und Icons), die
von der souveränen Basemap (`style.json`) genutzt werden.

> **Status-Hinweis:** Dieses Manifest dokumentiert die Herkunft und Lizenz der lokal gehosteten Schriftarten (Glyphs). Die Sprite-Artefakte befinden sich noch in der Scaffold-Phase.

## Strategie

Um echte **Style-Souveränität** (Phase 2) zu erreichen, dürfen wir keine externen Abhängigkeiten (wie CartoCDN oder
Mapbox-Server) für Schriften (Glyphs) oder Icons (Sprites) verwenden. Diese externen Aufrufe gefährden
Offline-Fähigkeit, Caching und führen zu stillen Tracking-Risiken durch Dritte.

Daher ist die Strategie für alle visuell benötigten Assets:

1. **Lokales Hosting**: Alle benötigten Assets sollen physisch in diesem Verzeichnis (`map-style/`) abgelegt und lokal
   ausgeliefert werden.
2. **Pfad-Integration**: In der `style.json` verweisen `sprite` und `glyphs` auf relative Pfade (`./sprites/sprite`,
   `./glyphs/{fontstack}/{range}.pbf`).
3. **Klare Lizenzen**: Jedes Asset muss mit einer kompatiblen, dokumentierten Open-Source-Lizenz versehen sein.

## Glyphs (Schriften)

Verzeichnis: `map-style/glyphs/`

MapLibre benötigt Schriften im Protocol Buffer Format (PBF), gesplittet in Unicode-Ranges.

- **Ausgewählte Schriftart:** Noto Sans Regular (wie in `style.json` referenziert)
- **Lizenz:** SIL Open Font License (OFL)
- **Herkunft / Erzeugung:** Die Schriftarten (v2.0) werden über das deterministische Skript `scripts/basemap/fetch-glyphs.sh` reproduzierbar vom offiziellen [OpenMapTiles Fonts Release](https://github.com/openmaptiles/fonts/releases) geladen und über einen SHA256-Hash validiert. Da es sich um kompilierte Artefakte handelt, sind die `.pbf`-Dateien nicht im Repo eingecheckt. Das Deployment-Skript `weltgewebe-up` versucht als "Best Effort Guard", fehlende Fonts beim Stack-Start aus der definierten Quelle zu beziehen und bereitzustellen.

## Sprites (Icons & Pattern)

Verzeichnis: `map-style/sprites/`

MapLibre nutzt Spritesheets (`sprite.png`, `sprite@2x.png` und `sprite.json`), um POI-Icons, Highway-Shields oder
Füllmuster (Background Patterns) zu rendern.

- **Lizenz:** (noch festzulegen, z. B. CC0 / Public Domain / OpenStreetMap kompatibel). Lizenz und Herkunft sind derzeit
  unvollständig.
- **Inhalt:** Minimalistisches Set, abgestimmt auf eine beruhigte Infrastruktur-Basemap. Konkreter Inhaltsumfang ist
  noch offen.

_Hinweis: Die Sprite-Dateien (`sprite.json`, `sprite.png`, etc.) müssen hier noch generiert und abgelegt werden._
