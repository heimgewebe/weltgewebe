---
id: docs.blueprints.kartenklarheit
title: Blaupause zur Optimierung der Karte
doc_type: blueprint
status: draft
relations:
  - type: relates_to
    target: docs/reports/map-architekturkritik.md
  - type: relates_to
    target: docs/blueprints/map-blaupause.md
  - type: relates_to
    target: docs/blueprints/map-roadmap.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
summary: Blaupause zur Optimierung der Kartenarchitektur von stiller Leere zu expliziter Szene.
---
# Blaupause zur Optimierung der Karte

**These:** Die Karte ist nicht primär ein Stilproblem, sondern ein Wahrheits-, Zustands- und Contract-Problem.
**Antithese:** Reines Refactoring der großen Map-Route oder bloße UI-Politur würde das Grundproblem verdecken.
**Synthese:** Die Karte wird am wirksamsten optimiert, wenn zuerst Laufzeitwahrheit, dann Szenenmodell, dann Typen, dann Modus- und Zustandsgrenzen gehärtet werden. Genau diese Spannungen liegen im Repo bereits offen: `+page.ts` schluckt Fehler per Fallback-Arrays, `+page.svelte` bündelt Orchestrierung, der Debug-Hinweis signalisiert API-Modus getrennt von der Basemap-Konfiguration, und die Map-Schiene ist als eigenes Bündel aus Route, Typen, Overlay- und Basemap-Dateien organisiert.

## 0. Titel und Zweck

**Arbeitstitel:**
Kartenklarheit 1.0 – Von stiller Leere zu expliziter Szene

**Zweck:**
Die Karte soll von einer funktionierenden, aber impliziten Orchestrierung zu einer klar modellierten, fehlertoleranten, testbaren und erweiterbaren Kartenarchitektur weiterentwickelt werden.

Blaupause bedeutet hier: ein vorgelagerter, verbindender Bauplan.
Etymologie: „Blaupause“ stammt aus dem historischen Lichtpausverfahren, bei dem technische Zeichnungen mit weißer Linie auf blauem Grund vervielfältigt wurden. Im übertragenen Sinn ist eine Blaupause also kein Endprodukt, sondern ein präziser Bauentwurf.

---

## 1. Zielbild

Die optimierte Karte besitzt am Ende fünf Eigenschaften:

### 1.1 Explizite Laufzeitwahrheit

Die Karte kann sauber unterscheiden zwischen:

- Daten vorhanden
- Daten teilweise vorhanden
- Daten konnten nicht geladen werden

Leere Karte darf nie mehr bedeuten: „Vielleicht ist alles okay, vielleicht ist alles kaputt.“

### 1.2 Explizites Szenenmodell

Zwischen geladenen Domänendaten und sichtbarer Karte existiert eine klar definierte Zwischenschicht: die Szene.

Diese Szene beschreibt:

- welche Entitäten dargestellt werden,
- welche Overlays sichtbar sind,
- welcher Ladezustand gilt,
- welche degradierte Lage vorliegt,
- welche Fokus- und Suchzustände aktiv sind.

### 1.3 Harte Entitäts-Contracts

Map-Entitäten werden nicht mehr über einen weichen Sammeltyp mit vielen optionalen Feldern beschrieben, sondern über diskriminierte Varianten.

### 1.4 Getrennte Betriebsachsen

API-Modus und Basemap-Modus werden diagnostisch und semantisch getrennt.

### 1.5 Reduzierte implizite Macht von `+page.svelte`

Nicht zwingend kleinere Datei, aber weniger versteckte Verantwortung.

---

## 2. Problemkarte des Ist-Zustands

### 2.1 Die Route lädt Daten, aber ohne explizite Fehlerdomäne

`apps/web/src/routes/map/+page.ts` lädt nodes, accounts und edges über `fetchResource()`. Fehler werden geloggt, dann wird das jeweilige Fallback-Array zurückgegeben, und die Route liefert regulär `{ nodes, accounts, edges }` zurück. Das ist robust im engeren Sinn, aber semantisch unscharf.

### 2.2 Die Map-Seite ist zentraler Orchestrator

`apps/web/src/routes/map/+page.svelte` ist sichtbar der Mittelpunkt der Kartenlogik: Debug-Hinweis, Panels, Overlays, ActionBar, SearchOverlay, FilterOverlay, Loading-Overlay, Map-Container. Das ist derzeit funktional, aber es bündelt unterschiedliche Zustandsregime in einer Stelle.

### 2.3 Die Map-Schiene ist schon modular angelegt

