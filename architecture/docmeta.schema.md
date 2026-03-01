---
id: docmeta.schema
role: norm
status: canonical
last_reviewed: 2026-02-28
depends_on: []
verifies_with:
  - scripts/docmeta/check_repo_index_consistency.py
  - scripts/docmeta/check_doc_review_age.py
  - scripts/docmeta/generate_system_map.py
---

# Docmeta Schema

Dieses Dokument definiert das Schema für Frontmatter-Metadaten in den kanonischen Entry-Docs.

> **Hinweis:** Das Frontmatter wird bewusst durch einen eingeschränkten, deterministischen
> Mini-Parser gelesen. Strukturierte YAML-Blocklisten werden ausdrücklich nur für die
> Felder `depends_on` und `verifies_with` garantiert.

* **id**: Eindeutiger Identifier des Dokuments.
* **role**: Rolle des Dokuments (norm | reality | runbooks | action).
* **organ**: (Optional) Architektonisches Ownership-Feld für maschinelles Routing
  (z.B. governance, runtime, contracts, docmeta, deploy).
* **status**: Status (canonical).
* **last_reviewed**: Datum der letzten Überprüfung im Format YYYY-MM-DD.
* **depends_on**: Liste von Dokumenten-IDs, von denen dieses Dokument abhängt.
* **verifies_with**: Liste von Checks/Scripts, die dieses Dokument verifizieren.
