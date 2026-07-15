---
id: process.merge-quality-gate
title: Merge-Qualitätsgate
doc_type: policy
status: active
summary: Verbindlicher, risikogewichteter Mergeprozess mit exakten Diff- und Reviewbelegen.
relations:
  - type: relates_to
    target: .github/PULL_REQUEST_TEMPLATE.md
  - type: relates_to
    target: .github/grabowski-required-checks.json
  - type: relates_to
    target: .github/workflows/ci.yml
  - type: relates_to
    target: .github/workflows/review-evidence.yml
  - type: relates_to
    target: scripts/quality/review_governance.py
  - type: relates_to
    target: scripts/quality/tests/test_review_governance.py
---

# Merge-Qualitätsgate

Dieses Dokument beschreibt den verbindlichen Qualitätsprozess für nichttriviale
Änderungen am Weltgewebe. Ziel ist nicht möglichst viel Bürokratie, sondern eine
prüfbare Bindung zwischen dem tatsächlich gemergten Code und genau dem Diff, der
geprüft wurde.

## Grundprinzip

Ein Merge ist nur zulässig, wenn:

1. Basis- und Head-Commit eindeutig feststehen;
2. ein vollständiges Reviewpaket für genau diesen Diff vorliegt;
3. alle erforderlichen Prüfungen grün sind;
4. die risikogewichteten Reviewbelege exakt zu Basis, Head und Diff passen;
5. unmittelbar vor dem Merge kein Basis-, Head- oder Diffwechsel stattgefunden hat;
6. der Merge und gegebenenfalls der Produktionsabschluss separat zurückgelesen wurden.

## Risikoklassen

Jeder Pull Request enthält genau einen maschinenlesbaren Marker:

```text
<!-- weltgewebe-risk: R0|R1|R2|R3 -->
```

| Klasse | Beispiele | Erforderliche Reviews |
| --- | --- | --- |
| R0 | kleine Dokumentationsänderung, höchstens 50 geänderte Zeilen | keine externe Reviewpflicht |
| R1 | Konfiguration, Metadaten, ungefährliche Werkzeuge | mindestens ein exakter PASS-Beleg |
| R2 | Produktlogik, API, UI, Persistenz, nichtprivilegierte CI | mindestens zwei Prüfer und zwei Reviewachsen |
| R3 | Authentifizierung, Datenschutz, Sicherheit, Migration, Deployment, privilegierte Workflows | mindestens zwei Prüfer und zwei Reviewachsen; mindestens eine Hochrisikoachse |

Bestimmte Pfade erzwingen automatisch eine Mindestklasse. Eine niedrigere
Deklaration führt fail-closed zum Gatefehler. R0 ist nur für kleine reine
Markdown-Änderungen zulässig.

## Reviewpaket

Der Workflow `Review Evidence Gate` führt ausschließlich Code aus dem wörtlich
festgelegten Branch `main` aus. Er checkt keinen PR-Code aus, lädt keine PR-Gitobjekte
und führt keinen PR-Code aus. Das ist wichtig, weil `pull_request_target` und
`issue_comment` einen Token besitzen, der Commitstatus setzen darf.

Der PR wird ausschließlich über die GitHub-API als Diff-, Patch- und JSON-Datenstrom
gelesen. Vor und nach dem Download werden Basis- und Head-SHA verglichen. Der
Workflow erzeugt:

- `weltgewebe-pr-<nr>-<head>-<diffhash>.diff` – den von GitHub gelieferten
  Textdiff, dessen Dateiblockzahl gegen die vollständige Dateiliste geprüft wird;
- `*.patch` – die von GitHub gelieferte Patchdarstellung;
- `*.review.json` – Bindung, Hashes, Dateiliste, Umfang und nicht im Textdiff
  dargestellte Dateien;
- `*.review-request.md` – fertiger Auftrag für einen externen Prüfer;
- `evaluation.json` – maschinenlesbares Gate-Urteil.

Der Reviewbeleg muss mindestens enthalten:

```json
{
  "schema_version": 1,
  "pr_number": 123,
  "base_sha": "40-stellige SHA",
  "head_sha": "40-stellige SHA",
  "diff_sha256": "64-stellige SHA-256",
  "risk_class": "R2",
  "reviewer": "eindeutige Prüferidentität",
  "report_sha256": "SHA-256 des Reviewtexts vor dem Marker",
  "review_axis": "correctness",
  "verdict": "PASS",
  "findings_resolved": true
}
```

Der vollständige Reviewbericht steht als normaler Kommentartext vor dem Marker.
Der Beleg folgt genau einmal im selben Kommentar:

```text
<VOLLSTÄNDIGER REVIEWBERICHT>
<!-- weltgewebe-review-evidence
{...}
-->
```

`report_sha256` muss dem SHA-256 des getrimmten UTF-8-Texts vor dem Marker
entsprechen. Berichte unter 120 Byte, mehrere Belegblöcke in einem Kommentar oder
doppelt verwendete Berichtshashes zählen nicht als unabhängige Reviews.

