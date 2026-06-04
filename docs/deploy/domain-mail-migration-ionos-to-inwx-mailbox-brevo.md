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
  - `kontakt@weltgewebe.net`
  - admin@weltgewebe.net optional als Alias
  - optional temporäre Weiterleitung an externe Recovery-Mail

Brevo:
  - noreply@login.weltgewebe.net
  - optional noreply@weltgewebe.net
  - technische Magic-Link-Mail

Weltgewebe Runtime:
  APP_BASE_URL=https://weltgewebe.net
  SMTP_HOST=<Brevo SMTP Host>
  SMTP_PORT=587
  SMTP_USER=<Brevo SMTP User>
  SMTP_PASS=<Secret Store>
  SMTP_FROM=noreply@login.weltgewebe.net
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

### Ist-Zustand nach Mailmigration

- **weltgewebe.net**:
  - Human Mail: mailbox.org, pass.
  - Technical Login Mail: Brevo, pass.
  - Registrar/DNS: IONOS SE / UI-DNS, noch offen für INWX.
  - Web A record: 149.233.190.131, Providerrolle noch prüfen.

- **weltweb.net**:
  - Registrar/DNS: IONOS SE / UI-DNS.
  - Mail: No-Mail public/authoritative pass.
  - Web: IONOS-nahe Webfläche, gesondert zu entscheiden.

- **weltweberei.org**:
  - Registrar/DNS: IONOS SE / UI-DNS.
  - Mail: No-Mail public/authoritative pass.
  - Web: aktive WordPress-/Apache-/PHP-Fläche; nicht ohne Web-Migrationsentscheidung anfassen.

## 3a. Bestätigte Preflight-Belege

- `AUTH_LOG_MAGIC_TOKEN=0` wurde lokal am laufenden Heimserver-Container bestätigt.
- Der laufende API-Container nutzt aktuell IONOS-SMTP für Magic-Link-Mail.
- `kontakt@weltgewebe.net` hat im IONOS-Bestand nur vernachlässigbaren lokalen Mailbestand. Die Migration des Mailarchivs ist daher niedriges Risiko.
- Kritisch ist nicht die IMAP-Menge, sondern die bisherige Weiterleitung von `kontakt@weltgewebe.net`; sie muss im Zielzustand bewusst neu entschieden, nachgebaut oder entfernt werden.

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

### Phase 0 — Bestand sichern

- **Ziel**: Vollständige Dokumentation der aktuellen DNS- und E-Mail-Konfiguration.
- **Aktionen**: DNS-Zonen-Exporte anlegen, MX-Prioritäten notieren, IONOS aktiv lassen.
- **Gate**: Vollständige IONOS-Zone gesichert.
- **Rollback-Hinweis**: Keine Live-Veränderungen, daher kein Rollback nötig.

### Phase 1 — Zielkonten vorbereiten

- **Ziel**: Zielkonten anlegen und bereitstellen.
- **Aktionen**: Accounts bei INWX, mailbox.org und Brevo einrichten.
- **Gate**: Konten sind zugreifbar.
- **Rollback-Hinweis**: Konten können wieder gelöscht werden.

### Phase 2 — DNS-Zielzone entwerfen

- **Ziel**: Blaupause der neuen DNS-Zone.
- **Aktionen**: INWX-Einträge im Dashboard vorbereiten (aber noch nicht als Nameserver eintragen).
- **Gate**: Ziel-DNS-Tabelle fertig und geprüft.
- **Rollback-Hinweis**: Einträge können im Dashboard wieder verworfen werden.

### Phase 3 — mailbox.org vorbereiten und testen

- **Ziel**: `kontakt@weltgewebe.net` ist empfangsbereit.
- **Aktionen**: Mailbox anlegen und (falls möglich) Test-Routing prüfen.
- **Gate**: mailbox.org Account ist bereit.
- **Rollback-Hinweis**: Rückkehr zur IONOS-Mailbox.

### Phase 4 — Brevo vorbereiten und testen

- **Ziel**: `noreply@login.weltgewebe.net` ist sendebereit.
- **Aktionen**: Brevo-Dashboard-Verifikationscodes abrufen, ggf. anlegen.
- **Gate**: Brevo-Verifikationsdaten liegen vor.
- **Rollback-Hinweis**: Keine Live-Auswirkung auf bisherigen Versand.

### Phase 5a — INWX DNS-Zone vorbereiten

- **Ziel**: Blaupause der neuen DNS-Zone.
- **Aktionen**:
  - vollständige IONOS-Zonen exportieren/sichern.
  - INWX-Zone mit allen aktuellen Records vorbereiten.
  - Mailrecords exakt übernehmen:
    - weltgewebe.net MX/SPF/DKIM/DMARC für mailbox.org.
    - login.weltgewebe.net Brevo TXT/DMARC/DKIM/CNAME.
    - weltweb.net und weltweberei.org No-Mail.
  - Webrecords exakt übernehmen:
    - A/AAAA/CNAME für apex/www/api.
    - keine Web-Interpretation ohne Beweis.
  - Zonenvergleich dokumentieren.
- **Gate**: Ziel-DNS-Tabelle fertig und geprüft.
- **Rollback-Hinweis**: Einträge können im Dashboard wieder verworfen werden.

### Phase 5b — INWX Nameserver-Cutover

- **Ziel**: INWX übernimmt die aktive DNS-Auflösung.
- **Aktionen**:
  - Nameserver-Cutover zu INWX.
- **Gate**:
  - DNS-Propagation abgeschlossen. `dig` gegen autoritative INWX-Nameserver und öffentliche Resolver erfolgreich.
  - Test: weltgewebe.net A / www / api, MX/TXT/DMARC, login.weltgewebe.net Brevo records, secondary domains No-Mail.
  - HTTP checks für Website/WordPress/Redirects.
  - Magic-Link-Smoke.
  - kontakt@ inbound/outbound optional erneut prüfen.
