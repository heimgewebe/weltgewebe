FROM caddy:2.8.4-builder AS builder

# Version is pinned intentionally to avoid supply-chain drift.
# Update only via explicit PR.
# We pin both the builder image and the explicit build target to ensure
# determinism and satisfy plugin constraints (e.g. caddy-ratelimit requires >=2.8.0).
RUN xcaddy build v2.8.4 \
    --with github.com/mholt/caddy-ratelimit@v0.1.0

FROM caddy:2.8.4

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
