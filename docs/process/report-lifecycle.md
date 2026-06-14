---
id: process.report-lifecycle
title: Report Lifecycle Policy
doc_type: policy
status: draft
canonicality: kanonisch nach Contract-Alignment
summary: >
  Zukünftige Regeln für den Lebenszyklus von Reports. Definiert Status,
  Review-Fristen, Ablösung und Archivierung.
relations:
  - type: relates_to
    target: docs/process/README.md
---

# Report Lifecycle Policy

## Zweck

Dieses Dokument definiert den Lebenszyklus von Dokumenten unter `docs/reports/`
sowie von weiteren Artefakten, die ausdrücklich die `doc_type: report` oder
`lifecycle`-Rolle tragen.

Es soll sicherstellen, dass Reports nicht lautlos veralten und bei Ablösung oder
Archivierung ein klarer Pfad erkennbar bleibt.

## Geltungsbereich

Die Policy gilt für:

- Alle Dateien in `docs/reports/*.md`.
- Jede Datei, die `doc_type: report` deklariert, unabhängig vom Verzeichnis.

Sie gilt nicht für:

- Architektur-Dokumente (`docs/adr/`, `docs/blueprints/`, `docs/specs/`),
  sofern sie nicht explizit als Report markiert sind.
- Aufgaben (`docs/tasks/`).
- Code-Kommentare.

## Contract-Alignment-Gate

Aktuell ist dieses Dokument ein Entwurf (Draft). Es dokumentiert ein
Zielmodell. Dieses Modell darf erst auf echten Bestand angewendet werden
(Pilot, Backfill, Validator), wenn geklärt ist, wo die neuen Lifecycle-Felder
technisch definiert werden.

Die Entscheidung zur Abgrenzung von `status`, `lifecycle_state`,
`superseded_by`, Inventory-Tooling und `relations[type=supersedes]` wird in
`docs/process/report-lifecycle-contract-alignment.md` vorbereitet.

Basis für diese Entscheidung ist die Bestandsaufnahme im
[Report Lifecycle Inventory](../_generated/report-lifecycle-inventory.md).
Erst nach dieser Entscheidung wird die Policy verbindlich.

Das bestehende Inventory-Tooling kennt `lifecycle_state` noch nicht. Diese
Policy benennt das Zielmodell; die Ausrichtung von Inventory, Validator und
späterer Übersicht folgt in separaten Tooling-PRs.

## Vokabular-Gate

Für den ersten Wurf (Inventory, Policy, Pilot) ist nur das Folgende erlaubt:

- Keine harten Enums in Frontmatter-Validatoren einbauen, bevor der Pilot nicht abgeschlossen ist.
- Referenzklassen in Inventory und Validator strikt trennen: Primary Reference
  vs Derived Reference.

- **Primary Reference**: Ein direkter Frontmatter-Link aus einem anderen
  handgeschriebenen Dokument, das als kanonisch oder normativ gilt. Zum
  Beispiel Tasks, Blueprints, ADRs, Specs, Proofs, Reports oder Roadmap.
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

Wichtig:
`deprecated` ist kein Papierkorb.
`archived` ist keine Löschung.
`superseded` braucht eine nachvollziehbare Ablösung.

## Lifecycle-Felder

- **lifecycle**: Report-Klasse oder Lifecycle-Rolle.
- **owner_task**: Task, Vorhaben, Kontrollpunkt oder Prozess, der die Verantwortung für den Report trägt. In Phase 1 noch als menschlich lesbarer Wert (noch kein Enum erzwingen).
- **review_after**: ISO-Datum im Format `YYYY-MM-DD`, ab dem erneute Prüfung
  fällig wird.
- **lifecycle_state**: Report-spezifischer Lifecycle-Zustand, zum Beispiel
  `active`, `deferred`, `superseded` oder `archived`. Dieses Feld ist Teil des
  Zielmodells und wird erst nach Contract-Alignment oder eigenem
  Lifecycle-Schema validatorfähig.
- **superseded_by**: Pfad zum ablösenden Artefakt. Dieses Feld darf nicht als
  alleinige Supersession-Wahrheit verstanden werden. Die bestehende
  Repo-Mechanik bildet Supersession über `relations` mit `type: supersedes`
  abb: Das neue Artefakt verweist auf das alte Artefakt. Ein späterer Validator
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

Im alten Report, falls das Lifecycle-Feld contract-aktiv wird:

```yaml
status: superseded
superseded_by: docs/reports/new-proof.md
```

Im neuen oder ersetzenden Dokument:

```yaml
relations:
  - type: supersedes
    target: docs/reports/old-proof.md
```

Die Lifecycle-Felder werden in exakt dieser snake_case-Schreibweise geführt:
`lifecycle`, `owner_task`, `review_after`, `superseded_by`. Spätere Validatoren
sollen abweichende Schreibweisen wie `ownerTask` oder `reviewAfter` nicht als
gleichwertig behandeln.

## Pflichtfelder nach Lifecycle-Zustand

| lifecycle_state | lifecycle | owner_task | review_after | superseded_by | Bemerkung |
| --- | --- | --- | --- | --- | --- |
| active | erforderlich | erforderlich | erforderlich | nein | Aktive Reports brauchen Zweck, Verantwortung und Review-Zeitpunkt. |
| deferred | erforderlich | erforderlich | erforderlich | nein | Zurückgestellte Reports warten auf Prüfung oder Reaktivierung; abgelöste Reports sind `superseded`. |
| superseded | erforderlich | erforderlich | optional | erforderlich | Ablösung muss explizit nachvollziehbar sein. |
| archived | erforderlich | erforderlich | nein | erforderlich* | Historisch erhalten, nicht mehr handlungsleitend; Legacy-Ausnahmen brauchen später ein explizites Ausnahmefeld. |

`draft` und `deprecated` bleiben DocMeta-Statuswerte. Wenn ein Report zusätzlich
einen Lifecycle-Zustand braucht, wird dieser über `lifecycle_state` modelliert.

`erforderlich*` bedeutet: Das aktuelle Inventory meldet terminale Status ohne
`superseded_by` als Lücke. Nach der Contract-Alignment-Entscheidung muss ein
späterer Tooling-PR diese Prüfung auf `lifecycle_state` oder ein separates
Lifecycle-Schema ausrichten.

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
lifecycle_state: active
```

### Superseded proof

```yaml
status: active
lifecycle: proof
owner_task: OPT-ARC-001
lifecycle_state: superseded
superseded_by: docs/reports/new-proof.md
```

### Archived legacy report

Archivierte Legacy-Dokumente ohne eindeutiges Ersatzartefakt bleiben eine
offene Entscheidung und dürfen erst nach einem eigenen Ausnahmefeld oder
Validator-Verhalten modelliert werden.

Diese Beispiele zeigen das Zielmodell nach abgeschlossenem Contract Alignment.

## Offene Entscheidungen

- Welche Werte für `owner_task` genau zulässig werden.
- Ob für `review_after` später zusätzliche Regeln wie maximale Review-Intervalle gelten.
- Ob `lifecycle` später ein Enum wird.
- Wann `deprecated` statt `superseded` verwendet wird.
- Ob physische Archivierung überhaupt nötig ist.
- Ob `docs/proofs/**` später eigene Lifecycle-Policy bekommt.
- Ob generated Reports eigene Review-Logik brauchen.
