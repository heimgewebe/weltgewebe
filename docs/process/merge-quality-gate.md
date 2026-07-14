---
id: process.merge-quality-gate
title: Weltgewebe Merge Quality Gate
doc_type: policy
status: active
last_reviewed: 2026-07-14
summary: >
  Fail-closed Qualitätsordnung für risikogewichtete Weltgewebe-Änderungen,
  hashgebundene Reviewpakete, Required Checks und Produktionsnachweise.
relations:
  - type: relates_to
    target: docs/process/README.md
  - type: relates_to
    target: .github/grabowski-required-checks.json
  - type: relates_to
    target: .github/workflows/review-evidence.yml
---

# Weltgewebe Merge Quality Gate

Das Weltgewebe ist das primäre Projekt. Fehlerfreiheit kann nicht versprochen
werden; verbindlich ist deshalb eine fail-closed Nachweiskette. Ein Merge ist nur
zulässig, wenn genau die zu mergende Änderung geprüft wurde und sämtliche Belege
noch zu Basis, Head und Diff passen.

## Grundregel

Für jeden nichttrivialen Pull Request gelten gleichzeitig:

1. Der PR deklariert eine Risikoklasse.
2. GitHub erzeugt einen vollständigen, herunterladbaren Diff und Patch.
3. Das Paket bindet PR, Basis-Commit, Head-Commit, Merge-Basis und Diff-SHA-256.
4. Die risikogewichtete Zahl unabhängiger Reviews liegt als PR-Kommentar vor.
5. Jeder Beleg nennt dieselben Bindungswerte und ein eindeutiges Urteil.
6. Ein Push, Basiswechsel oder anderer Diff entwertet alte Belege automatisch.
7. CI, Review Evidence Gate und GitHub-Mainschutz müssen unmittelbar vor dem
   Merge grün sein.
8. Nach dem Merge werden Mergecommit, Deploymentversion und Liveverhalten
   zurückgelesen.

Ein grüner Testlauf zu einer früheren Fassung ist kein Beleg für die aktuelle
Fassung.

## Risikoklassen

| Klasse | Bedeutung | Mindestprüfung |
| --- | --- | --- |
| R0 | höchstens 50 geänderte Markdown-Zeilen | technische Gates, kein Fremdreview |
| R1 | begrenzte Änderung ohne Code- oder Betriebsrisiko | ein exakter PASS-Beleg |
| R2 | Anwendungscode, API, Tests, Skripte oder Abhängigkeiten | zwei Prüfer, zwei Achsen |
| R3 | Auth, Datenschutz, Sicherheit, Nebenläufigkeit, Migration, CI oder Betrieb | zwei Prüfer, zwei Achsen, davon eine Hochrisikoachse |

Die Deklaration erfolgt im PR-Text:

```text
<!-- weltgewebe-risk: R2 -->
```

Der Gate-Code ermittelt zusätzlich eine Mindestklasse aus den geänderten Pfaden.
Eine zu niedrige Deklaration wird abgewiesen. R0 ist ausschließlich für kleine
Markdown-Änderungen zulässig.

## Reviewpaket

Der Workflow `Review Evidence Gate` läuft aus dem vertrauenswürdigen
Default-Branch. Er checkt keinen PR-Code aus und führt keinen PR-Code aus. Das ist
wichtig, weil `pull_request_target` und `issue_comment` einen Token besitzen, der
Commitstatus setzen darf.

Er holt die PR-Commits ausschließlich als inerte Git-Objekte und erzeugt:

- `weltgewebe-pr-<nr>-<head>-<diffhash>.diff` – vollständiger GitHub-vergleichbarer
  Diff, einschließlich Binärdaten;
- `*.patch` – anwendbare Commitserie;
- `*.review.json` – Bindung, Hashes, Dateiliste und Umfang;
- `*.review-request.md` – fertiger Auftrag für einen externen Prüfer;
- `evaluation.json` – maschinenlesbares Gate-Urteil.

Das Actions-Artefakt wird 30 Tage aufbewahrt. Vor jedem nichttrivialen Merge wird
zusätzlich der aktuelle vollständige GitHub-Diff als extern herunterladbares
Artefakt gesichert.