- **Rollback-Hinweis**: Nameserver zurück auf IONOS stellen.

### Phase 5c — Registrar-Transfer zu INWX

- **Ziel**: Domain bei INWX registrieren.
- **Aktionen**:
  - Registrar-Transfer einleiten. Der genaue Ablauf hängt von den Provider-Restriktionen ab:
    - **Pfad A**: IONOS erlaubt Nameserver-Wechsel zu INWX vor dem Registrar-Transfer (bevorzugt). In diesem Fall ist Phase 5b vor Phase 5c abzuschließen.
    - **Pfad B**: Registrar-Transfer zu INWX muss zuerst erfolgen, die DNS-Zone ist bei INWX vorbereitet, Nameserver werden danach aktiviert.
  - Transfer-Lock/Auth-Code nur manuell handhaben, nicht im Repo speichern.
- **Gate**: Ablaufdaten beachtet (weltgewebe.net und weltweb.net bis 2026-06-19, weltweberei.org bis 2027-05-26). Keine Domain kurz vor Ablauf ohne expliziten Transferplan riskieren.
- **Rollback-Hinweis**: Transfer abbrechen, falls unvorhergesehene Probleme auftreten.

### Phase 5d — IONOS Retention/Kündigungsentscheidung

- **Ziel**: Alten Provider geordnet abschalten.
- **Aktionen**: IONOS erst kündigen/reduzieren, wenn bestimmte Bedingungen erfüllt sind.
- **Gate**:
  - Registrar bei INWX bestätigt.
  - DNS bei INWX autoritativ bestätigt.
  - Webhosting/Redirects entweder migriert oder bewusst anderweitig gesichert.
  - Mailgates nach INWX-DNS weiter grün.
  - Rollback-/Notfallpfad dokumentiert.
- **Rollback-Hinweis**: Nach Kündigung kein Rollback mehr möglich.

### Phase 6 — Runtime-Cutover auf Brevo

- **Ziel**: Weltgewebe API nutzt Brevo statt IONOS.
- **Aktionen**: `.env` auf Brevo-SMTP ändern, API-Container neustarten.
- **Gate**: Runtime-Test zeigt Brevo-Werte ohne Errors.
- **Rollback-Hinweis**: SMTP-Werte zurück auf IONOS ändern.

### Phase 7 — Magic-Link-Proof

- **Ziel**: Benutzer können sich einloggen.
- **Aktionen**: Login-Prozess über `https://weltgewebe.net` initiieren, E-Mail-Empfang checken, Magic Link klicken.
- **Gate**: Erfolgreiche Session-Erstellung.
- **Rollback-Hinweis**: Siehe Phase 5 & 6.

### Phase 8 — Beobachtungsfenster

- **Ziel**: Stabilität gewährleisten.
- **Aktionen**: Log-Analyse, Fehler-Monitoring, Bounce-Checks in Brevo.
- **Gate**: Mindestens 48 Stunden ohne Versand-/Empfangsprobleme.
- **Rollback-Hinweis**: Falls Fehler auftreten, Rollback zu IONOS prüfen.

### Phase 9 — IONOS kündigen

- **Ziel**: Alten Provider abschalten.
- **Aktionen**: IONOS-Vertrag kündigen.
- **Gate**: Phase 8 erfolgreich absolviert.
- **Rollback-Hinweis**: Nach Kündigung kein Rollback mehr möglich.

## 8. Test-Gates

- IONOS darf erst gekündigt werden, wenn:
  - INWX-DNS-Zone vollständig gesetzt und geprüft ist
  - mailbox.org Empfang und Versand für `kontakt@weltgewebe.net` funktionieren (proved)
  - Brevo-Domain/Subdomain verifiziert ist (proved)
  - Brevo-Testmail SPF/DKIM/DMARC besteht oder mindestens nicht fehlschlägt (proved)
  - Weltgewebe Magic-Link-Mail über Brevo funktioniert (proved)
  - live-env nach Recreate Brevo-Werte zeigt (proved)
  - Secondary domains No-Mail public/authoritative (proved)
  - Rollback-Pfad noch offen ist

## 9. Rollback-Prinzip

Sollte ein Migrationsschritt scheitern, müssen DNS und Einstellungen auf die letzten funktionierenden Werte (IONOS) zurückgerollt werden können, solange der IONOS-Account aktiv ist.

## 10. Nicht-Ziele / Verbote

- Keine Speicherung von Provider-Secrets im Repository.
- Keine Live-DNS-Änderungen als Teil von Dokumentations-PRs.

## 11. Offene Belege

- Vollständige IONOS-DNS-Zone für weltgewebe.net, weltweb.net, weltweberei.org.
- MX-Prioritäten und TTLs gesichert.
- mailbox.org Empfang und Versand für `kontakt@weltgewebe.net` getestet. (erledigt/proved)
- Brevo Sending-Domain/Subdomain verifiziert. (erledigt/proved)
- Brevo SPF/DKIM/DMARC im Test geprüft. (erledigt/proved)
- Entscheidung zur bisherigen Weiterleitung von `kontakt@weltgewebe.net` getroffen.
- Runtime nach Recreate zeigt Brevo-SMTP-Werte. (erledigt/proved)
- Weltgewebe Magic-Link wird über Brevo verschickt. (erledigt/proved)
- Magic-Link zeigt auf `https://weltgewebe.net`. (erledigt/proved)
- Login erzeugt Session. (erledigt/proved)
- AUTH_LOG_MAGIC_TOKEN=0. (erledigt/proved)
