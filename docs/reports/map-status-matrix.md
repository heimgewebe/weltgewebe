---
id: map-status-matrix
title: Map Status Matrix
doc_type: status-matrix
status: active
summary: >
  Dieses Dokument bildet den auf Basis der vorhandenen Repo-Evidenz belegbaren Ist-Zustand der Basemap-Architektur ab.
relations:
  - type: relates_to
    target: docs/blueprints/map-roadmap.md
  - type: relates_to
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
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
- **Ist**: `style.json` vorhanden, Glyphs lokal. Overlay-Lesbarkeit gegen Basemap ist strukturell durch Playwright-Tests validiert (`edge-visibility.spec.ts`). Basemap-Client-Verhalten im E2E-Test-Build verifiziert: `basemap-sovereignty-testbuild.spec.ts` bestätigt, dass `isStyleLoaded()` ohne externe CDN-Abhängigkeiten auflöst (1/1 grün, 2026-04-23).
- **Status**: Teil
- **Fehlend**: Echte visuelle Abnahme (Manual QA / VRT) gegen reale Basemap-Renders.

## 3. Runtime-Integration

- **Soll**: MapLibre nutzt PMTiles-Artefakt via Caddy ohne externe CDN-Calls.
- **Ist**: Client-Verhalten ist belegt: `basemap-client-integration.spec.ts` bestätigt, dass Frontend das PMTiles-Protokoll parst und Range-Header sendet (E2E-verifiziert, 2026-04-23, 1/1 grün). Route-Contract ist belegt (Caddy-Route in `Caddyfile`/`Caddyfile.heim`, per Guard `caddy-basemap-route-guard.sh` validiert). `PUBLIC_BASEMAP_MODE` Contract ist verankert.
- **Status**: Teil
- **Fehlend**: Echter E2E-Nachweis gegen reales Caddy-Backend mit echtem PMTiles-Byte-Stream im CI (HTTP 206 Responses).

## 4. Betrieb und Versionierung

- **Soll**: `basemap-vX.pmtiles`, `meta.json` Sentinel Contract, Atomic Switch.
- **Ist**: Sentinel Contract und Rollback-Logik in Scripts implementiert.
- **Status**: Erledigt

## 5. Ausbau

- **Soll**: Offline-Modus, regionale Tilesets, mehrskalige Projektionen, verbesserte Faden-Lesbarkeit.
- **Ist**: Regionale Scripts für Hamburg und Deutschland vorhanden. Heatmap bewusst entfernt (Dichtevisualisierung erfolgt ausschließlich über Fäden). Heatmap-Invariante durch `no-activity-heatmap.spec.ts` E2E-verifiziert (1/1 grün, 2026-04-23).
- **Status**: Teil
- **Fehlend**: Offline-Modus-Konzept, Clustering ohne Semantikbruch.

---

## 6. Kartenklarheit-Architektur (Nachtrag 2026-04-23)

Ergänzender Status zur Kartenklarheit-Roadmap (Phasen 1–6):

| Bereich | Status | Nachweis |
| :--- | :--- | :--- |
| MapLoadState (`ok \| partial \| failed`) | Erledigt | Unit-Tests: `scene.test.ts` (10/10), E2E: `map-load-fallback.spec.ts` (4/4 grün) |
| MapSceneModel / `buildMapScene()` | Erledigt | Unit-Tests: `scene.test.ts` (10/10) |
| Diskriminierte Union `MapEntityViewModel` | Erledigt | Unit-Tests: `scene.test.ts` (10/10) |
| Getrennte Diagnostics (`apiMode` / `basemapMode`) | Erledigt | E2E: `map-load-fallback.spec.ts` — Debug-Badge-Test grün |
| Zustands-Ownership dokumentiert | Erledigt | JSDoc-Ownership-Matrix in `uiView.ts` |
| Degradierte UI-Zustände (Banner) | Erledigt | E2E: `map-load-fallback.spec.ts` (partial + failed) grün |
| Suchlogik auf `scene.entities` | Erledigt | E2E: `map-interaction.spec.ts` grün |
| Filterlogik auf `scene.entities` | Erledigt | E2E: `map-interaction.spec.ts` grün |
| Fokus/Komposition | Erledigt | E2E: `map-interaction.spec.ts` grün (unverändert) |
| Faden-Invariante (kein Heatmap) | Erledigt | E2E: `no-activity-heatmap.spec.ts` (1/1 grün) |
| Default-View (Hammer Park) | Erledigt | E2E: `map-default-view.spec.ts` (1/1 grün) |
| Basemap-Modus-Auflösung | Erledigt | Unit-Tests: `basemap.test.ts` (7/7) |
| PMTiles-URL-Rewriting | Erledigt | Unit-Tests: `basemap.test.ts` (7/7) |

**Teststand (2026-04-23):**
- Unit-Tests (vitest): 39/39 grün
- E2E-Tests (Playwright, Chromium): 22/22 grün (inkl. Basemap-Sovereignty, Client-Integration, Map-Interaktion, Load-Fallback, Heatmap-Guard, Default-View)

**Noch ausstehend (nicht durch automatisierte Tests abgedeckt):**
- Echter Caddy+PMTiles-E2E-Nachweis (HTTP 206 im CI)
- Manuelle / VRT-basierte visuelle Abnahme der Overlay-Lesbarkeit
