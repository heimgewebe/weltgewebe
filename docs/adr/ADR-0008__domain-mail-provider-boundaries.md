---
id: adr.ADR-0008-domain-mail-provider-boundaries
title: "ADR-0008 — Domain-, Mail- und SMTP-Providergrenzen"
doc_type: reference
status: accepted
summary: >
  Kanonisiert die Trennung von Domain/DNS, menschlicher Mailbox und technischer
  Magic-Link-Mail für Weltgewebe.
relations:
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/runbooks/domain-mail-cutover.md
---

# ADR-0008 — Domain-, Mail- und SMTP-Providergrenzen

## Status

accepted

## Kontext

- IONOS liefert aktuell DNS/Mailbox und SMTP.

- Public Login/Magic Link hängt an SMTP.

- Heimserver ist Entwicklung/Heimruntime, nicht langfristige Produktionsplattform.

## Entscheidung

- INWX für Registrar/DNS.

- mailbox.org für menschliche Mailbox `kontakt@weltgewebe.net`.

- Brevo für technische Magic-Link-Mail `login@weltgewebe.net`.

- App-/Produktionshosting bleibt entkoppelt.

## Nicht-Ziele

- keine Secrets im Repo.

- kein Live-Cutover durch diesen PR.

- keine Terraform-/Provider-Automation.

## Konsequenzen

- IONOS darf erst nach erfolgreichen Gates gekündigt werden.

- `kontakt@` und `login@` dürfen nicht vermischt werden.

- `APP_BASE_URL` muss im öffentlichen Betrieb `https://weltgewebe.net` sein.

## Alternativen

- netcup All-in-one.

- Cloudflare + Mailprovider.

- IONOS reduziert behalten.

## Begründung

- Trennung der Lebenszyklen: Domainbesitz, menschliche Mail, technische Login-Mail, App-Hosting.
