### 📄 weltgewebe/infra/compose/monitoring/prometheus.yml

**Größe:** 191 B | **md5:** `b120ae667279988bdc058618653cfcfc`

```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: api
    static_configs:
      - targets:
          - host.docker.internal:8080 # on Linux consider host networking or extra_hosts
```