Es existieren bereits getrennte Pfade für:

- Basemap-Konfiguration,
- Overlay-Module,
- MapLibre-Komponenten,
- Stores,
- Route-Loader,
- Route-View,
- Tests.

Das ist wichtig: Wir bauen nicht aus Chaos Ordnung, sondern aus Vorstruktur Explizitheit.

### 2.4 Die Debug-Semantik ist nur halb ehrlich

Der DEV/Test-Debugblock zeigt `Mode: REMOTE` oder `Mode: DEMO (local)` abhängig von `PUBLIC_GEWEBE_API_BASE`, während die Basemap separat konfiguriert wird. Das erzeugt eine scheinbare Eindeutigkeit, wo tatsächlich zwei Modi gleichzeitig existieren können.

---

## 3. Leitprinzipien der Optimierung

### 3.1 Wahrheit vor Eleganz

Ein hässlicher, aber wahrer Degradationszustand ist besser als eine elegante, aber irreführende Leere.

### 3.2 Szene vor Route

Die Route lädt Rohmaterial. Die Szene macht daraus Kartenwirklichkeit.

### 3.3 Contracts vor Refactoring

Bevor Dateien zerteilt werden, müssen erst die semantischen Grenzen explizit werden.

### 3.4 Diagnose vor Beschleunigung

Wir optimieren erst, wenn klar ist, was optimiert wird und warum.

### 3.5 Karte als Interaktionssystem, nicht nur Renderer

Die Basemap ist Untergrund. Die eigentliche Karte entsteht aus Szene, Overlays, Fokus, Suche, Komposition und Zustandskommunikation.

---

## 4. Zielarchitektur

### 4.1 Neue Hauptschichten

#### A. Datenlade-Schicht

Verantwortlich für:

- API-Zugriffe
- Fehlererfassung
- Rohdaten
- Ladeklassifikation

Ort:

- primär `apps/web/src/routes/map/+page.ts`
- optional Hilfsmodul `apps/web/src/lib/map/load.ts`

#### B. Szenen-Schicht

Verantwortlich für:

- Übersetzung von Rohdaten in Kartenwirklichkeit
- Vereinheitlichung von Nodes / Accounts / später weiteren Entitäten
- Bestimmung sichtbarer Overlays
- Bereitstellung eines stabilen Scene-Contracts

Ort:

- neu: `apps/web/src/lib/map/scene.ts`
- Typen in `apps/web/src/lib/map/types.ts` oder ausgelagert nach `scene.types.ts`

#### C. Render-/Interaktions-Schicht

Verantwortlich für:

- Darstellung
- UI-Interaktionen
- Event-Weiterleitung
- MapLibre-Einbindung

Ort:

- `apps/web/src/routes/map/+page.svelte`
- bestehende Overlay- und Komponentenmodule

#### D. Diagnostik-Schicht

Verantwortlich für:

- Anzeige technischer Zustände
- Trennung von API-Mode und Basemap-Mode
- DEV-/Test-Diagnostik

Ort:

- zunächst in `+page.svelte`
- später optional eigene Komponente `MapDiagnostics.svelte`

---

### 4.2 Ziel-Contracts

#### 4.2.1 MapLoadState

```typescript
type MapLoadState = "ok" | "partial" | "failed";
```

Bedeutung:

- `ok`: alle benötigten Ressourcen erfolgreich
- `partial`: mindestens eine Ressource fehlt, aber darstellbare Szene vorhanden
- `failed`: Kernszene nicht sinnvoll aufbaubar

#### 4.2.2 MapResourceStatus

```typescript
type MapResourceStatus = {
  resource: "nodes" | "accounts" | "edges";
  status: "ok" | "failed";
  error?: string;
};
```

#### 4.2.3 MapRouteData

```typescript
type MapRouteData = {
  nodes: Node[];
  accounts: Account[];
  edges: Edge[];
  loadState: MapLoadState;
  resourceStatus: MapResourceStatus[];
};
```

#### 4.2.4 MapSceneModel

```typescript
type MapSceneModel = {
  entities: MapEntityViewModel[];
  edges: Edge[];
  loadState: MapLoadState;
  diagnostics: {
    apiMode: "remote" | "local";
    basemapMode: "local-sovereign" | "remote-style";
    degraded: boolean;
  };
};
```

#### 4.2.5 MapEntityViewModel

Später als diskriminierte Union:

```typescript
type MapEntityViewModel =
  | { type: "node"; ... }
  | { type: "account"; ... }
  | { type: "garnrolle"; ... }
  | { type: "ron"; ... };
```

