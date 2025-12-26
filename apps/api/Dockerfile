# Use the same Rust version as defined in toolchain.versions.yml and compose.core.yml
FROM rust:1.89.0-bullseye as builder

WORKDIR /app

# Copy the entire workspace
COPY . .

# Build the API binary in release mode
RUN cargo build --release --bin weltgewebe-api

# Runner stage
FROM debian:bullseye-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y libssl-dev ca-certificates && rm -rf /var/lib/apt/lists/*

# Copy the binary from builder
COPY --from=builder /app/target/release/weltgewebe-api /app/weltgewebe-api

# Expose the port
EXPOSE 8080

# Run the binary
CMD ["./weltgewebe-api"]
