---
id: map-architekturkritik
title: Architekturkritik Map-Implementierung
doc_type: report
status: active
summary: Strukturelle Architekturkritik der Map-Implementierung(en) im Weltgewebe-Projekt gemäß weltgewebe.architecture.critique.
relations:
  - type: relates_to
    target: docs/blueprints/map-blaupause.md
  - type: relates_to
    target: docs/blueprints/map-roadmap.md
  - type: relates_to
    target: docs/reports/map-status-matrix.md
  - type: relates_to
    target: docs/policies/architecture-critique.md
---

# Architekturkritik Map-Implementierung

Dieses Dokument liefert eine strukturelle Architekturkritik des Map-Subsystems unter strikter Anwendung der `weltgewebe.architecture.critique` Richtlinie. Der Fokus liegt darauf, ob die Denkstruktur tragfähig ist und ob gebaut wird wie beschlossen.

Geltungsbereich: Modul (Map-Subsystem, alle Komponenten).
Kritiktiefe: Strukturell.

## 1. Dialektik

- **These:** Die aktuelle Map-Implementierung ist inhaltlich stark, anschlussfähig und als Basis für Gate A funktional. Das System funktioniert und liefert die geforderten Features.
- **Antithese:** Die Architektur leidet unter normativer Unschärfe, schwachen Contracts (`RenderableMapPoint` ist unterdeterminiert) und weist beginnende strukturelle Schulden auf (Gottobjekt in `+page.svelte`). Es ist unklar, ob fehlende formale Entscheidungen (kein ADR für Repo-Trennung) ein unkontrollierter Drift oder bewusste Aufschiebung sind.
- **Synthese:** Das System ist aktuell tragfähig, aber als Steuerungsinstrument für langfristiges Wachstum noch unvollständig. Es bedarf zwingend einer Klärung des Normstatus (was ist bindend, was ist Entwurf) und der Konkretisierung von Ziel-Contracts (insb. Typ-Sicherheit für Rendering), um nicht unter steigender Komplexität zusammenzubrechen.

## 2. Diagnose

**Befundklasse: B** (Warnung: potenzielle Schwächen, kontextabhängig. Keine der Schwächen gefährdet die aktuelle Tragfähigkeit, aber mehrere akkumulieren strukturelles Risiko bei Wachstum).

### Normstatus-Klärung

Die folgenden Befunde unterscheiden zwischen:

- **normativer Abweichung** (gegen bestätigte Architekturentscheidung)
- **offener Architekturfrage** (kein ADR / Blueprint draft)

| Befund | Aktueller Status | Korrekte Einordnung |
| :--- | :--- | :--- |
| **Repo-Trennung (Monorepo vs. Multi-Repo)** | Spannung | offene Architekturentscheidung, kein Verstoß |
| **Basemap/Overlay-Trennung** | implizit normativ | teilweise normativ, aber nicht formalisiert |

### Evidenzgradierung der Hauptbefunde

- Gottobjekt `+page.svelte`: **Belegt** (`apps/web/src/routes/map/+page.svelte` operiert mit ca. 560 Zeilen als starker Orchestrator: Datentransformation, MapLibre-Init und Event-Delegation konzentriert).
- Schwacher Contract `RenderableMapPoint`: **Belegt** (`apps/web/src/lib/map/types.ts`: alle semantisch relevanten Felder wie `type`, `kind`, `tags` sind optional).
- Verwendung `MapPoint`: **Plausibel** ungenutzt (im analysierten Overlay-Pfad de facto nicht verwendet; repo-weite Nichtverwendung bleibt aber vorerst offen).
- Asymmetrie der Overlay-Paradigmen: **Belegt** (Nodes expliziter State vs. Edges impliziter State in MapLibre).
- Typedrift (account vs. garnrolle): **Belegt** (`apps/web/src/lib/map/overlay/nodes.ts`: `getMarkerCategory` behandelt die Strings "account" und "garnrolle" als identische Rendervariante).
- Fehlerpolitik „soft fail to empty world“: **Belegt** (`apps/web/src/routes/map/+page.ts`: `fetchResource()` loggt Fehler, gibt dann aber Fallback-Arrays zurück; damit kollabieren „keine Daten“ und „Daten konnten nicht geladen werden“ in denselben Laufzeitzustand).
- Zustands-Ownership nur implizit: **Belegt** (`apps/web/src/routes/map/+page.svelte`: globale Stores wie `uiView`, `searchStore`, `filterStore`, `authStore`, lokale Komponentenvariablen sowie MapLibre-/Overlay-Zustände werden in einem Orchestrator gebündelt).
- Modus-Semantik vermischt: **Belegt** (`apps/web/src/routes/map/+page.svelte`: Debug-Badge zeigt `Mode: REMOTE` bzw. `Mode: DEMO (local)` anhand der API-Basis; zugleich wird die Basemap separat über `currentBasemap` und `resolveBasemapStyle()` gesteuert).
- Fehlender View-Model-Contract zwischen Loader und Renderer: **Belegt** (`apps/web/src/routes/map/+page.ts` liefert rohe Listen `nodes`, `accounts`, `edges`; die semantische Verdichtung zum Render-Modell erfolgt erst in `apps/web/src/routes/map/+page.svelte`).

