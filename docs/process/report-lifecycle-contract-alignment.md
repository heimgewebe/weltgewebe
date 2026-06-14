---
id: process.report-lifecycle-contract-alignment
title: Report Lifecycle Contract Alignment
doc_type: decision
status: draft
summary: >
  Entscheidungsvorbereitung und Zielentscheidung zur Abgrenzung von DocMeta-
  Status, Report-Lifecycle-Zustand, Lifecycle-Feldern, Inventory-Tooling und
  Supersession-Relationen.
relations:
  - type: relates_to
    target: docs/process/report-lifecycle.md
  - type: relates_to
    target: docs/process/README.md
---

# Report Lifecycle Contract Alignment

## Zweck

Dieses Dokument entscheidet die Abgrenzung zwischen bestehendem DocMeta-Modell
und künftigem Report-Lifecycle-Modell.

Die Report-Lifecycle-Policy beschreibt ein Zielmodell. Vor Pilot, Backfill oder
Validator muss festgelegt werden, welche Felder bestehende DocMeta-Wahrheit sind
und welche Felder als report-spezifisches Lifecycle-Modell eingeführt werden.

## Ausgangslage

- `docs/_generated/report-lifecycle-inventory.md` zeigt den Reportbestand und
  die aktuell fehlenden Lifecycle-Felder.
- `docs/process/report-lifecycle.md` beschreibt das Zielmodell.
- Der bestehende DocMeta-Contract kennt bereits allgemeine Dokumentstatuswerte.
- `deferred`, `superseded` und `archived` sind aktuell keine global gültigen
  DocMeta-Statuswerte.
- Die bestehende Supersession-Mechanik nutzt `relations` mit
  `type: supersedes`.
- Das aktuelle Inventory-Tooling liest noch `status` für terminale Zustände und
  kennt `lifecycle_state` noch nicht.

## Nicht-Ziele

- Keine Änderung an `contracts/docmeta.schema.json`.
- Keine Änderung an `architecture/docmeta.schema.md`.
- Keine Änderung an `repo.meta.yaml`.
- Keine Änderung an `scripts/docmeta/**`.
- Kein Validator.
- Kein Backfill.
- Kein Pilot-Report.
- Keine Report-Frontmatter-Änderung.
- Keine Archivierung.
- Keine Löschung.

## Entscheidung

Report-Lifecycle-Metadaten werden zunächst als report-spezifisches Zielmodell
behandelt.

Der bestehende DocMeta-Status bleibt global und wird nicht mit
report-spezifischen Lifecycle-Zuständen überladen.

Für Reports wird folgende Zielstruktur vorbereitet:

```yaml
doc_type: report
status: active
lifecycle: audit
owner_task: OPT-ARC-001
review_after: 2026-07-13
lifecycle_state: active
```

Dabei gilt:

| Feld | Bedeutung |
| --- | --- |
| `doc_type` | bestehende Dokumentart |
| `status` | bestehender globaler DocMeta-Status |
| `lifecycle` | Report-Klasse oder Lifecycle-Rolle |
| `owner_task` | verantwortlicher Task, Vorhaben oder Prozess |
| `review_after` | Review-Datum im Format `YYYY-MM-DD` |
| `lifecycle_state` | report-spezifischer Lifecycle-Zustand |
| `superseded_by` | optionaler Zielpfad bei Ablösung, nur konsistent mit Supersession-Relation |

## Status-Abgrenzung

Bestehende DocMeta-Statuswerte behalten ihre bisherige Bedeutung.

Beispiele:

- `draft`
- `active`
- `deprecated`
- `canonical`

Report-spezifische Lifecycle-Zustände werden nicht direkt als globale
DocMeta-Statuswerte eingeführt.

Zielvokabular für `lifecycle_state`:

- `active`
- `deferred`
- `superseded`
- `archived`

