---
id: process.report-lifecycle
title: Report Lifecycle Policy
doc_type: policy
status: active
summary: >
  Policy für Lebenszyklus, Status, Pflichtfelder, Archivierung und Löschung
  von Reports.
relations:
  - type: relates_to
    target: docs/process/README.md
  - type: relates_to
    target: docs/_generated/report-lifecycle-inventory.md
  - type: relates_to
    target: docs/process/report-lifecycle-contract-alignment.md
---

# Report Lifecycle Policy

## Zweck

Diese Datei ist die aktive, report-spezifische Report-Lifecycle-Regel.
Sie erweitert den globalen DocMeta-Contract nicht.
Globale DocMeta-Felder oder Statuswerte benötigen einen separaten Contract-PR.

Reports sollen nicht dauerhaft als scheinbar aktuelle Wahrheit im Repo liegen.
Jeder Report soll beantworten können:

- Wozu existiert er?
- Welcher Task oder welches Vorhaben gehört dazu?
- Ist er aktiv?
- Wann muss er überprüft werden?
- Wodurch wurde er abgelöst?
- Darf er archiviert werden?
- Darf er gelöscht werden?

Diese Policy ist eine Regelgrundlage, keine rückwirkende Bereinigung.

## Geltungsbereich

**Discovery-Surface:** Alle Markdown-Dateien unter `docs/reports/` werden
inventarisiert.

**Policy-Scope:** Die Report-Lifecycle-Regeln gelten zunächst für Dateien
unter `docs/reports/` mit `doc_type: report`.

**Aktueller Validator-Scope:** Der Validator untersucht dieselbe Population,
setzt die Policy aber derzeit nur teilweise technisch durch.

Andere `doc_type`-Werte unter `docs/reports/` erscheinen im Inventory, werden
aber nicht als Reports validiert.

## Aktuelle Nicht-Ziele

- kein Massen-Backfill bestehender Reports,
- kein changed-only strict,
- kein global strict,
- keine Erweiterung des globalen DocMeta-Contracts,
- keine automatische Archivierung,
- keine Löschung,
- keine automatische `owner_task`-Zuordnung,
- keine automatisch berechneten `review_after`-Daten,
- keine fachliche Wahrheitsbewertung von Reportinhalten.

## Implementierungsstand

### Umgesetzt

- Inventory,
- Policy,
- Alignment-Entscheidung,
- Pilot,
- report-spezifischer Validator,
- Modi `report`, `warn`, `strict`,
- generierte Overview,
- Teil-Backfills.

### In diesem Slice

- vollständige Dokument-Reconciliation,
- CI-Warnmodus,
- deterministische Erzeugung beider Lifecycle-Flächen,
- Task-Control-Registrierung.

### Nachgelagert

- restliche Reportklassifikation,
- semantische Validatorhärtung,
- changed-only strict,
- global strict,
- Archivierungsprozess,
- separate Löschprüfung.

## Geltungs- und Durchsetzungsgrenze

- Lifecycle-Felder sind als report-spezifisches Modell implementiert.
- Der globale DocMeta-Contract bleibt unverändert.
- Inventory und Validator lesen `lifecycle_state`.
- Der CI-Warnmodus ist aktiv.
- Technische Validatorfehler wie ungefangene Import- oder Laufzeitfehler
  blockieren.
- Lifecycle-Findings bleiben im Warnmodus nicht blockierend.
- Die vollständige blockierende Erkennung fehlenden oder nicht parsebaren
  Report-Frontmatters ist noch nicht umgesetzt.
- Enums, ISO-Datum, Task-Existenz und Supersession-Konsistenz sind noch nicht
  vollständig geprüft.
- Strict-Modi bleiben deaktiviert.

## Begriffe

- **Report**: Markdown-Dokument unter `docs/reports/*.md`, das einen Befund,
  Audit, Proof, Status oder eine entscheidungsvorbereitende Auswertung
  beschreibt.
- **Lifecycle**: Rolle eines Reports im Lebenszyklus: warum er existiert, wie
  lange er handlungsleitend ist und wann er geprüft oder abgelöst wird.
- **Status**: globaler DocMeta-Status, zum Beispiel `draft`, `active`,
  `deprecated` oder `canonical`.
