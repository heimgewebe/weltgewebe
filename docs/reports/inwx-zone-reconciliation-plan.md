---
id: reports.inwx-zone-reconciliation-plan
title: "INWX Zone Reconciliation Plan"
doc_type: report
status: active
summary: >
  Redigiertes Offline-Zonenmanifest und Cutover-Eingabe für den abrupten
  INWX-DNS-/Registrar-Cutover nach abgeschlossener Mailmigration.
relations:
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/runbooks/domain-mail-cutover.md
  - type: relates_to
    target: docs/reports/domain-provider-role-finding.md
---

# INWX Zone Reconciliation Plan

## Status

Prepared offline plan only. No live provider changes performed.

The manifest still requires a last-minute IONOS export, live provider-dashboard checks, and reviewer approval before the activation window. It is not evidence of a completed cutover or a live prepared INWX zone.

## Operator Constraint

INWX pre-DNS/predelegation is unavailable for this migration. This report is therefore an offline reconciliation and cutover input manifest, not a live prepared provider zone.

## Scope

- `weltgewebe.net`
- `weltweb.net`
- `weltweberei.org`

Cloudflare is not part of this cutover.

## Offline Zone Manifest Contract

The offline zone manifest is a non-live, manually reviewed cutover artifact. It must not contain secrets. Every live target record must carry the following fields before approval:

| Domain | Name | Type | Value/Target | TTL | Purpose | Primary source | Required before go-live | Post-cutover test | Failure risk | Status |
|---|---|---|---|---|---|---|---|---|---|---|

Allowed status values are `confirmed`, `needs live provider check`, and `do not copy`. In the tables below, `unknown` TTL means the operator must obtain or consciously choose the value during the last-minute provider review; it must not be silently inferred.

## Source Priority

1. Current IONOS zone export captured immediately before the activation window
2. Current mailbox.org and Brevo provider-dashboard values
3. Final mail migration audit summaries
4. Provider role finding
5. Older stored DNS snapshots only as historical evidence

## Current Target Model

- `weltgewebe.net` human mail: mailbox.org
- `login.weltgewebe.net` technical login mail: Brevo
- `weltweb.net`: no-mail
- `weltweberei.org`: no-mail
- INWX target: registrar/DNS
- IONOS remains active until registrar/DNS/web/mail/Magic-Link cutover is proven and the 48-hour observation window has passed

## Offline Target Records

All entries remain offline instructions until the abrupt INWX activation window. `needs live provider check` is deliberate: the current IONOS export and provider dashboards are external operational inputs and have not been re-verified by this documentation-only change.

### weltgewebe.net

