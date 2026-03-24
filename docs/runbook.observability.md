---
id: docs.runbook.observability
title: Observability Runbook
doc_type: runbook
status: active
summary: >
  Runbook für Systembeobachtung und Metriken.
relations:
  - type: relates_to
    target: docs/runbook.md
---
## Observability – Local Profile

## Start

```bash
docker compose -f infra/compose/compose.observ.yml up -d
```

- Prometheus: [http://localhost:9090](http://localhost:9090)
- Grafana:    [http://localhost:3001](http://localhost:3001) (anon Viewer)
- Loki:       [http://localhost:3100](http://localhost:3100)
- Tempo:      [http://localhost:3200](http://localhost:3200)

This is purely optional and local, does not block anything – but gives you immediate graphics.
