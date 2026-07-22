# Public metrics boundary

The API exposes Prometheus metrics on its internal `/metrics` route. The documented
Prometheus scraper reaches the API directly through `host.docker.internal:8080`,
using Prometheus' default `/metrics` path. This internal scrape path does not
require public Internet exposure.

The production VPS edge therefore keeps operational metrics private:

- `https://weltgewebe.net/api/metrics` and descendants return HTTP `404`;
- `https://api.weltgewebe.net/metrics` and descendants return HTTP `404`.

`infra/caddy/Caddyfile.vps` enforces this boundary before the generic API reverse
proxy routes. The API's internal `/metrics` route remains unchanged so the
Prometheus scrape contract in `infra/compose/monitoring/prometheus.yml` continues
to work.

After a production deployment, verify the public boundary with read-only requests:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://weltgewebe.net/api/metrics
curl -sS -o /dev/null -w '%{http_code}\n' https://api.weltgewebe.net/metrics
```

Both requests must return `404`. A successful public `404` verifies only the edge
access boundary; it does not prove that the internal Prometheus scraper is healthy.
