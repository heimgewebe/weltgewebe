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
SMTP_FROM=noreply@login.weltgewebe.net
AUTH_PUBLIC_LOGIN=1
AUTH_LOG_MAGIC_TOKEN=0
```

### Mail-Gates

- Mail an `kontakt@weltgewebe.net` kommt bei mailbox.org an.
- Antwort von `kontakt@weltgewebe.net` kommt extern an.
- Brevo-Testmail von `noreply@login.weltgewebe.net` kommt an.
- Headerprüfung: SPF pass, DKIM pass, DMARC nicht fail.
- Weltgewebe Magic-Link kommt an.
- Magic-Link zeigt auf `https://weltgewebe.net`.
- Login erzeugt Session.

## Rollback

- MX zurück auf IONOS, falls IONOS aktiv
- SMTP zurück auf IONOS, falls Credentials aktiv
- A/CNAME zurück auf letzte bekannte funktionierende Zone

## Post-Cutover

- 48 Stunden Beobachtungsfenster einhalten.
- Brevo Bounces/Logs prüfen.
- mailbox.org Empfang/Versand erneut prüfen.
- IONOS erst nach erfolgreichen Gates und Beobachtungsfenster kündigen.
- Nach IONOS-Kündigung ist Rollback über IONOS nicht mehr verfügbar.

### Brevo-Subdomain-DNS-Gate

Da der technische Magic-Link-Absender `noreply@login.weltgewebe.net` verwendet, müssen zusätzlich zu den Apex-Mail-Records auch die Brevo-Records der Subdomain geprüft werden.

```bash
set -euo pipefail

CHECK="$(mktemp)"

{
  echo "== TXT login.weltgewebe.net =="
  dig +short TXT login.weltgewebe.net
  echo

  echo "== CNAME brevo1._domainkey.login.weltgewebe.net =="
  dig +short CNAME brevo1._domainkey.login.weltgewebe.net
  echo

  echo "== CNAME brevo2._domainkey.login.weltgewebe.net =="
  dig +short CNAME brevo2._domainkey.login.weltgewebe.net
  echo

  echo "== TXT _dmarc.login.weltgewebe.net =="
  dig +short TXT _dmarc.login.weltgewebe.net
  echo
} | tee "$CHECK"

grep -F "brevo-code:d9e7825df780e9cce6c9fbe8d1ea5abd" "$CHECK"
grep -F "b1.login-weltgewebe-net.dkim.brevo.com" "$CHECK"
grep -F "b2.login-weltgewebe-net.dkim.brevo.com" "$CHECK"
grep -F "v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com" "$CHECK"

echo "OK: Brevo subdomain DNS records present"
```

Erwartung:

```text
OK: Brevo subdomain DNS records present
```

Hinweis: Kein SPF-/Return-Path-Record wird hier ergänzt, solange Brevo keinen separaten Zielwert dafür ausgibt.
