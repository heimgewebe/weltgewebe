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

Diese Datei ist die Report-Lifecycle-Regel.

Diese Policy ist eine aktive, report-spezifische Prozessregel.
Sie erweitert den globalen DocMeta-Contract nicht.
Neue globale DocMeta-Felder oder Statuswerte benötigen weiterhin einen separaten Contract-PR.

Reports sollen nicht dauerhaft als scheinbar aktuelle Wahrheit im Repo liegen.
Jeder Report soll später beantworten können:

- Wozu existiert er?
- Welcher Task oder welches Vorhaben gehört dazu?
- Ist er aktiv?
- Wann muss er überprüft werden?
- Wodurch wurde er abgelöst?
- Darf er archiviert werden?
- Darf er gelöscht werden?

Wichtig: Diese Policy ist eine Regelgrundlage, keine rückwirkende Bereinigung.

## Geltungsbereich

Discovery-Surface:
Alle Markdown-Dateien unter `docs/reports/` werden inventarisiert.

Validator- und Policy-Scope:
Verbindlich geprüft werden zunächst Dateien unter `docs/reports/` mit `doc_type: report`.

Andere `doc_type`-Werte unter `docs/reports/` erscheinen im Inventory, werden aber nicht als Reports validiert.

## Aktuelle Nicht-Ziele

- kein Massen-Backfill bestehender Reports,
- kein changed-only strict,
- kein global strict,
- keine Erweiterung des globalen DocMeta-Contracts,
- keine automatische Archivierung,
- keine Löschung,
- keine automatische owner_task-Zuordnung,
- keine automatisch berechneten review_after-Daten,
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
- CI-Warnmodus ist aktiv.
- Findings im Warnmodus blockieren nicht.
- Parser-, Import- und Laufzeitfehler des Validators müssen blockieren.
- Semantische Enums, ISO-Datum, Task-Existenz und Supersession-Konsistenz sind noch nicht vollständig geprüft.
- Strict-Modi bleiben deaktiviert.

## Begriffe

- **Report**: Ein Markdown-Dokument unter `docs/reports/*.md`, das einen Befund, Audit, Proof, Status oder eine entscheidungsvorbereitende Auswertung beschreibt.
- **Lifecycle**: Die Rolle eines Reports im Lebenszyklus: warum er existiert, wie lange er handlungsleitend ist und wann er geprüft oder abgelöst wird.
- **Status**: Der globale DocMeta-Status eines Reports, zum Beispiel `draft`, `active`, `deprecated` oder `canonical`.
- **Lifecycle-Zustand**: Der report-spezifische Zustand in `lifecycle_state`, zum Beispiel `active`, `superseded` oder `archived`.
- **Supersession**: Eine explizite Ablösung durch ein anderes Artefakt. Supersession bedeutet nicht automatisch Löschung.
- **Archivierung**: Ein Report bleibt erhalten, ist aber nicht mehr handlungsleitend.
- **Löschung**: Physisches Entfernen eines Reports aus dem Repo. Löschung ist der letzte Schritt und nur nach separater Prüfung erlaubt.
- **Primary Reference**: Eine handgeschriebene Referenz aus fachlich relevanten Dokumenten, zum Beispiel Tasks, Blueprints, ADRs, Specs, Proofs, Reports oder Roadmap.
- **Derived Reference**: Eine generierte Referenz aus `docs/_generated/**`. Sie zeigt Sichtbarkeit oder Indexierung, beweist aber nicht automatisch fachliche Aktualität.

## Report-Klassen

- **audit**: Prüft einen Bestand, Datenzustand oder Prozesszustand. Risiko: veraltet schnell, wenn Daten oder Prozess wechseln.
- **proof**: Belegt eine technische oder organisatorische Eigenschaft. Risiko: verliert Gültigkeit bei Code-, CI- oder Infrastrukturänderungen.
  Die Klasse `proof` kann für Reports unter `docs/reports/*.md` genutzt werden,
  die einen Proof-Charakter haben. Dateien unter `docs/proofs/**` bleiben in
  dieser Phase vom Geltungsbereich ausgenommen und können später eine eigene
  Lifecycle-Regel bekommen.
- **status**: Verdichtet aktuellen Stand eines Vorhabens. Risiko: wird leicht mit dauerhafter Wahrheit verwechselt.
- **decision-prep**: Bereitet eine Entscheidung vor, ersetzt sie aber nicht. Risiko: bleibt nach Entscheidung weiter sichtbar, obwohl die Entscheidung schon gefallen ist.
- **generated**: Wird automatisch erzeugt und soll nicht manuell editiert werden. Risiko: Drift zwischen Generator und committed Artefakt.
  Diese Klasse gilt nur für Artefakte, die ausdrücklich als Report geführt
  werden. Nicht jedes Artefakt unter `docs/_generated/**` wird dadurch zu einem
  Report.
