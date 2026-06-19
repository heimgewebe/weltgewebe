---
id: docs.reports.domain-runtime-data-source-reconciliation
title: Domain Runtime Data Source Reconciliation
doc_type: report
status: active
owner: docs-mechanik
summary: Dokumentiert, warum DB-PROOF-001 derzeit nicht aus der Runtime beweisbar ist: heimserver-API und PostgreSQL laufen, aber Domain-Nodes/-Edges fehlen sowohl in PostgreSQL als auch in JSONL.
relations:
  - type: relates_to
    target: docs/reports/domain-edge-reference-audit.md
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/tasks/index.json
  - type: relates_to
    target: docs/blueprints/domain-data-postgres-cutover.md
  - type: relates_to
    target: docs/reports/opt-arc-001-db-proof-matrix.json
---

# Domain Runtime Data Source Reconciliation

Task: DB-PROOF-001  
Status: diagnostic / blocker-confirmed / no-runtime-domain-edges

## Executive Summary

DB-PROOF-001 ist derzeit nicht durchführbar, weil keine repräsentativen Runtime-Domain-Edges existieren. Die Runtime-PostgreSQL-DB auf heimserver ist erreichbar und wird für Sessions genutzt, enthält aber keine Domain-Accounts, Nodes oder Edges. Die JSONL-Datenquelle enthält ebenfalls keine Nodes oder Edges.

## What this proves

- PostgreSQL ist angebunden.
- Sessions persistieren in PostgreSQL.
- Domain-PostgreSQL ist nicht als Runtime-Domain-Quelle aktiv befüllt.
- JSONL bleibt ohne Domain-Postgres-Schalter der Domain-Default-Pfad.
- Die hostseitige JSONL-Quelle enthält derzeit keine repräsentativen Nodes/Edges.
- Für die containerseitige `/data`-Quelle wurden keine aktiven `demo.nodes.jsonl`- oder `demo.edges.jsonl`-Dateien beobachtet.
- DB-PROOF-001 kann nicht mit `auditable_edges_total > 0` erfüllt werden.

## What this does not prove

- Es beweist nicht, dass Domain-Postgres defekt ist.
- Es beweist nicht, dass FKs ungeeignet sind.
- Es beweist nicht, dass Guard/Quarantine zwingend ist.
- Es beweist nicht, dass keine UI-/API-Flows existieren.
- Es beweist nur: Die aktuelle Runtime enthält keine auditierbaren Domain-Edges.

## Runtime Evidence

Datum: 2026-06-18  
Host: heimserver  
API Container: weltgewebe-api-1  
DB Container: weltgewebe-db-1  

### API Environment

Observed redacted keys:

- `DATABASE_URL=<redacted>`
- keine `WELTGEWEBE_DOMAIN_*`-Keys beobachtet

Secrets emitted: no  
Raw data emitted: no

### PostgreSQL Counts

- `domain_accounts: 0`
- `domain_nodes: 0`
- `domain_edges: 0`
- `sessions: 9`

### JSONL Counts

Deploy path:

- `/opt/weltgewebe/.gewebe/in/demo.accounts.jsonl: 1 line`
- `/opt/weltgewebe/.gewebe/in/demo.nodes.jsonl: 0 lines`
- `/opt/weltgewebe/.gewebe/in/demo.edges.jsonl: 0 lines`

Container-visible path for the production compose JSONL source (`GEWEBE_IN_DIR=/data`):

- `/data/demo.accounts.jsonl: 1 line`
- `/data/demo.nodes.jsonl: not observed in container-visible scan`
- `/data/demo.edges.jsonl: not observed in container-visible scan`

The container-visible scan checked `/data` and observed only `/data/demo.accounts.jsonl` for demo JSONL input. It did not observe `/data/demo.nodes.jsonl` or `/data/demo.edges.jsonl`.

## Code/Config Interpretation

`DATABASE_URL` allein schaltet Domain-Daten nicht auf PostgreSQL um. Es ermöglicht Datenbankzugriff und Session-Persistenz. Domain-Read/Write bleibt ohne explizite Domain-Schalter beim JSONL/default-Pfad.

Relevante Schalter:

- `WELTGEWEBE_DOMAIN_READ_SOURCE`
- `WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE`
- `WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE`
- `WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE`

Backfill-, Read-Path- und Write-Path-Proofs belegen Fähigkeiten, aber keinen produktiven Runtime-Datenbestand.

## Decision Matrix

| Option | Beschreibung | Kann DB-PROOF-001 wieder aufnehmen? | Risiko |
|---|---|---:|---|
| Echte UI/API-Runtime erzeugt Domain-Daten | Operator erzeugt reale Nodes/Edges über vorhandene Runtime-Flows | Ja, wenn der Edge-Audit gegen die aktive Quelle `auditable_edges_total > 0` liefert und redigiert läuft | gering bis mittel |
| Redigierter Runtime-JSONL-Snapshot | Repräsentativer Export mit Nodes/Edges, keine Rohdaten im Repo | Ja, wenn Herkunft und Repräsentativität belegt sind | mittel |
| Kontrollierter Seed | Dedizierter Seed erzeugt repräsentative, nicht-produktive Domain-Daten | Nur wenn als repräsentativ beschlossen | mittel |
| Postgres-Cutover | Domain-Read/Write auf PostgreSQL umstellen | Nein, Folgetask; kein DB-PROOF-Ersatz | hoch |
| Synthetische Minimalfixture | künstliche 1-Edge-Fixture | Nein | Scheinevidenz |

## Recommendation

DB-PROOF-001 bleibt `partial`.

Vor einem erneuten DB-PROOF-001-Audit muss eine repräsentative Domain-Datenquelle bereitstehen.

Empfohlene nächste Entscheidung:

1. Sollen echte Runtime-Flows Domain-Nodes/-Edges erzeugen?
2. Soll ein redigierter Runtime-JSONL-Snapshot bereitgestellt werden?
3. Soll ein kontrollierter Seed als repräsentativ gelten?
4. Oder soll Domain-Postgres-Cutover separat vorbereitet werden?

## Follow-up Gate for DB-PROOF-001

DB-PROOF-001 darf erst wieder aufgenommen werden, wenn eine repräsentative Domain-Datenquelle bereitsteht:

- Runtime-PostgreSQL enthält `domain_nodes_count > 0` und `domain_edges_count > 0`, oder
- ein redigierter Runtime-JSONL-Snapshot mit Nodes/Edges liegt vor, oder
- ein kontrollierter Seed ist explizit als repräsentative Datenquelle beschlossen.

Zusätzlich muss vor einer FK-vs-Guard-Entscheidung gelten:

- der Edge-Audit läuft gegen diese Quelle,
- `auditable_edges_total > 0`,
- Auditoutput ist redigiert,
- keine DSN/Secrets/Rohdaten werden committed.