Nicht textuell dargestellte Binär- oder Großdateien erscheinen als
`opaque_files`. Sie blockieren das Gate derzeit fail-closed, weil ein Textreview
ihren tatsächlichen Inhalt nicht beweisen kann. Ein separates, hashgebundenes
Artefakt-Prüfverfahren ist dafür eine spätere Erweiterung.

Ein neuer Push, ein Basiswechsel oder ein anderer Diffhash entwertet den Beleg
automatisch. Für dieselbe Kombination aus Prüfer und Reviewachse zählt nur der
zeitlich neueste exakte Beleg. Ein späteres `BLOCKED` oder `FAIL` hebt einen früheren
PASS derselben Kombination auf.

## Erforderliche Prüfungen

Die Datei `.github/grabowski-required-checks.json` enthält die kanonische Liste der
Checks, die Grabowski vor einem Merge lesen muss. Dazu gehören insbesondere:

- `Core Guard Tests`;
- `ci`;
- `Docs & Shell Hygiene`;
- `PostgreSQL integration proofs`;
- `Web E2E`;
- `Required merge gate`;
- `Review evidence gate`.

Der Required-Merge-Gate-Job bleibt der vorhandene CI-Aggregator. Das
Review-Evidence-Gate ergänzt ihn um die exakte Reviewbindung. Der GitHub-Ruleset
wird separat verwaltet; eine Datei im Repository kann ihn weder beweisen noch
ändern.

## Bootstrap

Der Workflow kann seine eigene Einführung nicht vor seinem ersten Merge aus dem
Default-Branch ausführen. Für den Bootstrap gelten daher dieselben Bindungen
manuell:

1. finalen Head und aktuellen Basiscommit lesen;
2. vollständigen aktuellen GitHub-Diff und Patch erzeugen;
3. SHA-256 und Dateiliste sichern;
4. zwei voneinander unabhängige R3-Reviews einholen;
5. jeden Beleg an Basis, Head und Diff-SHA-256 binden;
6. erst danach mergen;
7. den neuen Workflow gegen einen offenen PR live auslösen;
8. Artefakte, Commitstatus und Ruleset separat zurücklesen.

Die Datei `.github/grabowski-required-checks.json` ist die maschinenlesbare
Sollvorgabe für Grabowski. Der reale GitHub-Ruleset-Zustand muss nach Änderungen
separat zurückgelesen werden; die Repositorydatei allein ändert keinen Ruleset.

## Sicherheitsgrenze des Workflows

Der privilegierte Workflow darf niemals:

- den PR-Branch auschecken oder PR-Gitobjekte abrufen;
- Python-, Shell-, Node- oder Buildcode aus dem PR ausführen;
- Secrets an PR-Inhalte übergeben;
- Reviewbelege nichtberechtigter Kommentarautoren zählen;
- Reviewbelege zählen, deren Kommentarautor nicht zusätzlich in
  `.github/review-evidence-authorities.json` freigegeben ist;
- bei internen Fehlern erfolgreich enden.

Ein Review kann von einem externen Prüfer stammen und durch einen freigegebenen
Attestierer in den PR übertragen werden. Das Feld `reviewer` bezeichnet den vom
Attestierer benannten Prüfer; der GitHub-Kommentarautor muss zusätzlich in der
versionierten Allowlist `.github/review-evidence-authorities.json` stehen.
Repositoryrollen allein reichen nicht aus. Der Hash bindet die Attestation an den
sichtbaren vollständigen Bericht. Für R2 und R3 müssen Prüferidentität, Reviewachse
und Berichtshash jeweils verschieden sein. Technisch bewiesen werden die Identität
des Attestierers, der Berichtshash und dessen Diffbindung – nicht eine unabhängige
Authentifizierung der frei benannten Prüferidentität.

Alle Parser- und Bundlefunktionen stammen aus `main`. API-Daten werden nur als
Bytes oder JSON geparst. Eine unvollständige Dateiliste, ein SHA-Wechsel, eine
fehlende Patchdarstellung oder ein interner Fehler führt zu `evaluation.json` mit
`pass: false` und zu einem fehlgeschlagenen Commitstatus. Dateien ohne GitHub-
Textdarstellung werden im Manifest als `opaque_files` markiert und blockieren das
Gate bis zu einem separaten Artefakt-Prüfverfahren.

## Merge- und Produktionsabschluss

Vor dem Merge wird der vollständige aktuelle GitHub-Diff erneut erzeugt und mit
SHA-256 gesichert. Der Mergeoperator vergleicht:

- PR-Nummer;
- Basis-SHA;
- Head-SHA;
- Diff-SHA-256;
- Reviewbelege;
- Required Checks.

Nach dem Merge werden Mergecommit und Zielbranch zurückgelesen. Wenn die Änderung
den Produktionsbetrieb betrifft, folgt getrennt davon der Deploy- und Livebeweis.
Ein erfolgreicher Merge ist kein Beweis für einen erfolgreichen Rollout.
