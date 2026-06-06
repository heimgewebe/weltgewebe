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
- Offline-Zonenmanifest je Domain finalisiert und reviewed.
- INWX-Vor-DNS/Predelegation ist für diesen Ablauf nicht verfügbar.
- Provider-Dashboard-Zugänge sind im Aktivierungsfenster verfügbar.
- DNSSEC-Status ist geprüft; falls aktiv, Deaktivierung vor Transfer ist als manueller Operator-Schritt eingeplant.
- IONOS bleibt aktiv und wird nicht im selben Arbeitsgang gekündigt.
- Cloudflare ist nicht Teil dieses Cutovers.

## Rollen

- Operator (Durchführung)
- Reviewer (Prüfung der Gates)

## Sicherheitsregeln

- Keine Secrets, Auth-Codes oder Transfer-Codes in Logs oder Dokumentation.
- Rollback-Zeitfenster von mindestens 48 Stunden sicherstellen.
- `dig`-Kommandos in diesem Runbook sind Prüfbeispiele und kein Beleg für einen bereits erfolgten Cutover.

## Offline-Zonenmanifest

Das Offline-Zonenmanifest ist die manuell geprüfte, nicht-live Eingabequelle für das Aktivierungsfenster. Es enthält keine Secrets und dokumentiert je Record Domain, Name, Typ, Value/Target, TTL sofern bekannt, Zweck, Primärquelle, Pflicht vor Live-Schaltung, Testkommando nach Cutover, Fehlerrisiko und einen der Status `confirmed`, `needs live provider check` oder `do not copy`.

## Preflight

- IONOS-Zone exportiert.
- Offline-Zonenmanifest je Domain finalisiert und reviewed.
- mailbox.org Account vorbereitet.
- Brevo Account vorbereitet.
- DNS-Zielrecords gegen Provider-Dashboards geprüft.
- DNSSEC-Status geprüft und ein gegebenenfalls notwendiger manueller Deaktivierungsschritt dokumentiert.
- Rollback-Zeitfenster offen.
- IONOS noch aktiv.
- Web-Rollen geklärt oder ausdrücklich als offenes Risiko markiert.

## Dry Run

- Offline-Zonenmanifest als Tabelle und Copy-Paste-Eingabe prüfen.
- Brevo-DNS-Records nicht blind setzen; Provider-Dashboard bleibt Primärquelle.
- Runtime-Zielwerte prüfen, aber durch dieses Doku-Runbook nicht ändern.
- Stop-Kriterien und Dashboard-Verfügbarkeit mit Operator und Reviewer bestätigen.

## Abruptes INWX-Aktivierungsfenster

Das Aktivierungsfenster ist ein kontrollierter manueller Ablauf. INWX wird nicht als vorab live vorbereitete Zone angenommen. Zwischen Aktivierung und vollständiger Record-Eingabe besteht ein minimiertes, aber nicht vollständig eliminierbares Fehlerfenster.

### Zone Comparison Gate

- `@`: A/AAAA/CNAME stimmen mit der freigegebenen Web-Rollenentscheidung überein.
- `www`: CNAME/A stimmen mit dem Offline-Zonenmanifest überein.
- `api`: CNAME/A für das Backend stimmen mit dem Offline-Zonenmanifest überein.
- `login`: TXT/CNAME für Brevo Verification/DKIM stimmen mit dem Brevo-Dashboard überein.
- `_dmarc`: TXT-Record stimmt mit der jeweiligen Mail-Rolle überein.
- `MX`: mailbox.org-Prioritäten und Ziele stimmen mit dem mailbox.org-Dashboard überein.
- `DKIM`: mailbox.org- und Brevo-DKIM-Records stimmen mit den jeweiligen Provider-Dashboards überein.
- `weltweb.net` und `weltweberei.org`: No-Mail-Records und Webziele sind geprüft.

### Operator-Schritte

1. Last-Minute-Ist-Zone bei IONOS sichern.
2. Offline-Zonenmanifest final freigeben.
3. DNSSEC-Status prüfen; falls aktiv, Deaktivierung vor Transfer als manuellen Schritt dokumentieren.
4. INWX-Aktivierungsfenster starten.
5. Transfer-/Nameserver-/INWX-Aktivierungspfad je Providerlage durchführen.
6. INWX-Zone unmittelbar aus Offline-Zonenmanifest befüllen.
7. Web/API-Records setzen.
8. mailbox.org MX/SPF/DKIM/DMARC setzen.
9. Brevo `login.*` Records setzen.
10. No-Mail-Records für Neben-Domains setzen.
11. Autoritative INWX-DNS-Gates ausführen.
12. Öffentliche Resolver-Gates ausführen.
13. HTTP/Web/API-Smokes ausführen.
14. mailbox.org-Smokes ausführen.
15. Brevo/Magic-Link-Smokes ausführen.
16. Cutover-Artefakt ohne Secrets schreiben.

