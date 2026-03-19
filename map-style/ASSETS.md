# Asset Manifest: Glyphs & Sprites

Dieses Verzeichnis dokumentiert die Herkunft, Lizenzierung und Integration der visuellen Assets (Schriften und Icons), die von der souveränen Basemap (`style.json`) genutzt werden.

## Strategie

Um echte **Style-Souveränität** (Phase 2) zu erreichen, dürfen wir keine externen Abhängigkeiten (wie CartoCDN oder Mapbox-Server) für Schriften (Glyphs) oder Icons (Sprites) verwenden. Diese externen Aufrufe gefährden Offline-Fähigkeit, Caching und führen zu stillen Tracking-Risiken durch Dritte.

Daher ist die Strategie für alle visuell benötigten Assets:

1. **Lokales Hosting**: Alle Assets liegen physisch in diesem Repository (`map-style/`).
2. **Pfad-Integration**: In der `style.json` verweisen `sprite` und `glyphs` auf relative Pfade (`./sprites/sprite`, `./glyphs/{fontstack}/{range}.pbf`).
3. **Klare Lizenzen**: Jedes Asset muss mit einer kompatiblen, dokumentierten Open-Source-Lizenz versehen sein.

## Glyphs (Schriften)

Verzeichnis: `map-style/glyphs/`

MapLibre benötigt Schriften im Protocol Buffer Format (PBF), gesplittet in Unicode-Ranges.

- **Ausgewählte Schriftart:** Noto Sans Regular (wie in `style.json` referenziert)
- **Lizenz:** SIL Open Font License (OFL)
- **Herkunft:** Generiert aus den originalen Google Fonts via MapLibre-kompatiblen Tools (z.B. fontmaker).

*Hinweis: Die `.pbf` Dateien für "Noto Sans Regular" müssen in `map-style/glyphs/Noto Sans Regular/` abgelegt werden. Bisher existiert das Verzeichnis als Platzhalter.*

## Sprites (Icons & Pattern)

Verzeichnis: `map-style/sprites/`

MapLibre nutzt Spritesheets (`sprite.png`, `sprite@2x.png` und `sprite.json`), um POI-Icons, Highway-Shields oder Füllmuster (Background Patterns) zu rendern.

- **Lizenz:** (noch festzulegen, z. B. CC0 / Public Domain / OpenStreetMap kompatibel)
- **Inhalt:** Minimalistisches Set, abgestimmt auf eine beruhigte Infrastruktur-Basemap.

*Hinweis: Die Sprite-Dateien (`sprite.json`, `sprite.png`, etc.) werden hier generiert und abgelegt.*
