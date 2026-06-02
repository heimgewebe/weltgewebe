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

- IONOS-Zone exportiert
- mailbox.org Account vorbereitet
- Brevo Account vorbereitet
- DNS-Zielrecords aus Provider-Dashboards notiert
- Rollback-Zeitfenster offen
- IONOS noch aktiv

## Dry Run

- Ziel-DNS als Tabelle prüfen
- Brevo-DNS-Records noch nicht blind setzen
- Runtime-Zielwerte vorbereitet, aber nicht aktiv

## Cutover

- DNS/Nameserver nur nach Preflight-Gates ändern
- mailbox.org MX aktivieren
- Brevo-DNS-Verifikation aktivieren
- Runtime auf Brevo-SMTP ändern
- Dienste kontrolliert neu erzeugen / deployen

## Verification

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
| awk -F= '
  $1 ~ /^(APP_BASE_URL|AUTH_|SMTP_|WEBAUTHN_|RUST_LOG|WEB_UPSTREAM_)/ {
    if ($1 ~ /(PASS|PASSWORD|SECRET|TOKEN|PRIVATE_KEY|API_KEY)/) {
      print $1"=<REDACTED>"
    } else {
      print
    }
  }
'
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

- mailbox.org Empfang/Versand
- Brevo-Testmail
- Headerprüfung
- Weltgewebe Magic-Link
- Session-Proof

## Rollback

- MX zurück auf IONOS, falls IONOS aktiv
- SMTP zurück auf IONOS, falls Credentials aktiv
- A/CNAME zurück auf letzte bekannte funktionierende Zone