### Gates

- INWX authoritative DNS pass.
- Öffentliche Resolver zeigen die erwarteten Records oder die noch laufende Propagation ist nachvollziehbar dokumentiert.
- mailbox.org mail pass.
- Brevo login mail pass.
- Magic-Link pass.
- Secondary domains No-Mail pass.
- Web/API/redirect pass oder ausdrücklich akzeptiertes offenes Risiko.
- Keine Secrets in Artefakten.

## Verification

### DNS-Gates über die delegierte Auflösung

```bash
dig NS weltgewebe.net +short
dig A weltgewebe.net +short
dig A www.weltgewebe.net +short
dig A api.weltgewebe.net +short
dig MX weltgewebe.net +short
dig TXT weltgewebe.net +short
dig TXT _dmarc.weltgewebe.net +short

dig MX weltweb.net +short
dig TXT weltweb.net +short
dig TXT _dmarc.weltweb.net +short

dig MX weltweberei.org +short
dig TXT weltweberei.org +short
dig TXT _dmarc.weltweberei.org +short
```

### DNS-Gates gegen autoritative INWX-Nameserver

`<inwx-ns>` ist während des Aktivierungsfensters durch einen tatsächlich im INWX-Dashboard oder in der Delegation ausgewiesenen autoritativen Nameserver zu ersetzen; keinen Wert aus dem Repo ableiten.

```bash
dig @<inwx-ns> weltgewebe.net A
dig @<inwx-ns> www.weltgewebe.net A
dig @<inwx-ns> api.weltgewebe.net A
dig @<inwx-ns> weltgewebe.net MX
dig @<inwx-ns> weltgewebe.net TXT
dig @<inwx-ns> _dmarc.weltgewebe.net TXT
```

### DNS-Gates gegen öffentliche Resolver

```bash
dig @1.1.1.1 weltgewebe.net A
dig @8.8.8.8 weltgewebe.net A
dig @9.9.9.9 weltgewebe.net A

dig @1.1.1.1 weltgewebe.net MX
dig @8.8.8.8 weltgewebe.net MX
dig @9.9.9.9 weltgewebe.net MX
```

### HTTP/Web/API-Smokes

- `weltweberei.org`: WordPress/HTTP-Smoke vor und nach Cutover.
- `weltweb.net`: Web-/Redirect-Smoke.
- `weltgewebe.net`: Apex, `www` und `api` gegen die freigegebene Web-Rollenentscheidung prüfen.

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

### Brevo-Subdomain-DNS-Gate

Da der technische Magic-Link-Absender `noreply@login.weltgewebe.net` verwendet, müssen zusätzlich zu den Apex-Mail-Records auch die Brevo-Records der Subdomain geprüft werden. Brevo-Verification-TXT-Werte sind nach ihrer Veröffentlichung öffentliche DNS-Zielwerte; sie sind keine Auth-Codes, Transfer-Codes, API-Keys oder Provider-Zugangsdaten. Die erwarteten Werte müssen trotzdem unmittelbar vor dem Aktivierungsfenster nochmals gegen das Brevo-Dashboard geprüft werden.

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

Erwartung bei erfolgreicher späterer Betriebsprüfung:

```text
OK: Brevo subdomain DNS records present
```

Hinweis: Kein SPF-/Return-Path-Record wird hier ergänzt, solange Brevo keinen separaten Zielwert dafür ausgibt.

## Rollback

Rollback ist nur vollständig möglich, solange IONOS als steuernder DNS-/Registrar-Pfad verfügbar bleibt. Nach abgeschlossenem Registrartransfer ist der primäre Wiederherstellungspfad in der Regel die Korrektur der INWX-Zone, nicht die Rückkehr zu IONOS.

- Bei kleinen oder isolierten Recordfehlern die INWX-Zone korrigieren.
- Nameserver nur dann zurück zu IONOS stellen, wenn dieser Pfad noch verfügbar und die IONOS-Zone weiterhin intakt ist.
- Keine IONOS-Kündigung im selben Arbeitsgang.
- Keine IONOS-Zonen vor Ende des Stabilitätsfensters löschen.
- SMTP- oder Web-Runtime-Rollback ist ein separater Operator-Schritt und nicht Teil dieses Doku-PRs.

## Post-Cutover

- Mindestens 48 Stunden Beobachtungsfenster einhalten.
- Registrar, autoritative und öffentliche DNS-Antworten beobachten.
- Web/API/Redirects erneut prüfen.
- Brevo Bounces/Logs prüfen.
- mailbox.org Empfang/Versand erneut prüfen.
- Magic-Link erneut prüfen.
- IONOS erst nach erfolgreichem Registrar-/DNS-/Web-/Mail-/Magic-Link-Proof und Beobachtungsfenster überhaupt für eine Kündigungsentscheidung betrachten.
- Nach IONOS-Kündigung ist Rollback über IONOS nicht mehr verfügbar.
