---
id: docs.blueprints.kartenklarheit-roadmap
title: Roadmap – Kartenklarheit
doc_type: roadmap
status: draft
relations:
  - type: relates_to
    target: docs/blueprints/kartenklarheit.md
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
  - type: relates_to
    target: docs/blueprints/map-roadmap.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
summary: Abhakbare Umsetzungsroadmap zur Optimierung der Kartenarchitektur von stiller Leere zu expliziter Szene.
---

# Roadmap – Kartenklarheit

Statuslegende: `[ ] offen`, `[~] in Arbeit`, `[x] erledigt`

## Ziel

Die Karte soll von einer impliziten Orchestrierung zu einer expliziten, fehlertoleranten, testbaren und erweiterbaren Kartenarchitektur weiterentwickelt werden.

## Erfolgskriterien auf oberster Ebene

- [ ] API-Fehler erzeugen keinen still normalen Leerzustand mehr.
- [ ] Die Kartenroute liefert ein explizites Route-Modell mit Ladezustand.
- [ ] Die Karten-UI konsumiert eine Szene statt lose Rohdatenlogik.
- [ ] Map-Entitäten sind typseitig diskriminiert statt weich optional.
- [ ] API-Modus und Basemap-Modus sind separat sichtbar.
- [ ] Neue Overlays können ergänzt werden, ohne dass `apps/web/src/routes/map/+page.svelte` erneut unsichtbar Verantwortung aufsammelt.

---

## Phase 0 – Ausgangslage sichern

### Ziel der Phase 0

Vor jeder Änderung die aktuelle Map-Schiene, ihre Pfade und ihre Tests als Referenz sichern.

### Arbeitspakete für Phase 0

- [ ] Relevante Einstiegspfade dokumentieren:
  - `apps/web/src/routes/map/+page.ts`
  - `apps/web/src/routes/map/+page.svelte`
  - `apps/web/src/lib/map/types.ts`
  - `apps/web/src/lib/map/overlay/nodes.ts`
  - `apps/web/src/lib/map/config/basemap.current.ts`
- [ ] Relevante vorhandene Tests sammeln:
  - `apps/web/tests/map-load-fallback.spec.ts`
  - `apps/web/tests/map-interaction.spec.ts`
  - `apps/web/tests/komposition.spec.ts`
  - `apps/web/tests/edge-visibility.spec.ts`
  - `apps/web/tests/basemap-client-integration.spec.ts`
- [ ] Vorher-Zustand kurz als Ist-Notiz festhalten:
  - Loader schluckt Fehler per Fallback
  - Route und UI sind eng gekoppelt
  - Szenenmodell fehlt
  - Debug-Semantik ist nur teilweise getrennt

### Stop-Kriterium für Phase 0

- [ ] Die betroffenen Dateien und Tests sind eindeutig benannt.
- [ ] Es gibt eine kurze Ist-Notiz als Ausgangsbasis für spätere Reviews.

---

## Phase 1 – Laufzeitwahrheit einziehen

### Ziel der Phase 1

Aus stiller Fehlerverdeckung wird explizite Kartenwahrheit.

### Arbeitspakete für Phase 1

- [ ] `MapLoadState` definieren (`ok | partial | failed`).
- [ ] `MapResourceStatus` definieren.
- [ ] `apps/web/src/routes/map/+page.ts` so erweitern, dass die Route nicht nur `nodes`, `accounts`, `edges`, sondern auch `loadState` und `resourceStatus` zurückgibt.
- [ ] Fehler je Ressource klassifizieren statt nur implizit auf Fallback-Arrays zu reduzieren.
- [ ] Für degradierte Zustände klare Regeln definieren:
  - [ ] Wann gilt `partial`?
  - [ ] Wann gilt `failed`?
- [ ] `apps/web/src/routes/map/+page.svelte` so anpassen, dass `partial` sichtbar kommuniziert wird.
- [ ] `apps/web/src/routes/map/+page.svelte` so anpassen, dass `failed` nicht wie normale Leere aussieht.
- [ ] UI-Texte für degradierte Zustände knapp und eindeutig formulieren.

### Verifikation für Phase 1

- [ ] `apps/web/tests/map-load-fallback.spec.ts` auf neuen Route-/UI-Zustand anpassen.
- [ ] Neuer Testfall für `partial` ergänzt.
- [ ] Neuer Testfall für `failed` ergänzt.
- [ ] Manuell geprüft: Leere Karte ist nicht mehr semantisch doppeldeutig.

### Stop-Kriterium für Phase 1

- [ ] Ein API-Ausfall ist im UI als degradierter Zustand erkennbar.
- [ ] Die Route hat einen expliziten Ladezustand.

