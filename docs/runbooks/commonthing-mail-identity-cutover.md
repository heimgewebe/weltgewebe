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
  wurde mit `From: noreply@login.commonthing.net` vom Relay akzeptiert und die
  kontrollierte Nachricht ist im Postfach hinter `kontakt@commonthing.net`
  angekommen.

Damit sind Brevo-Relay und der menschliche Inbound-Pfad belegt. Das ersetzt weder
den menschlichen Outbound-Beweis noch den anwendungsseitigen Magic-Link-Beweis.
Die produktive Runtime verwendet daher weiterhin den Legacy-Absender.

## 6. Zustellung vor dem Cutover beweisen

Der in ADR-0008 festgelegte Zustellbeweis ist ein **Vorgänger** des Repository-,
Runtime- und Public-Surface-Cutovers. Die folgenden Gates müssen deshalb vor
Schritt 7 abgeschlossen sein:

1. Eine kontrollierte Nachricht an `kontakt@commonthing.net` kommt in der
   vorgesehenen mailbox.org-Mailbox an.
2. Eine kontrollierte Nachricht wird aus mailbox.org **mit**
   `From: kontakt@commonthing.net` an einen unabhängigen kontrollierten Empfänger
   gesendet und dort empfangen. Ein bloßer Alias-Eintrag oder lokaler
   mailbox.org-zu-mailbox.org-Test reicht dafür nicht aus.
3. Der aktuelle Release-Kandidat erzeugt außerhalb der produktiven Runtime einen
   echten Magic-Link mit `APP_BASE_URL=https://commonthing.net` und
   `SMTP_FROM=noreply@login.commonthing.net`. Dafür dürfen die bestehenden
   Brevo-Credentials verwendet werden, aber keine produktive Runtime-Konfiguration
   und kein produktiver Persistenzzustand verändert werden.
4. Der kontrollierte Empfänger erhält diese Magic-Link-Mail; sichtbarer Absender
   und Link-Host stimmen mit den commonThing-Zielwerten überein.

Erst wenn alle vier Gates positiv belegt sind, darf der PR gemergt und der
Produktions-Cutover gestartet werden. Ohne kontrollierten Testempfänger wird kein
externer Testversand improvisiert.

## 7. Repository, kanonische Env und Runtime umschalten

Sind alle vier Vorab-Zustellgates aus Schritt 6 positiv belegt, wird zuerst der
finale PR-Head vollständig reviewed und durch CI geprüft. Erst danach wird der PR
über den kanonischen Captain-Pfad gemergt. Der Merge allein ändert die produktive
Env-Datei noch nicht.

Nach autoritativ bestätigtem Merge wird `/etc/weltgewebe/weltgewebe.env` mit dem
bestehenden Reconciler auf die gemeinsame kanonische Wahrheit gebracht. Dabei wird
`APP_BASE_URL` **nicht** aus `/opt/weltgewebe/.env` übernommen, sondern immer auf
`https://commonthing.net` kanonisiert. Der explizite Mail-Cutover erlaubt nur den
neuen oder den Legacy-Absender.

Zuerst das `0700`-Backup-Verzeichnis sicherstellen und einen Dry-run mit dem
commonThing-Absender erzeugen:

```bash
sudo -n install -d -m 0700 -o root -g root /var/backups/weltgewebe/env
cd /opt/weltgewebe
PREVIEW="$(sudo -n python3 scripts/ops/reconcile_public_login_smtp_env.py \
  --source /opt/weltgewebe/.env \
  --destination /etc/weltgewebe/weltgewebe.env \
  --backup-dir /var/backups/weltgewebe/env \
  --smtp-from-override noreply@login.commonthing.net \
  --json)"
printf '%s\n' "$PREVIEW"
PLAN_SHA256="$(printf '%s\n' "$PREVIEW" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["plan_sha256"])')"
```

Dann ausschließlich exakt diesen Plan anwenden; derselbe Override gehört zum
Planvertrag und muss beim Apply erneut angegeben werden:

