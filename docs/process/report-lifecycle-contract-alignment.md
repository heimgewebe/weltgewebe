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
- Kein Validator.
- Kein Backfill.
- Kein Pilot-Report.
- Keine Report-Frontmatter-Änderung.
- Keine Archivierung.
- Keine Löschung.

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
- Der Warnmodus ist im Docs Guard aktiv.
- Lifecycle-Findings bleiben im Warnmodus nicht blockierend.
- Technische Fehler des Lifecycle-Validators bleiben im blockierenden
  Validierungsjob blockierend.
- Die Lifecycle-Generatoren laufen im nicht blockierenden Diagnosejob.
- Kein Strict-Blocking.
- Validator und Inventory erfassen derzeit nur direkte Markdown-Dateien unter
  `docs/reports/`; rekursive Archivpfade bleiben Folgearbeit.

## Legacy ohne Ersatz

Archivierte Legacy-Reports dürfen ohne künstlichen `superseded_by`-Pfad
geführt werden, sofern die fehlende Ablösung fachlich begründet ist.
Für `lifecycle_state: superseded` bleibt ein nachvollziehbarer Ersatzpfad
erforderlich.
Eine maschinenlesbare Legacy-Ausnahme und deren Validatorprüfung sind noch
nicht implementiert.

## Verbleibende Entscheidungen

- Schemaort für report-spezifische Lifecycle-Felder
- zulässige Werte für `lifecycle`
- zulässige Werte für `lifecycle_state`
- ISO-Datumsvalidierung für `review_after`
- `owner_task`-Existenzprüfung
- Supersession-Konsistenz (`superseded_by` vs. `relations[type=supersedes]`)
- Changed-only strict
- Global strict
