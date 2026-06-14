---
id: process.report-lifecycle
title: Report Lifecycle Policy
doc_type: policy
status: draft
summary: >
  Policy für Lebenszyklus, Status, Pflichtfelder, Archivierung und Löschung
  von Reports.
relations:
  - type: relates_to
    target: docs/process/README.md
  - type: relates_to
    target: docs/_generated/report-lifecycle-inventory.md
---

# Report Lifecycle Policy

## Zweck

Diese Datei ist der vorgeschlagene Zielort für Report-Lifecycle-Regeln. Sie
bleibt `draft`, bis die Policy in einem späteren Schritt in das Truth Model
und den DocMeta-Contract integriert oder bewusst als nicht-kanonische
Prozessregel bestätigt wird.

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

Gilt für:

- `docs/reports/*.md`

Noch nicht verbindlich für:

- `docs/proofs/**`
- `docs/adr/**`
- `docs/specs/**`
- `docs/blueprints/**`
- `docs/tasks/**`

Diese Policy beschreibt zunächst Reports. Andere Dokumenttypen können Reports referenzieren und dadurch deren Archivierung oder Löschung blockieren, werden aber selbst nicht durch diese Policy klassifiziert.

## Nicht-Ziele

- Diese Policy klassifiziert noch keine bestehenden Reports.
- Diese Policy archiviert keine Reports.
- Diese Policy löscht keine Reports.
- Diese Policy aktiviert keinen Validator.
- Diese Policy verschärft keine CI.
- Diese Policy verändert keine Task-Wahrheit.
- Diese Policy ersetzt keine fachliche Review-Entscheidung.

## Contract-Alignment-Gate

Diese Policy beschreibt das Zielmodell. Die hier beschriebenen zusätzlichen
Lifecycle-Felder und Statuswerte sind noch nicht automatisch Teil des
bestehenden DocMeta-Contracts.

Vor dem ersten Backfill oder einer Pilot-Annotation im Frontmatter muss ein
separater Contract-Schritt entscheiden:

- ob `contracts/docmeta.schema.json` und `architecture/docmeta.schema.md`
  erweitert werden,
- ob Lifecycle-Metadaten in einem eigenen Report-Lifecycle-Schema validiert
  werden,
- oder ob die Policy auf das bestehende DocMeta-Vokabular zurückgeschnitten
  wird.

Bis diese Entscheidung getroffen ist, dürfen neue Statuswerte wie `deferred`,
`superseded` und `archived` nicht als allgemein contract-gültige
DocMeta-Statuswerte verstanden werden.

## Begriffe

- **Report**: Ein Markdown-Dokument unter `docs/reports/*.md`, das einen Befund, Audit, Proof, Status oder eine entscheidungsvorbereitende Auswertung beschreibt.
- **Lifecycle**: Die Rolle eines Reports im Lebenszyklus: warum er existiert, wie lange er handlungsleitend ist und wann er geprüft oder abgelöst wird.
- **Status**: Der aktuelle Zustand eines Reports, zum Beispiel `draft`, `active`, `superseded` oder `archived`.
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

Die folgenden Statuswerte bilden das Zielvokabular für den Report-Lifecycle.
Sie sind erst dann als Frontmatter-Werte verwendbar, wenn das
Contract-Alignment-Gate abgeschlossen ist.

- **draft**: In Arbeit oder vorbereitend. Noch nicht maßgeblich.
- **active**: Aktuell handlungsleitend oder als gültiger Bezugspunkt verwendbar.
- **deferred**: Bewusst zurückgestellt. Nicht verworfen, aber derzeit nicht handlungsleitend.
- **superseded**: Durch ein anderes Artefakt ersetzt. Das ablösende Artefakt soll über `superseded_by` angegeben werden.
- **archived**: Historisch erhalten, aber nicht mehr handlungsleitend.
- **deprecated**: Veraltet oder nicht mehr empfohlen, aber Ersatz, Archivierung oder Löschung sind noch nicht abschließend geklärt.

Wichtig:
`deprecated` ist kein Papierkorb.
`archived` ist keine Löschung.
`superseded` braucht eine nachvollziehbare Ablösung.

## Lifecycle-Felder

- **lifecycle**: Report-Klasse oder Lifecycle-Rolle.
- **owner_task**: Task, Vorhaben, Kontrollpunkt oder Prozess, der die Verantwortung für den Report trägt. In Phase 1 noch als menschlich lesbarer Wert (noch kein Enum erzwingen).
- **review_after**: ISO-Datum im Format `YYYY-MM-DD`, ab dem erneute Prüfung
  fällig wird.
- **superseded_by**: Pfad zum ablösenden Artefakt. Dieses Feld darf nicht als
  alleinige Supersession-Wahrheit verstanden werden. Die bestehende
  Repo-Mechanik bildet Supersession über `relations` mit `type: supersedes`
  ab: Das neue Artefakt verweist auf das alte Artefakt. Ein späterer Validator
  muss `superseded_by` und `relations[type=supersedes]` gegeneinander prüfen
  oder eine der beiden Formen als kanonisch festlegen.

Auch diese zusätzlichen Lifecycle-Felder sind Zielmodell-Felder. Ob sie direkt
im DocMeta-Frontmatter, in einem separaten Lifecycle-Schema oder über einen
späteren Validator geprüft werden, entscheidet das Contract-Alignment-Gate.

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

