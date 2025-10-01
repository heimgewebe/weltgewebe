# Observability – Local Profile

## Start
```bash
docker compose -f infra/compose/compose.observ.yml up -d
```

- Prometheus: http://localhost:9090
- Grafana:    http://localhost:3001 (anon Viewer)
- Loki:       http://localhost:3100
- Tempo:      http://localhost:3200

This is purely optional and local, does not block anything – but gives you immediate graphics.
