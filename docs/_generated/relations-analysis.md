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
| Dokumente gesamt | 126 |
| Dokumente mit ausgehenden Relationen | 123 |
| Dokumente als Ziel referenziert | 96 |
| Relationen gesamt | 393 |
| — depends_on | 18 |
| — relates_to | 373 |
| — supersedes | 2 |
| Isolierte Dokumente | 2 |
| depends_on Zyklen | 0 |

### Warnungen

> Heuristische Hinweise — keine CI-Fehler. Zyklen deuten auf zirkuläre Abhängigkeiten, hohe Vernetzung auf zentrale Dokumente, die bei Änderungen besondere Aufmerksamkeit erfordern.

- ⚠️ High outbound count (13): `docs/roadmap.md` — possible over-linking
- ⚠️ High outbound count (12): `docs/blueprints/domain-data-postgres-cutover.md` — possible over-linking
- ⚠️ High outbound count (9): `docs/blueprints/blueprint-agent-safety-control-layer.md` — possible over-linking
- ⚠️ High inbound count (15): `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — central dependency, review carefully
- ⚠️ High inbound count (14): `docs/deploy/README.md` — central dependency, review carefully
- ⚠️ High inbound count (12): `docs/deployment.md` — central dependency, review carefully
- ⚠️ High inbound count (12): `docs/reports/optimierungsstatus.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/blueprints/auth-roadmap.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/tasks/board.md` — central dependency, review carefully
- ⚠️ High inbound count (10): `docs/adr/ADR-0007__auth-persistence-production-db-path.md` — central dependency, review carefully

### Zyklen (depends_on)

_Keine Zyklen gefunden._

### Hubs (hohe Vernetzung)

**Ausgehend (outbound):**

- `docs/roadmap.md` — 13 ausgehende Relationen
- `docs/blueprints/domain-data-postgres-cutover.md` — 12 ausgehende Relationen
- `docs/blueprints/blueprint-agent-safety-control-layer.md` — 9 ausgehende Relationen

**Eingehend (inbound):**

- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — 15 eingehende Relationen
- `docs/deploy/README.md` — 14 eingehende Relationen
- `docs/deployment.md` — 12 eingehende Relationen
- `docs/reports/optimierungsstatus.md` — 12 eingehende Relationen
- `docs/blueprints/auth-roadmap.md` — 11 eingehende Relationen
- `docs/tasks/board.md` — 11 eingehende Relationen
- `docs/adr/ADR-0007__auth-persistence-production-db-path.md` — 10 eingehende Relationen

### Isolierte Dokumente

> Dokumente ohne eingehende und ausgehende Relationen (index.md/README.md ausgenommen).

- `docs/reports/cost-report.md`
- `docs/tasks/DEPLOY-DNS-001B.md`

