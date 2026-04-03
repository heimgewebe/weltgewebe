---
id: map-status-matrix
title: Map Status Matrix
doc_type: status-matrix
status: active
summary: >
  Dieses Dokument bildet den wahren, beweisbaren Zustand (Ist-Zustand) der Basemap-Architektur ab.
---

# Map Status Matrix

Dieses Dokument bildet den wahren, beweisbaren Zustand (Ist-Zustand) der Basemap-Architektur ab.

## 1. Basemap Grundlage
- **Soll**: Lokales Artefakt generieren (planetiler, PMTiles, Heimserver/Caddy).
- **Ist**: Alle infrastrukturellen Werkzeuge und Prozesse zur Offline-Generierung sind vorhanden.
- **Status**: Erledigt
- **Nachweis**: `scripts/basemap/build-hamburg-pmtiles.sh`

## 2. Style-Souveränität
- **Soll**: Eigenes `style.json`, Glyphs lokal, keine fremden Abhängigkeiten.
- **Ist**: `style.json` vorhanden, Glyphs lokal. Overlay-Lesbarkeit gegen Basemap ist strukturell durch Playwright-Tests validiert (`edge-visibility.spec.ts`), die echte visuelle Abnahme kann aktuell nur manuell erfolgen.
- **Status**: Teil
- **Fehlend**: Echte visuelle Abnahme (Manual QA / VRT).

## 3. Runtime-Integration
- **Soll**: MapLibre nutzt PMTiles-Artefakt via Caddy ohne externe CDN-Calls.
- **Ist**: Frontend parst das PMTiles-Protokoll und sendet korrekte Range-Header (geprüft im Mock-Test `basemap-client-integration.spec.ts`). `PUBLIC_BASEMAP_MODE` Contract ist verankert.
- **Status**: Teil
- **Fehlend**: Echter E2E-Nachweis gegen reales Caddy-Backend mit echtem PMTiles-Byte-Stream.

## 4. Betrieb und Versionierung
- **Soll**: `basemap-vX.pmtiles`, `meta.json` Sentinel Contract, Atomic Switch.
- **Ist**: Sentinel Contract und Rollback-Logik in Scripts implementiert.
- **Status**: Erledigt

## 5. Ausbau
- **Soll**: Heatmap/Activity-Layer, Offline-Modus, Regionale Tilesets.
- **Ist**: Regionale Scripts für Hamburg und Deutschland vorhanden. Heatmap-Frontend-Layer `activity.ts` implementiert und getestet, liest `weight`. Serverseitige Activity-Daten (Event-Stream) fehlen.
- **Status**: Teil
- **Fehlend**: Event-Stream-Integration im Backend, Offline-Modus-Konzept.
