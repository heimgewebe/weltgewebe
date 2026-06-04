---
id: reports.domain-provider-role-finding
title: "Finding: Aktuelle Domain- und Provider-Rollen"
doc_type: report
status: active
summary: >
  Redigierter Statusbericht zu Registrar, DNS, E-Mail und Web für
  weltgewebe.net, weltweb.net und weltweberei.org.
relations:
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/runbooks/domain-mail-cutover.md
  - type: relates_to
    target: docs/tasks/board.md
---

# Finding: Aktuelle Domain- und Provider-Rollen

> Dieser Bericht erfasst den operativen Zwischenstand (Post-Mailmigration, Pre-DNS-Cutover) ohne private Secrets.

## Provider-Basis

- **IONOS SE**: Aktueller Registrar für alle drei Domains.
- **UI-DNS**: Aktueller Nameserver-Provider (DNS-Autorität) für alle drei Domains.

## Domain-Status

### weltgewebe.net

- **Mail (Human)**: mailbox.org. (Erfolgreich migriert).
- **Mail (Technical Login)**: Brevo (`noreply@login.weltgewebe.net`). (Erfolgreich migriert).
- **Web**: Rolle und Ziel-IP (`149.233.190.131`) noch offen und vor Registrar-Cutover zu verifizieren.

### weltweb.net

- **Mail**: No-Mail public/authoritative (MX 0 ., v=spf1 -all, p=reject).
- **Web**: Zeigt derzeit IONOS-nahe Webfläche. Diese Rolle muss vor Kündigung separat entschieden werden.

### weltweberei.org

- **Mail**: No-Mail public/authoritative.
- **Web**: Aktive WordPress-/Apache-/PHP-Fläche bei IONOS. Darf nicht ohne dedizierte Web-Migrationsentscheidung gekündigt oder umgezogen werden.

## Sicherheitsvermerk

Dieser Bericht enthält absichtlich:

- Keine Secrets (SMTP-Passwörter, Auth-Codes etc.).
- Keine privaten Vertragsdaten.
- Keine sensiblen internen Routing-Details.
