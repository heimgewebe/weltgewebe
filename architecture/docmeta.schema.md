---
id: docmeta.schema
title: Docmeta Schema
summary: Schema-Definition und Konventionen für Frontmatter-Metadaten in kanonischen Entry-Docs.
role: norm
organ: docmeta
status: canonical
canonicality: normative
lifecycle_state: active
owner: governance
review_after: 2026-10-11
last_reviewed: 2026-06-09
depends_on: []
relations: []
verifies_with:
  - scripts/docmeta/check_repo_index_consistency.py
  - scripts/docmeta/check_doc_review_age.py
  - scripts/docmeta/generate_system_map.py
  - scripts/docmeta/validate_relations.py
---

# Docmeta Schema

Dieses Dokument definiert das Frontmatter-Schema für alle in `manifest/repo-index.yaml` registrierten kanonischen Dokumente. Nur dort registrierte Dateien dürfen `status: canonical` tragen.

> **Hinweis:** Das Frontmatter wird durch einen eingeschränkten, deterministischen Mini-Parser gelesen. Für jedes kanonische Dokument vergleicht der Guard dessen Ergebnis blockierend mit PyYAML `BaseLoader`. Damit bleibt das erlaubte Format klein, ohne stille Fehlinterpretationen zuzulassen.

## Pflichtfelder kanonischer Dokumente

* **id**: stabiler, eindeutiger Identifier.
* **title**: menschenlesbarer Titel.
* **summary**: nicht-leere Zusammenfassung.
* **status**: für registrierte Dokumente immer `canonical`.
* **role**: Wahrheitsrolle (`norm`, `reality`, `runbooks`, `action`).
* **organ**: verantworteter System- oder Produktbereich.
* **canonicality**: Art der Geltung (`normative`, `reality`, `operational`, `supporting`, `diagnostic`, `navigation`, `generated`).
  Für manifestregistrierte kanonische Dokumente sind ausschließlich `normative`, `reality` und `operational` zulässig.
* **lifecycle_state**: Lebenszyklus (`active`, `superseded`, `archived`).
* **owner**: verantwortlicher Repo-Bereich.
* **last_reviewed**: Datum der letzten tatsächlichen Prüfung.
* **review_after**: spätester Termin der nächsten Prüfung.
* **depends_on** und **verifies_with**: Listen, auch wenn sie leer sind.

## Getrennte Achsen

`doc_type`, `canonicality` und `lifecycle_state` beantworten verschiedene Fragen:

* `doc_type`: Was für ein Dokument ist es?
* `canonicality`: Welche epistemische Rolle besitzt es?
* `lifecycle_state`: Ist es aktuell, abgelöst oder archiviert?

Ein Blueprint kann deshalb `doc_type: blueprint`, `canonicality: supporting` und `lifecycle_state: active` tragen, ohne kanonische Produktwahrheit zu beanspruchen.

## Optionale Felder

* **doc_type**: Dokumentart, etwa `specification`, `policy`, `runbook`, `blueprint` oder `report`.
* **relations** und **audit_gaps**: typisierte Beziehungen beziehungsweise bekannte Lücken.
* **scope** und **description**: zusätzliche Policy-Beschreibung, soweit nötig.

## Attention-Quellenentscheidung für kanonische Produktverträge

Jedes im Manifest unter der Zone `product` registrierte Dokument muss eine maschinenlesbare Quellenentscheidung tragen. Sie beantwortet nicht, ob das Dokument Attention erwähnt, sondern ob sein Fachvertrag kanonische persönliche Fakten erzeugt, aus denen Attention projiziert werden darf.

Jeder Status verlangt zusätzlich eine nicht-leere `attention_source_rationale`, damit die Entscheidung prüfbar bleibt.

* `attention_source_status: source` verlangt `attention_source_facts`, `attention_projection` und `attention_transition_tests` als nicht-leere Listen. Projektions- und Testpfade müssen im Repository existieren.
* `attention_source_status: none` darf keine Source- oder Blockerfelder mitschleppen.
* `attention_source_status: blocked` verlangt konkrete `attention_missing_facts` und `attention_followup_task: BUREAU-*`. Ohne den fehlenden Fachfakt darf Attention keine persönliche Behauptung erzeugen.

Diese Metadaten sind Architekturvertrag, **keine zweite Attention-Datenbank** und kein persistenter Nutzerzustand. Ein allgemeines Kästchen für jeden Pull Request ist ausdrücklich nicht Teil des Vertrags. Zusätzlich läuft in Pull Requests ein gezielter Change-Impact-Guard nur dann, wenn sich Produktlogik unter `apps/` oder `contracts/domain/` ändert. Dann muss der PR genau eine Entscheidung tragen: `<!-- weltgewebe-attention-impact: contract -->` verlangt die gleichzeitige Änderung mindestens eines kanonischen Produktvertrags; `<!-- weltgewebe-attention-impact: none -->` verlangt zusätzlich eine konkrete Begründung über `<!-- weltgewebe-attention-rationale: ... -->`. Diese PR-Angabe ist ausschließlich Reviewevidenz und niemals Fach- oder Nutzerzustand.