Damit verschiebt sich die Kritik leicht: Nicht nur Typen und Repo-Norm sind weich, sondern auch die Laufzeitwahrheit der Karte ist an mehreren Stellen nur implizit modelliert.

## 3. Kontrastprüfung

- **Interpretation A (Unkontrollierter Drift):** Die Architektur driftet unkontrolliert. Die Zusammenballung im Gottobjekt und der Typedrift (Mischung von `account` und `garnrolle`) deuten auf erodierende Systemgrenzen hin.
- **Interpretation B (Bewusste Schulden):** Die Architektur ist bewusst pragmatisch für Gate A und noch nicht stabilisiert. Das Gottobjekt ist ein temporärer Konzentrationspunkt, der Typedrift eine laufende Migrationsstrategie, und das fehlende ADR eine bewusst offengehaltene Entscheidung, bis mehr Erkenntnisse vorliegen.

*Synthese:* Beide Lesarten sind plausibel; die Entscheidung hängt am erwarteten Wachstum (Gate B/C).

## 4. Architekturkritik

### Achse A: Truth Model & Achse D: Runtime vs. Docs

*Befund:* Blueprint empfiehlt Repository-Trennung, Monorepo ist Realität. Kein ADR vorhanden.
*Einordnung:* Dies ist eine **offene Architekturfrage**, keine normative Abweichung (Blueprint = draft).
*Befund:* Kommentar in `+page.svelte` behauptet einen strikten Remote-Style, aber `apps/web/src/lib/map/config/basemap.current.ts` erzwingt in Entwicklungs- und Testumgebungen den lokalen souveränen Modus (`resolvedMode = local-sovereign in dev`).
*Einordnung:* Normative Unschärfe und Klassenverwechslung (Laufzeit vs. Dokumentation).

### Achse B: Contracts & Achse C: Semantik

*Befund:* Zwischen Route-Loader und Kartenrenderer existiert kein expliziter Szenen- oder View-Model-Contract.
*Einordnung:* `+page.ts` liefert Domänenlisten, `+page.svelte` übernimmt die Verdichtung in ein Darstellungsmodell. Damit wird die Grenze zwischen Domänenmodell und Kartenansicht spät und implizit gezogen.
*Fehlender Zielcontract:* Ein explizites `MapRouteModel` oder `MapSceneModel` fehlt.
*Nötig für:*

- testbare Trennung von Datenbeschaffung und Kartensemantik
- stabilere Kopplung zwischen Loader, Overlay-Logik und UI-Zuständen

*Befund:* `RenderableMapPoint` ist als Container semantisch unterdeterminierter (alles optional).
*Fehlender Zielcontract:* Eine **diskriminierte Union für Map-Entitäten** fehlt.
*Nötig für:*

- eindeutige Rendering-Logik (ohne Type-Guards/Fallbacks)
- Eliminierung von Typedrift (`Node` vs. `Garnrolle` vs. `Ron` als explizite Varianten)
- Compile-time-Sicherheit statt Fallbacks
- Genau ein Koordinatenformat (`lon` vs. `lng`).

*Epistemische Lücke:* Der vollständige Datenpfad `AccountRon` → Rendering fehlt. Das `MapPoint` Schema ist im analysierten Overlay-Kontext ungenutzt (X fehlt, nötig für Y: repo-weite Usage-Prüfung von MapPoint fehlt, nötig für die sichere Bereinigung des Typen-Systems).