| Domain | Name | Type | Value/Target | TTL | Purpose | Primary source | Required before go-live | Post-cutover test | Failure risk | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| `weltgewebe.net` | `@` | A | `149.233.190.131` | unknown | Web apex | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> weltgewebe.net A` | Website unavailable or routed incorrectly | needs live provider check |
| `weltgewebe.net` | `www` | A | `149.233.190.131` | unknown | Web frontend | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> www.weltgewebe.net A` | Website alias unavailable or routed incorrectly | needs live provider check |
| `weltgewebe.net` | `api` | A | `149.233.190.131` | unknown | Public API | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> api.weltgewebe.net A` | API and login flow unavailable | needs live provider check |
| `weltgewebe.net` | `@` | MX | `10 mxext1.mailbox.org.` | unknown | Human mail ingress | mailbox.org dashboard | yes | `dig @<inwx-ns> weltgewebe.net MX` | Inbound mail loss or delay | needs live provider check |
| `weltgewebe.net` | `@` | MX | `10 mxext2.mailbox.org.` | unknown | Human mail ingress | mailbox.org dashboard | yes | `dig @<inwx-ns> weltgewebe.net MX` | Inbound mail loss or delay | needs live provider check |
| `weltgewebe.net` | `@` | MX | `20 mxext3.mailbox.org.` | unknown | Human mail ingress | mailbox.org dashboard | yes | `dig @<inwx-ns> weltgewebe.net MX` | Inbound mail loss or delay | needs live provider check |
| `weltgewebe.net` | `@` | TXT | `v=spf1 include:mailbox.org ~all` | unknown | mailbox.org SPF | mailbox.org dashboard | yes | `dig @<inwx-ns> weltgewebe.net TXT` | SPF failure or reduced deliverability | needs live provider check |
| `weltgewebe.net` | `_dmarc` | TXT | `v=DMARC1; p=none; rua=mailto:kontakt@weltgewebe.net` | unknown | Human-mail DMARC | mailbox.org policy decision and current mail audit | yes | `dig @<inwx-ns> _dmarc.weltgewebe.net TXT` | Missing policy/reporting or DMARC failure | needs live provider check |
| `weltgewebe.net` | `MBO0001._domainkey` | CNAME | `mbo0001._domainkey.mailbox.org.` | unknown | mailbox.org DKIM | mailbox.org dashboard | yes | `dig @<inwx-ns> MBO0001._domainkey.weltgewebe.net CNAME` | DKIM failure or reduced deliverability | needs live provider check |
| `weltgewebe.net` | `MBO0002._domainkey` | CNAME | `mbo0002._domainkey.mailbox.org.` | unknown | mailbox.org DKIM | mailbox.org dashboard | yes | `dig @<inwx-ns> MBO0002._domainkey.weltgewebe.net CNAME` | DKIM failure or reduced deliverability | needs live provider check |
| `weltgewebe.net` | `MBO0003._domainkey` | CNAME | `mbo0003._domainkey.mailbox.org.` | unknown | mailbox.org DKIM | mailbox.org dashboard | yes | `dig @<inwx-ns> MBO0003._domainkey.weltgewebe.net CNAME` | DKIM failure or reduced deliverability | needs live provider check |
| `weltgewebe.net` | `MBO0004._domainkey` | CNAME | `mbo0004._domainkey.mailbox.org.` | unknown | mailbox.org DKIM | mailbox.org dashboard | yes | `dig @<inwx-ns> MBO0004._domainkey.weltgewebe.net CNAME` | DKIM failure or reduced deliverability | needs live provider check |
| `weltgewebe.net` | `login` | TXT | `brevo-code:d9e7825df780e9cce6c9fbe8d1ea5abd` | unknown | Brevo domain verification | Brevo dashboard | yes | `dig @<inwx-ns> login.weltgewebe.net TXT` | Brevo sender verification fails | needs live provider check |
| `weltgewebe.net` | `_dmarc.login` | TXT | `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` | unknown | Brevo DMARC | Brevo dashboard | yes | `dig @<inwx-ns> _dmarc.login.weltgewebe.net TXT` | DMARC reporting/policy mismatch | needs live provider check |
| `weltgewebe.net` | `brevo1._domainkey.login` | CNAME | `b1.login-weltgewebe-net.dkim.brevo.com.` | unknown | Brevo DKIM | Brevo dashboard | yes | `dig @<inwx-ns> brevo1._domainkey.login.weltgewebe.net CNAME` | Magic-Link DKIM failure | needs live provider check |
| `weltgewebe.net` | `brevo2._domainkey.login` | CNAME | `b2.login-weltgewebe-net.dkim.brevo.com.` | unknown | Brevo DKIM | Brevo dashboard | yes | `dig @<inwx-ns> brevo2._domainkey.login.weltgewebe.net CNAME` | Magic-Link DKIM failure | needs live provider check |

Brevo verification TXT values are public DNS target values once published. They are not auth codes, transfer codes, API keys, or provider credentials. Nevertheless, the operator must re-check every Brevo verification value against the Brevo dashboard immediately before the activation window and keep its manifest status at `needs live provider check` until that review is complete.

No Brevo SPF/Return-Path record is included unless Brevo issues a separate target value. The operator must not invent one during the activation window.

### weltweb.net

| Domain | Name | Type | Value/Target | TTL | Purpose | Primary source | Required before go-live | Post-cutover test | Failure risk | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| `weltweb.net` | `@` | A | `217.160.0.145` | unknown | Existing web role pending final decision | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> weltweb.net A` | Existing web surface unavailable or misrouted | needs live provider check |
| `weltweb.net` | `@` | AAAA | `2001:8d8:100f:f000::200` | unknown | Existing IPv6 web role pending final decision | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> weltweb.net AAAA` | IPv6 clients fail or reach wrong target | needs live provider check |
| `weltweb.net` | `@` | MX | `0 .` | unknown | Explicit no-mail policy | Current authoritative audit and approved no-mail policy | yes | `dig @<inwx-ns> weltweb.net MX` | Domain may accept or misroute mail | needs live provider check |
| `weltweb.net` | `@` | TXT | `v=spf1 -all` | unknown | Explicit no-mail SPF | Current authoritative audit and approved no-mail policy | yes | `dig @<inwx-ns> weltweb.net TXT` | Spoofing policy weakened | needs live provider check |
| `weltweb.net` | `_dmarc` | TXT | `v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s` | unknown | Explicit no-mail DMARC | Current authoritative audit and approved no-mail policy | yes | `dig @<inwx-ns> _dmarc.weltweb.net TXT` | Spoofing policy weakened | needs live provider check |

No `www` record is included unless the web-role decision explicitly adds one.

### weltweberei.org

| Domain | Name | Type | Value/Target | TTL | Purpose | Primary source | Required before go-live | Post-cutover test | Failure risk | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| `weltweberei.org` | `@` | A | `217.160.0.5` | unknown | Existing WordPress web surface | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> weltweberei.org A` | WordPress unavailable or misrouted | needs live provider check |
| `weltweberei.org` | `@` | AAAA | `2001:8d8:100f:f000::200` | unknown | Existing WordPress IPv6 path | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> weltweberei.org AAAA` | IPv6 clients fail or reach wrong target | needs live provider check |
| `weltweberei.org` | `www` | A | `217.160.0.5` | unknown | WordPress `www` surface | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> www.weltweberei.org A` | `www` site unavailable or misrouted | needs live provider check |
| `weltweberei.org` | `www` | AAAA | `2001:8d8:100f:f000::200` | unknown | WordPress `www` IPv6 path | Current IONOS export plus approved web-role decision | yes | `dig @<inwx-ns> www.weltweberei.org AAAA` | IPv6 `www` clients fail or reach wrong target | needs live provider check |
| `weltweberei.org` | `@` | MX | `0 .` | unknown | Explicit no-mail policy | Current authoritative audit and approved no-mail policy | yes | `dig @<inwx-ns> weltweberei.org MX` | Domain may accept or misroute mail | needs live provider check |
| `weltweberei.org` | `@` | TXT | `v=spf1 -all` | unknown | Explicit no-mail SPF | Current authoritative audit and approved no-mail policy | yes | `dig @<inwx-ns> weltweberei.org TXT` | Spoofing policy weakened | needs live provider check |
| `weltweberei.org` | `_dmarc` | TXT | `v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s` | unknown | Explicit no-mail DMARC | Current authoritative audit and approved no-mail policy | yes | `dig @<inwx-ns> _dmarc.weltweberei.org TXT` | Spoofing policy weakened | needs live provider check |