---

## 5. Umsetzungsphasen

### Phase 1 – Laufzeitwahrheit einziehen

**Ziel:**
Aus stiller Fehlerverdeckung wird explizite Kartenwahrheit.

**Maßnahmen:**
**5.1 `+page.ts` erweitern:**
Die Route liefert nicht mehr nur rohe Listen, sondern auch:

- `loadState`
- `resourceStatus`

**5.2 Fehler nicht nur loggen, sondern klassifizieren:**
Jede Ressource bekommt einen Status:

- erfolgreich
- fehlgeschlagen

**5.3 Degradierte Zustände sichtbar machen:**
`+page.svelte` zeigt:

- bei `partial`: Hinweis auf eingeschränkte Kartensicht
- bei `failed`: klare Fehlermeldung oder Fallback-Ansicht

**5.4 Bestehende Tests erweitern:**
Besonders relevant:

- `map-load-fallback.spec.ts`
- ggf. neue Tests für `partial` und `failed`

*Die Testbasis existiert bereits im Web-Testbaum.*

**Erfolgskriterium:**
Ein Entwickler kann im UI sehen, ob die Karte leer ist, weil keine Daten da sind, oder weil das Laden scheitert.

**Risiko:**
Gering. Diese Phase verändert keine Grundarchitektur, sondern macht implizite Zustände explizit.

---

### Phase 2 – Szenenmodell einziehen

**Ziel:**
Rohdaten und Kartenwirklichkeit trennen.

**Maßnahmen:**
**5.5 Neues Modul `scene.ts`:**
Neu einführen:

- `buildMapScene(...)`
- Transformation aus `MapRouteData` in `MapSceneModel`

**5.6 `+page.svelte` konsumiert Szene statt Rohlisten:**
Die Svelte-Route soll nicht mehr primär selbst semantisch verdichten, sondern eine vorbereitete Szene erhalten.

**5.7 Such-, Filter- und Fokuslogik an Szene koppeln:**
Nicht rohe Listen filtern, sondern explizit modellierte Szene.

**Erfolgskriterium:**
Die Karte kann logisch beschrieben werden als:
„Die Route lädt Daten; die Szene beschreibt, was sichtbar ist.“

**Risiko:**
Mittel. Hier beginnt echter Umbau. Aber der Hebel ist hoch.

**Nutzen:**
Sehr hoch. Das ist der Schritt, der spätere Erweiterungen überhaupt erst stabil macht.

---

### Phase 3 – Entitätstypen härten

**Ziel:**
`RenderableMapPoint` verliert seine lose Container-Natur und wird zu einem überprüfbaren Entitätstyp-System.

**Maßnahmen:**
**5.8 Ist-Zustand dokumentieren:**
Welche Felder von `RenderableMapPoint` sind heute optional? Welche werden tatsächlich genutzt?

**5.9 Diskriminierte Union einführen:**
Ersetzen oder parallel einführen:

- `node`
- `account`
- `garnrolle`
- `ron`

**5.10 Marker-Kategorisierung umstellen:**
`nodes.ts` und verwandte Logik sollen nicht mehr Strings vermischen, sondern auf echte Varianten reagieren.

**5.11 MapPoint erst nach Beweis bereinigen:**
Nur nach repo-weitem Nachweis, nicht auf Verdacht.

**Erfolgskriterium:**
Marker- und Overlay-Logik arbeiten ohne semantische Ratespiele.

**Risiko:**
Mittel bis erhöht. Typenumstellungen ziehen gern Folgearbeit nach sich.

**Nutzen:**
Langfristig sehr hoch. Das ist die strukturelle Härtung gegen zukünftigen Drift.

---

### Phase 4 – Modus- und Diagnostik-Semantik trennen

**Ziel:**
API-Herkunft und Basemap-Modus getrennt sichtbar machen.

**Maßnahmen:**
**5.12 Debug-Hinweis aufspalten:**
Statt einem Modus:

- API mode
- Basemap mode

**5.13 Begrifflich säubern:**
Nicht mehr nur `REMOTE` / `DEMO`, sondern:

- API: `remote` / `local`
- Basemap: `local-sovereign` / `remote-style`

**5.14 Optional: Diagnostik auslagern:**
Bei Bedarf `MapDiagnostics.svelte`

**Erfolgskriterium:**
Ein Entwickler kann sofort sehen:

- woher Daten kommen,
- wie die Basemap läuft,
- ob die Karte degradiert ist.

---

### Phase 5 – Zustands-Ownership klären und nur dann zerlegen

