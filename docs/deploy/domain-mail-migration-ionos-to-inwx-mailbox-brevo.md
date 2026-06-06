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

## 6a. Kanonische Cutover-Artefakte

### Offline-Zonenmanifest

Das Offline-Zonenmanifest ist ein nicht-live geschaltetes, manuell geprüftes Cutover-Artefakt. Es enthält keine Secrets und umfasst für jeden Eintrag Domain, Record-Name, Record-Type, Value/Target, TTL sofern bekannt, Zweck, Primärquelle, Pflicht vor Live-Schaltung, Testkommando nach Cutover, Risiko bei Fehler und den Status `confirmed`, `needs live provider check` oder `do not copy`.

```markdown
| Domain | Name | Type | Value/Target | TTL | Zweck | Primärquelle | Pflicht vor Live-Schaltung | Testkommando nach Cutover | Risiko bei Fehler | Status |
|---|---|---|---|---|---|---|---|---|---|---|
```

### Abruptes INWX-Aktivierungsfenster

Das abrupte INWX-Aktivierungsfenster ist ein kontrolliertes manuelles Zeitfenster: Der Registrar-/Nameserver-/INWX-Aktivierungspfad wird manuell gestartet, die INWX-Zone unmittelbar aus dem Offline-Zonenmanifest befüllt, anschließend werden autoritative INWX- und öffentliche Resolver-Gates sowie Web/API-, mailbox.org- und Brevo-DNS/Subdomain-Smokes ausgeführt. Der finale Magic-Link-Proof folgt erst nach dem Runtime-Cutover auf Brevo in Phase 6 und wird in Phase 7 erzeugt. Recordfehler werden sofort bei INWX korrigiert. Eine Rückkehr zu IONOS ist nur ein begrenzter Pfad, solange IONOS noch als steuernder DNS-/Registrar-Pfad verfügbar ist. Cloudflare ist nicht Teil dieses Cutovers.

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

### Phase 2 — Offline-Zonenmanifest entwerfen

- **Ziel**: vollständige, copy-paste-fähige Zielzone ohne Live-Wirkung.
- **Aktionen**:
  - aktuelle IONOS-Zonen exportieren/sichern.
  - Provider-Dashboard-Werte von mailbox.org und Brevo als Primärquelle notieren.
  - Zielrecords für `weltgewebe.net`, `weltweb.net` und `weltweberei.org` als Offline-Zonenmanifest dokumentieren.
  - Records markieren als: Web/API, mailbox.org, Brevo, No-Mail, nicht kopieren.
  - Vier-Augen-Review durchführen.
- **Gate**: Offline-Zonenmanifest vollständig, geprüft und ohne Secrets.
- **Rollback-Hinweis**: Keine Live-Veränderung, daher kein technischer Rollback nötig.

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

### Phase 5a — Offline-Zielzone finalisieren

- **Ziel**: letzte freigegebene Eingabequelle für das abrupte INWX-Aktivierungsfenster.
- **Aktionen**:
  - Last-Minute-Abgleich gegen aktuelle IONOS-Zone.
  - mailbox.org- und Brevo-Records erneut gegen Provider-Dashboards prüfen.
  - DNSSEC-Status für `weltgewebe.net`, `weltweb.net` und `weltweberei.org` prüfen; falls aktiv, DNSSEC bei IONOS manuell deaktivieren und die Entfernung des jeweiligen Parent-DS-Records über öffentliche Resolver verifizieren.
  - Verbleibenden alten IONOS-DS ohne passend signierte INWX-Zone domain-spezifisch als Blocker markieren; für diese Domain dann keinen Nameserver-, Transfer- oder INWX-Aktivierungsschritt starten.
  - Zielrecords als Copy-Paste-Blöcke oder Tabelle finalisieren.
  - Stop-Kriterien prüfen.
- **Gate**: Manifest ist final, Reviewer hat freigegeben, IONOS bleibt aktiv und der DS-Zustand ist für jede Domain im Cutover-Scope geprüft. Bei zuvor aktivem DNSSEC ist die jeweilige Parent-DS-Entfernung verifiziert; andernfalls bleibt die betroffene Domain blockiert.
- **Rollback-Hinweis**: Bis hier keine Live-DNS-Änderung.

### Phase 5b — Abruptes INWX-Aktivierungsfenster

