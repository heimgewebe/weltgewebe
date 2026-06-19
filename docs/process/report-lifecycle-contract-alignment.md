---
id: process.report-lifecycle-contract-alignment
title: Report Lifecycle Contract Alignment
doc_type: decision
status: active
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

## Ursprüngliche Entscheidung

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

## Implementierter Stand

Die Entscheidung wurde in folgenden Repo-Flächen umgesetzt:

- `scripts/docmeta/generate_report_lifecycle_inventory.py`
- `scripts/docmeta/generate_report_lifecycle.py`
- `scripts/docmeta/validate_report_lifecycle.py`
- `scripts/docmeta/tests/test_validate_report_lifecycle.py`
- `docs/_generated/report-lifecycle-inventory.md`
- `docs/_generated/report-lifecycle.md`

Dabei gilt:

- `lifecycle_state` wird vom Inventory verarbeitet.
- Der Validator existiert.
- Modi `report`, `warn` und `strict` existieren.
- Pilot und Teil-Backfills sind erfolgt.
- CI-Blocking ist noch nicht aktiviert.

## Legacy ohne Ersatz

Archivierte oder veraltete Legacy-Reports ohne eindeutiges Ersatzartefakt
dürfen nicht durch künstliche `superseded_by`-Pfade repariert werden.

Dafür braucht es später eine explizite Regel, zum Beispiel:

- ein eigenes Ausnahmefeld,
- eine dokumentierte Verwerfungsbegründung,
- oder ein Validator-Verhalten für historische Reports.

In diesem PR wird keine solche Ausnahme technisch eingeführt.

## Verbleibende Entscheidungen

- Schemaort für report-spezifische Lifecycle-Felder
- Zulässige Enums für `lifecycle` und `owner_task`
- ISO-Datumsvalidierung für `review_after`
- `owner_task`-Existenzprüfung
- Supersession-Konsistenz (`superseded_by` vs `relations[type=supersedes]`)
- Changed-only strict
- Global strict
