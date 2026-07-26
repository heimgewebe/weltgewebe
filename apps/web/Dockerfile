FROM node:20.19.0-alpine@sha256:8bda036ddd59ea51a23bc1a1035d3b5c614e72c01366d989f4120e8adca196d4 AS builder
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@9.11.0 --activate
COPY apps/web/package.json apps/web/pnpm-lock.yaml ./
COPY apps/web/scripts/verify-cookie-version.js ./scripts/verify-cookie-version.js
RUN pnpm install --frozen-lockfile
COPY apps/web ./
COPY policies/performance.v1.json /policies/performance.v1.json
ARG GIT_COMMIT_SHA
ARG BUILD_TIMESTAMP
RUN printf '%s' "${GIT_COMMIT_SHA}" | grep -Eq '^[0-9a-f]{40}$'     && printf '%s' "${BUILD_TIMESTAMP}" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})$'     && GIT_COMMIT_SHA="${GIT_COMMIT_SHA}" BUILD_TIMESTAMP="${BUILD_TIMESTAMP}"        pnpm run build:container

FROM caddy:2.7@sha256:236c6a30ccb84fa412a5360ca8b586d804faba0621ea182fb45902608cd8a563
COPY apps/web/Caddyfile.container /etc/caddy/Caddyfile
COPY --from=builder /workspace/build /srv/weltgewebe
# The upstream binary carries cap_net_bind_service for privileged ports. This
# image listens on 8080, so remove that file capability before the non-root,
# no-new-privileges runtime instead of rewriting the binary through a copy.
RUN setcap -r /usr/bin/caddy \
    && chmod 0444 /etc/caddy/Caddyfile \
    && mkdir -p /data /config /tmp \
    && chown -R 10001:10001 /data /config /tmp /srv/weltgewebe
USER 10001:10001
EXPOSE 8080
