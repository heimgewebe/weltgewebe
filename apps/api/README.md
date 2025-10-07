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

4. **Run the API**

   ```bash
   cargo run
   ```

   By default the service listens on <http://localhost:8080>.

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
