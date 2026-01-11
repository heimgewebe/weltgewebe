# Use the same Rust version as defined in toolchain.versions.yml and compose.core.yml
FROM rust:1.89.0-bullseye as builder

WORKDIR /app

# 1) Copy manifests first to cache dependencies
COPY Cargo.toml Cargo.lock ./
COPY apps/api/Cargo.toml apps/api/Cargo.toml

# 2) Create dummy source to compile dependencies
RUN mkdir -p apps/api/src && echo "fn main() {println!(\"dummy\");}" > apps/api/src/main.rs

# 3) Build dependencies (caches compilation of external crates)
RUN cargo build --release --bin weltgewebe-api

# 4) Remove dummy source and copy actual source
RUN rm -rf apps/api/src
COPY . .

# 5) Build the actual API binary
# Note: 'touch' might be needed to ensure cargo sees files as new if file times are preserved
RUN touch apps/api/src/main.rs && cargo build --release --bin weltgewebe-api

# Runner stage
FROM debian:bullseye-slim

WORKDIR /app

# Install runtime dependencies
# curl/wget is needed for healthchecks. ca-certificates for HTTPS.
RUN apt-get update && apt-get install -y ca-certificates wget && rm -rf /var/lib/apt/lists/*

# Copy the binary from builder
COPY --from=builder /app/target/release/weltgewebe-api /app/weltgewebe-api

# Expose the port
EXPOSE 8080

# Run the binary
CMD ["./weltgewebe-api"]