### Achse D: Runtime-Fehlerpolitik & Zustandswahrheit

*Befund:* Die Kartenroute besitzt keine explizite Fehlerdomäne. API-Ausfälle werden in `apps/web/src/routes/map/+page.ts` als leere Listen weitergereicht.
*Einordnung:* Strukturelle Schwäche im Runtime-Contract. Der Zustand „keine Daten vorhanden“ ist derzeit nicht sauber von „Daten konnten nicht geladen werden“ getrennt.
*Folge:* Leere Welt kann semantisch sowohl „es gibt nichts“ als auch „das System ist degradiert“ bedeuten.
*Beobachtung aus Code:*
`fetchResource()` loggt Fehler und gibt das jeweilige Fallback-Array zurück. Dadurch werden Ausfälle einzelner Ressourcen implizit in leere Listen übersetzt, bevor die Route am Ende regulär `{ nodes, accounts, edges }` an die UI zurückgibt. Ein expliziter Fehlerkontext fehlt.

*Nötig für:*

- einen expliziten Ladezustand (`ok | partial | failed`)
- UI-seitig unterscheidbare degradierte Zustände
- Verhinderung stiller Fehldeutung von Leere als Normalzustand

*Befund:* Zustands-Ownership ist nur implizit geklärt.
*Einordnung:* In `apps/web/src/routes/map/+page.svelte` überlagern sich globale Stores, lokale Komponentenvariablen und impliziter MapLibre-/Overlay-Zustand.
*Risiko:* Sobald eine zweite Datenpipeline (z. B. Echtzeit-Updates) oder ein weiteres Overlay hinzukommt, wird unklar, welches Regime Quelle der Wahrheit ist.
*Synthese:* Das Problem ist nicht nur Dateigröße, sondern unklare Zuständigkeitsgrenzen.

### Achse G: Komplexität & Achse E: Kartenarchitektur

*Befund:* `+page.svelte` operiert als Gottobjekt (Konzentration von Datentransformation, MapLibre-Init, Event-Delegation).
*Kipppunkt:* Der Orchestrator kippt von "zentraler Koordinator" zu "Gottobjekt", sobald:

- eine zweite unabhängige Datenpipeline (z. B. Echtzeit-Updates) hinzukommt oder
- ein weiteres Overlay mit eigener Zustandslogik integriert wird.

*Befund:* Asymmetrie der Overlay-Paradigmen (Nodes mit explizitem Zustand, Edges mit implizitem Zustand in MapLibre) ist historisch gewachsen, nicht dediziert entschieden.

### Achse C: Semantik & Achse D: Betriebsmodi

*Befund:* Betriebsmodi sind begrifflich nicht sauber getrennt.
*Einordnung:* Die UI signalisiert einen `REMOTE`/`DEMO`-Modus anhand der API-Basis-URL, während die Basemap-Achse separat konfiguriert wird. Damit werden Datenquelle, Basemap-Modus und Betriebsart semantisch zusammengezogen.
*Folge:* Debug-Informationen können trügerisch eindeutig wirken, obwohl API- und Basemap-Achse unterschiedlich stehen.
*Nötig für:*

- getrennte Begriffe für API-Modus und Basemap-Modus
- präzisere Debug-/Diagnostik-Signale

*Beobachtung aus Code:*
Im DEV-/Test-Debugblock der UI (`div.debug-badge`) wird der Modus anhand von `PUBLIC_GEWEBE_API_BASE` als `Mode: REMOTE` oder `Mode: DEMO (local)` signalisiert. Die Konfiguration der Basemap (`local-sovereign` vs. `remote-style`) läuft jedoch getrennt davon, wodurch der Badge eine trügerische Eindeutigkeit vermittelt.

### Achse E: Kartenarchitektur (Faden-Invariante)

*Befund:* Die Faden-Invariante (Heatmap-Verbot) ist implementiert und durch einen Test (`no-activity-heatmap.spec.ts`) validiert.
*Einordnung:* Die Invariante ist **testseitig gesichert, aber nicht strukturell erzwungen**. Es gibt keinen Contract auf Design-Ebene, der einen künftigen Layer namens `heatmap` statisch verhindert.