- **Lifecycle-Zustand**: report-spezifischer Zustand in `lifecycle_state`, zum
  Beispiel `active`, `superseded` oder `archived`.
- **Supersession**: explizite Ablösung durch ein anderes Artefakt.
- **Archivierung**: Report bleibt erhalten, ist aber nicht mehr
  handlungsleitend.
- **Löschung**: physisches Entfernen eines Reports aus dem Repo.
- **Primary Reference**: handgeschriebene Referenz aus fachlich relevanten
  Dokumenten.
- **Derived Reference**: generierte Referenz aus `docs/_generated/**`.

## Report-Klassen

- **audit**: prüft einen Bestand, Datenzustand oder Prozesszustand.
- **proof**: belegt eine technische oder organisatorische Eigenschaft.
- **status**: verdichtet den aktuellen Stand eines Vorhabens.
- **decision-prep**: bereitet eine Entscheidung vor, ersetzt sie aber nicht.
- **generated**: wird automatisch erzeugt und nicht manuell editiert.
- **planning**: beschreibt geplante Arbeit oder offene Schritte.
- **legacy**: historisch nützlich, aber nicht mehr handlungsleitend.

Die Klasse `proof` kann für Reports unter `docs/reports/*.md` genutzt werden.
Dateien unter `docs/proofs/**` bleiben in dieser Phase vom Geltungsbereich
ausgenommen und können später eine eigene Lifecycle-Regel bekommen.

## Status-Semantik

Bestehende DocMeta-Statuswerte behalten ihre Contract-Bedeutung.
Report-spezifische Zustände werden in `lifecycle_state` modelliert.

- **active**: aktuell handlungsleitend oder als gültiger Bezugspunkt verwendbar.
- **deferred**: bewusst zurückgestellt.
- **superseded**: durch ein anderes Artefakt ersetzt.
- **archived**: historisch erhalten, aber nicht mehr handlungsleitend.

`active` kann sowohl als DocMeta-Status als auch als `lifecycle_state`
vorkommen. Der DocMeta-Status beschreibt die allgemeine Dokumentgültigkeit;
`lifecycle_state` beschreibt die fachliche Handlungsrelevanz.

`deprecated` ist kein Papierkorb. `archived` ist keine Löschung.
`superseded` braucht eine nachvollziehbare Ablösung.

## Lifecycle-Felder

- **lifecycle**: Report-Klasse oder Lifecycle-Rolle.
- **owner_task**: verantwortlicher Task, Vorhaben, Kontrollpunkt oder Prozess.
  - bevorzugt registrierte Task-ID,
  - abgeschlossene Tasks dürfen Proof- oder Audit-Reports weiter besitzen,
  - keine Pseudo-Task-ID nur zur Befüllung des Feldes,
  - unbelegte Eigentümerschaft bleibt als Leerstelle sichtbar.
- **review_after**: ISO-Datum `YYYY-MM-DD`, ab dem erneute Prüfung fällig wird.
  - fachlich durch Anlass, Meilenstein oder Review-Rhythmus begründet,
  - kein pauschaler 30-Tage-Default,
  - überfällig bedeutet reviewbedürftig, nicht automatisch falsch,
  - externe Provider-, DNS- oder Runtime-Claims brauchen frischen Live-Check.
- **lifecycle_state**: report-spezifischer Lifecycle-Zustand. Der Validator
  verarbeitet das Feld bereits für Anwesenheits- und zustandsabhängige
  Pflichtfeldprüfungen. Enums und weitere Konsistenzprüfungen sind
  nachgelagert.
- **superseded_by**: Pfad zum ablösenden Artefakt. Das Feld wird bereits
  verwendet, darf aber nicht alleinige Supersession-Wahrheit sein. Die
  Relationenkonsistenz wird noch nicht vollständig geprüft.

`lifecycle` ersetzt `doc_type` nicht. `doc_type` beschreibt die Dokumentart;
`lifecycle` beschreibt die Rolle des Reports im Lebenszyklus.

Die Feldnamen sind verbindlich snake_case:
`lifecycle`, `owner_task`, `review_after`, `lifecycle_state`, `superseded_by`.

## Pflichtfelder nach Lifecycle-Zustand

