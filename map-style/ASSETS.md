# Asset Manifest: Glyphs & Sprites

Dieses Verzeichnis dokumentiert die Herkunft, Lizenzierung und Integration der visuellen Assets (Schriften und Icons), die von der souveränen Basemap (`style.json`) genutzt werden.

> **Status-Hinweis:** Derzeit dokumentiert dieses Manifest die beabsichtigte lokale Asset-Strategie. Es ist noch kein vollständiges, abschließendes Lizenz- und Bestandsmanifest. Die konkrete Toolchain und die physischen Artefakte fehlen noch (Scaffold-Phase).

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
- **Geplante Herkunft / Erzeugung:** Ableitung aus quelloffenen Font-Dateien via MapLibre-kompatibler Toolchain (z. B. fontmaker). Die konkrete Toolchain, Reproduktionsschritte und die genaue Version der Input-Quelle sind noch verbindlich festzulegen.

_Hinweis: Die `.pbf` Dateien für "Noto Sans Regular" müssen in `map-style/glyphs/Noto Sans Regular/` abgelegt werden. Bisher existiert das Verzeichnis nur als Platzhalter._

## Sprites (Icons & Pattern)

Verzeichnis: `map-style/sprites/`

MapLibre nutzt Spritesheets (`sprite.png`, `sprite@2x.png` und `sprite.json`), um POI-Icons, Highway-Shields oder Füllmuster (Background Patterns) zu rendern.

- **Lizenz:** (noch festzulegen, z. B. CC0 / Public Domain / OpenStreetMap kompatibel). Lizenz und Herkunft sind derzeit unvollständig.
- **Inhalt:** Minimalistisches Set, abgestimmt auf eine beruhigte Infrastruktur-Basemap. Konkreter Inhaltsumfang ist noch offen.

_Hinweis: Die Sprite-Dateien (`sprite.json`, `sprite.png`, etc.) müssen hier noch generiert und abgelegt werden._
