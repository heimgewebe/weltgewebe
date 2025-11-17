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
