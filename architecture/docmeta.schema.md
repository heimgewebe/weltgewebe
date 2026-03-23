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

### Referenzformat

Targets verwenden **repo-root-relative Pfade** (z.B. `docs/blueprints/ui-state-machine.md`).
Keine IDs als Targets — Pfade sind direkt navigierbar und eindeutig.

## Zone-spezifische Felder (architecture/, runtime/, runbooks/)

* **role**: Rolle des Dokuments (norm | reality | runbooks | action).
* **organ**: (Optional) Architektonisches Ownership-Feld für maschinelles Routing
  (z.B. governance, runtime, contracts, docmeta, deploy).
* **last_reviewed**: Datum der letzten Überprüfung im Format YYYY-MM-DD.
* **verifies_with**: Liste von Checks/Scripts, die dieses Dokument verifizieren.
* **audit_gaps**: Liste von bekannten Lücken, offenen Fragen oder technischen Schulden (optional).
