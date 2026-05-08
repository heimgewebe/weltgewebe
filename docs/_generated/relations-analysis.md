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
| Dokumente gesamt | 86 |
| Dokumente mit ausgehenden Relationen | 84 |
| Dokumente als Ziel referenziert | 66 |
| Relationen gesamt | 197 |
| — depends_on | 13 |
| — relates_to | 182 |
| — supersedes | 1 |
| — updates | 1 |
| Isolierte Dokumente | 1 |
| depends_on Zyklen | 0 |

### Warnungen

> Heuristische Hinweise — keine CI-Fehler. Zyklen deuten auf zirkuläre Abhängigkeiten, hohe Vernetzung auf zentrale Dokumente, die bei Änderungen besondere Aufmerksamkeit erfordern.

- ⚠️ High outbound count (12): `docs/roadmap.md` — possible over-linking
- ⚠️ High inbound count (13): `docs/deploy/README.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/deployment.md` — central dependency, review carefully

### Zyklen (depends_on)

_Keine Zyklen gefunden._

### Hubs (hohe Vernetzung)

**Ausgehend (outbound):**

- `docs/roadmap.md` — 12 ausgehende Relationen

**Eingehend (inbound):**

- `docs/deploy/README.md` — 13 eingehende Relationen
- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — 11 eingehende Relationen
- `docs/deployment.md` — 11 eingehende Relationen

### Isolierte Dokumente

> Dokumente ohne eingehende und ausgehende Relationen (index.md/README.md ausgenommen).

- `docs/reports/cost-report.md`

