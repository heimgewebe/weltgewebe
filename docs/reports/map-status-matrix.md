---
id: map-status-matrix
title: Map Status Matrix
doc_type: status-matrix
status: active
summary: >
  Dieses Dokument bildet den auf Basis der vorhandenen Repo-Evidenz belegbaren Ist-Zustand der Basemap-Architektur ab.
---

# Map Status Matrix

Dieses Dokument bildet den auf Basis der vorhandenen Repo-Evidenz belegbaren Ist-Zustand ab. Es ist rein diagnostisch und ersetzt nicht die normative [Roadmap](../blueprints/map-roadmap.md), sondern dokumentiert den belegbaren Stand gegenüber diesem Zielbild.

Das Feld `generated_from` (bzw. die Metadaten) benennt bewusst nur die zentralen Primärquellen der Diagnosebildung (Blueprints, zentrale Codepfade). Die vollständigen, konkreten Belege finden sich transparent im `code_runtime_evidence` der jeweiligen JSON-Bereiche.

## 1. Basemap Grundlage

- **Soll**: Lokales Artefakt generieren (planetiler, PMTiles).
- **Ist**: Alle infrastrukturellen Werkzeuge und Prozesse zur Offline-Generierung des Artefakts sind vorhanden.
- **Status**: Erledigt
- **Nachweis**: `scripts/basemap/build-hamburg-pmtiles.sh`

## 2. Style-Souveränität

- **Soll**: Eigenes `style.json`, Glyphs lokal, keine fremden Abhängigkeiten.
- **Ist**: `style.json` vorhanden, Glyphs lokal. Overlay-Lesbarkeit gegen Basemap ist strukturell durch Playwright-Tests validiert (`edge-visibility.spec.ts`), die echte visuelle Abnahme kann aktuell nur manuell erfolgen.
- **Status**: Teil
- **Fehlend**: Echte visuelle Abnahme (Manual QA / VRT).

## 3. Runtime-Integration

- **Soll**: MapLibre nutzt PMTiles-Artefakt via Caddy ohne externe CDN-Calls.
- **Ist**: Client-Verhalten ist belegt (Frontend parst PMTiles-Protokoll und sendet Range-Header im Mock `basemap-client-integration.spec.ts`). Route-Contract ist belegt (Caddy-Route existiert in `Caddyfile`/`Caddyfile.heim` und wird per Guard `caddy-basemap-route-guard.sh` validiert). `PUBLIC_BASEMAP_MODE` Contract ist verankert.
- **Status**: Teil
- **Fehlend**: Echter E2E-Nachweis gegen reales Caddy-Backend mit echtem PMTiles-Byte-Stream im CI.

## 4. Betrieb und Versionierung

- **Soll**: `basemap-vX.pmtiles`, `meta.json` Sentinel Contract, Atomic Switch.
- **Ist**: Sentinel Contract und Rollback-Logik in Scripts implementiert.
- **Status**: Erledigt

## 5. Ausbau

- **Soll**: Heatmap/Activity-Layer, Offline-Modus, Regionale Tilesets.
- **Ist**: Regionale Scripts für Hamburg und Deutschland vorhanden. Heatmap-Frontend-Layer `activity.ts` implementiert und getestet, liest `weight`. Serverseitige Activity-Daten (Event-Stream) fehlen.
- **Status**: Teil
- **Fehlend**: Event-Stream-Integration im Backend, Offline-Modus-Konzept.
