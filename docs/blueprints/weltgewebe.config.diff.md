# Blueprint Configuration Diff

## 1. Web Service (Docker Compose)

Add a `web` service to serve the static frontend locally.
(Note: Using Caddy image for static serving, since `adapter-static` produces files).

**File:** `infra/compose/compose.prod.yml` (or similar)

```yaml
services:
  web:
    image: caddy:2.8-alpine
    restart: unless-stopped
    volumes:
      # Option A (Canonical): CI Artifacts are synced to host
      - /opt/weltgewebe/apps/web/build:/srv
      # Option B (Dev): Bind-mount source build
      # - ../../apps/web/build:/srv
    networks:
      - default
```

## 2. Web Dockerfile (Build Stage Only)

Create a build-only Dockerfile for the frontend assets.
The output `build/` directory will be mounted or copied to the web server.

**File:** `apps/web/Dockerfile`

```dockerfile
# Build Stage
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY . .

# Adapter-static: produces static files in build/
# PUBLIC_ variables are baked at build time!
ENV PUBLIC_GEWEBE_API_BASE="/api"
RUN pnpm build
```

## 3. Caddy Routing (Gateway)

Update the main Gateway Caddy to proxy to the local web container instead of Cloudflare.
Establish correct layers (Host-Debug vs User-Entry).

**File:** `infra/caddy/Caddyfile` (Reference)

```caddy
# User-Entry (Heimnetz)
weltgewebe.home.arpa {
  # API Proxy (Internal Service Name: api, Port: 8080)
  handle_path /api/* {
    reverse_proxy api:8080
  }

  # Serve local UI (Web container, Port: 80 for Caddy image)
  # Alternative: reverse_proxy https://weltgewebe.pages.dev (Fallback)
  reverse_proxy web:80
}

# Host-Debug (Localhost only)
:8081 {
  reverse_proxy api:8080
}
```

## 4. Frontend Config Strategy

Since `adapter-static` is used (verified in `svelte.config.js`):

- `PUBLIC_` environment variables are **Build-Time Only**.
- Runtime injection (`env.js`) is complex with static hosting.
- **Recommended Strategy (Option A):** Use relative paths (`/api`) for all requests.
  This works natively when serving under the same origin (Caddy reverse proxy).
  No extra runtime config needed.

## Diagnose-Only Section (Next Steps)

Check these files to verify assumptions:

1. `apps/web/svelte.config.js` (Verify adapter-static output directory).

   ```bash
   rg "adapter" apps/web/svelte.config.js
   ```

2. `apps/api/src/routes/auth.rs` (Verify implementation of Auth routes).

   ```bash
   rg "route" apps/api/src/routes/auth.rs
   ```

3. `infra/compose/compose.heimserver.override.yml` (Check conflicting ports/mounts).

4. `infra/caddy/Caddyfile` (Verify upstream config).

> **Humor:** Why did the developer go broke? Because he used Cloudflare cache for everything,
> even his bank account balance. (Stale reads are expensive.)