## Abhängigkeiten (`depends_on`)

`depends_on` ist das **kanonische, direkte Frontmatter-Feld** für Dokumentabhängigkeiten.

* **Typ**: Liste von Doc-IDs (z. B. `depends_on: [andere.doc.id]`).
* **Pflicht für kanonische Dokumente**: Jedes in `manifest/repo-index.yaml` geführte Dokument muss `depends_on` tragen.
* **Leere Liste ist gültig** und der Standard für Dokumente ohne Abhängigkeit:

  ```yaml
  depends_on: []
  ```

* **Vorrang vor `relations`**: Ist ein direktes `depends_on` vorhanden (auch `[]`), gewinnt es gegenüber `relations[type=depends_on]`.
* **Legacy-Fallback**: Fehlt das direkte Feld, wird `relations[type=depends_on]` weiterhin als Abhängigkeitsquelle gelesen, damit noch nicht migrierte Dokumente nicht abrupt brechen.

Alle Konsumenten (`scripts/docmeta/review_impact.py`, `scripts/docmeta/generate_system_map.py`,
`scripts/docmeta/check_repo_index_consistency.py`, `scripts/docmeta/export_docs_index.py`) lösen
Abhängigkeiten einheitlich über `extract_depends_on()` in `scripts/docmeta/docmeta.py` auf.

## Relationen (`relations`)

Kanonischer Mechanismus für typisierte Relationen (`relates_to`, `supersedes`, `implements`, `verifies`, `derived_from`, `contradicts`). Für Abhängigkeiten
ist das direkte Feld `depends_on` kanonisch (siehe oben); `relations[type=depends_on]` bleibt nur als
Legacy-Fallback erhalten. Jede Relation ist ein Objekt mit `type` und `target`.

```yaml
relations:
  - type: relates_to
    target: docs/specs/ui-state-machine.md
  - type: supersedes
    target: docs/konzepte/garnrolle.md
```

### Relationstypen

| Typ | Semantik | Konsument |
| --- | --- | --- |
| `relates_to` | Allgemeine thematische Querverbindung | backlinks, orphan-guard |
| `depends_on` | Dieses Dokument setzt das Zieldokument voraus | backlinks, orphan-guard |
| `supersedes` | Dieses Dokument löst das Zieldokument ab | backlinks, orphan-guard, supersession-map |
| `implements` | Das Dokument oder Artefakt setzt den Zielvertrag um | backlinks, impact |
| `verifies` | Das Dokument oder Artefakt belegt den Zielvertrag | backlinks, evidence |
| `derived_from` | Das Dokument ist aus dem Ziel abgeleitet | backlinks |
| `contradicts` | Bewusst sichtbarer, noch nicht aufgelöster Widerspruch | conflict review |

Andere Typen sind **nicht erlaubt** und werden vom Guard abgelehnt.

### Autorenregeln — Wann welchen Typ verwenden?

**`relates_to`** — lose, kontextuelle Verbindung.
Zwei Dokumente behandeln verwandtes Thema, ohne harte Abhängigkeit.

* ✅ ADR → Blueprint, der den gleichen Feature-Bereich betrifft
* ✅ Konzeptdokument → Spec, die das Konzept konkretisiert
* ❌ NICHT verwenden, wenn ein Dokument ohne das andere sinnlos wäre → dann `depends_on`
* ❌ NICHT verwenden, wenn ein Dokument das andere ersetzt → dann `supersedes`

**`depends_on`** — funktionale oder logische Abhängigkeit.
Dieses Dokument setzt das Zieldokument inhaltlich voraus.

> **Hinweis:** Bevorzugt wird das direkte Feld `depends_on` (siehe oben). Der
> Relationstyp `depends_on` bleibt nur als Legacy-Fallback dokumentiert.

* ✅ Spec, die auf dem Datenmodell aufbaut:

  ```yaml
  relations:
    - type: depends_on
      target: docs/datenmodell.md
  ```

* ✅ Runbook, das eine Deployment-Anleitung referenziert
* ❌ NICHT verwenden für lose thematische Nähe → dann `relates_to`

**`supersedes`** — Ablösung.
Dieses Dokument ersetzt das Zieldokument vollständig.

* ✅ Neues Konzeptdokument löst altes ab:

  ```yaml
  relations:
    - type: supersedes
      target: docs/konzepte/alt.md
  ```

* ❌ NICHT verwenden, wenn beide Dokumente weiterhin gültig sind → dann `relates_to`

### Referenzformat (PATH-Policy)

Targets verwenden **repo-root-relative Pfade** (z.B. `docs/specs/ui-state-machine.md`).

**Regeln:**

