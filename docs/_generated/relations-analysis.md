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
| Dokumente gesamt | 76 |
| Dokumente mit ausgehenden Relationen | 73 |
| Dokumente als Ziel referenziert | 56 |
| Relationen gesamt | 152 |
| — relates_to | 151 |
| — supersedes | 1 |
| Isolierte Dokumente | 1 |
| depends_on Zyklen | 0 |

### Warnungen

> Heuristische Hinweise — keine CI-Fehler. Zyklen deuten auf zirkuläre Abhängigkeiten, hohe Vernetzung auf zentrale Dokumente, die bei Änderungen besondere Aufmerksamkeit erfordern.

- ⚠️ High inbound count (13): `docs/deploy/README.md` — central dependency, review carefully
- ⚠️ High inbound count (11): `docs/deployment.md` — central dependency, review carefully

### Zyklen (depends_on)

_Keine Zyklen gefunden._

### Hubs (hohe Vernetzung)

**Eingehend (inbound):**

- `docs/deploy/README.md` — 13 eingehende Relationen
- `docs/deployment.md` — 11 eingehende Relationen

### Isolierte Dokumente

> Dokumente ohne eingehende und ausgehende Relationen (index.md/README.md ausgenommen).

- `docs/reports/cost-report.md`

