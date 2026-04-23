# Glyphs

Dieses Verzeichnis ist der lokale Ablageort für MapLibre-kompatible Schriftarten im Protocol Buffer Format (PBF). Die kompilierten Artefakte werden bewusst **nicht** ins Git-Repository eingecheckt.

Die MapLibre `style.json` erwartet die Schrift "Noto Sans Regular" und ist auf den relativen Pfad
`./glyphs/{fontstack}/{range}.pbf` konfiguriert.

Um die Karte lokal (im Modus `local-sovereign`) mit Text-Labels rendern zu können, müssen die Schriftarten einmalig bezogen werden. Führe dazu folgendes Skript aus:

```bash
./scripts/basemap/fetch-glyphs.sh
```

Für den Produktionsbetrieb versucht `weltgewebe-up` den Download als Best-Effort-Guard automatisch durchzuführen (siehe `map-style/ASSETS.md`).
