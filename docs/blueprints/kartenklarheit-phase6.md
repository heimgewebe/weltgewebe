---
id: docs.blueprints.kartenklarheit-phase6
title: Kartenklarheit Phase 6: Der Wahrheitsbeweis
summary: Der Abschlussplan für Phase 6 der Kartenklarheit, definiert als Wahrheits-Upgrade und Beweis-Framework.
status: "in progress"
doc_type: blueprint
relations:
  - type: relates_to
    target: docs/blueprints/kartenklarheit.md
  - type: relates_to
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
---

# Kartenklarheit Phase 6: Der Wahrheitsbeweis

Diese Datei beschreibt den Abschlussplan für Phase 6 der Kartenklarheit, wie im Issue formuliert.

## These

Phase 6 ist kein „Feature bauen“, sondern ein Wahrheits-Upgrade:
Alles, was behauptet wird („funktioniert“, „souverän“, „klar“), wird jetzt real ausgeführt, gemessen und widerlegt – oder bestätigt.

## Antithese

Der typische Fehler: Phase 6 wird als „noch ein paar Tests schreiben“ verstanden.
Das ist falsch. Tests ohne realen Kontext (Caddy, PMTiles, echte UI-Flows) sind nur Simulationen von Sicherheit.

## Synthese

Phase 6 ist ein Beweis-Framework, kein Test-Framework.

---

## Phase-6-Abschlussplan (präzise, umsetzbar)

### 0. Diagnose-Gate (Pflicht vor Umsetzung)

Ist-Zustand (belegt):

- Playwright-Tests fuer Karteninteraktion, degradierte API-Zustaende und Basemap-Clientverhalten existieren
- `basemap.spec.ts` prueft Modus- und Style-Aufloesung
- `basemap-client-integration.spec.ts` und `basemap-sovereignty-testbuild.spec.ts` belegen den lokalen clientseitigen Basemap-Pfad im Testkontext
- ABER: kein durchgehender Live-Systembeweis von Browser oder curl → Caddy → PMTiles-Artefakt → HTTP 206 im CI

Hypothesen:

1. E2E deckt UI und den clientseitigen lokalen Pfad ab, aber nicht die Live-Infrastruktur (Caddy plus Artefakt)
2. Der Runtime-Beweis ist vorbereitet, aber ohne Artefakt und Caddy im CI bewusst nur `NOT_PROVEN`
3. „funktioniert“ ist fuer Interaktion und Loader-Verhalten bereits belegt, fuer den Live-Basemap-Pfad aber noch nicht systemisch erzwungen

Checks (minimal, copyfähig):

```bash
# 1. laufen bestehende Playwright Tests wirklich stabil?
cd apps/web && pnpm test

# 2. gibt es echten Netzwerkverkehr zur Basemap?
curl -I http://localhost:8081/basemap/hamburg.pmtiles

# 3. liefert Caddy Range Requests korrekt?
curl -H "Range: bytes=0-1000" http://localhost:8081/basemap/hamburg.pmtiles
```

Zusätzlicher manueller Check:

- Lädt die Karte vollständig ohne Fallback?
- In DevTools: keine 404, keine Tile Errors

Stop-Kriterium:
→ Erst wenn diese Checks deterministisch reproduzierbar sind, darf gebaut werden.

---

### 1. E2E-Testmatrix (Kern)

Ziel: User-Realität simulieren

#### 1.1 Minimalfälle (müssen grün sein)

- Map lädt initial korrekt
- Nodes erscheinen
- Filter verändert sichtbare Nodes
- Suche fokussiert Karte
- Overlay öffnet korrekt

👉 Playwright-Beispiel:

```typescript
test('map basic flow', async ({ page }) => {
  await page.goto('/map');
  await expect(page.locator('.map')).toBeVisible();

  await page.fill('[data-test=search]', 'Hamburg');
  // Hinweis: Selektoren sind illustrativ. Im realen Test die korrekten data-testids des Repos verwenden.
  expect(await page.locator('.node').count()).toBeGreaterThan(0);
});
```

