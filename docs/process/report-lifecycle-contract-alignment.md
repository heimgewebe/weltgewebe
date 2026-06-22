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

### Owner-resolution decision

- **Normative Quellen**: `docs/tasks/index.json` (für strukturierte Task-Control-IDs) und `docs/reports/optimierungsstatus.md` (als kanonische menschliche Wahrheitsquelle für OPT-IDs).
- **Lookup-Fläche**: `docs/reports/optimierungsstatus.json` dient als maschinenlesbare Lookup-Fläche.
- **Wahrheit**: Es gibt keine eigenständige JSON-Wahrheit; die JSON-Datei darf vor vollständigem Paritätsnachweis nicht allein über die Gültigkeit entscheiden.
- **Historische Ownership**: Ein erledigter oder geschlossener Task darf weiterhin Owner eines historischen Reports bleiben.
- **Verbot von Platzhaltern**: Platzhalter (z. B. `TBD`, `docs-mechanik`) sowie unregistrierte Kontrollpunkte (z. B. `MAP-PROOF-001`) sind ungültig.

### Compatibility baseline

Baseline: 2026-06-22, commit `e31e434d48e9b166de8ec894a79fc2d2a840e2f0`.
Scanned all non-empty `owner_task` values in `docs/reports/*.md`.
Result: 5 unique IDs across 16 report usages; 0 unresolved IDs.

| Owner-ID | Verwendungen | Task-Index | OPT-Markdown | OPT-JSON | Identität | Normative Quellenstatus-Konsistenz | Parität |
| -------- | -----------: | ---------- | ------------ | -------- | --------- | ---------------------------------- | ------- |
| `DOCMETA-REPORT-LIFECYCLE-001` | 1 | True | False | False | resolved_task_index | not_comparable | not_applicable |
| `DOMAIN-PG-002` | 1 | True | False | False | resolved_task_index | not_comparable | not_applicable |
| `OPT-API-002` | 5 | False | True | True | resolved_opt_markdown | not_comparable | confirmed_for_id |
| `OPT-ARC-001` | 8 | True | True | True | resolved_both | consistent | confirmed_for_id |
| `TASK-CTL-005` | 1 | True | False | False | resolved_task_index | not_comparable | not_applicable |

### Decision status

- owner semantics: decided
- normative sources: decided
- compatibility audit: complete
- OPT markdown/json full parity: open
- validator enforcement: future-gated
- owner status compatibility: open

### Rollout-Reihenfolge

- warn
- triage
- small backfill slices
- semantic hardening
- changed-only strict
- global strict

### Enforcement-Vorbedingungen

Eine spätere blockierende Owner-Prüfung darf erst aktiviert werden, wenn:

- alle bestehenden Owner-IDs normativ auflösbar sind;
- vollständige OPT-Markdown–JSON-Parität geprüft wird oder der Resolver direkt die kanonische Markdown-Quelle liest;
- keine historische Ownership regressiert;
- Tests für beide normativen Quellen, Lookup-Drift und Konflikte existieren;
- Backfill-Restbestand ausreichend bereinigt ist.

## Verbleibende Entscheidungen

- Schemaort für report-spezifische Lifecycle-Felder
- zulässige Werte für `lifecycle`
- zulässige Werte für `lifecycle_state`
- ISO-Datumsvalidierung für `review_after`
- technische `owner_task`-Existenzprüfung (ohne Namensraum-Leerstelle, da dieser nun definiert ist)
- Supersession-Konsistenz (`superseded_by` vs. `relations[type=supersedes]`)
- Changed-only strict
- Global strict
