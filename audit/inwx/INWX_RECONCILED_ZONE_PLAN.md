# INWX Reconciled Zone Plan

## Status

No live provider changes performed.

## Source Priority

1. Fresh public resolver checks
2. Final audit docs
3. Provider role snapshot
4. Older stored DNS files as historical evidence only

## Domain: weltgewebe.net

### Records to create at INWX

| Host | Type | Priority | Value | TTL | Source | Reason |
|---|---:|---:|---|---:|---|---|
| @ | A | - | 149.233.190.131 | 3600 | dig | Main App IP |
| www | A | - | 149.233.190.131 | 3600 | dig | Web Redirect |
| api | A | - | 149.233.190.131 | 3600 | dig | API Route |
| @ | MX | 10 | mxext1.mailbox.org. | 3600 | dig / Mailbox target | mailbox.org Mail |
| @ | MX | 10 | mxext2.mailbox.org. | 3600 | dig / Mailbox target | mailbox.org Mail |
| @ | MX | 20 | mxext3.mailbox.org. | 3600 | dig / Mailbox target | mailbox.org Mail |
| @ | TXT | - | v=spf1 include:mailbox.org ~all | 3600 | dig | SPF mailbox.org |
| _dmarc | TXT | - | v=DMARC1; p=none; rua=mailto:kontakt@weltgewebe.net | 3600 | dig | DMARC Human |
| MBO0001._domainkey | CNAME | - | MBO0001._domainkey.mailbox.org. | 3600 | dig / Mailbox target | mailbox.org DKIM |
| MBO0002._domainkey | CNAME | - | MBO0002._domainkey.mailbox.org. | 3600 | dig / Mailbox target | mailbox.org DKIM |
| MBO0003._domainkey | CNAME | - | MBO0003._domainkey.mailbox.org. | 3600 | dig / Mailbox target | mailbox.org DKIM |
| MBO0004._domainkey | CNAME | - | MBO0004._domainkey.mailbox.org. | 3600 | dig / Mailbox target | mailbox.org DKIM |
| login | TXT | - | brevo-code:d9e7825df780e9cce6c9fbe8d1ea5abd | 3600 | dig / Brevo target | Brevo Auth Code |
| _dmarc.login | TXT | - | v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com | 3600 | dig / Brevo target | DMARC Login |
| brevo1._domainkey.login | CNAME | - | b1.login-weltgewebe-net.dkim.brevo.com. | 3600 | dig / Brevo target | Brevo DKIM 1 |
| brevo2._domainkey.login | CNAME | - | b2.login-weltgewebe-net.dkim.brevo.com. | 3600 | dig / Brevo target | Brevo DKIM 2 |

### Records intentionally not copied (weltgewebe.net)

| Host | Type | Old value | Reason |
|---|---:|---|---|
| @ | MX | mx00.ionos.de | Replaced by mailbox.org |
| @ | MX | mx01.ionos.de | Replaced by mailbox.org |
| @ | TXT | v=spf1 include:_spf-eu.ionos.com | Replaced by mailbox.org SPF |
| _dmarc | CNAME | dmarc.ionos.de | Replaced by custom DMARC |
| s1-ionos._domainkey | CNAME | - | Old IONOS DKIM |
| s2-ionos._domainkey | CNAME | - | Old IONOS DKIM |
| s42582890._domainkey | CNAME | - | Old IONOS DKIM |
| autodiscover | CNAME | adsredir.ionos.info | IONOS service |
| _domainconnect | CNAME | _domainconnect.ionos.com | IONOS service |
| _dep_ws_mutex | TXT | - | IONOS Website Builder Mutex (check web dependency if present) |

## Domain: weltweb.net

### Records to create at INWX (weltweb.net)

| Host | Type | Priority | Value | TTL | Source | Reason |
|---|---:|---:|---|---:|---|---|
| @ | A | - | 217.160.0.145 | 3600 | dig | Web Host |
| @ | AAAA | - | 2001:8d8:100f:f000::200 | 3600 | dig | Web Host IPv6 |
| @ | MX | 0 | . | 3600 | dig | Null MX (No-Mail) |
| @ | TXT | - | v=spf1 -all | 3600 | dig | SPF reject (No-Mail) |
| _dmarc | TXT | - | v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s | 3600 | dig | DMARC reject |

### Records intentionally not copied (weltweb.net)

(Do not create www, api, mail, autodiscover for weltweb.net)

## Domain: weltweberei.org

### Records to create at INWX (weltweberei.org)

| Host | Type | Priority | Value | TTL | Source | Reason |
|---|---:|---:|---|---:|---|---|
| @ | A | - | 217.160.0.5 | 3600 | dig | Web Host |
| @ | AAAA | - | 2001:8d8:100f:f000::200 | 3600 | dig | Web Host IPv6 |
| www | A | - | 217.160.0.5 | 3600 | dig | Web Host www |
| www | AAAA | - | 2001:8d8:100f:f000::200 | 3600 | dig | Web Host IPv6 www |
| @ | MX | 0 | . | 3600 | dig | Null MX (No-Mail) |
| @ | TXT | - | v=spf1 -all | 3600 | dig | SPF reject (No-Mail) |
| _dmarc | TXT | - | v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s | 3600 | dig | DMARC reject |

## Open Decisions / Blocker

- 8.8.8.8 failed to resolve some records due to timeout, however 1.1.1.1 successfully resolved all records.
- Confirm Brevo and MBO DKIM target CNAME formats with INWX support/testing for trailing dots (`.`).
