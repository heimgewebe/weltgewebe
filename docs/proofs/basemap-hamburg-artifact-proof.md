---
id: docs.proofs.basemap-hamburg-artifact-proof
title: Basemap Hamburg Artifact Proof (Heimserver)
doc_type: proof
status: active
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
- Visuelle Abnahme (MapLibre Browser/E2E): `NOT_PROVEN`

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
  ```
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
- Visuelle Browser-Abnahme
