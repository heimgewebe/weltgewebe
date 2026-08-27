---
id: deploy.public-metrics-boundary
title: Public Metrics Boundary
doc_type: reference
status: active
summary: Public/private boundary for Prometheus metrics at the production VPS edge.
relations:
  - type: relates_to
    target: docs/deploy/vps.md
  - type: relates_to
    target: infra/caddy/Caddyfile.vps
  - type: relates_to
    target: infra/compose/compose.observ.yml
---
# Public metrics boundary

The API exposes Prometheus metrics on its internal `/metrics` route. The optional
observability Compose overlay supplies its Prometheus configuration as an inline
Compose config and scrapes the API through the internal Compose alias
`weltgewebe-api:8080`. The production API port `8080` is not published on the
host, so this scrape path does not require public Internet exposure.

The production VPS edge keeps operational metrics private:

- `https://commonthing.net/api/metrics` and descendants return HTTP `404`;
- `https://api.weltgewebe.net/metrics` and descendants return HTTP `404`.

`infra/caddy/Caddyfile.vps` enforces this boundary before the generic API reverse
proxy routes. The API's own `/metrics` route remains unchanged. This preserves the
possibility of an internal scrape without treating the public edge as a scrape
target; internal scraper health must be verified separately.

After a production deployment, the canonical read-only public readiness checker
verifies both public metrics routes automatically. They can also be checked directly:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://commonthing.net/api/metrics
curl -sS -o /dev/null -w '%{http_code}\n' https://api.weltgewebe.net/metrics
```

Both requests must return `404`. A successful public `404` verifies only the edge
access boundary; it does not prove that an internal Prometheus scraper is configured
or healthy.
