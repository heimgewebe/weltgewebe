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
API_VERSION=<commit> GIT_COMMIT_SHA=<commit> BUILD_TIMESTAMP=<timestamp> \
  docker compose \
    -f infra/compose/compose.prod.yml \
    -f infra/compose/compose.observ.yml \
    up -d
```

- Prometheus: [http://localhost:9090](http://localhost:9090)
- Grafana:    [http://localhost:3001](http://localhost:3001) (anon Viewer)
- Loki:       [http://localhost:3100](http://localhost:3100)
- Tempo:      [http://localhost:3200](http://localhost:3200)

The observability profile is an optional overlay on the production Compose topology. Prometheus shares the internal default Docker network with the API and scrapes `weltgewebe-api:8080`; the API port is not published on the host. The Prometheus configuration is mounted read-only from `infra/compose/monitoring/prometheus.yml`.
