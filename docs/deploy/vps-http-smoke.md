---
id: deploy.vps-http-smoke
title: VPS HTTP Smoke Preflight
doc_type: runbook
status: draft
summary: DNS-free HTTP-only preflight path for the VPS before public DNS cutover.
relations:
  - type: relates_to
    target: docs/deploy/vps.md
  - type: relates_to
    target: docs/deploy/DRIFT_POLICY.md
  - type: relates_to
    target: infra/caddy/Caddyfile.http-smoke
  - type: relates_to
    target: infra/compose/compose.vps.override.yml
---
# VPS HTTP Smoke Preflight

This runbook acknowledges the VPS compose/Caddy drift introduced for the DNS-free smoke path.
It is not a production cutover procedure.

## Purpose

The VPS target keeps `infra/caddy/Caddyfile.vps` as the production default. For pre-cutover smoke tests,
`infra/caddy/Caddyfile.http-smoke` can be mounted instead by setting `WELTGEWEBE_CADDYFILE` to the HTTP smoke file.

The smoke file intentionally exposes only an HTTP listener and contains no TLS site blocks. This keeps the first
pre-cutover test away from automatic certificate issuance while still allowing local Host-header checks through Caddy.
It uses an explicit `http://weltgewebe.net` site address so the static CSP preflight validates the same host target
as the VPS deploy wrapper without enabling automatic HTTPS.

## Scope

The HTTP smoke path is only for the first VPS preflight before DNS changes. It may verify:

- proxy health on the HTTP listener
- API readiness through the Caddy-to-API route
- that non-health application paths are not served as the app during the plaintext smoke

It does not prove public HTTPS, ACME issuance, final host routing, or DNS propagation.

## Safety limits

During this preflight:

- do not change DNS or INWX records
- do not start mail or SMTP paths
- do not print `.env` contents or secrets
- do not treat the HTTP smoke file as production configuration

After DNS cutover is explicitly approved, the production VPS Caddyfile remains the canonical public HTTPS path.
