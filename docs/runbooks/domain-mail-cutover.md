---
id: runbooks.domain-mail-cutover
title: "Runbook — Domain-, Mail- und SMTP-Cutover"
doc_type: runbook
status: active
summary: >
  Operatives Runbook für den kontrollierten Cutover von IONOS zu
  INWX, mailbox.org und Brevo.
relations:
  - type: relates_to
    target: docs/runbooks/README.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/adr/ADR-0008__domain-mail-provider-boundaries.md
---

# Runbook — Domain-, Mail- und SMTP-Cutover

## Voraussetzungen

- Zugriff auf INWX, mailbox.org, Brevo und IONOS Dashboards.

- Zugriff auf die Produktions-Runtime (`.env`).

- Kenntnis der Test-Gates und Rollback-Verfahren.

## Rollen

- Operator (Durchführung)

- Reviewer (Prüfung der Gates)

## Sicherheitsregeln

- Keine Secrets in Logs oder Dokumentation.

- Rollback-Zeitfenster von mindestens 48 Stunden sicherstellen.

## Preflight

1. Alle notwendigen Provider-Accounts sind angelegt und bestätigt.
2. Ziel-DNS-Records liegen in INWX bereit, aber sind noch nicht aktiv.

## Cutover

1. DNS-Nameserver auf INWX umstellen.
2. MX-Records für mailbox.org aktivieren.
3. Brevo DNS-Verifikation durchführen.
4. Runtime (`.env`) auf Brevo SMTP aktualisieren.

## Test-Gates

### DNS-Gates

```bash
dig weltgewebe.net A
dig api.weltgewebe.net A
dig weltgewebe.net MX
dig weltgewebe.net TXT
dig _dmarc.weltgewebe.net TXT

```

### Runtime-Prüfung

```bash
docker inspect weltgewebe-api-1 \
  --format "{{range .Config.Env}}{{println .}}{{end}}" \
| grep -E "^(APP_BASE_URL|AUTH_|SMTP_|WEBAUTHN_|RUST_LOG)=" \
| sed -E "s/^(SMTP_PASS|.*SECRET|.*PASSWORD|.*PRIVATE_KEY|.*API_KEY|.*TOKEN)=.*/\1=<REDACTED>/"

```

### Erwartung nach Ziel-Cutover

```text
APP_BASE_URL=https://weltgewebe.net
SMTP_HOST=<Brevo SMTP Host>
SMTP_PORT=587
SMTP_USER=<Brevo SMTP User>
SMTP_FROM=login@weltgewebe.net
AUTH_PUBLIC_LOGIN=1
AUTH_LOG_MAGIC_TOKEN=0

```

### Mail-Gates

- Mail an `kontakt@weltgewebe.net` kommt bei mailbox.org an.

- Antwort von `kontakt@weltgewebe.net` kommt extern an.

- Brevo-Testmail von `login@weltgewebe.net` kommt an.

- Headerprüfung: SPF pass, DKIM pass, DMARC nicht fail.

- Weltgewebe Magic-Link kommt an.

- Magic-Link zeigt auf `https://weltgewebe.net`.

- Login erzeugt Session.

## Rollback

- IONOS-Mail/DNS nicht kündigen, solange Rollback benötigt werden kann.

- Bei Mailausfall: MX temporär zurück auf IONOS, falls IONOS-Mail noch aktiv ist.

- Bei SMTP-Ausfall: Weltgewebe SMTP temporär zurück auf alten Provider, falls Credentials noch gültig sind.

- Bei Web/API-Ausfall: A/CNAME-Records gegen letzte bekannte IONOS-Zone vergleichen.

## Post-Cutover

- IONOS-Kündigung erst nach erfolgreichen Gates.
