---
id: docmeta.schema
title: Docmeta Schema
summary: Schema-Definition und Konventionen für Frontmatter-Metadaten in kanonischen Entry-Docs.
role: norm
organ: docmeta
status: canonical
last_reviewed: 2026-03-02
relations: []
verifies_with:
  - scripts/docmeta/check_repo_index_consistency.py
  - scripts/docmeta/check_doc_review_age.py
  - scripts/docmeta/generate_system_map.py
  - scripts/docmeta/validate_relations.py
---

# Docmeta Schema

Dieses Dokument definiert das Schema für Frontmatter-Metadaten in den kanonischen Entry-Docs.

> **Hinweis:** Das Frontmatter wird bewusst durch einen eingeschränkten, deterministischen
> Mini-Parser gelesen. Strukturierte YAML-Blocklisten werden ausdrücklich nur für die
> Felder `relations`, `verifies_with` und `audit_gaps` garantiert.

## Pflichtfelder (alle Dokumente)

* **id**: Eindeutiger Identifier des Dokuments.
* **title**: Menschenlesbarer Titel.
* **status**: Status (canonical | active | deprecated | draft).
* **summary**: Nicht-leere Zusammenfassung (Platzhalter werden abgelehnt).

## Optionales Feld

* **doc_type**: Dokumenttyp (z.B. blueprint, reference, concept, runbook, generated).

## Relationen (`relations`)

Einziger kanonischer Relationsmechanismus. Jede Relation ist ein Objekt mit `type` und `target`.

```yaml
relations:
  - type: relates_to
    target: docs/blueprints/ui-state-machine.md
  - type: supersedes
    target: docs/konzepte/garnrolle.md
```

### Relationstypen

| Typ | Semantik | Konsument |
| --- | --- | --- |
| `relates_to` | Allgemeine thematische Querverbindung | backlinks, orphan-guard |
| `depends_on` | Dieses Dokument setzt das Zieldokument voraus | backlinks, orphan-guard |
| `supersedes` | Dieses Dokument löst das Zieldokument ab | backlinks, orphan-guard, supersession-map |

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

Targets verwenden **repo-root-relative Pfade** (z.B. `docs/blueprints/ui-state-machine.md`).

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

## Zone-spezifische Felder (architecture/, runtime/, runbooks/)

* **role**: Rolle des Dokuments (norm | reality | runbooks | action).
* **organ**: (Optional) Architektonisches Ownership-Feld für maschinelles Routing
  (z.B. governance, runtime, contracts, docmeta, deploy).
* **last_reviewed**: Datum der letzten Überprüfung im Format YYYY-MM-DD.
* **verifies_with**: Liste von Checks/Scripts, die dieses Dokument verifizieren.
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
2. Each list item starts with `- ` (indented, dash + space).
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
| Inline mappings | `- {type: foo, target: bar}` | Returned as bare string, not dict |
| Flow sequences | `[a, b]` as list items | Not parsed |
| Multi-line scalars | `target: >\n  long value` | Not parsed |
| Nested structures | Deeper than one key-value level | Not parsed |
| Anchors / aliases | `*ref`, `&anchor` | Not supported |

### Decision: Mini-Parser vs. Migration

**Decision: Mini-Parser is sufficient** (as of 2026-03).

Rationale:

* The supported subset covers 100 % of the actual relations usage in the
  repository (140 relations across all docs — all use `type:` + `target:`
  block list format without quotes, comments, or inline mappings).
* No silent misinterpretation risks for the currently used format.
* The parser behavior is deterministic and fully tested.

Re-evaluate if:

* Inline mappings or nested structures appear in real documents.
* A YAML library is already required as a dependency for other reasons.

