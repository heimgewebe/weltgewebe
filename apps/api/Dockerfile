# Use the same Rust version as defined in toolchain.versions.yml and compose.core.yml
FROM rust:1.89.0-bookworm AS builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends pkg-config libssl-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 1) Copy manifests first to cache dependencies
COPY Cargo.toml Cargo.lock ./
COPY apps/api/Cargo.toml apps/api/Cargo.toml

# 2) Fetch dependencies (this caches the index and downloads)

# DUMMY_TARGET_FOR_CARGO_FETCH
# Cargo erkennt Targets über src/main.rs|src/lib.rs. In dieser Stage sind ggf. nur Manifeste kopiert.
RUN mkdir -p apps/api/src && printf '%s\n' 'fn main() {}' > apps/api/src/main.rs
RUN cargo fetch --locked

# 3) Copy the rest of the workspace
COPY . .

# 4) Build the API binary in release mode
# Build against the checked-in lockfile for deterministic dependency resolution.
ARG CARGO_BUILD_JOBS=2
# Default to a conservative job count for Heimserver stability.
# CI or larger builders may override with --build-arg CARGO_BUILD_JOBS=<n>.
RUN CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS}" cargo build --release --locked --bin weltgewebe-api

# Runner stage
FROM debian:bookworm-slim

WORKDIR /app

# Install runtime dependencies
# wget is needed for healthchecks. ca-certificates for HTTPS.
# jq is needed for data seeding scripts.
# libssl3 is required by OpenSSL-linked Rust dependencies such as webauthn-rs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget jq libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy the binary from builder
COPY --from=builder /app/target/release/weltgewebe-api /app/weltgewebe-api

# Copy scripts for data seeding
# Note: Docker context is repo root
COPY scripts/dev/generate-demo-data.sh /usr/local/bin/generate-demo-data
COPY apps/api/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/generate-demo-data /usr/local/bin/entrypoint.sh

# Expose the port
COPY policies /app/policies
EXPOSE 8080

# Use entrypoint to handle data initialization
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

# Run the binary (passed to entrypoint)
CMD ["./weltgewebe-api"]
