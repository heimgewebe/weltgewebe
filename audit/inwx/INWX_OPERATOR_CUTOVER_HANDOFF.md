# INWX Operator Cutover Handoff

## Status

Prepared only. No live provider changes performed.

## Preconditions

- INWX account available.
- INWX 2FA active.
- Recovery mail is not under weltgewebe.net.
- IONOS remains active.
- Auth codes are not stored in audit/repo.
- Reconciled zone plan reviewed.
- Web risks acknowledged.

## Phase A — INWX Zones Prepare

1. Create DNS zone for weltgewebe.net.
2. Create DNS zone for weltweb.net.
3. Create DNS zone for weltweberei.org.
4. Enter records from INWX_RECONCILED_ZONE_PLAN.md.
5. Do not copy old IONOS mail/service records.
   *Note: INWX UI may normalize trailing dots on CNAME targets. Do not treat UI normalization as value drift if DNS output matches.*

## Phase B — Pre-Delegation Checks

- Check INWX zone values in UI/export.
- If INWX supports querying unpublished authoritative zone, query it.
- Otherwise use manual table comparison.

## Phase C — Nameserver Cutover

- Change nameservers from UI-DNS to INWX nameservers only after Zone Plan review.
- Do not perform registrar transfer in same step unless explicitly decided.

## Phase D — Post-Cutover Gates

### DNS Gates

- weltgewebe.net A/www/api
- weltgewebe.net mailbox.org MX/SPF/DKIM/DMARC
- login.weltgewebe.net Brevo TXT/DKIM/DMARC
- weltweb.net No-Mail
- weltweberei.org No-Mail

### Web Gates

- `https://weltgewebe.net`
- `https://www.weltgewebe.net`
- `https://api.weltgewebe.net` health or expected response
- `https://weltweb.net` expected response
- `https://weltweberei.org` WordPress page
- `https://www.weltweberei.org` redirect/page

### Mail Gates

- `kontakt@weltgewebe.net` inbound
- `kontakt@weltgewebe.net` outbound
- `noreply@login.weltgewebe.net` magic-link mail
- magic-link login creates session

## Rollback

- If DNS records are wrong but INWX authoritative: fix INWX zone.
- If delegation is broken: restore IONOS UI-DNS nameservers while IONOS remains active.
- Do not cancel IONOS in the same operation.
- Do not delete IONOS zone before observation window.

## Stop Criteria

Stop immediately if:

- Brevo records are missing or ambiguous.
- mailbox.org DKIM records are missing or ambiguous.
- WordPress/web records are unclear.
- INWX UI does not support Null MX as expected.
- Any Auth-Code or provider secret would need to be stored.
