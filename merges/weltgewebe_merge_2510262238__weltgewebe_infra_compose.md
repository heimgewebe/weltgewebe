### 📄 weltgewebe/infra/compose/compose.core.yml

**Größe:** 3 KB | **md5:** `e123001a9bff5640f956ec4a03dfa58c`

```yaml
version: "3.9"

services:
  web:
    profiles: ["dev"]
    image: node:20-alpine
    working_dir: /workspace
    command:
      - sh
      - -c
      - |
        if [ ! -d node_modules ]; then
          npm ci;
        fi;
        exec npm run dev -- --host 0.0.0.0 --port 5173
    volumes:
      - ../../apps/web:/workspace
    ports:
      - "5173:5173"
    depends_on:
      api:
        condition: service_healthy
    environment:
      NODE_ENV: development
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:5173 >/dev/null"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  api:
    profiles: ["dev"]
    image: rust:1.83-bullseye
    working_dir: /workspace
    command: ["cargo", "run", "--manifest-path", "apps/api/Cargo.toml", "--bin", "api"]
    environment:
      API_BIND: ${API_BIND:-0.0.0.0:8080}
      DATABASE_URL: postgres://welt:gewebe@pgbouncer:6432/weltgewebe
      RUST_LOG: ${RUST_LOG:-info}
    depends_on:
      pgbouncer:
        condition: service_started
    ports:
      - "8080:8080"
    volumes:
      - ../..:/workspace
      - cargo_registry:/usr/local/cargo/registry
      - cargo_git:/usr/local/cargo/git
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8080/health/live >/dev/null || curl -fsS http://localhost:8080/health/ready >/dev/null || curl -fsS http://localhost:8080/version >/dev/null"]
      interval: 5s
      timeout: 3s
      retries: 30
    restart: unless-stopped

  db:
    profiles: ["dev"]
    image: postgres:16
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-welt}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-gewebe}
      POSTGRES_DB: ${POSTGRES_DB:-weltgewebe}
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./sql/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-welt}"]
      interval: 5s
      timeout: 3s
      retries: 20
      start_period: 20s

  pgbouncer:
    profiles: ["dev"]
    image: edoburu/pgbouncer:1.20
    environment:
      DATABASE_URL: postgres://welt:gewebe@db:5432/weltgewebe
      POOL_MODE: transaction
      MAX_CLIENT_CONN: 200
      DEFAULT_POOL_SIZE: 10
      AUTH_TYPE: trust
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "6432:6432"

  caddy:
    profiles: ["dev"]
    image: caddy:2
    ports:
      - "8081:8081"
    volumes:
      - ../caddy/Caddyfile:/etc/caddy/Caddyfile:ro
    depends_on:
      web:
        condition: service_healthy
      api:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pg_data:
  cargo_registry:
  cargo_git:
```

### 📄 weltgewebe/infra/compose/compose.observ.yml

**Größe:** 482 B | **md5:** `ed2503dd1bc994acd9dc84efbfb815c6`

```yaml
version: "3.9"
services:
  prometheus:
    image: prom/prometheus:v2.54.1
    ports: ["9090:9090"]
    # volumes:
    #   - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
  grafana:
    image: grafana/grafana:11.1.4
    ports: ["3001:3000"]
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer
  loki:
    image: grafana/loki:3.2.1
    ports: ["3100:3100"]
  tempo:
    image: grafana/tempo:2.5.0
    ports: ["3200:3200"]
```