## 5. Alternativpfad (Blueprint-Ergänzungen)

Da es sich um Befundklasse B handelt, werden Architektur-Ergänzungen empfohlen:

1. **Contract Stabilisierung:** Refactoring von `RenderableMapPoint` zu einer Discriminated Union (z.B. `type: 'node' | 'garnrolle' | 'ron'`).
2. **Koordinaten-Konvention:** Festlegung auf exakt eine Konvention (z.B. `lat`/`lon`) und Entfernung von ungenutztem Code (`MapPoint`) erst nach vollständiger repo-weiter Usage-Prüfung.
3. **Norm-Festigung:** Explizite Entscheidung (via ADR), ob die Monorepo-Struktur beibehalten wird oder die Blueprint-Empfehlung formal abgelehnt wird.
4. **Runtime-Contract:** Einführung eines expliziten Lade-/Degradationsmodells für die Kartenroute statt stiller Fallback-Leere.
5. **View-Model-Schicht:** Einführung eines expliziten `MapRouteModel`/`MapSceneModel` zwischen Loader und Renderer.
6. **Betriebsmodi trennen:** API-Modus und Basemap-Modus diagnostisch und begrifflich entkoppeln.

## 6. Essenz + Folgepfad

**Hebel:** Normstatus klären + Contracts konkretisieren + Laufzeitwahrheit explizit machen → das verwandelt Analyse in Steuerung.

**Entscheidung:** Das System ist pragmatisch tragfähig für die aktuelle Phase. Vor dem Einzug weiterer Komplexität (weitere Overlays, Echtzeit-Updates) müssen die Typ-Contracts (Discriminated Union) gehärtet werden.

**Nächste Aktionen (Priorisiert):**

*Jetzt sinnvoll:*

- **Contract-Klarheit (`types.ts`):** Spec-Update vorbereiten (Discriminated Union für Overlay-Entitäten und Bereinigung toter Typen nach repo-weiter Prüfung).
- **Normstatus-Klärung:** Neues ADR zur Monorepo-Entscheidung verfassen, um die normative Lücke zum Blueprint formal zu schließen.
- **Runtime-Klarheit (`+page.ts`):** Degradationszustände der Kartenroute explizit modellieren, damit API-Ausfälle nicht als normale Leere erscheinen.
- **View-Model-Klarheit:** Karten-View-Model zwischen Loader und Renderer einziehen, bevor weitere Pipelines hinzukommen.
- **Modus-Klarheit:** Debug- und Diagnosebegriffe für API- und Basemap-Modus entkoppeln.
- **Kommentar-Drift:** Veraltete Kommentare zum Remote-Style in `+page.svelte` bereinigen.

*Noch nicht erzwingen:*

- **Refactoring von `+page.svelte`:** Dies sollte erst erfolgen, wenn der beschriebene Kipppunkt erreicht wird (weitere Pipelines oder Overlays).

*Präzisierung gegen Überreaktion:*

- **Kein vorschnelles Zerteilen:** Die Kritik richtet sich nicht gegen zentrale Orchestrierung als solche, sondern gegen implizite Zustands- und Fehlergrenzen. Ein reines Aufteilen der Datei ohne Klärung dieser Grenzen wäre kosmetisch.

**Unsicherheits- und Evidenzlage:**

- *Unsicherheitsgrad:* 0.12 (Ursache: einige Annahmen zu tatsächlicher Nutzung von `MapPoint` und zukünftigen Anforderungen).
- *Interpolationsgrad:* 0.18 (Ursache: Ableitung von Kipppunkt und Zielcontract, da nicht vollständig im Repo belegt).
- *Evidenzstatus:* Teilweise belegt (strukturell aus Code abgeleitet, normativ aus Drafts).
- *Offene Lücken:* Klarheit über den normativen Status der `map-blaupause.md`.

*Selbstkritische Restprüfung:*
Die wahrscheinlichste Überdehnung der Diagnose ist die Bewertung von `+page.svelte` als nahendes Gottobjekt. In einer UI-zentrierten Svelte-Anwendung ist ein gewisser Grad an Kompositionslogik in der Root-Route idiomatischer Standard. Ein vorschnelles Extraktions-Refactoring könnte die Lesbarkeit eher verschlechtern als verbessern.