- **planning**: Beschreibt geplante Arbeit, offene Schritte oder Ordnungsvorhaben. Risiko: Planungsstand wird mit Umsetzung verwechselt.
- **legacy**: Historisch nützlich, aber nicht mehr aktuell handlungsleitend. Risiko: unmarkierte Legacy-Dokumente erzeugen Scheinkohärenz.

## Status-Semantik

Die folgenden Werte beschreiben das Zielvokabular für den report-spezifischen
`lifecycle_state`. Bestehende DocMeta-Statuswerte wie `draft`, `active` und
`deprecated` behalten ihre bisherige Contract-Bedeutung. Neue
lifecycle-spezifische Zustände wie `deferred`, `superseded` und `archived`
werden nicht direkt als globale DocMeta-Statuswerte eingeführt.

- **active**: Aktuell handlungsleitend oder als gültiger Bezugspunkt verwendbar.
- **deferred**: Bewusst zurückgestellt. Nicht verworfen, aber derzeit nicht handlungsleitend.
- **superseded**: Durch ein anderes Artefakt ersetzt. Das ablösende Artefakt soll über `superseded_by` und/oder `relations[type=supersedes]` nachvollziehbar sein.
- **archived**: Historisch erhalten, aber nicht mehr handlungsleitend.

`draft`, `active`, `deprecated` und `canonical` bleiben DocMeta-Statuswerte.
Wenn ein Report zusätzlich einen Lifecycle-Zustand braucht, wird dieser über
`lifecycle_state` modelliert.

`active` kann sowohl als bestehender DocMeta-Status als auch als
report-spezifischer `lifecycle_state` vorkommen. Der DocMeta-Status beschreibt
die allgemeine Dokumentgültigkeit; `lifecycle_state: active` beschreibt, ob der
Report fachlich noch handlungsleitend ist.

Wichtig:
`deprecated` ist kein Papierkorb.
`archived` ist keine Löschung.
`superseded` braucht eine nachvollziehbare Ablösung.

## Lifecycle-Felder

- **lifecycle**: Report-Klasse oder Lifecycle-Rolle.
- **owner_task**: Task, Vorhaben, Kontrollpunkt oder Prozess, der die Verantwortung für den Report trägt.
  - `owner_task` verweist bevorzugt auf eine registrierte Task-ID.
  - Ein abgeschlossener Task darf Eigentümer eines historischen Proof- oder Audit-Reports bleiben.
  - Keine Pseudo-Task-ID nur zur Befüllung des Feldes erfinden.
  - Fehlt ein belastbarer Eigentümer, bleibt die Leerstelle sichtbar.
  - Querschnittsreports dürfen erst annotiert werden, wenn ein ehrlicher Eigentümer bestimmt ist.
- **review_after**: ISO-Datum im Format `YYYY-MM-DD`, ab dem erneute Prüfung
  fällig wird.
  - Das Datum muss durch fachlichen Anlass, Meilenstein oder Review-Rhythmus begründet sein.
  - Kein pauschaler, unbelegter 30-Tage-Default.
  - Ein überfälliges Datum macht einen Report nicht automatisch falsch, sondern reviewbedürftig.
  - Externe Provider-, DNS- oder Runtime-Claims benötigen vor Bestätigung einen frischen Live-Check.
- **lifecycle_state**: Report-spezifischer Lifecycle-Zustand, zum Beispiel `active`, `deferred`, `superseded` oder `archived`. Der Validator verarbeitet `lifecycle_state` bereits für Anwesenheits- und zustandsabhängige Pflichtfeldprüfungen. Zulässige Enums und weitere semantische Konsistenzprüfungen sind noch nachgelagert.
- **superseded_by**: Pfad zum ablösenden Artefakt. Feld wird bereits verwendet, es darf nicht alleinige Supersession-Wahrheit sein, Relationenkonsistenz wird noch nicht vollständig geprüft. Die bestehende Repo-Mechanik bildet Supersession über `relations` mit `type: supersedes` ab: Das neue Artefakt verweist auf das alte Artefakt.

`lifecycle` ersetzt `doc_type` nicht. `doc_type` beschreibt die Dokumentart im
Repo, zum Beispiel `report` oder `policy`. `lifecycle` beschreibt die Rolle
eines Reports innerhalb seines Lebenszyklus, zum Beispiel `audit`, `proof`
oder `status`.

Beispiel:

```yaml
doc_type: report
lifecycle: audit
```

Beispiel für die spätere Abbildung einer Ablösung:

Im alten Report, falls die Lifecycle-Felder contract-aktiv werden:

```yaml
status: deprecated
lifecycle_state: superseded
superseded_by: docs/reports/new-proof.md
```

Im neuen oder ersetzenden Dokument:

```yaml
relations:
  - type: supersedes
    target: docs/reports/old-proof.md
```

Die Lifecycle-Felder werden in exakt dieser snake_case-Schreibweise geführt:
`lifecycle`, `owner_task`, `review_after`, `lifecycle_state`, `superseded_by`.
Spätere Validatoren sollen abweichende Schreibweisen wie `ownerTask`,
`reviewAfter` oder `lifecycleState` nicht als gleichwertig behandeln.

