---
id: deploy.vps-http-route-smoke-risks
title: VPS HTTP Route Smoke Risks
doc_type: note
status: draft
summary: Risk register for route-only VPS HTTP smoke evidence.
relations:
  - type: relates_to
    target: docs/deploy/vps-http-route-smoke.md
  - type: relates_to
    target: docs/deploy/vps-http-smoke.md
---
# VPS HTTP Route Smoke Risks

Route-only evidence is narrower than runtime evidence. This file names the main risks so the receipt cannot silently inflate a route proof into a deploy proof.

| Risk class | Failure mode | Control | If ignored |
| --- | --- | --- | --- |
| Evidence inflation | A route-only pass is reported as API readiness or deploy success. | Receipt must state `route-only` and `real API readiness remains unproven`. | The team may close a runtime issue without having started the real API safely. |
| Hidden database mutation | A smoke retry starts the configured production API and triggers startup migrations. | Route-only boundary forbids production API start and database migrations. | A supposedly read-only/no-migration operation mutates the database. |
| Frontend/CSP blind spot | The route smoke does not serve the frontend app and therefore proves no frontend build or CSP behavior. | Runbook forbids frontend/CSP readiness claims. | A blank page or asset failure may be missed until later cutover checks. |
| Upstream blind spot | Static route checks can show that `/api/*` points toward an upstream, but not that the upstream works. | `/api/health/ready` from the real API remains a separate runtime gate. | Proxy shape is mistaken for application health. |
| DNS/ACME confusion | HTTP-only route evidence is mistaken for public DNS or HTTPS readiness. | Explicitly forbid DNS, INWX, HTTPS, and ACME claims. | Public cutover may be attempted without resolver/certificate evidence. |
| Drift between config and runtime | The documented route-only surface may diverge from `infra/caddy/Caddyfile.http-smoke`. | Static test checks the route surface and no-frontend/no-TLS boundary. | Documentation stays green while Caddy behavior changes. |
| Synthetic-upstream overclaim | A later harness with a fake upstream proves forwarding mechanics but not the Rust API. | Synthetic upstream receipts must say `not real API readiness`. | Fake 200 responses mask real application startup failures. |

## Practical interpretation

The route-only smoke is a map-reading exercise, not a crossing of the river. Useful: yes. Sufficient for deploy: no. The bridge toll is still paid at the live API/runtime gate.