WordPress/web behavior must be smoke-tested during the activation window and throughout the observation period.

## Records Not To Copy

These records have manifest status `do not copy` unless a new, explicit provider or web-role proof supersedes that status:

- IONOS MX:
  - `mx00.ionos.de`
  - `mx01.ionos.de`
- IONOS SPF:
  - `include:_spf-eu.ionos.com`
- IONOS DKIM:
  - `s1-ionos._domainkey`
  - `s2-ionos._domainkey`
  - `s42582890._domainkey`, if present
- IONOS autodiscover:
  - `autodiscover` CNAME `adsredir.ionos.info`
- IONOS DomainConnect:
  - `_domainconnect` CNAME `_domainconnect.ionos.com`
- IONOS DMARC indirection:
  - `_dmarc` CNAME `dmarc.ionos.de`
- `_dep_ws_mutex`:
  - do not copy unless a current website-builder dependency is confirmed

## Resolver Note

Earlier public-resolver audits are historical evidence only. Fresh authoritative INWX and public resolver checks must run during the activation window; local or public cache staleness must be documented rather than treated as target-value truth.

## Operator Guardrails

- Do not start the INWX activation window before the offline zone manifest has been reviewed.
- Do not describe the INWX zone as already prepared unless a live provider check proves it.
- Treat all target records as offline instructions until the activation window.
- Keep IONOS active until post-cutover observation has passed.
- Do not perform registrar transfer and nameserver actions without the documented provider-specific manual sequence and stop criteria.
- Check DNSSEC immediately before transfer; if active, record manual deactivation as a required operator step.
- After completed registrar transfer, prefer immediate INWX zone correction; return to IONOS may no longer be available.
- Do not cancel IONOS during this operation.

## Remaining Operational Gaps

- The current IONOS zone export is missing from the repository or remains external.
- The exact INWX dashboard activation flow requires a live manual check.
- DNSSEC status requires a live provider check.
- The AUTH code remains outside the repository and is handled manually only.
- A human must schedule and approve the actual maintenance window.

## Secret Policy

No secrets, auth codes, transfer codes, raw headers, tokens, nonces, session cookies, SMTP passwords, or private provider data are stored in this report.