| lifecycle_state | lifecycle | owner_task | review_after | superseded_by | Bemerkung |
| --- | --- | --- | --- | --- | --- |
| active | erforderlich | erforderlich | erforderlich | nein | Zweck, Verantwortung und Review-Zeitpunkt |
| deferred | erforderlich | erforderlich | erforderlich | nein | Prüfung oder Reaktivierung ausstehend |
| superseded | erforderlich | erforderlich | optional | erforderlich | Ablösung explizit nachvollziehbar |
| archived | erforderlich | erforderlich | nein | optional | Bei tatsächlicher Ablösung Zielpfad angeben; Legacy ohne Ersatz bleibt gesondert zu begründen |

Die Tabelle ist aktive Policy. Der Validator setzt davon derzeit nur einen
Teil technisch durch.

## Referenzklassen

Primary references kommen aus handgeschriebenen Artefakten, zum Beispiel:

- `docs/tasks/**`
- `docs/blueprints/**`
- `docs/reports/**`
- `docs/adr/**`
- `docs/specs/**`
- `docs/proofs/**`
- `docs/roadmap.md`

Derived references kommen aus `docs/_generated/**`.

Regeln:

- Primary references können Archivierung und Löschung blockieren.
- Derived references allein blockieren keine Archivierung.
- Vor physischer Archivierung oder Löschung muss ein Referenzcheck laufen.

Ob eine Primary Reference blockiert, hängt vom Status und Zweck des
referenzierenden Dokuments ab.

## Archivierungsregeln

Standard ist `status: deprecated` mit `lifecycle_state: archived`.

Lifecycle-State-only Archivierung ist der Standard der ersten Ausbaustufen.
Die Datei bleibt zunächst am Ort; Links bleiben stabil.

Physische Archivierung nach `docs/reports/archive/YYYY/<report>.md` ist nur
zulässig, wenn:

- keine aktiven Primary References brechen,
- `superseded_by` geprüft ist oder eine historische Begründung existiert,
- relevante Tasks, Proofs und Blueprints angepasst sind,
- generierte Dokumente reproduziert wurden,
- ein eigener PR erstellt wird.

Dieser Slice archiviert keine Reports.

## Löschregeln

Direktes Löschen aus `status: draft`, `status: active` oder
`lifecycle_state: active` ist nicht erlaubt.

Löschen ist nur zulässig, wenn:

- `lifecycle_state` `archived` oder `superseded` ist,
- `superseded_by` existiert oder eine explizite Ausnahme begründet ist,
- keine aktive Primary Reference existiert,
- kein Audit-, Compliance- oder Rekonstruktionswert besteht,
- generierte Artefakte reproduzierbar bleiben,
- die Löschung in einem eigenen PR erfolgt.

## Rollout-Modell

1. Warnmodus in CI,
2. evidenzbasierte Resttriage,
3. kleine Backfill-Slices,
4. semantische Validatorhärtung,
5. changed-only strict,
6. global strict erst bei bereinigtem Bestand,
7. Archivierung nach Policy- und Referenzprüfung,
8. Löschung nur separat und nach vollständigem Referenzcheck.

Changed-only strict kommt vor global strict, damit Altlasten nicht jeden
Feature-PR blockieren.

## Beispiele

### Active audit

```yaml
status: active
lifecycle: audit
owner_task: OPT-ARC-001
review_after: 2026-07-13
lifecycle_state: active
```

### Superseded proof

```yaml
status: deprecated
lifecycle: proof
owner_task: OPT-ARC-001
lifecycle_state: superseded
superseded_by: docs/reports/new-proof.md
```

### Archived legacy report

Archivierte Legacy-Dokumente ohne eindeutiges Ersatzartefakt bleiben eine
offene Entscheidung und dürfen erst nach einem eigenen Ausnahmefeld oder
Validator-Verhalten modelliert werden.

## Offene Entscheidungen

- zulässige Werte für `lifecycle`,
- zulässige Werte für `lifecycle_state`,
- genaue Regeln für `owner_task`,
- zusätzliche Regeln für `review_after`,
- Verhältnis von `deprecated` und `superseded`,
- physische Archivierung,
- eigene Lifecycle-Policy für `docs/proofs/**`,
- Review-Logik für generierte Reports.
