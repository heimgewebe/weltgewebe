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
- Verwendung `MapPoint`: **Plausibel** ungenutzt (im Overlay de facto nicht verwendet, potenziell obsolet).
- Asymmetrie der Overlay-Paradigmen: **Belegt** (Nodes expliziter State vs. Edges impliziter State in MapLibre).
- Typedrift (account vs. garnrolle): **Belegt** (`apps/web/src/lib/map/overlay/nodes.ts`: `getMarkerCategory` behandelt die Strings "account" und "garnrolle" als identische Rendervariante).

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

*Befund:* `RenderableMapPoint` ist als Container semantisch unterdeterminierter (alles optional).
*Fehlender Zielcontract:* Eine **diskriminierte Union für Map-Entitäten** fehlt.
*Nötig für:*

- eindeutige Rendering-Logik (ohne Type-Guards/Fallbacks)
- Eliminierung von Typedrift (`Node` vs. `Garnrolle` vs. `Ron` als explizite Varianten)
- Compile-time-Sicherheit statt Fallbacks
- Genau ein Koordinatenformat (`lon` vs. `lng`).

*Epistemische Lücke:* Der vollständige Datenpfad `AccountRon` → Rendering fehlt, und das ungenutzte `MapPoint` Schema deutet auf potenziell obsoleten Code hin (X fehlt, nötig für Y: Klarheit über den Lifecycle von MapPoint fehlt, nötig für die Bereinigung des Typen-Systems).

### Achse G: Komplexität & Achse E: Kartenarchitektur

*Befund:* `+page.svelte` operiert als Gottobjekt (Konzentration von Datentransformation, MapLibre-Init, Event-Delegation).
*Kipppunkt:* Der Orchestrator kippt von "zentraler Koordinator" zu "Gottobjekt", sobald:

- eine zweite unabhängige Datenpipeline (z. B. Echtzeit-Updates) hinzukommt oder
- ein weiteres Overlay mit eigener Zustandslogik integriert wird.

*Befund:* Asymmetrie der Overlay-Paradigmen (Nodes mit explizitem Zustand, Edges mit implizitem Zustand in MapLibre) ist historisch gewachsen, nicht dediziert entschieden.

### Achse E: Kartenarchitektur (Faden-Invariante)

*Befund:* Die Faden-Invariante (Heatmap-Verbot) ist implementiert und durch einen Test (`no-activity-heatmap.spec.ts`) validiert.
*Einordnung:* Die Invariante ist **testseitig gesichert, aber nicht strukturell erzwungen**. Es gibt keinen Contract auf Design-Ebene, der einen künftigen Layer namens `heatmap` statisch verhindert.

## 5. Alternativpfad (Blueprint-Ergänzungen)

Da es sich um Befundklasse B handelt, werden Architektur-Ergänzungen empfohlen:

1. **Contract Stabilisierung:** Refactoring von `RenderableMapPoint` zu einer Discriminated Union (z.B. `type: 'node' | 'garnrolle' | 'ron'`).
2. **Koordinaten-Konvention:** Festlegung auf exakt eine Konvention (z.B. `lat`/`lon`) und Entfernung von obsoletem Code (`MapPoint`).
3. **Norm-Festigung:** Explizite Entscheidung (via ADR), ob die Monorepo-Struktur beibehalten wird oder die Blueprint-Empfehlung formal abgelehnt wird.

## 6. Essenz + Folgepfad

**Hebel:** Normstatus klären + Contracts konkretisieren → das verwandelt Analyse in Steuerung.

**Entscheidung:** Das System ist pragmatisch tragfähig für die aktuelle Phase. Vor dem Einzug weiterer Komplexität (weitere Overlays, Echtzeit-Updates) müssen die Typ-Contracts (Discriminated Union) gehärtet werden.

**Nächste Aktionen (Priorisiert):**

*Jetzt sinnvoll:*

- **Contract-Klarheit (`types.ts`):** Spec-Update vorbereiten (Discriminated Union für Overlay-Entitäten und Bereinigung toter Typen).
- **Normstatus-Klärung:** Neues ADR zur Monorepo-Entscheidung verfassen, um die normative Lücke zum Blueprint formal zu schließen.
- **Kommentar-Drift:** Veraltete Kommentare zum Remote-Style in `+page.svelte` bereinigen.

*Noch nicht erzwingen:*

- **Refactoring von `+page.svelte`:** Dies sollte erst erfolgen, wenn der beschriebene Kipppunkt erreicht wird (weitere Pipelines oder Overlays).

**Unsicherheits- und Evidenzlage:**

- *Unsicherheitsgrad:* 0.12 (Ursache: einige Annahmen zu tatsächlicher Nutzung von `MapPoint` und zukünftigen Anforderungen).
- *Interpolationsgrad:* 0.18 (Ursache: Ableitung von Kipppunkt und Zielcontract, da nicht vollständig im Repo belegt).
- *Evidenzstatus:* Teilweise belegt (strukturell aus Code abgeleitet, normativ aus Drafts).
- *Offene Lücken:* Klarheit über den normativen Status der `map-blaupause.md`.

*Selbstkritische Restprüfung:*
Die wahrscheinlichste Überdehnung der Diagnose ist die Bewertung von `+page.svelte` als nahendes Gottobjekt. In einer UI-zentrierten Svelte-Anwendung ist ein gewisser Grad an Kompositionslogik in der Root-Route idiomatischer Standard. Ein vorschnelles Extraktions-Refactoring könnte die Lesbarkeit eher verschlechtern als verbessern.