---

## Phase 2 – Explizites Karten-Szenenmodell einziehen

### Ziel der Phase 2

Rohdaten und sichtbare Kartenwirklichkeit trennen.

### Arbeitspakete für Phase 2

- [ ] Neues Modul einführen: `apps/web/src/lib/map/scene.ts`
- [ ] `MapRouteData` definieren.
- [ ] `MapSceneModel` definieren.
- [ ] Zentrale Funktion bauen, z. B. `buildMapScene(...)`.
- [ ] Transformation aus `nodes/accounts/edges + loadState` in `MapSceneModel` implementieren.
- [ ] Diagnostikdaten in die Szene integrieren.
- [ ] `apps/web/src/routes/map/+page.svelte` auf Szenenverbrauch umstellen.
- [ ] Bestehende UI-Logik prüfen:
  - [ ] Suchlogik
  - [ ] Filterlogik
  - [ ] Fokuslogik
  - [ ] Panel-Öffnung
- [ ] Nur die Logik in der Route belassen, die wirklich View-spezifisch ist.

### Verifikation für Phase 2

- [ ] Szene kann unabhängig von der Route gebaut und geprüft werden.
- [ ] Mindestens ein Test für `buildMapScene(...)` ergänzt.
- [ ] `+page.svelte` konsumiert Szene statt selbst Rohdaten zusammenzusetzen.
- [ ] Keine Funktionsverluste in bestehenden Map-Interaktionstests.

### Stop-Kriterium für Phase 2

- [ ] Die Karte lässt sich logisch beschreiben als: „Route lädt Daten, Szene beschreibt Sichtbarkeit.“

---

## Phase 3 – Entitäts-Contracts härten

### Ziel der Phase 3

`RenderableMapPoint` von einem weichen Sammeltyp zu einem klaren Entitätssystem entwickeln.

### Arbeitspakete für Phase 3

- [ ] Ist-Zustand von `RenderableMapPoint` dokumentieren:
  - [ ] Welche Felder sind optional?
  - [ ] Welche Felder werden real genutzt?
- [ ] Zielmodell für diskriminierte Union entwerfen.
- [ ] Varianten definieren:
  - [ ] `node`
  - [ ] `account`
  - [ ] `garnrolle`
  - [ ] `ron`
- [ ] `MapEntityViewModel` oder Nachfolger sauber typisieren.
- [ ] `apps/web/src/lib/map/overlay/nodes.ts` auf echte Varianten umstellen.
- [ ] Marker-Kategorisierung nicht mehr über lose String-Vermischung laufen lassen.
- [ ] Genau eine Koordinatenkonvention festlegen.
- [ ] Repo-weite Prüfung durchführen, ob `MapPoint` noch gebraucht wird.
- [ ] `MapPoint` nur dann entfernen oder entwerten, wenn seine tatsächliche Nutzung belegt ausgeschlossen ist.

### Verifikation für Phase 3

- [ ] Typsystem erzwingt Entitätsvarianten explizit.
- [ ] Marker-/Overlay-Logik arbeitet ohne semantische Ratespiele.
- [ ] Mindestens ein Test deckt die Variantenlogik ab.
- [ ] Keine implizite Gleichsetzung von `account` und `garnrolle` mehr ohne explizite Entscheidung.

### Stop-Kriterium für Phase 3

- [ ] Die Karten-Entitäten sind compile-time-seitig klar unterscheidbar.

---

## Phase 4 – Modus- und Diagnostik-Semantik trennen

### Ziel der Phase 4

API-Herkunft und Basemap-Modus separat sichtbar machen.

### Arbeitspakete für Phase 4

- [ ] Diagnostikmodell definieren:
  - [ ] `apiMode`
  - [ ] `basemapMode`
  - [ ] `degraded`
- [ ] Bestehenden Debug-Hinweis prüfen und umstellen.
- [ ] Begriffe schärfen:
  - [ ] API: `remote` / `local`
  - [ ] Basemap: `local-sovereign` / `remote-style`
- [ ] Optional: `MapDiagnostics.svelte` einführen, wenn die Route sonst wieder unnötig Verantwortung ansammelt.
- [ ] Sichtbarkeitsregel definieren:
  - [ ] nur DEV/Test
  - [ ] oder separat aktivierbar

### Verifikation für Phase 4

- [ ] Im Debugzustand sind API-Modus und Basemap-Modus getrennt sichtbar.
- [ ] Keine trügerische Ein-Modus-Semantik mehr.
- [ ] Mindestens ein Test oder Snapshot prüft den Diagnostikzustand.

### Stop-Kriterium für Phase 4

- [ ] Ein Entwickler kann auf einen Blick erkennen, woher Daten kommen und wie die Basemap läuft.

