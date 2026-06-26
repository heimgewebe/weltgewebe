---
id: docs.generated.relations-analysis
title: Relations Analysis
doc_type: generated
status: active
summary: Automatische Analyse des Relationsgraphen — Zyklen, Hubs, Isolation, Verteilung.
---

## Weltgewebe Relations Analysis

Generated automatically. Do not edit.

### Übersicht

| Metrik | Wert |
| --- | --- |
| Dokumente gesamt | 132 |
| Dokumente mit ausgehenden Relationen | 131 |
| Dokumente als Ziel referenziert | 101 |
| Relationen gesamt | 431 |
| — depends_on | 18 |
| — relates_to | 410 |
| — supersedes | 3 |
| Isolierte Dokumente | 0 |
| depends_on Zyklen | 0 |

### Warnungen

> Heuristische Hinweise — keine CI-Fehler. Zyklen deuten auf zirkuläre Abhängigkeiten, hohe Vernetzung auf zentrale Dokumente, die bei Änderungen besondere Aufmerksamkeit erfordern.

- ⚠️ High outbound count (13): `docs/blueprints/domain-data-postgres-cutover.md` — possible over-linking
- ⚠️ High outbound count (13): `docs/roadmap.md` — possible over-linking
- ⚠️ High outbound count (9): `docs/blueprints/blueprint-agent-safety-control-layer.md` — possible over-linking
- ⚠️ High outbound count (8): `docs/reports/domain-edge-write-path-proof.md` — possible over-linking
- ⚠️ High inbound count (15): `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — central dependency, review carefully
- ⚠️ High inbound count (15): `docs/deploy/README.md` — central dependency, review carefully
- ⚠️ High inbound count (15): `docs/tasks/board.md` — central dependency, review carefully
- ⚠️ High inbound count (12): `docs/deployment.md` — central dependency, review carefully
- ⚠️ High inbound count (12): `docs/reports/optimierungsstatus.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/blueprints/auth-roadmap.md` — central dependency, review carefully
- ⚠️ High inbound count (10): `docs/adr/ADR-0007__auth-persistence-production-db-path.md` — central dependency, review carefully
- ⚠️ High inbound count (10): `docs/blueprints/domain-data-postgres-cutover.md` — central dependency, review carefully

### Zyklen (depends_on)

_Keine Zyklen gefunden._

### Hubs (hohe Vernetzung)

**Ausgehend (outbound):**

- `docs/blueprints/domain-data-postgres-cutover.md` — 13 ausgehende Relationen
- `docs/roadmap.md` — 13 ausgehende Relationen
- `docs/blueprints/blueprint-agent-safety-control-layer.md` — 9 ausgehende Relationen
- `docs/reports/domain-edge-write-path-proof.md` — 8 ausgehende Relationen

**Eingehend (inbound):**

- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — 15 eingehende Relationen
- `docs/deploy/README.md` — 15 eingehende Relationen
- `docs/tasks/board.md` — 15 eingehende Relationen
- `docs/deployment.md` — 12 eingehende Relationen
- `docs/reports/optimierungsstatus.md` — 12 eingehende Relationen
- `docs/blueprints/auth-roadmap.md` — 11 eingehende Relationen
- `docs/adr/ADR-0007__auth-persistence-production-db-path.md` — 10 eingehende Relationen
- `docs/blueprints/domain-data-postgres-cutover.md` — 10 eingehende Relationen

### Isolierte Dokumente

> Dokumente ohne eingehende und ausgehende Relationen (index.md/README.md ausgenommen).

_Keine isolierten Dokumente._

