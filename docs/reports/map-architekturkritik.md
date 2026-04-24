---
id: map-architekturkritik
title: Architekturkritik Map-Implementierung
doc_type: report
status: active
summary: Strukturelle Architekturkritik der aktuellen Kartenroute auf Basis des tatsaechlichen Repo-Stands.
relations:
  - type: relates_to
    target: docs/blueprints/kartenklarheit-roadmap.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
---

Dieses Dokument bewertet die aktuelle Kartenimplementierung so, wie sie im Repo
heute vorliegt. Massgeblich sind dabei vor allem
`apps/web/src/routes/map/+page.svelte`,
`apps/web/src/lib/data/dummy.json`, `apps/web/tests/map-smoke.spec.ts`,
`apps/web/tests/map-marker-panel.spec.ts` und `infra/caddy/Caddyfile`.

## 1. Dialektik

- **These:** Die Kartenroute ist fuer einen Demo- und Interaktionsstand
  brauchbar. Marker werden gerendert, das rechte Panel reagiert auf Auswahl,
  und die Kerninteraktion ist durch Browser-Tests abgesichert.
- **Antithese:** Die Implementierung verdrahtet Demo-Daten,
  Karteninitialisierung, Markererzeugung, Drawer-Orchestrierung und
  Query-Parameter-Verhalten in einer einzelnen Routendatei. Damit fehlen
  belastbare Grenzen fuer Datenquelle, Fehlerzustand und Basemap-Strategie.
- **Synthese:** Der Stand ist als MVP tragfaehig, aber nicht als geklaerte
  Kartenarchitektur. Die naechsten Schritte muessen weniger auf kosmetische
  Extraktion als auf explizite Daten- und Betriebsvertraege zielen.

## 2. Diagnose

**Befundklasse: B** - funktional tragfaehig, aber mit klarer struktureller Restschuld.

### Belegte Staerken

- Marker-Interaktion ist vorhanden und durch `apps/web/tests/map-marker-panel.spec.ts` belegt.
- Die Route `/map` wird im Browser geladen und zeigt die erwarteten Grundelemente; belegt durch `apps/web/tests/map-smoke.spec.ts`.
- URL-Parameter fuer Drawer-Zustaende (`l`, `r`, `t`) sind in der Route
  explizit implementiert statt rein implizit im DOM versteckt.

### Belegte Schwaechen

- **Zentrale Orchestrierung in einer Datei:**
  `apps/web/src/routes/map/+page.svelte` bundelt Datenimport, lokalen Typ,
  Kartenaufbau, Marker-Lifecycle, Tastatursteuerung und Drawer-Zustand.
- **Direkt verdrahtete Datenquelle:** Die Karte importiert
  `apps/web/src/lib/data/dummy.json` unmittelbar. Es gibt keinen expliziten
  Loader-, API- oder Fehlervertrag.
- **Lokaler statt wiederverwendbarer Datencontract:** `MapPoint` ist aktuell
  ein lokaler Typ in `+page.svelte`, nicht ein benannter Contract mit klarer
  Verantwortlichkeit.
- **Externe Basemap-Abhaengigkeit:** Die Route initialisiert MapLibre mit
  `https://demotiles.maplibre.org/style.json`. Damit ist die Basemap derzeit
  weder repo-souveraen noch durch Caddy im Projekt kontrolliert.
- **Testabdeckung fokussiert nur den Glueckspfad:** Vorhanden sind Smoke- und
  Marker-Panel-Tests; nicht belegt sind Fehlerfaelle, leere Daten,
  Basemap-Ausfall oder Offline-Verhalten.

## 3. Kontrastpruefung

- **Interpretation A (bewusster Demo-Zuschnitt):** Die Verdrahtung ist fuer
  einen fruehen UI-Stand angemessen; Geschwindigkeit war wichtiger als
  Architekturgrenzen.
- **Interpretation B (beginnender Drift):** Wenn dieser Stand ohne explizite
  Daten- und Basemap-Entscheidung fortgeschrieben wird, verfestigt sich ein
  implizites Architekturmodell ohne pruefbare Wahrheit.

*Synthese:* Beide Lesarten sind plausibel. Genau deshalb muss die Doku den
Stand klein und ehrlich halten, statt bereits eine weiterentwickelte
Architektur zu behaupten.

## 4. Architekturkritik

### Achse A - Truth Model

Die groesste Schwaeche ist derzeit nicht fehlende Abstraktion, sondern
fehlende Klarheit ueber den Wahrheitsort der Kartendaten. Solange `dummy.json`
direkt in der Route importiert wird, existiert kein belastbarer Unterschied
zwischen Demo-Stand, Entwicklungsquelle und spaeterem Runtime-Modell.

