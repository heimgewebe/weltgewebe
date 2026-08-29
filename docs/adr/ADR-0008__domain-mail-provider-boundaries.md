---
id: adr.ADR-0008-domain-mail-provider-boundaries
title: "ADR-0008 — Domain-, Mail- und SMTP-Providergrenzen"
doc_type: reference
status: accepted
summary: >
  Kanonisiert die Trennung von Domain/DNS, menschlicher Mailbox und technischer
  Magic-Link-Mail für commonThing einschließlich der Legacy-Kompatibilität.
relations:
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/runbooks/commonthing-mail-identity-cutover.md
---

# ADR-0008 — Domain-, Mail- und SMTP-Providergrenzen

## Status

accepted

## Kontext

- INWX ist Registrar und autoritativer DNS-Provider.
- commonThing ist die kanonische öffentliche Produktidentität.
- Public Login/Magic Link hängt an einem verifizierten technischen SMTP-Absender.
- Menschliche Kontaktmail und technische Login-Mail besitzen getrennte Providerrollen.

## Entscheidung

- INWX bleibt für Registrar/DNS zuständig.
- mailbox.org trägt die kanonische menschliche Mailbox `kontakt@commonthing.net`.
- Brevo trägt den kanonischen technischen Magic-Link-Absender
  `noreply@login.commonthing.net`.
- Die früheren Mailidentitäten bleiben während der Migration als
  Kompatibilitätsweg erhalten und werden nicht im selben Schritt entfernt.
<!-- commonthing-naming: legacy -->
- `kontakt@weltgewebe.net` bleibt Alias bzw. Zustellweg zur menschlichen Mailbox.
<!-- commonthing-naming: legacy -->
- `noreply@login.weltgewebe.net` bleibt Legacy-Absender, bis der neue Brevo-Pfad
  Ende-zu-Ende belegt ist, und danach nur solange der Kompatibilitätsvertrag gilt.
- App-/Produktionshosting bleibt von beiden Mailprovidern entkoppelt.

## Explizite Rollentrennung

- `kontakt@commonthing.net` = menschliche Kontakt-/Adminadresse bei mailbox.org.
- `noreply@login.commonthing.net` = technischer Magic-Link-Absender über Brevo.
- Ein menschliches Postfach darf nicht als automatischer Login-Absender verwendet
  werden; der technische Absender ist kein Support-Postfach.

## Cutover-Vertrag

Die Reihenfolge ist fail-closed:

1. neue Identität beim jeweiligen Provider anlegen,
2. nur die vom Provider tatsächlich ausgegebenen DNS-Records bei INWX ergänzen,
3. autoritative DNS-Antworten und Provider-Verifikation zurücklesen,
4. technische Zustellung bzw. menschliche Inbound/Outbound-Mail beweisen,
5. erst danach Repository, Runtime und öffentliche Kontaktflächen kanonisch umschalten,
6. Legacy-Adressen beobachten und erst in einer separaten späteren Entscheidung abbauen.

Repository-Konfiguration oder DNS-Einträge allein beweisen keine Zustellbarkeit.

## Nicht-Ziele

- keine Secrets im Repo,
- keine erfundenen DKIM-, SPF- oder Provider-Verifikationswerte,
- keine Entfernung der Legacy-Adressen im Phase-3-Cutover,
- keine Kopplung von Webhosting und Mailprovider.

## Konsequenzen

- `SMTP_FROM` muss nach dem technischen Cutover exakt
  `noreply@login.commonthing.net` sein.
- `APP_BASE_URL` bleibt im öffentlichen Betrieb `https://commonthing.net`.
- Impressum und Datenschutz dürfen `kontakt@commonthing.net` erst live ausweisen,
  wenn die Adresse bei mailbox.org nachweislich zustellbar ist.
- Ein fehlgeschlagener Provider- oder DNS-Readback stoppt den Cutover; er wird nicht
  durch einen Repository-Merge überstimmt.

## Weitergeltende angrenzende Domainverträge

Die Identitätsmigration ändert nicht automatisch die Rollen anderer Domains:

- `weltweb.net` und `weltweberei.org` bleiben No-Mail-Domains, sofern das nicht in
  einer separaten Entscheidung geändert wird.
- Die Web-/WordPress-Nutzung von `weltweberei.org` bleibt ein eigener Fall und wird
  nicht durch diesen Mail-Cutover mitverändert.
- `home.arpa` bleibt ausschließlich Heim-/Entwicklungsziel und ist keine öffentliche
  Produktions- oder Mailidentität.

Damit werden weiterhin gültige Grenzen aus der früheren Fassung dieser ADR bewahrt,
ohne deren inzwischen überholten IONOS-Betriebszustand als aktuelle Wahrheit
fortzuschreiben.

## Alternativen

- ein einzelner All-in-one-Provider: verworfen wegen unnötiger Kopplung der
  Lebenszyklen von Domainbesitz, menschlicher Mail, Login-Mail und App-Hosting.
- Weiterbetrieb ausschließlich unter der früheren Produktidentität: verworfen,
  weil commonThing bereits die kanonische Web- und API-Identität ist.

## Begründung

Die Trennung hält Domainbesitz, menschliche Kommunikation, technische
Authentifizierung und App-Hosting unabhängig migrierbar und rückrollbar.
