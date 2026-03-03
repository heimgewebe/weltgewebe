# Plan: Repo zu “selbstorganisierender Dokument-Engine” machen

## Phase 0: Diagnose-Gate (ohne Patch-Rausch)

Ziel: Ist-Zustand belegen, ohne Annahmen.

Checks (2–5):

- [ ] `make docs-guard` lokal/CI laufen lassen und Artefakte sichern (`artifacts/docmeta/*`).
- [ ] Zähle: wie viele kanonische Docs,
  wie viele ohne `id`, wie viele ohne `last_reviewed`,
  wie viele mit `depends_on`/`verifies_with`.
- [ ] Linkreport: broken internal links, Anzahl total links.
- [ ] Impactreport: cycles? missing ids? transitive impacts plausibel?
- [ ] `SYSTEM_MAP`: deterministisch (zweimal laufen lassen, git diff muss leer bleiben).
- [ ] Stop-Kriterium: Artefakte stabil + deterministisch; sonst erst Determinismus fixen, bevor Struktur ausgebaut wird.

## Phase 1: Kanonisches Docmeta-Minimum (Contract-first)

Ziel: Jeder kanonische Doc ist gleichartig parsbar.

### 1.1 Frontmatter-Standard (Minimalset)

Für alle kanonischen Docs verpflichtend:

- [ ] `id` (string, unique, stabil)
- [ ] `role` (enum)
- [ ] `organ` (string/enum falls du willst)
- [ ] `status` (enum, aktuell nur canonical ok)
- [ ] `last_reviewed` (YYYY-MM-DD)

Optional aber strukturiert:

- [ ] `depends_on` (list)
- [ ] `verifies_with` (list)

### 1.2 Schema anpassen

Dein `contracts/docmeta.schema.json` sollte die Realität widerspiegeln:

- [ ] Entweder: `depends_on`/`verifies_with` sind required (auch wenn leer)
- [ ] Oder: optional, aber dann muss jeder Exporter/Report robust damit umgehen
- [ ] Empfehlung: required + default `[]` erzwingen. Das reduziert Sonderfälle.

### 1.3 Normalisierung erzwingen

- [ ] `normalize_list_field()` ist ok, aber: nur als Kompatibilitätsschicht.
  Langfristig: Frontmatter schreibt echte YAML-Listen, keine stringified lists.

Nutzenklasse: deterministische Maschinenlesbarkeit.
Risiko: mittleres PR-Rauschen, wenn viele Dateien angepasst werden.

## Phase 2: Self-linking durch IDs (nicht durch Pfade)

Ziel: Links überleben Umbenennungen.

### 2.1 ID-Link-Konvention

Definiere eine interne Linkform:

- [ ] `doc:<id>` als kanonischer “Link”
- [ ] Renderer/Checker löst `doc:<id>` → Pfad via docs index (JSON)

### 2.2 Autogenerierter Docs Index

Du hast `artifacts/docmeta/docs.index.json`. Mach daraus bewusst:

- [ ] deterministisch
- [ ] stable sort
- [ ] enthält `id`, `path`, `role`, `organ`, `depends_on`, `verifies_with`, `freshness_status`

### 2.3 Link-Checker erweitern

`check_links.py` soll zusätzlich:

- [ ] `doc:<id>` Links prüfen (existiert ID?)
- [ ] optional auto-suggest: “meintest du doc:xyz?” (Levenshtein nur wenn wirklich nötig; sonst lassen)

Nutzen: Umbenennen/Verschieben wird billig.
Risiko: gering; neue Syntax muss dokumentiert werden.

## Phase 3: Selbstorganisation via Artefakte (Reports als Steuerungsinstrument)

Ziel: Repo zeigt dir täglich: “wo brennt’s”, ohne dass du suchst.

### 3.1 Standard-Artefaktset unter `artifacts/docmeta/`

Beibehalten/ausbauen:

- [ ] `freshness.{json,md}`
- [ ] `link_report.{json,md}`
- [ ] `verification_report.{json,md}` (aktuell md; JSON ergänzen)
- [ ] `impact.{json,md}`
- [ ] `docs.index.json`
- [ ] `system_map.md` (oder `SYSTEM_MAP.md` generiert)

### 3.2 “Known debt” als first-class

Neues Artefakt:

- [ ] `audit_gaps.json` + `audit_gaps.md`

Einträge: `{id, topic, severity, evidence, next_check}`

- [ ] Quelle: entweder Frontmatter-Feld `audit_gaps:` oder separate `audit_gaps.yaml`

Das ist die “Schuldenliste”, die CI sichtbar macht, ohne sofort zu blockieren.

Nutzen: Priorisierung, klare nächste Schritte.
Risiko: gering.

## Phase 4: Guard-Semantik sauber (warn/strict/fail-closed)

Ziel: Policy ist verständlich und wirkt wie ein Schalthebel, nicht wie eine Wundertüte.

### 4.1 Policy-Invarianten

- [ ] `warn_days < fail_days` (du hast das bereits als Copilot-Punkt; ich würde es dringend enforced lassen)

Mode-Semantik:

- [ ] `warn`: niemals exit 1 wegen Doku-Qualität, nur warnen (außer Parser-/Schema-Verstoß)
- [ ] `strict`: exit 1 bei “echten Fehlern” (missing id, invalid date, missing verify scripts, cycles)
- [ ] `fail-closed`: wie strict + ggf. zusätzliche “keine Unknowns” Regeln

### 4.2 “Unknowns” definieren

Was ist ein Fehler vs Unknown?

- [ ] Fehlend/invalid in kanonischen Docs = Fehler in strict/fail-closed
- [ ] Broken internal file links = Fehler in strict/fail-closed
- [ ] Missing verifies_with scripts = Warn oder Fehler je nach mode (du hast es so angelegt; gut)

Nutzen: weniger Streit, weniger Überraschung.
Risiko: wenn zu hart, blockierst du dich selbst.

## Phase 5: Repo-Information als navigierbares System (Leitstand-light)

Ziel: Ein neuer Contributor (oder du in 3 Monaten) versteht das System in 5 Minuten.

### 5.1 “Start Here” + Map

- [ ] `README.md` oben: 5 Links (constitution, system map, runtime, operations, naming/network)
- [ ] `SYSTEM_MAP.md` bleibt autogen und diff-guarded

### 5.2 Rollen/Organe als Taxonomie

Zwingend konsistent:

- [ ] `role` ist Zone (norm/reality/runbooks/action)
- [ ] `organ` ist Zuständigkeit (runtime/governance/docmeta/edge/...)

### 5.3 Suchbarkeit

- [ ] optional: `tags` (liste)
- [ ] Synonyme/Glossar: nur wenn du wirklich suchbasiert arbeitest