- **Ziel**: INWX übernimmt DNS/Registrar-Rolle; die Zone wird unmittelbar aus dem Offline-Zonenmanifest befüllt.
- **Aktionen**:
  - Transfer-/Nameserver-/INWX-Aktivierungspfad manuell starten.
  - INWX-Zone unmittelbar aus dem Offline-Zonenmanifest befüllen.
  - Web/API-Records setzen.
  - mailbox.org MX/SPF/DKIM/DMARC setzen.
  - Brevo `login.*` Records setzen.
  - No-Mail-Records für Neben-Domains setzen.
  - autoritative INWX-DNS-Gates ausführen.
  - öffentliche Resolver-Gates ausführen.
  - HTTP/Web/API-Smokes ausführen.
  - mailbox.org-Smokes ausführen.
  - Brevo-DNS/Subdomain-Gates ausführen; noch keinen finalen Magic-Link-Proof behaupten.
- **Gate**:
  - autoritative INWX-DNS-Antworten korrekt.
  - öffentliche Resolver zeigen erwartete Records oder Propagation ist nachvollziehbar dokumentiert.
  - Web/API-Smokes laufen.
  - mailbox.org Empfang/Versand läuft.
  - Brevo-DNS/Subdomain-Records sind korrekt; dies ist noch kein Runtime- oder Magic-Link-Proof via Brevo.
  - Neben-Domains erfüllen No-Mail/Web-Gates oder sind als offenes Risiko dokumentiert.
- **Rollback-Hinweis**:
  - Bei kleinen Recordfehlern: INWX-Zone korrigieren.
  - Bei strukturellem Fehler und noch möglicher Rückkehr: Nameserver zurück auf IONOS.
  - Nach abgeschlossenem Registrartransfer kann Rollback faktisch INWX-Zonenkorrektur statt Rückkehr zu IONOS bedeuten.

### Phase 5c — Registrar-Transfer zu INWX

- **Ziel**: Domain bei INWX registrieren.
- **Aktionen**:
  - Registrar-Transfer einleiten. Der genaue Ablauf hängt von den Provider-Restriktionen ab:
    - **Pfad A**: IONOS erlaubt Nameserver-Wechsel zu INWX vor dem Registrar-Transfer. Auch dann wird die INWX-Zone erst im abrupten Aktivierungsfenster aus dem Offline-Zonenmanifest befüllt; Phase 5b ist vor Abschluss von Phase 5c durchzuführen.
    - **Pfad B**: Registrar-Transfer zu INWX muss zuerst erfolgen. In diesem Fall wird die INWX-Zone erst im abrupten Aktivierungsfenster aus dem Offline-Zonenmanifest befüllt. Zwischen Aktivierung und vollständiger Record-Eingabe besteht ein minimiertes, aber nicht eliminierbares Fehlerfenster.
  - Transfer-Lock/Auth-Code nur manuell handhaben, nicht im Repo speichern.
- **Gate**: Ablaufdaten beachtet (weltgewebe.net und weltweb.net bis 2026-06-19, weltweberei.org bis 2027-05-26). Keine Domain kurz vor Ablauf ohne expliziten Transferplan riskieren.
- **Rollback-Hinweis**: Transfer nur abbrechen, solange der konkrete Provider-Flow dies technisch und vertraglich noch zulässt. Nach gestarteter oder abgeschlossener Transferphase sind primär die sofortige Korrektur der INWX-Zone und, falls erforderlich, der Provider-Support zu nutzen; eine Rückkehr zu IONOS darf nicht als sicher verfügbar angenommen werden.

### Phase 5d — IONOS Retention Policy — deferred decision

- **Ziel**: IONOS unverändert aktiv halten und die spätere Kündigungs-/Reduktionsentscheidung erst nach Phase 8 freigeben.
- **Aktionen**: Diese Entscheidung noch nicht in Phase 5 ausführen. IONOS erst nach abgeschlossenem Phase-6-Runtime-Cutover, Phase-7-Magic-Link-Proof via Brevo und Phase-8-Beobachtungsfenster kündigen oder reduzieren.
- **Gate**:
  - Registrar bei INWX bestätigt.
  - DNS bei INWX autoritativ bestätigt.
  - Webhosting/Redirects entweder migriert oder bewusst anderweitig gesichert.
  - mailbox.org-Mailgates und Brevo-DNS/Subdomain-Gates nach INWX-DNS grün.
  - Phase 6 ist abgeschlossen: Die neu gestartete Live-Runtime zeigt redigiert die erwarteten Brevo-SMTP-Werte.
  - Phase 7 ist abgeschlossen: Ein erst nach diesem Runtime-Cutover erzeugter Magic-Link wurde über Brevo zugestellt und erzeugt erfolgreich eine Session.
  - Web/API-Smokes nach INWX-DNS grün oder offenes Risiko ausdrücklich akzeptiert.
  - Phase 8 ist abgeschlossen: Mindestens 48 Stunden Beobachtung ohne kritische DNS-, Web-, Mail- oder Magic-Link-Fehler.
  - Rollback-/Notfallpfad dokumentiert.
