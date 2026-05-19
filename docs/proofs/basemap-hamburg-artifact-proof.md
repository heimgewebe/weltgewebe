---
id: docs.proofs.basemap-hamburg-artifact-proof
title: Basemap Hamburg Artifact Proof (Heimserver)
doc_type: proof
status: active
summary: Proof that the Hamburg basemap PMTiles artifact was successfully built and deployed on the Heimserver.
relations:
  - type: relates_to
    target: scripts/basemap/build-hamburg-pmtiles.sh
  - type: relates_to
    target: scripts/guard/basemap-runtime-proof.sh
  - type: relates_to
    target: docs/roadmap.md
---

# Basemap Hamburg Artifact Proof (Heimserver)

- Host: `heimserver`
- Repo-Pfad: `/opt/weltgewebe`
- Erzeugungsdatum (UTC): `2026-05-17T07:30:48+00:00`
- Build-Befehl: `bash scripts/basemap/build-hamburg-pmtiles.sh`
- Generator/Script: `scripts/basemap/build-hamburg-pmtiles.sh` (Planetiler `0.8.2`, Image-Digest `ghcr.io/onthegomap/planetiler@sha256:10e4d6850664bd2ad7a223623383c48281e7d87fb427360838b13342cac012bb`)
- Input-Quelle: `https://download.geofabrik.de/europe/germany/hamburg-250101.osm.pbf`
- Input-SHA256 (pinned): `e9beba6f27594a3abe571dd632e752fb43c8a136b2517fa162988fd641f8cdc9`
- Output-Pfad lokal: `build/basemap/basemap-hamburg-v0.1.0.pmtiles`
- Output-Größe: `23948877` Bytes (~23 MiB)
- Output-SHA256: `f0734f0137c69b345ea81ed865519402d96f226fe15bc6c976134d9ed1f28a8e`
- Magic Header (bytes 0-6): `PMTiles` (`50 4d 54 69 6c 65 73`)

## Proof-Status

- Hamburg-PMTiles-Artefakt lokal erzeugt: `PROVEN`
- PMTiles Magic/Header lokal geprüft: `PROVEN`
- Range Delivery gegen echtes Artefakt lokal geprüft (`/local-basemap/...`, HTTP 206, `Accept-Ranges`, `Content-Range`): `PROVEN`
- PMTiles-Content-Guard-Scope (`BASEMAP_PROOF_SCOPE=pmtiles-content`): `PROVEN`
  - Beweis: Magic Header `PMTiles` an Offset 0 + SHA256 übereinstimmend via Guard ausgeführt
  - Ausgeführt am: 2026-05-17 auf heimserver, Branch `feat/basemap-pmtiles-content-proof`
  - Tiefe PMTiles-Strukturvalidierung: `NOT_PROVEN` (nicht implementiert)
- Visuelle Abnahme lokal auf heimserver (MapLibre Browser/E2E via Playwright): `PROVEN`
  - Browser: Chromium (Docker `mcr.microsoft.com/playwright:v1.55.1-noble`)
  - Ausgeführt am: 2026-05-17 auf heimserver, Branch `feat/basemap-visual-runtime-proof`
  - PMTiles-Range-Requests: 3 (alle mit `Range: bytes=0-16383`)
  - HTTP-206-Responses: 3 (`Content-Range: bytes 0-16383/23948877`)
  - Canvas gerendert: 1280×720px
  - MapLibre `isStyleLoaded()`: `true`
  - Externe Tile-Provider kontaktiert: 0 (sovereignty PROVEN)
  - Test: `apps/web/tests/proofs/basemap-real-hamburg-visual.proof.ts`
  - Start über opt-in Script: `pnpm --dir apps/web test:proof:basemap-real`
  - Laufzeit: 3.1s
- Visuelle Abnahme in GitHub Actions Standard-CI (`pnpm --dir apps/web test:ci`): `NOT_PROVEN`
  - Grund: Der opt-in Proof-Test läuft absichtlich nicht in `test:ci`, weil das reale PMTiles-Artefakt in Standard-CI nicht garantiert erzeugt wird.
  - Konsequenz: Standard-CI-Erfolg ist **kein** visueller PMTiles-Runtime-Proof.

## Belegauszüge

- Artefaktdatei:
  - `23948877 build/basemap/basemap-hamburg-v0.1.0.pmtiles`
  - `f0734f0137c69b345ea81ed865519402d96f226fe15bc6c976134d9ed1f28a8e  build/basemap/basemap-hamburg-v0.1.0.pmtiles`
- Header-Bytes:
  - `00000000: 50 4d 54 69 6c 65 73 03 ...`
- HTTP-Range-Proof:
  - `HTTP/1.1 206 Partial Content`
  - `Accept-Ranges: bytes`
  - `Content-Range: bytes 0-511/23948877`
- Guard pmtiles-content (case 3 — require + real artefact + SHA256):

  ```text
  PROVEN: PMTiles Magic/Header verified
    File:         build/basemap/basemap-hamburg-v0.1.0.pmtiles
    Size:         23948877 bytes
    Magic header: "PMTiles" at offset 0
    SHA256 check: PROVEN
  NOT_PROVEN: Deep PMTiles structure validation (tile index, directory, metadata integrity)
  ```

## Nicht bewiesen

- Vollständige PMTiles-Strukturvalidierung über Magic-Check hinaus
- Vollständigkeit/Qualität des Tile-Inhalts
- Produktionshosting/-deployment

## Visueller Beweis (Playwright)

```json
{
  "timestamp": "2026-05-17T09:21:50.484Z",
  "verdict": "PROVEN",
  "pmtiles_filename": "basemap-hamburg.pmtiles",
  "pmtiles_requests_total": 3,
  "pmtiles_range_requests": 3,
  "pmtiles_206_responses": 3,
  "canvas_dimensions": { "width": 1280, "height": 720 },
  "style_loaded": true,
  "remote_violations": [],
  "first_request": { "url": "http://127.0.0.1:5173/local-basemap/basemap-hamburg.pmtiles", "rangeHeader": "bytes=0-16383" },
  "first_206_response": { "status": 206, "contentRange": "bytes 0-16383/23948877" }
}
```
