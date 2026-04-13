---
id: docs.blueprints.kartenklarheit-phase6
title: Kartenklarheit Phase 6: Der Wahrheitsbeweis
description: Der Abschlussplan für Phase 6 der Kartenklarheit, definiert als Wahrheits-Upgrade und Beweis-Framework.
status: "in progress"
doc_type: blueprint
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

## 0. Diagnose-Gate (Pflicht vor Umsetzung)

Ist-Zustand (belegt):

- Playwright-Tests existieren (`apps/web/tests/...`)
- Basemap-Tests existieren (Client + Fallback)
- API-Tests existieren
- ABER: kein durchgehender Systembeweis von UI → Map → Basemap → Netzwerk

Hypothesen:

1. E2E deckt UI ab, aber nicht Infrastruktur (Caddy/PMTiles)
2. Basemap läuft lokal, aber nicht deterministisch unter CI
3. „funktioniert“ ist aktuell nur komponentenweise wahr

Checks (minimal, copyfähig):

```bash
# 1. laufen bestehende Playwright Tests wirklich stabil?
cd apps/web && pnpm test

# 2. gibt es echten Netzwerkverkehr zur Basemap?
curl -I http://localhost:8080/tiles/hamburg.pmtiles

# 3. liefert Caddy Range Requests korrekt?
curl -H "Range: bytes=0-1000" http://localhost:8080/tiles/hamburg.pmtiles
```

# 4. lädt Karte vollständig ohne Fallback?

# (manuell + devtools prüfen: keine 404/Tile errors)

Stop-Kriterium:
→ Erst wenn diese Checks deterministisch reproduzierbar sind, darf gebaut werden.

---

## 1. E2E-Testmatrix (Kern)

Ziel: User-Realität simulieren

### 1.1 Minimalfälle (müssen grün sein)

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
  await expect(page.locator('.node')).toHaveCountGreaterThan(0);
});
```

### 1.2 Degradationsfälle (entscheidend!)

- Basemap fällt aus → UI bleibt stabil
- API fällt aus → UI zeigt sinnvolle Zustände
- langsames Netzwerk → keine UI-Kollision

👉 das ist echte Klarheit, nicht Happy Path.

---

## 2. Basemap-Runtime-Beweis (kritischster Punkt)

### 2.1 Was wirklich bewiesen werden muss

Nicht:

- „style.json existiert“
- „pmtiles gebaut“

Sondern:

- Browser → HTTP → Caddy → PMTiles → Range Request → Rendering

### 2.2 Minimal-Setup

```bash
# Basemap bauen
./scripts/basemap/build-hamburg-pmtiles.sh

# Caddy starten
docker compose up caddy -d

# prüfen:
curl -I http://localhost:8080/tiles/hamburg.pmtiles
```

### 2.3 Beweisfälle

- Range Requests funktionieren (206 Partial Content)
- Tiles werden geladen (keine 404/ERR)
- Karte rendert ohne Fallback

👉 Ohne das ist „Basemap-Souveränität“ nur Theorie.

---

## 3. Visuelle Abnahme (der unterschätzte Teil)

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

## 4. Doku-Konsolidierung

Nach bestandenem Beweis:

Muss synchron sein:

- `docs/blueprints/kartenklarheit-roadmap.md`
- `docs/reports/map-status-matrix.md`
- `docs/reports/map-architekturkritik.md`

Regel:

Kein [x], ohne reproduzierbaren Beweis.

---

## 5. Definition von „fertig“ (harte Kriterien)

Du darfst Phase 6 nur schließen, wenn:

- E2E läuft stabil lokal + CI
- Basemap läuft über echtes Caddy + PMTiles
- visuelle Darstellung ist geprüft
- keine stillen Fallbacks aktiv
- Doku entspricht exakt Realität

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

---
