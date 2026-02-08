FROM caddy:2.7.6-builder AS builder

# Version is pinned intentionally to avoid supply-chain drift.
# Update only via explicit PR.
RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit@v0.1.0

FROM caddy:2.7.6

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