### Achse B - Contracts

`MapPoint` ist lokal definiert und nicht als repo-weiter Kartencontract
beschrieben. Damit bleibt offen, ob Marker semantisch nur Demo-Objekte oder
schon ein fachlicher Datentyp sind.

### Achse C - Betriebsmodi

Die Basemap nutzt derzeit einen externen Demo-Style. Gleichzeitig erlaubt die
aktuelle CSP in `infra/caddy/Caddyfile` keine expliziten externen Tile-Hosts
in `img-src`. Das ist kein unmittelbarer Laufzeitbeweis fuer einen Fehler,
aber ein klarer Hinweis darauf, dass Basemap-Strategie und
Infrastruktur-Dokumentation noch nicht sauber zusammenlaufen.

### Achse D - Runtime vs. Tests

Die vorhandenen Tests belegen erfolgreiche Darstellung und Marker-Auswahl. Sie
belegen nicht, wie sich die Karte bei fehlenden Daten, langsamer Datenquelle
oder Basemap-Ausfall verhaelt.

### Achse E - Komplexitaet

Die Route ist mit aktuell rund 450 Zeilen noch kein unrettbares Gottobjekt,
aber bereits der zentrale Sammelpunkt fuer mehrere Verantwortlichkeiten. Ohne
explizite Entkopplung von Datenquelle und Kartenzustand ist weitere
Erweiterung riskant.

## 5. Folgepfad

1. **Datenvertrag explizit machen:** Datenquelle aus `+page.svelte` loesen und Lade-/Fehlerzustaende definieren.
2. **Basemap-Entscheidung treffen:** Externe Demo-Basemap bewusst dokumentieren oder auf repo-kontrollierte Assets umstellen.
3. **Kartencontract benennen:** `MapPoint` oder Nachfolger aus der Route loesen und als klaren Contract beschreiben.
4. **Regressionen verbreitern:** Tests fuer Fehlerpfade, Query-Parameter-Navigation und Basemap-Verhalten nachziehen.

## 6. Essenz

**Hebel:** Wahrheit vor Komplexitaet.
**Entscheidung:** Die aktuelle Karte ist ein brauchbarer MVP, aber noch keine ausformulierte Kartenarchitektur.
**Naechster sinnvoller Schritt:** Erst Datenquelle und Basemap-Strategie
explizit machen; erst danach lohnt groessere Strukturarbeit.

---

## Nachtrag: Basemap Runtime-Beweis vorbereitet, aber nicht vollstaendig geschlossen

Ein Guard-Script fuer den echten Basemap Runtime-Beweis wurde eingezogen:
`scripts/guard/basemap-runtime-proof.sh`

Dieses Script prueft (lokal, mit laufendem Caddy und echtem Artefakt):
- Caddy-Endpoint erreichbar
- Range-GET-Request liefert HTTP 206 (kein stiller 200 OK)
- Accept-Ranges oder Content-Range-Header vorhanden
- Unterscheidung zwischen PROVEN und NOT_PROVEN

Dazugehoeriger Guard-Workflow: `.github/workflows/basemap-runtime-proof.yml`
(non-blocking, `continue-on-error: true`).
Der Workflow startet **keinen** Caddy-Stack und baut **kein** PMTiles-Artefakt.
Ohne beides meldet der Guard nur `NOT_PROVEN` — das ist der aktuelle CI-Status.

**Bewertung:** Der Runtime-Beweis ist vorbereitet, aber noch nicht vollstaendig geschlossen.
Im aktuellen CI-Stack fehlen sowohl das echte PMTiles-Artefakt als auch ein laufendes
Caddy-Backend; der Guard meldet `NOT_PROVEN` — epistemisch korrekt, kein falscher Erfolgsstatus.

**Kein Ersatz fuer den Runtime-Beweis:**
- `apps/web/tests/basemap-client-integration.spec.ts` ist ein gemockter Client-Test.
  Er beweist MapLibre-Protokoll-Handling, nicht echte HTTP-Auslieferung.
- `scripts/guard/caddy-basemap-route-guard.sh` ist ein statischer Konfigurations-Check.
  Er beweist Caddyfile-Struktur, nicht reale Delivery.

**Konsequenz fuer Architekturkritik:** Achse C (Betriebsmodi) und Achse D (Runtime vs. Tests)
bleiben offen. Phase 6 wird erst geschlossen, wenn der Guard PROVEN meldet — mit echtem
Artefakt, laufendem Caddy und belegbarem HTTP-206-Nachweis im CI.
