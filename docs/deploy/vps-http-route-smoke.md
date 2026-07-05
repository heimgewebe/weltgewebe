---
id: deploy.vps-http-route-smoke
title: VPS HTTP Route Smoke
doc_type: runbook
status: draft
summary: DNS-free route-only preflight for the VPS when the real API startup path must not run.
relations:
  - type: relates_to
    target: docs/deploy/vps-http-smoke.md
---
# VPS HTTP Route Smoke

This is a narrower preflight than the normal VPS HTTP smoke. It exists for the case where the real API startup path is not allowed because startup migrations are outside the operation scope.

It may verify the HTTP host-header routing shape before DNS cutover. It must not be treated as proof that the production API process, database schema, mail, SMTP, ACME or public DNS path is ready.

## Safety limits

During this route-only smoke:

- do not change DNS or INWX records
- do not request or force ACME or HTTPS issuance
- do not print local environment files or secrets
- do not start the production API binary
- do not run database migrations
- do not treat the result as production cutover evidence

## Required receipt language

A passing receipt must say that this was route-only evidence. It must not claim real API readiness.
