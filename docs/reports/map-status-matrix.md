---
id: map-status-matrix
title: Map Status Matrix
doc_type: status-matrix
status: active
summary: Repo-wahre Statusmatrix fuer die aktuelle Kartenimplementierung.
relations:
  - type: relates_to
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
---

Dieses Dokument beschreibt den belegbaren Ist-Zustand der aktuellen
Kartenimplementierung. Massgeblich sind nur Dateien, die im aktuellen
Repo-Stand tatsaechlich vorhanden sind.

## 1. Kartendatenquelle

- **Soll**: Klare, explizite Datenquelle fuer die Karte.
- **Ist**: Die Route importiert `apps/web/src/lib/data/dummy.json` direkt in `apps/web/src/routes/map/+page.svelte`.
- **Status**: Teil
- **Nachweis**: `apps/web/src/routes/map/+page.svelte`, `apps/web/src/lib/data/dummy.json`
- **Fehlend**: Loader/API-Vertrag, Lade- und Fehlerzustaende.

## 2. Interaktion und Panel

- **Soll**: Marker-Auswahl oeffnet nachvollziehbar den Informationsbereich.
- **Ist**: Marker-Click setzt die Auswahl und oeffnet das rechte Panel.
- **Status**: Erledigt
- **Nachweis**: `apps/web/tests/map-marker-panel.spec.ts`

## 3. Basemap-Abhaengigkeit

- **Soll**: Dokumentierte und bewusst entschiedene Basemap-Strategie.
- **Ist**: MapLibre wird mit `https://demotiles.maplibre.org/style.json` initialisiert.
- **Status**: Teil
- **Nachweis**: `apps/web/src/routes/map/+page.svelte`
- **Fehlend**: Entscheidung, ob externe Demo-Assets akzeptiert oder ersetzt werden.

## 4. Infrastruktur-Kopplung

- **Soll**: Web-Runtime, Caddy-Proxy und Kartenabhaengigkeiten passen dokumentiert zusammen.
- **Ist**: `infra/caddy/Caddyfile` reverse-proxyt Web und API; eine
  spezifische repo-eigene Basemap-Konfiguration ist dort nicht hinterlegt.
- **Status**: Teil
- **Nachweis**: `infra/caddy/Caddyfile`
- **Fehlend**: Dokumentierte Zuordnung zwischen Basemap-Strategie, CSP und Runtime.

## 5. Testabdeckung

- **Soll**: Kerninteraktion und Fehlerpfade der Karte sind testseitig belegt.
- **Ist**: Smoke-Test und Marker-Panel-Test vorhanden; Fehler-, Lade- und Basemap-Ausfallpfade sind nicht belegt.
- **Status**: Teil
- **Nachweis**: `apps/web/tests/map-smoke.spec.ts`, `apps/web/tests/map-marker-panel.spec.ts`
- **Fehlend**: Tests fuer leere Daten, Fehlerzustaende, Basemap-Probleme und Offline-Verhalten.

## 6. Runtime-Integration

- **Soll**: Echter HTTP-206-Nachweis, dass Caddy ein reales PMTiles-Artefakt per Range-Request korrekt ausliefert.
- **Ist**: Guard-Script vorhanden (`scripts/guard/basemap-runtime-proof.sh`); prueft HTTP 206, Range-Header und
  unterscheidet explizit zwischen PROVEN und NOT_PROVEN. CI-Job vorhanden
  (`.github/workflows/basemap-runtime-proof.yml`), non-blocking.
- **Status**: Teil
- **Nachweis**: `scripts/guard/basemap-runtime-proof.sh`, `.github/workflows/basemap-runtime-proof.yml`
- **Fehlend**: Echter CI-Nachweis; PMTiles-Artefakt ist im CI aktuell nicht verfuegbar.
  Solange kein reales Artefakt im CI-Stack vorhanden ist, bleibt der HTTP-206-Beweis offen.
  Der gemockte Client-Test (`apps/web/tests/basemap-client-integration.spec.ts`) ist kein Ersatz.

## Essenz

Die Karte ist als Demo-Navigation mit Marker-Interaktion belegt. Nicht belegt
sind derzeit ein expliziter Datenvertrag, eine geklaerte Basemap-Strategie und
belastbare Fehlerpfade.
