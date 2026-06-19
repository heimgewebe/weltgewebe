---
id: deploy.public-app-base-url
title: Public APP_BASE_URL Contract
doc_type: reference
status: active
summary: Produktionsvertrag für öffentliche Magic-Link-URLs und interne Web-Upstreams.
relations:
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: infra/compose/compose.prod.override.yml
---
# Öffentliche APP_BASE_URL im Produktionsbetrieb

Stand: 2026-06-19

Die produktive `APP_BASE_URL` ist `https://weltgewebe.net`. Sie wird für öffentlich klickbare URLs verwendet, insbesondere für Magic Links.

Die internen Proxy-Ziele bleiben davon getrennt:

- `WEB_UPSTREAM_HOST=weltgewebe.home.arpa`
- `WEB_UPSTREAM_URL=https://weltgewebe.home.arpa`

Diese Trennung ist absichtlich. `APP_BASE_URL` beschreibt die öffentliche Adresse der Anwendung; `WEB_UPSTREAM_*` beschreibt den internen Zielweg hinter Caddy. Ein öffentlicher Upstream-Wert kann eine Proxy-Schleife oder falsches internes Routing erzeugen.

## Durchsetzung

`scripts/guard/prod-public-base-url-guard.sh` rendert `compose.prod.yml` und `compose.prod.override.yml` mit einer synthetischen Env-Datei und prüft:

- öffentliche `APP_BASE_URL` im API-Service;
- aktivierten öffentlichen Login;
- deaktiviertes Magic-Token-Logging;
- interne `WEB_UPSTREAM_*`-Werte im API- und Caddy-Service.

Die zugehörige Fixture-Suite liegt unter `scripts/tests/test_prod_public_base_url_guard.sh`. CI führt sowohl die Fixtures als auch den Guard gegen den echten Repository-Checkout aus.

## Betriebsgrenze

Diese Repo-Änderung führt keinen Live-Deploy, keine DNS-Änderung und keine Mailprovider-Änderung aus. Nach dem Merge bleibt ein kontrollierter Abgleich des Server-Checkouts und der laufenden Runtime erforderlich.
