---
id: runbooks.domain-mail-cutover
title: "Runbook — Domain-, Mail- und SMTP-Cutover"
doc_type: runbook
status: deprecated
summary: >
  Historisches Runbook für den abgeschlossenen Cutover von IONOS zu
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

> [!WARNING]
> Historisches Runbook.
>
> Der IONOS→INWX-Cutover für `weltgewebe.net` ist abgeschlossen.
> IONOS ist gekündigt.
> Dieses Dokument darf nicht für neue DNS-, Registrar- oder
> Provideränderungen verwendet werden.

## Geltender Zustand

- aktuelle Providerrollen:
  `docs/reports/domain-provider-role-finding.md`
- aktuelle Architektur:
  `docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md`
- öffentliche URL:
  `docs/deploy/public-app-base-url.md`
- offener Restbestand:
  `DEPLOY-DNS-001`

## Recovery-Grenze

Ein IONOS-Rollback ist nicht mehr verfügbar.
Aktuelle Fehler werden über INWX-Zonenkorrektur, DDNS-, Edge- und
Runtime-Prüfung behandelt.

Der historische Vollinhalt bleibt über die Git-Historie nachvollziehbar.
