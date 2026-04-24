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
`apps/web/src/routes/map/+page.ts`, `apps/web/src/routes/map/+page.svelte`,
`apps/web/src/lib/map/scene.ts`, `apps/web/src/lib/map/config/basemap.current.ts`,
`apps/web/src/lib/map/basemap.ts`, `apps/web/tests/map-interaction.spec.ts`,
`apps/web/tests/map-load-fallback.spec.ts`,
`apps/web/tests/basemap-client-integration.spec.ts`,
`apps/web/tests/basemap-sovereignty-testbuild.spec.ts` und `infra/caddy/Caddyfile`.

## 1. Dialektik

- **These:** Die Kartenroute besitzt inzwischen einen expliziten Loader-Contract,
  ein Szenenmodell, degradierte Ladezustaende und belastbare Browser-Tests fuer
  Interaktion und Fehlerpfade.
- **Antithese:** Die Produktionswahrheit der Basemap bleibt hybrid und der
  echte Live-Nachweis gegen Caddy plus PMTiles-Artefakt ist noch offen. Zudem
  bleibt `+page.svelte` ein starker Orchestrator fuer mehrere Verantwortlichkeiten.
- **Synthese:** Der Stand ist deutlich weiter als ein Demo-MVP, aber noch keine
  vollstaendig geschlossene Kartenarchitektur. Die offenen Fragen liegen heute
  weniger im Datenvertrag als in Produktionsmodus, Artefaktverfuegbarkeit und
  Runtime-Beweis.

## 2. Diagnose

**Befundklasse: B** - funktional tragfaehig, aber mit klarer struktureller Restschuld.

### Belegte Staerken

- `apps/web/src/routes/map/+page.ts` liefert einen expliziten Loader-Contract mit `loadState` und `resourceStatus`.
- `apps/web/src/lib/map/scene.ts` ist der zentrale Transformationspunkt zwischen Loader und Rendering.
- Marker-Interaktion, Context Panel und Escape-/Karteninteraktionen sind durch `apps/web/tests/map-interaction.spec.ts` belegt.
- Partielle und komplette API-Fehlerzustaende sind durch `apps/web/tests/map-load-fallback.spec.ts` belegt.
- Der clientseitige lokale Basemap-Pfad ist durch `apps/web/tests/basemap.spec.ts`, `apps/web/tests/basemap-client-integration.spec.ts` und `apps/web/tests/basemap-sovereignty-testbuild.spec.ts` belegt.
- URL-Parameter fuer Drawer-Zustaende (`l`, `r`, `t`) sind in der Route
  explizit implementiert statt rein implizit im DOM versteckt.

### Belegte Schwaechen

- **Zentrale Orchestrierung in einer Datei:**
  `apps/web/src/routes/map/+page.svelte` bundelt Datenimport, lokalen Typ,
  Kartenaufbau, Marker-Lifecycle, Tastatursteuerung und Drawer-Zustand.
- **Hybridmodus statt geschlossener Basemap-Wahrheit:**
  `currentBasemap` schaltet lokal/test standardmaessig auf `local-sovereign`,
  Produktion aber standardmaessig auf `remote-style`. Diese Hybridentscheidung
  ist technisch explizit, aber noch nicht architektonisch geschlossen.
- **Kompatibilitaetsalias statt vollstaendig bereinigtem Contract:** `MapPoint`
  existiert in `apps/web/src/lib/map/types.ts` nur noch als Deprecated-Alias;
  die Route arbeitet bereits auf `MapEntityViewModel`, aber die Typmigration
  ist noch nicht vollstaendig bereinigt.
- **Externe Basemap-Abhaengigkeit:** Die Route initialisiert MapLibre mit
  einer produktionsseitigen `remote-style`-Fallback-Konfiguration, solange
  `PUBLIC_BASEMAP_MODE` nicht explizit auf `local-sovereign` gesetzt wird.
- **Artefaktverfuegbarkeit bleibt unbelegt:** Infrastruktur und Guard fuer
  `/local-basemap/` sind vorhanden, aber ein reproduzierbarer CI-Nachweis mit
  echtem PMTiles-Artefakt und laufendem Caddy-Stack fehlt.

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

Die groesste Schwaeche liegt nicht mehr im Loader-Contract, sondern in der
Produktionswahrheit der Basemap. Datenquelle, `loadState` und Szene sind heute
explizit; offen bleibt, wann `local-sovereign` in Produktion verbindlich ist
und wie der Live-Runtime-Beweis systemisch erzwungen wird.

### Achse B - Contracts

`MapEntityViewModel` und `MapSceneModel` sind heute benannte Kartencontracts.
Offen bleibt die Bereinigung des Deprecated-Alias `MapPoint`, nicht der
grundsaetzliche Kartenvertrag.

### Achse C - Betriebsmodi

Die Basemap-Modi sind technisch klar getrennt: `local-sovereign` fuer dev/test,
`remote-style` als Produktionsdefault. Offen ist nicht die Implementierung,
sondern die Entscheidung, welcher Modus produktiv als Wahrheit gelten soll.

### Achse D - Runtime vs. Tests

Die vorhandenen Tests belegen Interaktion, degradierte API-Zustaende,
Basemap-Modi und den clientseitigen lokalen PMTiles-Pfad. Nicht belegt ist
der echte Live-Pfad `curl/browser -> Caddy -> PMTiles-Artefakt -> HTTP 206`.

### Achse E - Komplexitaet

Die Route ist trotz Loader- und Szenenextraktion weiterhin ein starker
Orchestrator. Weitere Erweiterungen bleiben riskant, wenn Runtime-Beweis,
Basemap-Modus und Interaktionslogik weiter in derselben Schicht zusammenlaufen.

## 5. Folgepfad

1. **Live-Runtime-Beweis schliessen:** Caddy plus PMTiles-Artefakt im CI bereitstellen und den HTTP-206-Nachweis erzwingen.
2. **Produktionsmodus entscheiden:** `remote-style` als bewusstes Produktionsfallback behalten oder `local-sovereign` verbindlich machen.
3. **Contract-Bereinigung abschliessen:** Deprecated-Alias `MapPoint` entfernen, sobald keine Consumer mehr existieren.
4. **Regressionen verbreitern:** Query-Parameter-Navigation und visuelle Abnahme gezielt nachziehen.

## 6. Essenz

**Hebel:** Wahrheit vor Komplexitaet.
**Entscheidung:** Die aktuelle Karte ist kein blosser Demo-Stand mehr, aber die Produktionswahrheit der Basemap ist noch nicht geschlossen.
**Naechster sinnvoller Schritt:** Runtime-Beweis und Produktionsmodus der Basemap explizit entscheiden; erst danach lohnt groessere Strukturarbeit.

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