Damit kann ein Report global `status: active` bleiben, während sein
report-spezifischer Zustand über `lifecycle_state` genauer beschrieben wird.

## Supersession-Abgrenzung

Die bestehende Repo-Mechanik für Ablösungen bleibt:

```yaml
relations:
  - type: supersedes
    target: docs/reports/old-report.md
```

Richtung:

```text
neues Artefakt --supersedes--> altes Artefakt
```

`superseded_by` darf nicht als alleinige Wahrheit eingeführt werden.

Wenn `superseded_by` später genutzt wird, muss ein Validator mindestens prüfen,
ob die umgekehrte `relations[type=supersedes]`-Relation existiert oder ob
bewusst eine andere kanonische Richtung beschlossen wurde.

## Inventory- und Validator-Abgrenzung

Das bestehende Report-Lifecycle-Inventory-Tooling bleibt in diesem PR
unverändert.

Das generierte Inventory-Artefakt darf sich nur ändern, wenn `make generate`
eine reproduzierbare Aktualisierung des aktuellen Dokumentationsgraphen erzeugt.

Es ist aktuell eine Bestandsaufnahme und liest noch:

- `status`
- `lifecycle`
- `owner_task`
- `review_after`
- `superseded_by`

Das Inventory kennt `lifecycle_state` noch nicht. Diese Abweichung ist in Phase
1.5 bewusst akzeptiert, weil dieser PR nur die Modellentscheidung trifft.

Ein späterer Tooling-PR muss entscheiden, ob:

- das Inventory zusätzlich `lifecycle_state` ausliest,
- terminale Zustände von `status` auf `lifecycle_state` umgestellt werden,
- oder ein separates Report-Lifecycle-Schema diese Prüfung übernimmt.

## Legacy ohne Ersatz

Archivierte oder veraltete Legacy-Reports ohne eindeutiges Ersatzartefakt
dürfen nicht durch künstliche `superseded_by`-Pfade repariert werden.

Dafür braucht es später eine explizite Regel, zum Beispiel:

- ein eigenes Ausnahmefeld,
- eine dokumentierte Verwerfungsbegründung,
- oder ein Validator-Verhalten für historische Reports.

In diesem PR wird keine solche Ausnahme technisch eingeführt.

## Konsequenzen für Phase 2

Der Pilot darf erst nach dieser Entscheidung erfolgen.

Für den ersten Pilot-Report soll nur bestehendes DocMeta-Vokabular im Feld
`status` verwendet werden. Neue Report-Zustände gehören in `lifecycle_state`,
nicht in `status`.

Beispiel für den späteren Pilot:

```yaml
doc_type: report
status: active
lifecycle: audit
owner_task: OPT-ARC-001
review_after: 2026-07-13
lifecycle_state: active
```

## Konsequenzen für Phase 3

Der spätere Validator soll zunächst report-spezifisch arbeiten.

Er soll prüfen:

- Reports unter `docs/reports/*.md`.
- Existenz und Format von `lifecycle`.
- Existenz und Format von `owner_task`.
- ISO-Format von `review_after`.
- Zulässigkeit von `lifecycle_state`.
- Konsistenz von `superseded_by` mit `relations[type=supersedes]`.
- Keine harte globale DocMeta-Status-Erweiterung ohne separaten Contract-PR.

## Offene Folgeentscheidungen

- Wird `lifecycle_state` Teil von `contracts/docmeta.schema.json`?
- Oder entsteht ein eigenes Report-Lifecycle-Schema?
- Wird `superseded_by` gespeichert, abgeleitet oder vermieden?
- Wie wird Legacy ohne Ersatz maschinenlesbar ausgenommen?
- Wann darf `status: deprecated` mit `lifecycle_state: archived` kombiniert
  werden?
- Wann wird das Inventory-Tooling auf `lifecycle_state` ausgerichtet?
- Ob und wann `repo.meta.yaml` diese Policy als kanonische Quelle registriert.