## Reviewbeleg

Ein berechtigter GitHub-Owner, Member oder Collaborator hinterlegt den Beleg als
PR-Kommentar. Der ausführliche Reviewtext kann darüber stehen. Der maschinenlesbare
Block folgt diesem Schema:

```text
<!-- weltgewebe-review-evidence
{
  "schema_version": 1,
  "pr_number": 123,
  "base_sha": "40 hex characters",
  "head_sha": "40 hex characters",
  "diff_sha256": "64 hex characters",
  "risk_class": "R2",
  "reviewer": "Claude Security Review",
  "review_axis": "security",
  "verdict": "PASS",
  "findings_resolved": true
}
-->
```

Zulässige Achsen sind:

- `correctness`, `regression`, `testing`;
- `architecture`, `maintainability`;
- `accessibility`, `user-experience`;
- `security`, `privacy`, `data-integrity`, `concurrency`, `migration`, `operations`.

Für R2 und R3 müssen Prüferidentitäten und Achsen verschieden sein. Ein späterer
`BLOCKED`- oder `FAIL`-Beleg desselben Prüfers auf derselben Achse ersetzt einen
früheren PASS. Ein PASS zählt nur mit `findings_resolved: true`.

Der Beleg beweist nicht, dass der externe Prüfer unfehlbar oder tatsächlich
unabhängig ist. Er beweist, welche Prüfperspektive für welchen exakten Diff als
abgeschlossen bestätigt wurde. Die inhaltliche Reviewqualität bleibt eine eigene
Verantwortung.

## GitHub-Schutz

Nach dem Bootstrap-Merge sind mindestens diese Kontexte als Required Checks zu
setzen:

- `Required merge gate`
- `Review evidence gate`

Zusätzlich gelten:

- Änderungen an `main` nur per Pull Request;
- kein Bypass;
- Branch vor Merge auf aktuellem `main`;
- alle Reviewgespräche aufgelöst;
- erneuter Readback von Head, Basis, Diff, CI und Reviewbelegen unmittelbar vor
  dem Merge.

Die Datei `.github/grabowski-required-checks.json` ist die maschinenlesbare
Sollvorgabe für Grabowski. Der reale GitHub-Ruleset-Zustand muss nach Änderungen
separat zurückgelesen werden; die Repositorydatei allein ändert keinen Ruleset.

## Sicherheitsgrenze des Workflows

Der privilegierte Workflow darf niemals:

- den PR-Branch auschecken;
- Python-, Shell-, Node- oder Buildcode aus dem PR ausführen;
- Secrets an PR-Inhalte übergeben;
- Reviewbelege nichtberechtigter Kommentarautoren zählen;
- bei internen Fehlern erfolgreich enden.

Alle Parser- und Bundlefunktionen stammen aus dem Default-Branch. Fehler führen
zu `evaluation.json` mit `pass: false` und zu einem fehlgeschlagenen Commitstatus.

## Merge- und Produktionsabschluss

Vor dem Merge wird der vollständige aktuelle GitHub-Diff erneut erzeugt und mit
SHA-256 gesichert. Der Mergeoperator vergleicht:

- PR-Nummer;
- Head- und Basis-SHA;
- vollständigen Diff-SHA-256;
- Required Checks;
- akzeptierte Reviewbelege;
- offene Gespräche und Mergefähigkeit.

Nach dem Merge werden mindestens geprüft:

- tatsächlicher Mergecommit;
- exakte Produktionsversion;
- zentrale API- und Browser-Smokes;
- Logs und Fehlerraten;
- bei Datenänderungen Backup-, Migrations- und Restorebelege;
- der dokumentierte Rückfallweg.

## Alternative Gewichtung

Für ein Nebenprojekt könnte R1 ohne Fremdreview zugelassen werden. Für das
Weltgewebe wird bewusst anders gewichtet: zusätzliche Reibung ist akzeptiert,
weil unbemerkte Fehler, Datenverlust oder Vertrauensschäden schwerer wiegen als
ein schnellerer Merge.