```yaml
# Im alten Report, falls das Lifecycle-Feld contract-aktiv wird:
status: superseded
superseded_by: docs/reports/new-proof.md
# Im neuen oder ersetzenden Dokument:
relations:
  - type: supersedes
    target: docs/reports/old-proof.md
```

Die Lifecycle-Felder werden in exakt dieser snake_case-Schreibweise geführt:
`lifecycle`, `owner_task`, `review_after`, `superseded_by`. Spätere Validatoren
sollen abweichende Schreibweisen wie `ownerTask` oder `reviewAfter` nicht als
gleichwertig behandeln.

## Pflichtfelder nach Status

| status | lifecycle | owner_task | review_after | superseded_by | Bemerkung |
| --- | --- | --- | --- | --- | --- |
| draft | empfohlen | empfohlen | optional | nein | Noch nicht handlungsleitend, aber spätere Zuordnung soll vorbereitet werden. |
| active | erforderlich | erforderlich | erforderlich | nein | Aktive Reports brauchen Zweck, Verantwortung und Review-Zeitpunkt. |
| deferred | erforderlich | erforderlich | erforderlich | nein | Zurückgestellte Reports warten auf Prüfung oder Reaktivierung; abgelöste Reports sind `superseded`. |
| superseded | erforderlich | erforderlich | optional | erforderlich | Ablösung muss explizit nachvollziehbar sein. |
| archived | erforderlich | erforderlich | nein | erforderlich* | Historisch erhalten, nicht mehr handlungsleitend; Legacy-Ausnahmen brauchen später ein explizites Ausnahmefeld. |
| deprecated | erforderlich | erforderlich | empfohlen | erforderlich* | Veraltet, aber endgültiger Umgang noch offen; Ablösung oder Ausnahme muss später maschinenlesbar werden. |

`erforderlich*` bedeutet: Das aktuelle Inventory meldet terminale Status ohne
`superseded_by` als Lücke. Falls historische Legacy-Dokumente ohne Ersatz
zulässig werden sollen, braucht das einen späteren Generator-/Validator-Schritt
mit explizitem Ausnahmefeld statt stiller Leerstelle.

Diese Tabelle ist in Phase 1 eine Policy-Zieldefinition. Sie ist noch kein aktiver CI-Guard. Technische Durchsetzung folgt erst in späteren Phasen.

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

Standard: `status: archived`

Status-only Archivierung ist der Standard der ersten Ausbaustufen. Die Datei bleibt zunächst am Ort. Dadurch brechen keine Links.

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

Direktes Löschen aus draft oder active ist nicht erlaubt.

Löschen nur, wenn alle Bedingungen erfüllt sind:

- Report ist `archived` oder `superseded`.
- `superseded_by` existiert oder ein später definiertes maschinenlesbares
  Ausnahmefeld dokumentiert bewusst, warum kein Ersatzartefakt existiert.
- Keine aktive Primary Reference existiert.
- Kein Audit-, Compliance- oder historischer Rekonstruktionswert besteht.
- Generierte Artefakte bleiben reproduzierbar.
- Löschung erfolgt in eigenem PR mit klarer Begründung.

Eine Löschung darf nie nebenbei in einem Feature-PR passieren.

## Rollout-Modell

1. **Inventory vorhanden**: Reportbestand sichtbar machen.
2. **Policy definieren**: diese Datei.
3. **Contract Alignment**: entscheiden, ob DocMeta-Contract,
   Architecture-Doku oder ein separates Lifecycle-Schema erweitert wird.
4. **Pilot**: genau einen Report annotieren, erst nach Contract Alignment.
5. **Validator**: `report`, `warn` und `strict` implementieren. `report` ist
   lokal nutzbar, `warn` kann nicht-blockierend in CI laufen, `strict` bleibt
   vorhanden, aber noch nicht aktiv.
6. **Backfill**: kleine Slices statt Massen-PR.
7. **Changed-only strict**: neue oder geänderte Reports müssen Felder tragen.
8. **Global strict**: erst nach abgeschlossenem Backfill.
9. **Archivierung**: zunächst status-only.
10. **Löschung**: nur separat und nach Referenzcheck.

Changed-only strict kommt vor global strict, damit Altlasten nicht jeden Feature-PR blockieren.

## Beispiele

Die folgenden Beispiele zeigen das Zielmodell nach abgeschlossenem
Contract-Alignment. Sie sind in dieser Phase noch keine allgemein gültigen
DocMeta-Frontmatter-Vorgaben.

### Active audit

```yaml
status: active
lifecycle: audit
owner_task: OPT-ARC-001
review_after: 2026-07-13
```

### Superseded proof

```yaml
status: superseded
lifecycle: proof
owner_task: OPT-ARC-001
superseded_by: docs/reports/new-proof.md
```

### Archived legacy report

Archivierte Legacy-Dokumente ohne eindeutiges Ersatzartefakt bleiben eine
offene Entscheidung und dürfen erst nach einem eigenen Ausnahmefeld oder
Validator-Verhalten modelliert werden.

## Offene Entscheidungen

- Welche Werte für `owner_task` genau zulässig werden.
- Ob für `review_after` später zusätzliche Regeln wie maximale Review-Intervalle gelten.
- Ob `lifecycle` später ein Enum wird.
- Wann `deprecated` statt `superseded` verwendet wird.
- Ob physische Archivierung überhaupt nötig ist.
- Ob `docs/proofs/**` später eigene Lifecycle-Policy bekommt.
- Ob generated Reports eigene Review-Logik brauchen.