```bash
sudo -n python3 scripts/ops/reconcile_public_login_smtp_env.py \
  --source /opt/weltgewebe/.env \
  --destination /etc/weltgewebe/weltgewebe.env \
  --backup-dir /var/backups/weltgewebe/env \
  --smtp-from-override noreply@login.commonthing.net \
  --apply \
  --expected-plan-sha256 "$PLAN_SHA256" \
  --json
```

Danach geheimnisarm zurücklesen: `APP_BASE_URL=https://commonthing.net` und
`SMTP_FROM=noreply@login.commonthing.net`; SMTP-Credentials werden nicht ausgegeben.
Erst dann muss der Readiness-Check gegen die kanonische VPS-Env bestehen:

```bash
sudo -n python3 scripts/ops/check_public_login_smtp_readiness.py \
  --env-file /etc/weltgewebe/weltgewebe.env \
  --production-public-login \
  --expected-smtp-from noreply@login.commonthing.net
```

Nur bei PASS wird der exakte Merge-Commit über den kanonischen
Produktions-Reconciler/Deploypfad ausgerollt. Nach dem Deployment werden aktive
Revision, API-Gesundheit, `APP_BASE_URL`, `SMTP_FROM`, Public-Login und
Runtimeintegrität frisch zurückgelesen. SMTP-Credentials müssen vorhanden sein,
werden aber niemals ausgegeben.

## 8. Produktionsakzeptanz nach dem Cutover

Nach Deployment und Runtime-Umschaltung werden die kritischen Beweise nochmals am
tatsächlich aktiven Produktionspfad wiederholt:

1. Runtime-Readback zeigt `SMTP_FROM=noreply@login.commonthing.net`.
2. Ein realer Produktions-Magic-Link wird an einen ausdrücklich kontrollierten
   Testempfänger gesendet.
3. Der empfangene Absender ist die commonThing-Adresse und der Link zeigt auf
   `https://commonthing.net`.
4. Impressum und Datenschutz zeigen `kontakt@commonthing.net`.
5. Der zuvor belegte menschliche Inbound-/Outbound-Pfad bleibt erreichbar.
6. Die Legacy-Adressen bleiben weiterhin erreichbar bzw. als definierter
   Kompatibilitätsweg verfügbar.

Ein erfolgreicher Vorabtest aus Schritt 6 erlaubt keinen Verzicht auf diese
Post-Cutover-Abnahme.

## 9. Rollback

Wenn nach dem Cutover ein **belegter technischer Mailfehler** auftritt, werden die
neuen DNS- oder Provider-Einträge nicht gelöscht. Stattdessen wird ausschließlich
`SMTP_FROM` über denselben revisionssicheren Reconciler auf
`noreply@login.weltgewebe.net` zurückgestellt. `APP_BASE_URL` bleibt dabei
kanonisch `https://commonthing.net`; die abgeschlossene Webidentität darf durch
einen Mail-Rollback nicht zurückgedreht werden.

Der Rollback verwendet erneut Dry-run → exakten `plan_sha256` → Apply, diesmal mit
`--smtp-from-override noreply@login.weltgewebe.net`. Danach werden die kanonische
Env-Datei und die tatsächlich aktive Runtime frisch zurückgelesen und über den
normalen Produktionspfad wiederhergestellt. Ein Rollback wird nur aufgrund eines
konkret belegten Fehlers ausgelöst, nicht vorsorglich.

Die öffentliche Kontaktadresse wird nur dann live geschaltet, wenn ihr menschlicher
Inbound- **und Outbound-Pfad** vorher nach Schritt 6 belegt wurden. Dadurch ist die
öffentliche Rechts-/Kontaktfläche nicht von einem ungeprüften Mailpfad abhängig.

## 10. Abschlusskriterium

Phase 3 ist erst terminal, wenn Providerstatus, autoritatives DNS, Vorabzustellung,
Runtime-Absender, realer Produktions-Magic-Link-Mailpfad, menschliche Kontaktmail
und öffentliche Kontaktflächen übereinstimmen. Die Entfernung der
Legacy-Identitäten gehört ausdrücklich nicht zu dieser Phase.
