# Use the same Rust version as defined in toolchain.versions.yml and compose.core.yml
FROM rust:1.89.0-bullseye AS builder

WORKDIR /app

# 1) Copy manifests first to cache dependencies
COPY Cargo.toml Cargo.lock ./
COPY apps/api/Cargo.toml apps/api/Cargo.toml

# Cargo determines targets by looking at src/ (unless explicitly declared).
# For `cargo fetch` we need the workspace member to have its target files present.
COPY apps/api/src/ apps/api/src/

# 2) Fetch dependencies (this caches the index and downloads)
RUN cargo fetch

# 3) Copy the rest of the workspace
COPY . .

# 4) Build the API binary in release mode
# Offline mode is not strictly necessary but ensures we use what we fetched
RUN cargo build --release --bin weltgewebe-api

# Runner stage
FROM debian:bullseye-slim

WORKDIR /app

# Install runtime dependencies
# curl/wget is needed for healthchecks. ca-certificates for HTTPS.
# jq is needed for data seeding scripts.
RUN apt-get update && apt-get install -y ca-certificates wget jq && rm -rf /var/lib/apt/lists/*

# Copy the binary from builder
COPY --from=builder /app/target/release/weltgewebe-api /app/weltgewebe-api

# Copy scripts for data seeding
# Note: Docker context is repo root
COPY scripts/dev/generate-demo-data.sh /usr/local/bin/generate-demo-data
COPY apps/api/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/generate-demo-data /usr/local/bin/entrypoint.sh

# Expose the port
EXPOSE 8080

# Use entrypoint to handle data initialization
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Run the binary (passed to entrypoint)
CMD ["./weltgewebe-api"]
