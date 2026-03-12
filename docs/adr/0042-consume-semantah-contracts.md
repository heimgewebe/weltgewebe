---
id: adr.0042-consume-semantah-contracts
title: 0042 Consume Semantah Contracts
doc_type: reference
status: active
canonicality: derived
summary: Automatisch hinzugefügtes Frontmatter.
---
# ADR-0042: semantAH-Contracts konsumieren

Status: superseded

Beschluss:

- Weltgewebe liest JSONL-Dumps (Nodes/Edges) als Infoquelle (read-only).
- Kein Schreibpfad zurück. Eventuelle Events: getrennte Domain.

Konsequenzen:

- CI validiert nur Formate; Import-Job später.
- **Diese Entscheidung ist vorerst ausgesetzt.**
  - semantAH wird aktuell nicht als Datenquelle im Weltgewebe konsumiert.
  - Import-Jobs und CI-Validierungen wurden entfernt.