## Pflichtfelder nach Lifecycle-Zustand

| lifecycle_state | lifecycle | owner_task | review_after | superseded_by | Bemerkung |
| --- | --- | --- | --- | --- | --- |
| active | erforderlich | erforderlich | erforderlich | nein | Aktive Reports brauchen Zweck, Verantwortung und Review-Zeitpunkt. |
| deferred | erforderlich | erforderlich | erforderlich | nein | Zurückgestellte Reports warten auf Prüfung oder Reaktivierung; abgelöste Reports sind `superseded`. |
| superseded | erforderlich | erforderlich | optional | erforderlich | Ablösung muss explizit nachvollziehbar sein. |
| archived | erforderlich | erforderlich | nein | erforderlich* | Historisch erhalten, nicht mehr handlungsleitend; Legacy-Ausnahmen brauchen später ein explizites Ausnahmefeld. |

`draft` und `deprecated` bleiben DocMeta-Statuswerte. Wenn ein Report zusätzlich
einen Lifecycle-Zustand braucht, wird dieser über `lifecycle_state` modelliert.

Die Tabelle ist aktive Policy.
Der derzeitige Validator setzt davon nur einen Teil technisch durch.

## Referenzklassen

Primary references kommen aus handgeschriebenen Artefakten, zum Beispiel:

- `docs/tasks/**`
- `docs/blueprints/**`
- `docs/reports/**`
- `docs/adr/**`
- `docs/specs/**`
- `docs/proofs/**`
- `docs/roadmap.md`

Derived references kommen aus:

- `docs/_generated/**`

Regeln:

- Primary references können Archivierung und Löschung blockieren.
- Derived references allein blockieren keine Archivierung.
- Derived references zeigen aber, dass ein Report noch in generierten Übersichten erscheint.
- Vor physischer Archivierung oder Löschung muss ein Referenzcheck laufen.

Ob eine Primary Reference Archivierung oder Löschung blockiert, hängt vom
Status und Zweck des referenzierenden Dokuments ab. Eine historische oder
bereits archivierte Quelle blockiert nicht automatisch.

## Archivierungsregeln

Standard: `status: deprecated` mit `lifecycle_state: archived`

Lifecycle-State-only Archivierung ist der Standard der ersten Ausbaustufen. Die Datei bleibt zunächst am Ort. Dadurch brechen keine Links.

Physische Archivierung ist später optional:

- `docs/reports/archive/YYYY/<report>.md`

Nur erlaubt, wenn:

- keine aktiven Primary References brechen
- `superseded_by` geprüft ist oder bewusste historische Begründung existiert
- relevante Tasks, Proofs und Blueprints angepasst sind
- generated docs reproduziert wurden
- eigener PR erstellt wird

Wichtig: Noch keine Archivierung in diesem PR.

## Löschregeln

Direktes Löschen aus `status: draft`, `status: active` oder
`lifecycle_state: active` ist nicht erlaubt.

Löschen nur, wenn alle Bedingungen erfüllt sind:

- Report hat `lifecycle_state: archived` oder `lifecycle_state: superseded`.
- `superseded_by` existiert oder ein später definiertes maschinenlesbares
  Ausnahmefeld dokumentiert bewusst, warum kein Ersatzartefakt existiert.
- Keine aktive Primary Reference existiert.
- Kein Audit-, Compliance- oder historischer Rekonstruktionswert besteht.
- Generierte Artefakte bleiben reproduzierbar.
- Löschung erfolgt in eigenem PR mit klarer Begründung.

Eine Löschung darf nie nebenbei in einem Feature-PR passieren.

## Rollout-Modell

1. Warnmodus in CI,
2. evidenzbasierte Resttriage,
3. kleine Backfill-Slices,
4. semantische Validatorhärtung,
5. changed-only strict,
6. global strict erst bei bereinigtem Bestand.

Changed-only strict kommt vor global strict, damit Altlasten nicht jeden Feature-PR blockieren.

## Beispiele

Die folgenden Beispiele zeigen das Modell. Sie sind in dieser Phase noch keine allgemein gültigen DocMeta-Frontmatter-Vorgaben.

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

Archivierte Legacy-Dokumente ohne eindeutiges Ersatzartefakt bleiben eine offene Entscheidung und dürfen erst nach einem eigenen Ausnahmefeld oder Validator-Verhalten modelliert werden.

Diese Beispiele zeigen das Modell.

## Offene Entscheidungen

- Welche Werte für `owner_task` genau zulässig werden.
- Ob für `review_after` später zusätzliche Regeln wie maximale Review-Intervalle gelten.
- Ob `lifecycle` später ein Enum wird.
- Wann `deprecated` statt `superseded` verwendet wird.
- Ob physische Archivierung überhaupt nötig ist.
- Ob `docs/proofs/**` später eigene Lifecycle-Policy bekommt.
- Ob generated Reports eigene Review-Logik brauchen.
