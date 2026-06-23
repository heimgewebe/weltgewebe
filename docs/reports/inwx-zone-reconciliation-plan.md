---
id: reports.inwx-zone-reconciliation-plan
title: "INWX Zone Reconciliation Plan"
doc_type: report
status: deprecated
lifecycle: planning
lifecycle_state: archived
owner_task: DEPLOY-DNS-001
summary: >
  Archivierter Plan für den INWX-Cutover. Dies ist keine operative Anleitung.
relations:
  - type: relates_to
    target: docs/tasks/board.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/runbooks/domain-mail-cutover.md
  - type: relates_to
    target: docs/reports/domain-provider-role-finding.md
---

# INWX Zone Reconciliation Plan

> [!WARNING]
> Historische Planung – archiviert.
>
> Dieses Dokument beschrieb die Vorbereitung des inzwischen abgeschlossenen
> IONOS-zu-INWX-Cutovers für `weltgewebe.net`.
>
> Es ist keine operative Anleitung und darf nicht als Copy-Paste-Quelle
> für DNS-, Registrar- oder Provideränderungen verwendet werden.

## Ergebnis

- `weltgewebe.net` nutzt INWX und dynamisches DDNS.
- IONOS ist gekündigt.
- Die damaligen statischen IP-, IONOS- und Rollbackannahmen sind nicht mehr gültig.
- `weltweb.net` und `weltweberei.org` bleiben unter `DEPLOY-DNS-001` offen.

## Aktuelle Wahrheitsquellen

- `docs/reports/domain-provider-role-finding.md`
- `docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md`
- `docs/tasks/board.md`

Der historische Vollinhalt bleibt über die Git-Historie nachvollziehbar.
