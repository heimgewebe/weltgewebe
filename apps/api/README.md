# Weltgewebe API

The Weltgewebe API is a Rust-based Axum service that powers the platform's backend capabilities.
This README provides a quick orientation for running and developing the service locally.

## Quickstart

1. **Install dependencies**
   - [Rust toolchain](https://www.rust-lang.org/tools/install) (stable)
   - A running PostgreSQL instance (or use `make up` / `just up` for the dev stack)
   - Optional: a running NATS server when developing features that need messaging

2. **Copy the environment template**

   ```bash
   cp ../../.env.example .env
   ```

3. **Adjust the required environment variables** (either in `.env` or the shell).
   Values defined in `.env` take precedence over the defaults from Docker Compose when you use the
   local development stack.
   Recommended settings:
   - `API_BIND` &mdash; socket address to bind the API (default `0.0.0.0:8080`)
   - `DATABASE_URL` &mdash; PostgreSQL connection string (e.g. `postgres://user:password@localhost:5432/weltgewebe`)
   - `NATS_URL` &mdash; URL of the NATS server (e.g. `nats://127.0.0.1:4222`) when messaging is enabled
   - `AUTH_COOKIE_SECURE` &mdash; Set to `0` if you are developing locally over HTTP (non-HTTPS) to ensure cookies are accepted by the browser.

4. **Run the API**

   ```bash
   cargo run
   ```

   By default the service listens on <http://localhost:8080>.

## Security: CSRF & Proxy Configuration

The API implements strict CSRF protection for all state-changing endpoints (POST, PATCH, PUT, DELETE) that use session authentication.

### Host Header Requirement

The middleware validates the `Origin` and `Referer` headers against the request's `Host` header. If you deploy behind
a reverse proxy (e.g., Caddy, Cloudflare, NGINX):

- **Preferred Standard:** Ensure the proxy **forwards the original Host header** (e.g., `Host: weltgewebe.org`) to
  the API. This maintains the "same-origin" integrity check naturally.
- **Exception/Fallback:** If the proxy *must* rewrite the Host header (e.g., to `api:8080` internally), the CSRF
  check will fail because the browser sends an `Origin` matching the external domain. Only in this case should you add
  the external origin to `CSRF_ALLOWED_ORIGINS`. Do not use the allowlist as a permanent workaround for misconfigured
  proxies if Host forwarding is possible.

The middleware determines HTTP vs HTTPS enforcement solely based on the `Origin` or `Referer` scheme provided by the
client (except for localhost). It does **not** currently use `X-Forwarded-Proto` to infer protocol security.

### Development Overrides

For local development where Origin/Host might mismatch (e.g. strict frontend/backend separation on different ports),
you can whitelist origins:

- `CSRF_ALLOWED_ORIGINS` &mdash; Comma-separated list of allowed origins
  (e.g., `http://localhost:5173,https://my-dev-env.com`).

**Note:** The `/auth/login` endpoint is exempted from CSRF checks to facilitate initial session creation.

## Observability

- `GET /health/live` and `GET /health/ready` expose liveness and readiness information.
- `GET /metrics` renders Prometheus metrics including `http_requests_total{method,path}` and `build_info`.

## Development tasks

```bash
# Format the code
cargo fmt -- --check

# Lint
cargo clippy -- -D warnings

# Run tests
cargo test
```

All commands should be executed from the `apps/api` directory unless otherwise noted.
