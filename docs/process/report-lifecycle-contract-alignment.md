---
id: process.report-lifecycle-contract-alignment
title: Report Lifecycle Contract Alignment
doc_type: decision
status: active
summary: >
  Implementierte Abgrenzungsentscheidung zwischen globalem DocMeta-Status und report-spezifischem Lifecycle-Modell sowie Dokumentation der verbleibenden Durchsetzungsfragen.
relations:
  - type: relates_to
    target: docs/process/report-lifecycle.md
  - type: relates_to
    target: docs/process/README.md
---

# Report Lifecycle Contract Alignment

## Zweck

### Ursprüngliche Entscheidungsfrage

- globale DocMeta-Wahrheit versus report-spezifische Felder,
- keine Überladung von `status`,
- Supersession-Richtung.

### Heutige Geltung

- Entscheidung ist implementiert,
- report-spezifische Felder werden verwendet,
- globaler Contract bleibt unverändert,
- Warnmodus ist CI-aktiv,
- Strict und semantische Härtung bleiben offen.

## Ausgangslage

- Inventory verarbeitet `lifecycle_state`,
- Validator existiert,
- Pilot und Backfills existieren,
- Supersession-Relation existiert,
- globaler DocMeta-Contract kennt keine Lifecycle-Spezialzustände.


## Ursprüngliche Nicht-Ziele des Entscheidungs-Slices

- Keine Änderung an `contracts/docmeta.schema.json`.
- Keine Änderung an `architecture/docmeta.schema.md`.
- Keine Änderung an `repo.meta.yaml`.
- Keine Änderung an `scripts/docmeta/**`.
- kein Validator.
- kein Backfill.
- kein Pilot-Report.
- Keine Report-Frontmatter-Änderung.
- Keine Archivierung.
- Keine Löschung.

## Aktuelle Nicht-Ziele

- kein globaler Contract-Umbau,
- kein Massen-Backfill,
- kein Strict-Enforcement,
- keine Archivierung oder Löschung,
- keine automatische Owner- oder Reviewdatum-Ableitung.

## Aktuelle Nicht-Ziele

- kein globaler Contract-Umbau,
- kein Massen-Backfill,
- kein Strict-Enforcement,
- keine Archivierung oder Löschung,
- keine automatische Owner- oder Reviewdatum-Ableitung.

## Ursprüngliche Entscheidung

Report-Lifecycle-Metadaten werden zunächst als report-spezifisches Zielmodell
behandelt.

Der bestehende DocMeta-Status bleibt global und wird nicht mit
report-spezifischen Lifecycle-Zuständen überladen.

Folgende report-spezifische Struktur wurde eingeführt:

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

`superseded_by` wird bereits verwendet. `relations[type=supersedes]` bleibt bestehende gerichtete Relation. Die vollständige Konsistenzprüfung ist noch offen.

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
- Warnmodus wird in diesem PR in CI aktiviert.
- Findings bleiben nicht blockierend.
- Toolfehler bleiben blockierend.
- beide Generatorartefakte werden im Diagnosejob erzeugt.
- kein Strict-Blocking.

## Legacy ohne Ersatz

Archivierte oder veraltete Legacy-Reports ohne eindeutiges Ersatzartefakt
dürfen nicht durch künstliche `superseded_by`-Pfade repariert werden.

Dafür braucht es später eine explizite Regel, zum Beispiel:

- ein eigenes Ausnahmefeld,
- eine dokumentierte Verwerfungsbegründung,
- oder ein Validator-Verhalten für historische Reports.

In diesem Slice wird keine solche Ausnahme technisch eingeführt.

## Verbleibende Entscheidungen

- Schemaort für report-spezifische Lifecycle-Felder
- Zulässige Enums für `lifecycle` und `owner_task`
- ISO-Datumsvalidierung für `review_after`
- `owner_task`-Existenzprüfung
- Supersession-Konsistenz (`superseded_by` vs `relations[type=supersedes]`)
- Changed-only strict
- Global strict
