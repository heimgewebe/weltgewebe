The CI failed due to markdown formatting errors in `docs/reports/map-status-matrix.md`.
The errors indicate missing blank lines around lists and headings:
- MD022/blanks-around-headings: Headings should be surrounded by blank lines.
- MD032/blanks-around-lists: Lists should be surrounded by blank lines.

The content of `docs/reports/map-status-matrix.md` currently looks like:
```markdown
## 1. Basemap Grundlage
- **Soll**: Lokales Artefakt generieren (planetiler, PMTiles, Heimserver/Caddy).
- **Ist**: Alle infrastrukturellen Werkzeuge und Prozesse zur Offline-Generierung sind vorhanden.
- **Status**: Erledigt
- **Nachweis**: `scripts/basemap/build-hamburg-pmtiles.sh`

## 2. Style-Souveränität
- **Soll**: Eigenes `style.json`, Glyphs lokal, keine fremden Abhängigkeiten.
```

I need to fix the formatting to have blank lines around lists and headings.

```markdown
## 1. Basemap Grundlage

- **Soll**: Lokales Artefakt generieren (planetiler, PMTiles, Heimserver/Caddy).
- **Ist**: Alle infrastrukturellen Werkzeuge und Prozesse zur Offline-Generierung sind vorhanden.
- **Status**: Erledigt
- **Nachweis**: `scripts/basemap/build-hamburg-pmtiles.sh`

## 2. Style-Souveränität

- **Soll**: Eigenes `style.json`, Glyphs lokal, keine fremden Abhängigkeiten.
...
```

Let's modify `docs/reports/map-status-matrix.md` and commit the fix.
