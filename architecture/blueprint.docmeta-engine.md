---
id: blueprint.docmeta-engine
role: norm
organ: governance
status: canonical
last_reviewed: 2026-03-03
depends_on: []
verifies_with: []
---

# Plan: Repo zu "selbstorganisierender Dokument-Engine" machen

> **Hinweis:** Dieser Plan dient als strukturierte Blaupause und "North Star"-Dokument
> zur schrittweisen Umsetzung einer selbsterhaltenden Dokumentationsarchitektur.

## Prinzipien (Querschnitt)

- **Determinismus:** Alle generierten Artefakte (`docs.index.json`, `impact.md`, `SYSTEM_MAP.md`) müssen
  bei jedem Lauf identisch ausfallen (stable sort, keine Timestamp-Fluktuation).
- **Abhängigkeitsfrei:** Werkzeuge in `scripts/docmeta/` nutzen ausschließlich die Python Standardbibliothek.

## Phase 0: Diagnose-Gate (ohne Patch-Rausch)

Ziel: Ist-Zustand belegen, ohne Annahmen.

Checks (2-5):

- [x] `make docs-guard` lokal/CI laufen lassen und Artefakte sichern (`artifacts/docmeta/*`).
- [x] Zähle: wie viele kanonische Docs, wie viele ohne `id`, wie viele ohne `last_reviewed`, wie viele mit `depends_on`/`verifies_with`.
- [x] Linkreport prüfen: broken internal links, Anzahl total links in `artifacts/docmeta/link_report.json`.
- [x] Impactreport prüfen: cycles? missing ids? transitive impacts plausibel in `artifacts/docmeta/impact.json`.
- [x] `SYSTEM_MAP.md`: deterministisch (zweimal laufen lassen, `git diff --exit-code SYSTEM_MAP.md` muss leer bleiben).
- [x] Stop-Kriterium: Artefakte stabil + deterministisch; sonst erst Determinismus fixen, bevor Struktur ausgebaut wird.

## Phase 1: Kanonisches Docmeta-Minimum (Contract-first)

Ziel: Jeder kanonische Doc ist gleichartig parsbar.

### 1.1 Frontmatter-Standard (Minimalset)

Für alle kanonischen Docs in `manifest/repo-index.yaml` verpflichtend:

- [x] `id` (string, unique, stabil)
- [x] `role` (enum: norm, reality, runbooks, action)
- [x] `organ` (string, optionales Ownership)
- [x] `status` (enum: canonical)
- [x] `last_reviewed` (YYYY-MM-DD)

Optional aber strukturiert:

- [x] `depends_on` (list)
- [x] `verifies_with` (list)

### 1.2 Schema anpassen

Das Schema `contracts/docmeta.schema.json` anpassen:

- [x] `depends_on` und `verifies_with` in die `required` Liste aufnehmen (auch wenn das Array leer ist `[]`).
- [x] Verifikation via `python3 -m scripts.docmeta.validate_schema`.

### 1.3 Normalisierung erzwingen

- [x] `normalize_list_field()` in `scripts/docmeta/docmeta.py` als Kompatibilitätsschicht erhalten.
- [x] Langfristig: Frontmatter schreibt echte YAML-Listen in allen `.md` Dateien.

## Phase 2: Self-linking durch IDs (nicht durch Pfade)

Ziel: Links überleben Dateiumbenennungen und Verschiebungen.

### 2.1 ID-Link-Konvention

Definiere eine interne Linkform:

- [x] `doc:<id>` als kanonischer "Link" innerhalb von Markdown Dateien.
- [x] Renderer/Checker löst `doc:<id>` zu Dateipfaden auf.

### 2.2 Autogenerierter Docs Index

Das Artefakt `artifacts/docmeta/docs.index.json` ausbauen via `scripts/docmeta/export_docs_index.py`:

- [x] Enthält die Map: `id`, `path`, `role`, `organ`, `depends_on`, `verifies_with`, `last_reviewed`.

### 2.3 Link-Checker erweitern

Das Skript `scripts/docmeta/check_links.py` anpassen:

- [x] Lädt `artifacts/docmeta/docs.index.json` ein.
- [x] Prüft alle `doc:<id>` Links: Existiert die referenzierte ID im Index? Falls nicht, als `broken_link` markieren.

## Phase 3: Selbstorganisation via Artefakte (Reports)

Ziel: Repo zeigt täglich: "wo brennt's", ohne manuelle Suche.

### 3.1 Standard-Artefaktset ausbauen

Artefakte unter `artifacts/docmeta/` pflegen:

- [x] `freshness.{json,md}`
- [x] `link_report.{json,md}`
- [x] `impact.{json,md}`
- [x] `docs.index.json`
- [x] `SYSTEM_MAP.md` (via `scripts/docmeta/generate_system_map.py`)

### 3.2 "Known debt" als first-class

Neues Artefakt generieren:

- [x] `artifacts/docmeta/audit_gaps.json` + `artifacts/docmeta/audit_gaps.md` erstellen via neuem Skript `scripts/docmeta/generate_audit_gaps.py`.
- [x] Quelle: Das Frontmatter-Feld `audit_gaps:` als Block-Liste in `scripts/docmeta/docmeta.py` zulassen.
- [x] Einträge in `Makefile` unter `docs-guard` aufnehmen.

## Phase 4: Guard-Semantik sauber (warn/strict/fail-closed)

Ziel: Policy (in `manifest/review-policy.yaml`) ist verständlich und wirkt wie ein Schalthebel.

### 4.1 Policy-Invarianten

- [x] `warn_days < fail_days` in `scripts/docmeta/docmeta.py` enforced lassen.

Mode-Semantik anwenden in `check_links.py` und `review_impact.py`:

- [ ] `warn` Mode: Niemals `exit 1` wegen fehlenden IDs oder broken Links, nur `stderr` Warnungen.
- [ ] `strict` / `fail-closed` Mode: `exit 1` bei "echten Fehlern" (missing id, cycles, broken doc-links).

### 4.2 Fehler vs. Unknowns definieren

- [ ] Fehlend/invalid in kanonischen Docs (z.B. missing `id`) = Fehler in strict.
- [x] Duplicate Doc-IDs in kanonischen Docs systemweit = Fehler in strict.
- [ ] Broken internal `doc:<id>` Links = Fehler in strict.

## Phase 5: Repo-Information als navigierbares System

Ziel: Contributor versteht das System in 5 Minuten.

### 5.1 "Start Here" Links

- [ ] `README.md` oben mit 5 expliziten Links versehen (Constitution, System Map, Runtime, Operations, Architecture Overview).
- [ ] `SYSTEM_MAP.md` bleibt diff-guarded via `Makefile`.

## Definition of Done (DoD)

- [ ] `make docs-guard` läuft fehlerfrei und deterministisch.
- [ ] Alle kanonischen Dokumente (`manifest/repo-index.yaml`) haben verpflichtend eine `id`,
  `depends_on` und `verifies_with`.
- [ ] Der `doc:<id>` Resolver in `check_links.py` greift und funktioniert.
- [ ] Bei `mode: strict` (in `manifest/review-policy.yaml`) führt ein fehlender Link oder
  eine fehlende ID sofort zu `exit 1`.
- [ ] Keine funktionalen Änderungen an Frontend/Backend Code in dieser Phase (nur Docs & CI-Guards).
