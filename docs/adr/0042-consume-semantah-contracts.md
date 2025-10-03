# ADR-0042: semantAH-Contracts konsumieren

Status: accepted

Beschluss:

- Weltgewebe liest JSONL-Dumps (Nodes/Edges) als Infoquelle (read-only).
- Kein Schreibpfad zurück. Eventuelle Events: getrennte Domain.

Konsequenzen:

- CI validiert nur Formate; Import-Job später.
