### 📄 apps/api/Cargo.toml

**Größe:** 661 B | **md5:** `1e2e74243b53f7ab39631153465f3554`

```toml
[package]
name = "weltgewebe-api"
version = "0.1.0"
edition = "2021"
authors = ["Weltgewebe Team"]
license = "MIT"

[dependencies]
anyhow = "1"
axum = { version = "0.7", features = ["macros"] }
async-nats = "0.35"
dotenvy = "0.15"
prometheus = "0.14.0"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sqlx = { version = "0.8.1", default-features = false, features = ["runtime-tokio", "postgres"] }
tokio = { version = "1", features = ["macros", "rt-multi-thread"] }
tower = "0.5"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "fmt"] }
serde_yaml = "0.9"

[dev-dependencies]
serial_test = "3"
tempfile = "3"
```

### 📄 apps/api/README.md

**Größe:** 2 KB | **md5:** `d4e26f6f719e408fcf849bfbf4c80f82`

```markdown
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
```

