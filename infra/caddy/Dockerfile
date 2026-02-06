FROM caddy:2.7.6-builder AS builder

RUN xcaddy build \
    --with github.com/mholt/caddy-ratelimit@v0.1.0

FROM caddy:2.7.6

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
