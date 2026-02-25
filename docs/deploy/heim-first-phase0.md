# Heim-first UI (Phase 0) Deployment

This document acknowledges the deployment changes introduced for the "Heim-first UI" Phase 0 implementation.

## Changes

- **Infrastructure**:
  - `infra/caddy/Caddyfile`: Restored to its original state (Dev-Gateway proxying to `web:5173`).
  - `infra/caddy/Caddyfile.dev`: Created as the explicit configuration for the development environment.
  - `infra/caddy/Caddyfile.heim`: Created as the new configuration for the Heimserver deployment.
    - Serves static UI files locally for `weltgewebe.home.arpa` using `tls internal`.
    - Proxies API requests to `api:8080`.
    - Binds port `8081` to `127.0.0.1` (loopback only) for health checks.
    - Enforces security headers (CSP, X-Frame-Options, Referrer-Policy).
  - `infra/compose/compose.prod.yml`:
    - Added volume mount for `apps/web/build` artifacts to the Caddy container.
    - Updated Caddyfile mount to use `Caddyfile.heim`.
    - Exposed port `8081` bound to loopback for health checks.
  - `infra/compose/compose.core.yml`:
    - Updated Caddyfile mount to use `Caddyfile.dev`.

## Purpose

These changes enable the `weltgewebe.home.arpa` domain to be the authoritative source for the UI in the local network,
removing the dependency on Cloudflare Pages for local access, while preserving the development workflow and enhancing
security via loopback binding and deterministic TLS.

## Verification

The deployment drift check requires documentation updates when infrastructure changes. This file serves as that
acknowledgement.