#### 1.2 Degradationsfälle (entscheidend!)

- Basemap fällt aus → UI bleibt stabil
- API fällt aus → UI zeigt sinnvolle Zustände
- langsames Netzwerk → keine UI-Kollision

👉 das ist echte Klarheit, nicht Happy Path.

---

### 2. Basemap-Runtime-Beweis (kritischster Punkt)

#### 2.1 Was wirklich bewiesen werden muss

Nicht:

- „style.json existiert“
- „pmtiles gebaut“

Sondern:

- Browser → HTTP → Caddy → PMTiles → Range Request → Rendering

#### 2.2 Minimal-Setup

```bash
# Basemap bauen
./scripts/basemap/build-hamburg-pmtiles.sh

# Caddy starten
docker compose up -d caddy

# prüfen:
curl -I http://localhost:8081/basemap/hamburg.pmtiles
```

#### 2.3 Beweisfälle

- Range Requests funktionieren (206 Partial Content)
- Tiles werden geladen (keine 404/ERR)
- Karte rendert ohne Fallback

👉 Ohne das ist „Basemap-Souveränität“ nur Theorie.

#### 2.4 Status der CI-Beweise (Stand dieser Phase)

- [x] **Blockierender CI-Job fuer HTTP-206-Range-Delivery PROVEN.**
  Workflow `.github/workflows/basemap-runtime-proof.yml`, Job
  `basemap-range-delivery-proof`: realer `caddy:2.7`-Container, deterministisches
  `.pmtiles`-Testartefakt, Guard im Modus `require` mit Scope `range-delivery`.
  Fehlt 206 oder `Content-Range`, schlaegt der Job hart fehl.
  **PROVEN:** [CI-Lauf 25970466659](https://github.com/heimgewebe/weltgewebe/actions/runs/25970466659)
  (Commit 14feefd6), Guard-Output `PROVEN: Caddy PMTiles Range delivery verified
  (scope=range-delivery)`, Response `HTTP/1.1 206 Partial Content`.
  - Was der Job prueft: `curl -H 'Range: bytes=0-511' → Caddy → .pmtiles-Datei
    → 206 Partial Content + Accept-Ranges/Content-Range`.
  - Was *nicht* bewiesen ist: PMTiles-Magic-Byte-Check. Das Testartefakt im CI
    ist synthetisch und enthaelt keine echten Tiles.
- [x] **PMTiles-Magic-Byte-Check im CI (Scope `pmtiles-content`) PROVEN.** Job
  `basemap-pmtiles-content-proof` baut ein echtes Hamburg-PMTiles-Artefakt im Lauf,
  serviert es ueber Caddy und prueft Magic `"PMTiles"` an Offset 0, intra-run SHA256
  und HTTP-served Magic-Bytes. Der Job laeuft path-gated auf `pull_request`/`push`
  (nicht nur `workflow_dispatch`).
  **PROVEN:** Runs [26447341921](https://github.com/heimgewebe/weltgewebe/actions/runs/26447341921),
  [26535801825](https://github.com/heimgewebe/weltgewebe/actions/runs/26535801825),
  [27028165272](https://github.com/heimgewebe/weltgewebe/actions/runs/27028165272).
  Scope: nur Magic + intra-run SHA / HTTP-served Magic-Bytes — **kein** vollstaendiger
  Struktur-Check, keine Tile-Directory-Validierung.
- [x] **Browser-/PMTiles-Init-Proof im CI PROVEN.** Job `basemap-visual-proof`
  (`needs: basemap-pmtiles-content-proof`) ist grün auf `main`
  ([27028165272](https://github.com/heimgewebe/weltgewebe/actions/runs/27028165272),
  Job 79773804577; [26535801825](https://github.com/heimgewebe/weltgewebe/actions/runs/26535801825),
  Job 78164572577). Scope: separater direkter PMTiles-Range-Request mit HTTP 206,
  beobachteter lokaler PMTiles-Request, MapLibre-Canvas, `isStyleLoaded()`, 0 externe
  Provider (Browser → Vite-Middleware → PMTiles-Alias). **Kein** Beweis fuer
  Vector-Tile-Payload-/Tile-Datenlieferung, Pixel-/Baseline-Korrektheit oder einen
  produktionsnahen Caddy-Visual-Pfad.
- [ ] **PMTiles-Strukturvalidierung (P4).** Header/Directory/Metadata/Tile-Read
  jenseits der Magic-Bytes fehlt weiterhin.
- [ ] **Vector-Tile-Payload-/Tile-Datenlieferung.** Der aktuelle
  Browser-/PMTiles-Init-Proof belegt keinen echten Tile-Payload-Read (Source-loaded
  mit Tile-Payload).

---

### 3. Visuelle Abnahme (der unterschätzte Teil)

Warum wichtig:
Karten können formal korrekt und visuell falsch sein.

Optionen:

A) Minimal (schnell)

- Screenshot-Tests (Playwright)

```typescript
expect(await page.screenshot()).toMatchSnapshot('map.png');
```

B) Besser

- gezielte Layer-Checks:
- Farben stimmen
- Labels sichtbar
- Zoom-Level korrekt

---

### 4. Doku-Konsolidierung

Nach bestandenem Beweis:

Muss synchron sein:

- `docs/blueprints/kartenklarheit-roadmap.md`
- `docs/reports/map-status-matrix.md`
- `docs/reports/map-architekturkritik.md`

Regel:

Kein [x], ohne reproduzierbaren Beweis.

---

### 5. Definition von „fertig“ (harte Kriterien)

Du darfst Phase 6 nur schließen, wenn:

- E2E läuft stabil lokal + CI
- Basemap läuft über echtes Caddy + PMTiles
- visuelle Darstellung ist geprüft
- keine stillen Fallbacks aktiv
- Doku entspricht exakt Realität

---

### 6. CI-Verankerung (Pflicht)

Inhalt:

- Definition der Beweispflicht:
  - Welche Checks müssen automatisiert laufen?
  - Welche sind Blocking?

Beispiel (Konzept, abhängig von CI-Workflow-Ausbau):

- Playwright Tests → Pflicht (blocking)
- Basemap curl Checks → Pflicht
- Screenshot Tests → optional

Form:

Phase 6 ist in der Theorie definiert, aber erst systemisch erzwungen, wenn diese Checks in einem aktiven CI-Workflow grün sind.

### 7. Beweis-Artefakte

Gewünschte Nachweisarten:

- Logs
- Screenshots
- Testresultate

Beispielhafte Pfade (Ablageorte abhängig von Workflow-Design):

- `/artifacts/map-e2e/`
- `/artifacts/basemap-check/`

---

## Alternative Sinnachse (wichtig)

Du denkst gerade:
→ „Wie schließen wir Phase 6 ab?“

Alternative Frage:
→ „Welche unserer Wahrheiten sind aktuell unbegründet?“

Das kippt die Logik:

- Nicht: „Was fehlt noch?“
- Sondern: „Was glauben wir, ohne es bewiesen zu haben?“

Das ist der eigentliche Kern von Kartenklarheit.

---

## Risiken & Nebenwirkungen

Nutzen:

- drastisch höhere Systemzuverlässigkeit
- keine „funktioniert bei mir“-Illusion mehr
- echte Release-Fähigkeit

Risiken:

- Setup-Aufwand für Basemap + CI
- flaky Tests, wenn schlecht geschrieben
- visuelle Tests können nervig sein

Kritischer Punkt:

Wenn du Phase 6 überspringst, verschiebst du Unsicherheit in die Zukunft.
Und Zukunft hat die unangenehme Eigenschaft, plötzlich Produktion zu heißen.

---

## Für Dummies

Du hast ein Haus gebaut (Map, API, UI).
Phase 6 ist jetzt:

- Strom anschalten
- Wasser aufdrehen
- schauen, ob die Tür wirklich aufgeht

Vorher war alles nur Bauplan + Simulation.

---

## Essenz

Hebel: echte Ausführung statt Annahme
Entscheidung: jetzt Beweis bauen, nicht Features
