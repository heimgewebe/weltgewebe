---
id: docs.blueprints.kartenklarheit-roadmap
title: Roadmap - Kartenklarheit
doc_type: roadmap
status: active
relations:
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
summary: Roadmap fuer den Uebergang von der aktuellen Demo-Karte zu einer belastbaren, nachvollziehbaren Kartenarchitektur.
---

Statuslegende: `[ ] offen`, `[~] in Arbeit`, `[x] erledigt`

## Ziel

Die Kartenroute soll von einem lokal verdrahteten Demo-Stand zu einer klar
dokumentierten, testbaren und spaeter produktionsfaehigen
Kartenimplementierung weiterentwickelt werden.

## Gesicherte Ausgangslage

- [x] Kartenroute existiert in `apps/web/src/routes/map/+page.svelte`.
- [x] Kartendaten kommen aktuell direkt aus `apps/web/src/lib/data/dummy.json`.
- [x] Marker-Interaktion oeffnet das rechte Panel; dieser Ablauf ist durch `apps/web/tests/map-marker-panel.spec.ts` belegt.
- [x] Grundlegende Sichtbarkeit der Kartenroute ist durch `apps/web/tests/map-smoke.spec.ts` belegt.
- [x] Die Basemap verwendet derzeit einen externen Style (`https://demotiles.maplibre.org/style.json`).

---

## Phase 0 - Ist-Zustand sichern

### Ziel der Phase 0

Den aktuellen Demo-Stand explizit benennen, damit spaetere Verbesserungen
gegen einen klaren Referenzpunkt bewertet werden koennen.

### Arbeitspakete der Phase 0

- [x] Relevante Einstiegspfade benannt:
  - `apps/web/src/routes/map/+page.svelte`
  - `apps/web/src/lib/data/dummy.json`
  - `apps/web/src/lib/maplibre/MapLibre.svelte`
  - `apps/web/src/lib/maplibre/Marker.svelte`
- [x] Relevante Tests benannt:
  - `apps/web/tests/map-smoke.spec.ts`
  - `apps/web/tests/map-marker-panel.spec.ts`
- [x] Ist-Notiz festgehalten:
  - lokale Demo-Daten statt Loader/API
  - lokaler `MapPoint`-Typ direkt in `+page.svelte`
  - externer MapLibre-Demo-Style statt repo-eigener Basemap-Konfiguration

### Stop-Kriterium der Phase 0

- [x] Der Demo-Stand ist so dokumentiert, dass spaetere Architekturbehauptungen daran messbar sind.

---

## Phase 1 - Datenquelle explizit machen

### Ziel der Phase 1

Die Kartenroute soll nicht dauerhaft direkt auf Demo-Daten verdrahtet bleiben.

### Arbeitspakete der Phase 1

- [ ] Datenbeschaffung aus `+page.svelte` herausloesen.
- [ ] Entscheiden, ob die Karte aus Loader, API oder versionierter lokaler Quelle gespeist wird.
- [ ] Zwischen "keine Daten", "Laden" und "Fehler" unterscheiden.
- [ ] Den heute lokalen `MapPoint`-Typ in einen wiederverwendbaren Contract ueberfuehren.

### Verifikation der Phase 1

- [ ] Testfall fuer fehlende oder leere Datenquelle.
- [ ] Testfall fuer sichtbaren Fehlerzustand statt stiller Leere.

### Stop-Kriterium der Phase 1

- [ ] Die Kartenroute hat eine explizite Datenquelle und einen nachvollziehbaren Ladezustand.

---

## Phase 2 - Zustands- und Szenengrenzen klaeren

### Ziel der Phase 2

Kartenlogik, Markerzustand und Drawer-Zustand sollen nicht dauerhaft in einer einzelnen Routendatei zusammenliegen.

### Arbeitspakete der Phase 2

- [ ] Auswahlzustand, Markerbeschreibung und Paneldaten aus `+page.svelte` entkoppeln.
- [ ] Ein kleines Karten-View-Model oder Szenenmodell definieren.
- [ ] Query-Parameter-Zustand (`l`, `r`, `t`) und Kartenzustand getrennt dokumentieren.

### Verifikation der Phase 2

- [ ] Mindestens ein Test fuer Auswahl/Panel-Zustand ohne implizite DOM-Nebenannahmen.

### Stop-Kriterium der Phase 2

- [ ] Die Route ist nicht mehr alleinige Quelle fuer Kartenrendering, Markerzustand und Panel-Orchestrierung.

---

## Phase 3 - Basemap-Abhaengigkeit ehrlich machen

### Ziel der Phase 3

Die Basemap-Strategie soll dem tatsaechlichen Runtime-Verhalten entsprechen.

### Arbeitspakete der Phase 3

- [ ] Entscheiden, ob die externe Demo-Basemap bewusst akzeptiert oder ersetzt wird.
- [ ] Falls Ersatz gewuenscht ist: Style-, Asset- und Tile-Strategie im Repo dokumentieren.
- [ ] CSP- und Caddy-Konfiguration mit der realen Basemap-Abhaengigkeit abgleichen.

### Verifikation der Phase 3

- [ ] Dokumentierter Nachweis, ob externe Kartenassets erlaubt, benoetigt oder verboten sind.
- [ ] Browser-Test oder manuelle Pruefanleitung fuer die effektive Basemap-Aufloesung.

### Stop-Kriterium der Phase 3

- [ ] Es gibt keine implizite Basemap-Annahme mehr; die Abhaengigkeit ist dokumentiert und pruefbar.

---

## Phase 4 - Regressionen gezielt absichern

### Ziel der Phase 4