**Ziel:**
Nicht Datei-Größe bekämpfen, sondern Zuständigkeiten klären.

**Maßnahmen:**
**5.15 Ownership-Matrix schreiben:**
Welche Zustände leben:

- in Stores?
- in der Route?
- in MapLibre?
- in Overlays?

**5.16 Erst danach selektiv extrahieren:**
Nur wenn nötig:

- Szenenaufbau
- Interaktionslogik
- Diagnostik
- Overlay-Koordination

**5.17 Keine kosmetische Zerlegung:**
Wenn die semantischen Grenzen nicht klarer werden, ist Aufteilen nur Möbelrücken ohne Umzug.

---

## 6. Konkrete neue Dateien und Änderungen

**Neu:**

- `apps/web/src/lib/map/scene.ts`
- optional `apps/web/src/lib/map/scene.types.ts`
- optional `apps/web/src/lib/components/MapDiagnostics.svelte`

**Anpassen:**

- `apps/web/src/routes/map/+page.ts`
- `apps/web/src/routes/map/+page.svelte`
- `apps/web/src/lib/map/types.ts`
- `apps/web/src/lib/map/overlay/nodes.ts`
- ggf. `apps/web/src/lib/stores/*`, falls Szene- oder Diagnostikdaten dort besser verankert werden

**Tests:**

- `apps/web/tests/map-load-fallback.spec.ts`
- neue Spec für degradierte Zustände
- neue Spec für Szene- und Modusdiagnostik
- später Typ-/Renderingtests

---

## 7. Priorisierung

**Sofort:**

1. `MapLoadState`
2. `resourceStatus`
3. degradiertes UI
4. Tests für `partial` / `failed`

**Danach:**

1. `MapSceneModel`
2. zentrale Szenenfunktion
3. Umstellung der Route auf Szenenverbrauch

**Danach:**

1. diskriminierte Union
2. Marker-/Overlay-Härtung
3. repo-weite Prüfung zu `MapPoint`

**Zuletzt:**

1. Modusdiagnostik polieren
2. Zustands-Ownership dokumentieren
3. selektives Refactoring von `+page.svelte`

---

## 8. Akzeptanzkriterien

Die Blaupause gilt als erfolgreich umgesetzt, wenn folgende Sätze wahr sind:

**A:**
Ein API-Fehler erzeugt keinen still normalen Leerzustand mehr.

**B:**
Die Kartenroute gibt ein explizites Route-Modell mit Ladezustand zurück.

**C:**
Die Svelte-Route konsumiert eine Szene statt lose Rohdatenlogik.

**D:**
Map-Entitäten sind typseitig diskriminiert statt weich optional.

**E:**
API-Modus und Basemap-Modus sind separat sichtbar.

**F:**
Ein neues Overlay kann ergänzt werden, ohne dass die Route erneut unsichtbar Verantwortung aufsammelt.

---

## 9. Alternativpfad

Falls der große Szenenumbau zunächst zu viel ist, gibt es einen kleineren Pfad:

**Minimalpfad:**

- `MapLoadState`
- `resourceStatus`
- degradiertes UI
- Debug-Hinweis in zwei Modi trennen

**Vorteil:**
Schnell spürbare Verbesserung bei geringem Risiko.

**Nachteil:**
Das eigentliche Szenen- und Typenproblem bleibt erst einmal bestehen.

---

## 10. Empfehlung

Die Karte sollte nicht zuerst „schöner“, „schneller“ oder „kleiner“ gemacht werden.
Sie sollte zuerst ehrlicher werden.

Denn das eigentliche Problem ist nicht, dass sie nicht funktioniert.
Das eigentliche Problem ist, dass sie an mehreren Stellen mehr verschweigt als sagt. Und Software, die schweigt, wird später gern mystisch. Mystische Karten taugen für Fantasyromane, aber schlecht für Systempflege.

---

## 11. Essenz

**Hebel:** Laufzeitwahrheit explizit machen.
**Entscheidung:** Phase 1 und 2 sind der Kern; alles andere ist nachgeordnet.
**Nächste Aktion:** `MapLoadState` und `MapSceneModel` als erste feste Bauglieder einziehen.

**Unsicherheitsgrad:** 0.14
**Ursachen:** Die Hebel sind stark aus dem Repo ableitbar; unsicher bleibt nur die genaue Schnitttiefe zwischen Szene, Stores und Route.

**Interpolationsgrad:** 0.18
**Hauptquellen:** Zielarchitektur und empfohlene Reihenfolge sind teilweise Entwurf, nicht bereits im Repo vorgegeben.