- **Rollback-Hinweis**: Nach abgeschlossenem Registrartransfer kann Wiederherstellung bereits primär INWX-Zonenkorrektur bedeuten; nach IONOS-Kündigung ist kein IONOS-Rollback mehr möglich.

### Phase 6 — Runtime-Cutover auf Brevo

- **Ziel**: Weltgewebe API nutzt Brevo statt IONOS.
- **Aktionen**: `.env` auf Brevo-SMTP ändern, API-Container neu starten und anschließend die effektive Live-Umgebung redigiert prüfen.
- **Gate**: Der neu gestartete API-Container zeigt `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER` und `SMTP_FROM` mit den erwarteten Brevo-Werten; Secret-Werte bleiben redigiert. Vor diesem Gate ist kein Magic-Link-Test ein Brevo-Runtime-Proof.
- **Rollback-Hinweis**: SMTP-Werte zurück auf IONOS ändern.

### Phase 7 — Post-Runtime-Cutover Magic-Link-Proof via Brevo

- **Ziel**: Nach bewiesenem Phase-6-Runtime-Cutover belegen, dass die Weltgewebe API Magic-Link-Mail tatsächlich über Brevo versendet und Benutzer sich anmelden können.
- **Aktionen**: Erst nach dem Live-Env-Gate aus Phase 6 einen neuen Login-Prozess über `https://weltgewebe.net` initiieren, Brevo-Zustellung und Mail-Header prüfen, Magic Link klicken.
- **Gate**: Der nach dem Runtime-Cutover erzeugte Magic-Link wurde über Brevo zugestellt, zeigt auf `https://weltgewebe.net` und erzeugt erfolgreich eine Session.
- **Rollback-Hinweis**: Siehe Phase 5 & 6.

### Phase 8 — Beobachtungsfenster

- **Ziel**: Stabilität gewährleisten.
- **Aktionen**: Log-Analyse, Fehler-Monitoring, Bounce-Checks in Brevo.
- **Gate**: Mindestens 48 Stunden ohne kritische Registrar-, DNS-, Web/API-, Versand-, Empfangs- oder Magic-Link-Probleme.
- **Rollback-Hinweis**: Bei Recordfehlern die INWX-Zone korrigieren. Rückkehr zu IONOS nur prüfen, solange der steuernde IONOS-DNS-/Registrar-Pfad noch verfügbar ist.

### Phase 9 — IONOS kündigen

- **Ziel**: Alten Provider abschalten.
- **Aktionen**: Erst nach menschlicher Entscheidung und vollständig bewiesenem Registrar-/DNS-/Web-/Mail-/Magic-Link-Proof über eine IONOS-Kündigung entscheiden.
- **Gate**: Phase 8 mit mindestens 48 Stunden Beobachtung erfolgreich absolviert; alle Kündigungsabhängigkeiten sind ausdrücklich freigegeben.
- **Rollback-Hinweis**: Nach IONOS-Kündigung ist kein IONOS-Rollback mehr möglich; nach Registrartransfer kann der Wiederherstellungspfad schon vorher faktisch INWX-Zonenkorrektur bedeuten.

## 8. Test-Gates

- IONOS darf erst gekündigt werden, wenn:
  - INWX-DNS-Zone vollständig gesetzt und geprüft ist
  - mailbox.org Empfang und Versand für `kontakt@weltgewebe.net` funktionieren (proved)
  - Brevo-Domain/Subdomain verifiziert ist (proved)
  - Brevo-Testmail SPF/DKIM/DMARC besteht oder mindestens nicht fehlschlägt (proved)
  - live-env nach Restart/Recreate die erwarteten Brevo-SMTP-Werte redigiert zeigt (proved)
  - erst der danach neu erzeugte Weltgewebe Magic-Link über Brevo zugestellt wird und erfolgreich eine Session erzeugt (proved)
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
- Runtime nach Restart/Recreate zeigt redigiert die erwarteten Brevo-SMTP-Werte. (im Cutover erneut zu belegen)
- Ein erst danach erzeugter Weltgewebe Magic-Link wird über Brevo verschickt. (im Cutover erneut zu belegen)
- Dieser Magic-Link zeigt auf `https://weltgewebe.net` und erzeugt eine Session. (im Cutover erneut zu belegen)
- AUTH_LOG_MAGIC_TOKEN=0. (erledigt/proved)
