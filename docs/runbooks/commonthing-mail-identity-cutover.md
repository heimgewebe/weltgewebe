---
id: runbooks.commonthing-mail-identity-cutover
title: "Runbook — commonThing-Mailidentität umstellen"
doc_type: runbook
status: active
summary: >
  Fail-closed Ablauf für kontakt@commonthing.net bei mailbox.org und
  noreply@login.commonthing.net bei Brevo mit erhaltener Legacy-Kompatibilität.
relations:
  - type: relates_to
    target: docs/runbooks/README.md
  - type: relates_to
    target: docs/deploy/commonthing.naming.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/adr/ADR-0008__domain-mail-provider-boundaries.md
---

# Runbook — commonThing-Mailidentität umstellen

## Ziel

Kanonisch werden:

- menschliche Kontaktadresse: `kontakt@commonthing.net`,
- technischer Login-Absender: `noreply@login.commonthing.net`.

Die bisherigen Identitäten bleiben während der Beobachtungsphase erhalten.
<!-- commonthing-naming: legacy -->
`kontakt@weltgewebe.net` darf nicht abgeschaltet werden.
<!-- commonthing-naming: legacy -->
`noreply@login.weltgewebe.net` darf nicht abgeschaltet werden.

## Grundregel

```text
Provider anlegen → exakte DNS-Vorgaben lesen → DNS ergänzen → autoritativ lesen
→ Provider verifizieren → reale Zustellung beweisen → Runtime/Public Surface umschalten
→ beobachten → Legacy später separat bewerten
```

Ein späterer Schritt darf keinen früheren Beweis ersetzen. Insbesondere beweist ein
Repository-Merge weder Domainverifikation noch Mailzustellung.

## 1. Frischen Ausgangszustand lesen

Vor jeder Mutation prüfen:

- aktuellen `origin/main` und offene PRs/Writer,
- laufende Produktionsrevision,
- nicht geheime SMTP-Werte (`SMTP_HOST`, `SMTP_PORT`, `SMTP_AUTH`, `SMTP_FROM`),
- autoritative MX/TXT/CNAME-Antworten für `commonthing.net` und `login.commonthing.net`,
- aktuellen Providerstatus bei mailbox.org und Brevo.

SMTP-Benutzername, Passwort, API-Schlüssel oder Session-Cookies werden nicht in
Logs, PRs oder Operatorausgaben kopiert.

## 2. mailbox.org vorbereiten

1. `commonthing.net` im bestehenden mailbox.org-Konto als zusätzliche Domain bzw.
   Aliasdomain anlegen.
2. `kontakt@commonthing.net` auf dieselbe menschliche Mailbox binden.
3. Die von mailbox.org **für diese Domain tatsächlich ausgegebenen** MX-, SPF-,
   DKIM- und gegebenenfalls Verifikationswerte erfassen.
4. Noch keine bisherigen Domain-/Aliaswerte entfernen.

Keine Werte aus der alten Domain kopieren, wenn mailbox.org für die neue Domain
abweichende Werte ausgibt.

## 3. Brevo vorbereiten

1. `login.commonthing.net` als technische Senderdomain anlegen.
2. Die von Brevo tatsächlich ausgegebenen Domainverifikations-, DKIM-, SPF- und
   gegebenenfalls DMARC-Vorgaben erfassen.
3. `noreply@login.commonthing.net` als zulässigen Absender bestätigen.
4. Die bestehende Legacy-Senderdomain nicht entfernen.

Provider-generierte Tokens, Selektoren und Recordwerte werden niemals geraten.

## 4. DNS bei INWX ergänzen

Nur die in Schritt 2 und 3 frisch gelesenen Werte eintragen. Dabei:

- Web-A-Records von `commonthing.net` nicht verändern,
- keine vorhandenen Legacy-Mailrecords löschen,
- für `login.commonthing.net` keinen MX-Record erfinden, wenn Brevo keinen verlangt,
- bestehende Wildcard-/Webverträge nicht als Mailbeweis behandeln.

Nach jeder Mutation zuerst bei allen autoritativen INWX-Nameservern zurücklesen.
Bei unklarem Providerergebnis keine blinde Wiederholung.