---

## Phase 5 – Zustands-Ownership klären

### Ziel der Phase 5

Nicht Dateigröße bekämpfen, sondern Zuständigkeiten explizit machen.

### Arbeitspakete für Phase 5

- [ ] Ownership-Matrix schreiben:
  - [ ] Was lebt in Stores?
  - [ ] Was lebt in `+page.svelte`?
  - [ ] Was lebt implizit in MapLibre?
  - [ ] Was lebt in Overlay-Modulen?
- [ ] Für jede relevante Zustandsklasse eine Quelle-der-Wahrheit festlegen.
- [ ] Nur auf Basis dieser Matrix entscheiden, was aus `+page.svelte` herausgezogen wird.
- [ ] Selektive Extraktion nur dort, wo echte semantische Entlastung entsteht:
  - [ ] Szenenaufbau
  - [ ] Diagnostik
  - [ ] Interaktionskoordination
  - [ ] Overlay-Koordination

### Verifikation für Phase 5

- [ ] Es gibt eine explizite Ownership-Matrix.
- [ ] Keine rein kosmetische Datei-Zerlegung.
- [ ] Extraktion reduziert semantische Last, nicht nur Zeilenanzahl.

### Stop-Kriterium für Phase 5

- [ ] Die wichtigsten Zustände haben eine klar benannte Quelle der Wahrheit.

---

## Phase 6 – Härtung und Regression

### Ziel der Phase 6

Die neue Kartenarchitektur gegen Rückfall schützen.

### Arbeitspakete für Phase 6

- [ ] Relevante Testsuite vollständig durchlaufen.
- [ ] Fehlerszenarien gezielt prüfen:
  - [ ] Nodes fehlen
  - [ ] Accounts fehlen
  - [ ] Edges fehlen
  - [ ] mehrere Ressourcen fehlen
- [ ] Interaktionsszenarien erneut prüfen:
  - [ ] Suche
  - [ ] Filter
  - [ ] Fokus
  - [ ] Komposition
- [ ] Basemap-/Diagnostik-Szenarien erneut prüfen.
- [ ] Dokumentation aktualisieren:
  - [ ] `docs/blueprints/kartenklarheit.md`
  - [ ] `docs/reports/map-status-matrix.md`
  - [ ] ggf. `docs/reports/map-architekturkritik.md`

### Verifikation für Phase 6

- [ ] Keine Regression in Kerninteraktionen.
- [ ] Dokumentation entspricht dem tatsächlichen Zustand.
- [ ] Die Roadmap-Punkte können ehrlich abgehakt werden.

### Stop-Kriterium für Phase 6

- [ ] Die Karte ist expliziter, testbarer und semantisch klarer als zuvor.

---

## Minimalpfad, falls Kapazität knapp ist

### Ziel des Minimalpfads

Mit kleinem Eingriff maximalen Wahrheitsgewinn erzielen.

- [ ] `MapLoadState` einführen
- [ ] `resourceStatus` einführen
- [ ] degradiertes UI für `partial` / `failed`
- [ ] `apps/web/tests/map-load-fallback.spec.ts` und neue Fehlerfälle anpassen
- [ ] API-/Basemap-Modus im Debug-Hinweis trennen

### Minimalpfad erfolgreich, wenn


- [ ] Leere Karte nicht mehr still normal wirkt
- [ ] zentrale Diagnostik klarer geworden ist
- [ ] ohne großen Umbau spürbare Wahrheitsverbesserung erreicht wurde

---

## Nicht-Ziele

- [ ] Kein bloß kosmetisches Zerteilen von `+page.svelte`
- [ ] Kein Stil-Refactoring ohne semantischen Gewinn
- [ ] Keine voreilige Entfernung von `MapPoint` ohne repo-weiten Nachweis
- [ ] Keine Vermischung von Kartenoptimierung mit Basemap-Souveränitätsprogramm, sofern nicht diagnostisch nötig

---

## Abschlusskriterium

Die Roadmap ist erfüllt, wenn:

- [ ] die Karte degradierte Zustände explizit zeigt,
- [ ] ein Szenenmodell existiert,
- [ ] die wichtigsten Karten-Entitäten hart typisiert sind,
- [ ] die Diagnostik getrennte Betriebsachsen zeigt,
- [ ] Zustands-Ownership nicht mehr implizit im Routenorchestrator verschwindet.

---

## Essenz

**Hebel:** Laufzeitwahrheit → Szenenmodell → Typenhärtung.
**Entscheidung:** Erst explizit machen, dann aufräumen.
**Nächste Aktion:** Phase 1 als erstes echtes Lieferpaket umsetzen.