1. **Format**: Immer repo-root-relativ (z.B. `docs/konzepte/foo.md`)
2. **Keine absoluten Pfade** (`/docs/...` ist ungültig)
3. **Keine IDs** als Targets — Pfade sind direkt navigierbar und eindeutig
4. **Target muss existieren** — der Guard prüft, ob die Datei vorhanden ist
5. **Keine Selbstreferenzen** — ein Dokument darf nicht auf sich selbst zeigen
6. **Keine Duplikate** — identische (type, target)-Paare werden abgelehnt

**Bei Umbenennung:**
Wenn eine Zieldatei umbenannt wird, müssen alle `target:`-Einträge, die darauf
verweisen, manuell angepasst werden. Der Guard erkennt verwaiste Targets als Fehler.
Ein repo-weites `grep -r 'target: docs/alter-pfad.md'` hilft beim Auffinden.

### Guard-Validierung

`validate_relations.py` prüft automatisch:

| Regel | Fehler bei Verstoß |
| --- | --- |
| `relations` muss Liste sein | `must be a list` |
| Jeder Eintrag muss `type` + `target` haben | `missing required key` |
| Nur erlaubte Typen | `unknown relation type` |
| Target muss existieren | `does not exist` |
| Keine absoluten Pfade | `not absolute` |
| Keine Selbstreferenzen | `self-reference detected` |
| Keine Duplikate | `duplicate relation` |
| Keine Extra-Keys | `unexpected keys` |

## Kanonische Rollenfelder

* **role**: Rolle des Dokuments (norm | reality | runbooks | action).
* **organ**: Architektonisches Ownership-Feld für maschinelles Routing
  (z.B. governance, runtime, contracts, docmeta, deploy).
* **last_reviewed**: Datum der letzten Überprüfung im Format YYYY-MM-DD.
* **verifies_with**: Liste von Checks/Scripts, die dieses Dokument verifizieren.
  Pflichtfeld für kanonische Dokumente; leere Liste (`verifies_with: []`) ist erlaubt.
* **audit_gaps**: Liste von bekannten Lücken, offenen Fragen oder technischen Schulden (optional).

## Parser Contract (relations)

> **This parser supports a strict YAML subset. It is NOT a general YAML parser.**

The `relations` block is parsed by `scripts/docmeta/relations_parser.py`
(single source of truth). All tools that need relation data **must** import
from that module — no duplicate parsing logic elsewhere.

### Supported format (normative)

```yaml
relations:
  - type: relates_to
    target: docs/foo.md
  - type: supersedes
    target: docs/bar.md
```

**Rules:**

1. `relations:` must be a top-level key (column 0).
2. Each list item starts with `-` (dash), followed by a space, on an indented line. Any amount of leading whitespace is accepted.
3. Continuation keys are indented without a leading dash.
4. Key order within an entry is irrelevant (`target` before `type` is valid).
5. All keys per entry are preserved for downstream validation.
6. Empty list shorthand `relations: []` is supported.
7. Blank lines between entries are tolerated.
8. Comment lines (`# ...`) inside the block are ignored.
9. Simple surrounding quotes on values (`"val"` or `'val'`) are stripped.

### Explicitly NOT supported

| Pattern | Example | Behavior |
| --- | --- | --- |
| Inline mappings | `- {type: foo, target: bar}` | Misinterpreted as dict with garbage key (e.g. `{type`); caught by downstream validation |
| Flow sequences | `[a, b]` as list items | Not parsed |
| Multi-line scalars | `target: >\n  long value` | Not parsed |
| Nested structures | Deeper than one key-value level | Not parsed |
| Anchors / aliases | `*ref`, `&anchor` | Not supported |

### Entscheidung: eingeschränkter Parser mit blockierender YAML-Parität

**Entscheidung vom 11.07.2026:** Der Mini-Parser bleibt als deterministische Standardbibliotheks-Komponente erhalten. Er gilt jedoch nicht mehr allein als ausreichender Beleg.

Für jedes im Manifest registrierte kanonische Dokument führt `validate_schema.py` zusätzlich PyYAML mit `BaseLoader` aus und verlangt identische Datenstrukturen. Eine Abweichung ist ein CI-Fehler. Dadurch gilt:

1. Der zulässige YAML-Teil bleibt absichtlich klein und dokumentiert.
2. Mehrzeilige Skalare, verschachtelte Sonderformen oder andere vom Mini-Parser nicht verstandene Konstrukte werden nicht still akzeptiert.
3. Der frühere nicht-blockierende NOTICE-Mechanismus ist abgelöst.
4. Eine spätere vollständige Migration auf einen YAML-Parser bleibt möglich, ist aber für den heutigen Vertrag nicht erforderlich.

PyYAML ist deshalb eine verpflichtende Abhängigkeit des Docs-Guard. Der Laufzeitcode des Produkts bleibt davon unberührt.