## 5. Provider-Verifikation

Erst fortfahren, wenn beide Provider den neuen Zustand positiv bestätigen:

- mailbox.org akzeptiert `commonthing.net` und `kontakt@commonthing.net`,
- Brevo akzeptiert `login.commonthing.net` und den neuen technischen Absender,
- DKIM/SPF/weitere geforderte Authentifizierungsrecords sind beim Provider grün.

### Belegter Zwischenstand — 29. August 2026

Provider- und DNS-Vorbereitung sind abgeschlossen:

- mailbox.org führt `kontakt@commonthing.net` als externen Alias; der Legacy-Alias
  bleibt parallel bestehen;
- `commonthing.net` liefert die mailbox.org-MX-Records, SPF, vier DKIM-CNAMEs und
  DMARC auf allen drei autoritativen INWX-Nameservern sowie über öffentliche
  Resolver;
- Brevo führt `login.commonthing.net` als **Authentifiziert**; die Legacy-Senderdomain
  bleibt parallel authentifiziert;
- Brevo-Code, beide DKIM-CNAMEs und `_dmarc.login.commonthing.net` sind autoritativ
  und über öffentliche Resolver verifiziert;
- ein isolierter SMTP-Preflight mit den bestehenden produktiven Brevo-Credentials
  wurde mit `From: noreply@login.commonthing.net` vom Relay akzeptiert.

Der letzte Punkt beweist **Relay-Akzeptanz, nicht endgültige Zustellung im Postfach**.
Die produktive Runtime verwendet daher weiterhin den Legacy-Absender, bis Inbox-
und Magic-Link-Ende-zu-Ende-Beweise vorliegen.

## 6. Repository und Runtime umschalten

Der Phase-3-PR setzt die öffentlichen Kontaktflächen und den kanonischen
`SMTP_FROM`-Zielwert auf commonThing. Vor Produktionsaktivierung muss der
Readiness-Check mit dem exakten Zielwert bestehen:

```bash
python3 scripts/ops/check_public_login_smtp_readiness.py \
  --env-file /etc/weltgewebe/weltgewebe.env \
  --production-public-login \
  --expected-smtp-from noreply@login.commonthing.net
```

Beim Runtime-Cutover wird nur der notwendige Absenderwert geändert; bestehende
SMTP-Credentials werden nicht unnötig rotiert oder offengelegt.

## 7. Ende-zu-Ende-Beweis

Nach dem Deployment:

1. Runtime-Readback zeigt `SMTP_FROM=noreply@login.commonthing.net`.
2. Ein Magic-Link wird an einen ausdrücklich kontrollierten Testempfänger gesendet.
3. Der empfangene Absender ist die commonThing-Adresse und der Link zeigt auf
   `https://commonthing.net`.
4. `kontakt@commonthing.net` wird durch kontrollierten Inbound- und Outbound-Test
   belegt.
5. Impressum und Datenschutz zeigen die neue Kontaktadresse.
6. Die Legacy-Adressen bleiben weiterhin erreichbar bzw. als definierter
   Kompatibilitätsweg verfügbar.

Ohne kontrollierten Testempfänger wird kein externer Testversand improvisiert.

## 8. Rollback

Wenn der technische Absender nach der Umschaltung nicht zuverlässig zustellt, wird
`SMTP_FROM` auf den zuletzt belegten Legacy-Absender zurückgesetzt und der
Runtimezustand erneut gelesen. Provider- und DNS-Neueinträge müssen für die Diagnose
nicht vorschnell gelöscht werden.

Die öffentliche Kontaktadresse wird nur dann live geschaltet, wenn mailbox.org sie
vorher nachweislich angenommen hat; dadurch soll für den menschlichen Kontakt kein
DNS-bedingter Rollback nötig werden.

## 9. Abschlusskriterium

Phase 3 ist erst terminal, wenn Providerstatus, autoritatives DNS, Runtime-Absender,
realer Magic-Link-Mailpfad, menschliche Kontaktmail und öffentliche Kontaktflächen
übereinstimmen. Die Entfernung der Legacy-Identitäten gehört ausdrücklich nicht zu
dieser Phase.
