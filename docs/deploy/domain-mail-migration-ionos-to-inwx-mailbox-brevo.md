---
id: deploy.domain-mail-migration-ionos-inwx-mailbox-brevo
title: "Domain-/Mail-Migration: IONOS zu INWX + mailbox.org + Brevo"
doc_type: reference
status: active
summary: >
  Zielarchitektur und Migrationsplan für Domain, DNS, Kontaktmail und
  technische Magic-Link-Mail.
relations:
  - type: relates_to
    target: docs/deploy/README.md
  - type: relates_to
    target: docs/deploy/DRIFT_POLICY.md
  - type: relates_to
    target: docs/deployment.md
  - type: relates_to
    target: docs/deployment_governance.md
  - type: relates_to
    target: docs/runbooks/domain-mail-cutover.md
  - type: relates_to
    target: docs/adr/ADR-0008__domain-mail-provider-boundaries.md
---

# Domain-/Mail-Migration: IONOS zu INWX + mailbox.org + Brevo

## 1. Zweck

Dieser Plan beschreibt die Zielarchitektur und den Migrationspfad für die Trennung von Registrar, menschlicher Mailbox und technischer Magic-Link-Mail.

## 2. Zielarchitektur

```text
INWX:
  Registrar und DNS für:
  - weltgewebe.net
  - weltweb.net
  - weltweberei.org

mailbox.org:
  - kontakt@weltgewebe.net
  - admin@weltgewebe.net optional als Alias
  - optional temporäre Weiterleitung an externe Recovery-Mail

Brevo:
  - login@weltgewebe.net
  - optional noreply@weltgewebe.net
  - technische Magic-Link-Mail

Weltgewebe Runtime:
  APP_BASE_URL=https://weltgewebe.net
  SMTP_HOST=<Brevo SMTP Host>
  SMTP_PORT=587
  SMTP_USER=<Brevo SMTP User>
  SMTP_PASS=<Secret Store>
  SMTP_FROM=login@weltgewebe.net

```

## 3. Aktueller redigierter Ist-Zustand

```env
APP_BASE_URL=https://weltgewebe.home.arpa
AUTH_PUBLIC_LOGIN=1
AUTH_AUTO_PROVISION=1
AUTH_ALLOW_EMAILS=
AUTH_RL_EMAIL_PER_MIN=2
AUTH_RL_EMAIL_PER_HOUR=10
AUTH_RL_IP_PER_MIN=5
AUTH_RL_IP_PER_HOUR=30
SMTP_HOST=smtp.ionos.de
SMTP_PORT=587
SMTP_USER=kontakt@weltgewebe.net
SMTP_FROM=kontakt@weltgewebe.net
SMTP_PASS=<gesetzt, nicht dokumentieren>
WEB_UPSTREAM_HOST=weltgewebe.home.arpa
WEB_UPSTREAM_URL=https://weltgewebe.home.arpa

```

## 4. Providerrollen

- INWX: DNS-Verwaltung.

- mailbox.org: Verwaltung menschlicher Kommunikation.

- Brevo: Versand transaktionaler E-Mails (Login/Magic-Link).

## 5. DNS-Zielbild

Für `weltgewebe.net`:

```text
@      A/CNAME   <aktueller oder späterer Produktionshost>
api    A/CNAME   <aktueller oder späterer API-/Produktionshost>
www    A/CNAME   <Landingpage oder Redirect-Ziel>

MX     @         <mailbox.org MX>
TXT    @         <mailbox.org SPF>
DKIM             <mailbox.org DKIM laut Dashboard>

login  TXT/CNAME <Brevo Verification/DKIM/SPF laut Dashboard>

_dmarc TXT       "v=DMARC1; p=none; rua=mailto:kontakt@weltgewebe.net"

```

*Hinweis:* Provider-Dashboard-Werte sind Primärquelle. Keine auswendig geratenen SPF/DKIM-Werte.

Für `weltweb.net` und `weltweberei.org`:

- Klären, ob Mail benötigt wird.

- Falls keine Mail benötigt wird, defensives SPF/DMARC-Ziel dokumentieren, aber nicht live setzen.

- Dienen als Redirect-/Landing-Domains.

## 6. Runtime-Zielbild

Applikation und Mail-Infrastruktur müssen konform zur Zielarchitektur in der Produktions-Runtime konfiguriert werden.

## 7. Migrationsphasen

1. DNS-Übernahme durch INWX.
2. Einrichtung mailbox.org und Umstellung der MX-Einträge.
3. Einrichtung Brevo für Transaktionsmails.
4. Aktualisierung der Runtime-Umgebungsvariablen.

## 8. Test-Gates

- IONOS darf erst gekündigt werden, wenn:
  - INWX-DNS-Zone vollständig gesetzt und geprüft ist
  - mailbox.org Empfang und Versand für `kontakt@weltgewebe.net` funktionieren
  - Brevo-Domain/Subdomain verifiziert ist
  - Brevo-Testmail SPF/DKIM/DMARC besteht oder mindestens nicht fehlschlägt
  - Weltgewebe Magic-Link-Mail über Brevo funktioniert
  - live-env nach Recreate Brevo-Werte zeigt
  - Rollback-Pfad noch offen ist

## 9. Rollback-Prinzip

Sollte ein Migrationsschritt scheitern, müssen DNS und Einstellungen auf die letzten funktionierenden Werte (IONOS) zurückgerollt werden können, solange der IONOS-Account aktiv ist.

## 10. Nicht-Ziele / Verbote

- Keine Speicherung von Provider-Secrets im Repository.

- Keine Live-DNS-Änderungen als Teil von Dokumentations-PRs.

## 11. Offene Belege

- DNS-Propagation verifizieren.

- Brevo Deliverability prüfen.
