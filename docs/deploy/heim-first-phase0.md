# Heim-first UI (Phase 0) Deployment

This document acknowledges the deployment changes introduced for the "Heim-first UI" Phase 0 implementation.

## Changes

- **Infrastructure**:
  - `infra/caddy/Caddyfile`: Updated to serve static UI files locally for `weltgewebe.home.arpa` and proxy API requests.
  - `infra/compose/compose.prod.yml`:
    - Added volume mount for `apps/web/build` artifacts to the Caddy container.
    - Updated Caddyfile mount to use the local `Caddyfile` instead of `Caddyfile.prod`.
    - Exposed port `8081` for health checks.

## Purpose

These changes enable the `weltgewebe.home.arpa` domain to be the authoritative source for the UI in the local network,
removing the dependency on Cloudflare Pages for local access.

## Verification

The deployment drift check requires documentation updates when infrastructure changes. This file serves as that
acknowledgement.
