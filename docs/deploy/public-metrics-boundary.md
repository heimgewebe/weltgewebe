# Public metrics boundary

The API exposes Prometheus metrics on its internal `/metrics` route. A reference
Prometheus configuration in `infra/compose/monitoring/prometheus.yml` targets
`host.docker.internal:8080`, so that reference path does not require public
Internet exposure. The current optional local observability Compose profile does
not mount that configuration; this document therefore does not claim a healthy
or production Prometheus scrape path.

The production VPS edge keeps operational metrics private:

- `https://weltgewebe.net/api/metrics` and descendants return HTTP `404`;
- `https://api.weltgewebe.net/metrics` and descendants return HTTP `404`.

`infra/caddy/Caddyfile.vps` enforces this boundary before the generic API reverse
proxy routes. The API's own `/metrics` route remains unchanged. This preserves the
possibility of an internal scrape without treating the public edge as a scrape
target; internal scraper health must be verified separately.

After a production deployment, verify the public boundary with read-only requests:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://weltgewebe.net/api/metrics
curl -sS -o /dev/null -w '%{http_code}\n' https://api.weltgewebe.net/metrics
```

Both requests must return `404`. A successful public `404` verifies only the edge
access boundary; it does not prove that an internal Prometheus scraper is configured
or healthy.
