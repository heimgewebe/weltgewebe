FROM node:20.19.0-alpine@sha256:8bda036ddd59ea51a23bc1a1035d3b5c614e72c01366d989f4120e8adca196d4 AS builder
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@9.11.0 --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
COPY apps/web/scripts/verify-cookie-version.js ./scripts/verify-cookie-version.js
RUN pnpm install --frozen-lockfile
COPY apps/web ./
ARG GIT_COMMIT_SHA
ARG BUILD_TIMESTAMP
RUN printf '%s' "${GIT_COMMIT_SHA}" | grep -Eq '^[0-9a-f]{40}$'     && printf '%s' "${BUILD_TIMESTAMP}" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})$'     && GIT_COMMIT_SHA="${GIT_COMMIT_SHA}" BUILD_TIMESTAMP="${BUILD_TIMESTAMP}"        pnpm build

FROM caddy:2.7@sha256:236c6a30ccb84fa412a5360ca8b586d804faba0621ea182fb45902608cd8a563
COPY apps/web/Caddyfile.container /etc/caddy/Caddyfile
COPY --from=builder /workspace/build /srv/weltgewebe
RUN cp /usr/bin/caddy /usr/bin/caddy.uncapped \
    && mv /usr/bin/caddy.uncapped /usr/bin/caddy \
    && chmod 0755 /usr/bin/caddy \
    && chmod 0444 /etc/caddy/Caddyfile \
    && mkdir -p /data /config /tmp \
    && chown -R 10001:10001 /data /config /tmp /srv/weltgewebe
USER 10001:10001
EXPOSE 8080