Vorhandene Browser-Tests sollen von Smoke-Absicherung zu gezielter Kartenregression wachsen.

### Arbeitspakete der Phase 4

- [x] Grundlegende Sichtbarkeit der Route pruefen (`map-smoke.spec.ts`).
- [x] Marker-Panel-Interaktion pruefen (`map-marker-panel.spec.ts`).
- [ ] Fehler-, Leere- und Ladezustaende absichern.
- [ ] Basemap-Verhalten separat absichern.
- [ ] Tastatur- und Query-Parameter-Navigation gezielt absichern.

### Stop-Kriterium der Phase 4

- [~] Kerninteraktion ist testseitig abgedeckt; Daten- und Basemap-Fehlerpfade fehlen noch.

---

## Phase 5 — Souveraene Basemap-Infrastruktur einziehen

### Ziel der Phase 5

Die souveraene Basemap-Infrastruktur (PMTiles-Pipeline, Caddy-Route, Style-Souveraenitaet) ist operational verankert.

### Arbeitspakete der Phase 5

- [x] PMTiles-Pipeline und Build-Skripte vorhanden (`scripts/basemap/`).
- [x] Caddy-Route `/local-basemap/*` in produktionsrelevanten Caddyfiles korrekt konfiguriert.
- [x] Caddy-Route-Guard eingezogen (`scripts/guard/caddy-basemap-route-guard.sh`).
- [x] Souveraenes `style.json` im `map-style`-Verzeichnis vorhanden.
- [x] PMTiles-Protokoll im Frontend registriert; Frontend-Flag (`PUBLIC_BASEMAP_MODE`) vorhanden.

### Stop-Kriterium der Phase 5

- [x] Infrastruktur-Seite ist konfiguriert und statisch verifiziert.
  Echter Runtime-Nachweis (HTTP 206 gegen reales Caddy-Backend) ist noch offen und Thema von Phase 6.

---

## Phase 6 — Wahrheitsbeweis: Basemap Runtime Proof

### Ziel der Phase 6

[~] **In Arbeit** — Vollstaendiger Nachweis ist erst erledigt, wenn HTTP-206-Beweis im CI vorliegt.

Der vollstaendige Abschlussplan fuer Phase 6 ist in
[`docs/blueprints/kartenklarheit-phase6.md`](kartenklarheit-phase6.md) definiert.

### Was in Phase 6 bewiesen werden muss

Nicht:
- „style.json existiert"
- „pmtiles gebaut"
- „Playwright-Test gruenlich"

Sondern:
- Browser / curl → HTTP → Caddy → PMTiles-Byte-Stream → HTTP 206 Partial Content → Rendering

### Arbeitspakete der Phase 6

- [x] Basemap-Runtime-Proof-Guard vorhanden: `scripts/guard/basemap-runtime-proof.sh`
  - Prueft: PMTiles-Artefakt vorhanden, Caddy erreichbar, Range-Request liefert HTTP 206,
    Accept-Ranges/Content-Range-Header vorhanden, kein stiller 200-OK.
  - Unterscheidet explizit zwischen PROVEN und NOT_PROVEN.
- [x] Non-blocking Guard-Workflow vorhanden: `.github/workflows/basemap-runtime-proof.yml`
  - Laeuft ohne Artefakt und ohne Caddy; meldet `NOT_PROVEN` — kein falsches Gruen.
  - Startet keinen Docker-Stack, baut kein PMTiles-Artefakt.
- [ ] Echter CI-Nachweis: HTTP 206 gegen reales Caddy-Backend mit realem PMTiles-Byte-Stream.
  - **Offen:** PMTiles-Artefakt wird aktuell nicht im CI gebaut und steht dort nicht zur Verfuegung.
  - Solange kein echtes Artefakt im CI vorhanden ist, bleibt dieser Punkt offen.
- [ ] Visuelle Abnahme: Karte rendert ohne Fallback nach realem Tile-Load.

### Abgrenzung: Was kein Ersatz fuer den Runtime-Beweis ist

- `apps/web/tests/basemap-client-integration.spec.ts` ist ein **gemockter Client-Test**.
  Er validiert MapLibre-Protokoll-Handling ohne echtes HTTP-Backend — kein Runtime-Beweis.
- `scripts/guard/caddy-basemap-route-guard.sh` ist ein **statischer Konfigurations-Check**.
  Er prueft Caddyfile-Struktur ohne reale Auslieferung — kein Runtime-Beweis.

### Stop-Kriterium der Phase 6

- [ ] Guard-Script liefert PROVEN (HTTP 206 bestaetigt) in einem reproduzierbaren CI-Lauf mit
  echtem PMTiles-Artefakt und laufendem Caddy-Backend.

---

## Minimalpfad

- [x] Aktuellen Demo-Stand wahrheitsgetreu dokumentieren.
- [ ] Datenquelle explizit machen.
- [ ] Externe Basemap-Abhaengigkeit klar entscheiden.
- [ ] Fehlerpfade testbar machen.
- [~] Basemap-Runtime-Beweis: Guard vorhanden, echter CI-Nachweis noch offen.

---

## Essenz

**Hebel:** Ehrliche Bestandsaufnahme vor Ausbau.
**Entscheidung:** Erst den realen Demo-Stand sauber beschreiben, dann Datenquelle, Zustand und Basemap schrittweise haerten.
**Status:** Ausgangslage dokumentiert. Interaktion grob abgesichert.
Datenmodell, Fehlerdomaene und Basemap-Strategie bleiben offen.
Phase 6 (Basemap Runtime Proof): Guard-Script eingezogen, CI-Job non-blocking vorhanden.
Echter HTTP-206-Nachweis gegen reales Caddy-Backend steht noch aus.
