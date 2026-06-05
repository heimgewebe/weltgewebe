# INWX Zone Reconciliation Plan

## Status

Prepared plan only. No live provider changes performed.

## Scope

- weltgewebe.net
- weltweb.net
- weltweberei.org

## Source Priority

1. Fresh public DNS checks from the local migration audit
2. Final mail migration audit summaries
3. Provider role finding
4. Older stored DNS snapshots only as historical evidence

## Current Target Model

- weltgewebe.net human mail: mailbox.org
- login.weltgewebe.net technical login mail: Brevo
- weltweb.net: no-mail
- weltweberei.org: no-mail
- INWX target: registrar/DNS
- IONOS remains active until DNS/registrar/web cutover is proven

## Reconciled Target Records Summary

### weltgewebe.net

- A @ -> 149.233.190.131
- A www -> 149.233.190.131
- A api -> 149.233.190.131
- MX -> mailbox.org mxext1/mxext2/mxext3
- SPF -> v=spf1 include:mailbox.org ~all
- DMARC -> p=none, rua=mailto:`kontakt@weltgewebe.net`
- mailbox.org DKIM: MBO0001–MBO0004 CNAMEs
- Brevo login subdomain:
  - login TXT brevo-code
  - _dmarc.login TXT
  - brevo1/brevo2 DKIM CNAMEs

### weltweb.net

- A @ -> 217.160.0.145
- AAAA @ -> 2001:8d8:100f:f000::200
- MX 0 .
- SPF -> v=spf1 -all
- DMARC -> p=reject; sp=reject; adkim=s; aspf=s
- No www record unless separately decided

### weltweberei.org

- A/AAAA @ -> current web host
- A/AAAA www -> current web host
- MX 0 .
- SPF -> v=spf1 -all
- DMARC -> p=reject; sp=reject; adkim=s; aspf=s
- WordPress/web behavior must be smoke-tested after cutover

## Records Not To Copy

- IONOS MX
- IONOS SPF
- IONOS DKIM
- IONOS autodiscover
- IONOS DomainConnect
- IONOS DMARC CNAME
- _dep_ws_mutex unless current website-builder dependency is confirmed

## Resolver Note

Cloudflare DNS completed the required lookups. Some Google DNS queries timed out during local audit and are treated as resolver instability, not target value drift.

## Operator Guardrails

- Do not change nameservers before INWX zone review.
- Do not perform registrar transfer in the same step as nameserver cutover unless explicitly decided.
- Do not cancel IONOS during this operation.
- Keep rollback path via IONOS open.

## Secret Policy

No secrets, auth codes, transfer codes, raw headers, tokens, nonces, session cookies, SMTP passwords, or private provider data are stored in this report.
