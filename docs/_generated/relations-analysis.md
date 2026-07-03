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
| Dokumente gesamt | 152 |
| Dokumente mit ausgehenden Relationen | 151 |
| Dokumente als Ziel referenziert | 114 |
| Relationen gesamt | 511 |
| — depends_on | 19 |
| — relates_to | 489 |
| — supersedes | 3 |
| Isolierte Dokumente | 0 |
| depends_on Zyklen | 0 |

### Warnungen

> Heuristische Hinweise — keine CI-Fehler. Zyklen deuten auf zirkuläre Abhängigkeiten, hohe Vernetzung auf zentrale Dokumente, die bei Änderungen besondere Aufmerksamkeit erfordern.

- ⚠️ High outbound count (13): `docs/blueprints/domain-data-postgres-cutover.md` — possible over-linking
- ⚠️ High outbound count (13): `docs/roadmap.md` — possible over-linking
- ⚠️ High outbound count (9): `docs/blueprints/blueprint-agent-safety-control-layer.md` — possible over-linking
- ⚠️ High outbound count (8): `docs/reference/agent-operability-fixture-matrix.md` — possible over-linking
- ⚠️ High outbound count (8): `docs/reports/domain-edge-write-path-proof.md` — possible over-linking
- ⚠️ High inbound count (20): `docs/tasks/board.md` — central dependency, review carefully
- ⚠️ High inbound count (15): `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — central dependency, review carefully
- ⚠️ High inbound count (15): `docs/deploy/README.md` — central dependency, review carefully
- ⚠️ High inbound count (13): `docs/adr/ADR-0007__auth-persistence-production-db-path.md` — central dependency, review carefully
- ⚠️ High inbound count (13): `docs/reports/auth-status-matrix.md` — central dependency, review carefully
- ⚠️ High inbound count (13): `docs/reports/optimierungsstatus.md` — central dependency, review carefully
- ⚠️ High inbound count (12): `docs/deployment.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/blueprints/auth-roadmap.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/blueprints/domain-data-postgres-cutover.md` — central dependency, review carefully

### Zyklen (depends_on)

_Keine Zyklen gefunden._

### Hubs (hohe Vernetzung)

**Ausgehend (outbound):**

- `docs/blueprints/domain-data-postgres-cutover.md` — 13 ausgehende Relationen
- `docs/roadmap.md` — 13 ausgehende Relationen
- `docs/blueprints/blueprint-agent-safety-control-layer.md` — 9 ausgehende Relationen
- `docs/reference/agent-operability-fixture-matrix.md` — 8 ausgehende Relationen
- `docs/reports/domain-edge-write-path-proof.md` — 8 ausgehende Relationen

**Eingehend (inbound):**

- `docs/tasks/board.md` — 20 eingehende Relationen
- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — 15 eingehende Relationen
- `docs/deploy/README.md` — 15 eingehende Relationen
- `docs/adr/ADR-0007__auth-persistence-production-db-path.md` — 13 eingehende Relationen
- `docs/reports/auth-status-matrix.md` — 13 eingehende Relationen
- `docs/reports/optimierungsstatus.md` — 13 eingehende Relationen
- `docs/deployment.md` — 12 eingehende Relationen
- `docs/blueprints/auth-roadmap.md` — 11 eingehende Relationen
- `docs/blueprints/domain-data-postgres-cutover.md` — 11 eingehende Relationen

### Isolierte Dokumente

> Dokumente ohne eingehende und ausgehende Relationen (index.md/README.md ausgenommen).

_Keine isolierten Dokumente._

