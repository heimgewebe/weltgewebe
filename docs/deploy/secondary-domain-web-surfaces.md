---
id: deploy.secondary-domain-web-surfaces
title: Sekundäre Domain-Webflächen
doc_type: reference
status: active
summary: >
  Definiert das Weltweberei-Webartefakt und den Handoff an den
  externen Heimserver-Edge für weltweb.net und weltweberei.org.
relations:
  - type: relates_to
    target: docs/deploy/README.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/reports/domain-provider-role-finding.md
  - type: relates_to
    target: docs/tasks/board.md
---

# Sekundäre Domain-Webflächen

Dieses Dokument beschreibt das repo-seitige Webartefakt für `weltweberei.org`
und den Handoff-Vertrag an den externen Heimserver-Edge für `weltweb.net`
(permanenter Redirect) und `weltweberei.org` (statische Informationsfläche).

Es ist ein **Artefakt- und Handoff-Vertrag**, kein Beleg für öffentliche
Einsatzbereitschaft. Der tatsächliche öffentliche Cutover ist Folgearbeit im
Repo `heimgewebe/heimserver` und anschließende Operatorarbeit.

## 1. Eigentumsgrenzen

```text
heimgewebe/weltgewebe
- besitzt Inhalt und Build-Artefakt der Informationsseite;
- beweist den statischen Buildpfad;
- verändert nicht die aktive öffentliche Frontdoor.

heimgewebe/heimserver
- besitzt das operative Edge-Template;
- muss den aktiven Edge-Zustand vor einem Patch read-only prüfen;
- implementiert später Redirect und statische Domainroute;
- synchronisiert erst nach Review zum Host.

INWX
- besitzt Registrar- und DNS-Rolle;
- wird nicht durch diesen PR verändert.
```

## 2. Belegte Artefaktkette

```text
Quelle:
apps/web/static/weltweberei/

Build:
apps/web/build/weltweberei/

Host-Mount:
 /opt/weltgewebe/apps/web/build

Edge-Mount:
 /srv/weltgewebe-web

Vorgesehener Site-Root:
 /srv/weltgewebe-web/weltweberei
```

Der Quell-zu-Build-Schritt ist deterministisch belegt: `apps/web/static/`
wird durch den normalen Web-Build (`CI=true pnpm -C apps/web build`)
unverändert nach `apps/web/build/` kopiert. Der Browser-Proof
(`apps/web/tests/weltweberei-information.spec.ts`) prüft das Artefakt auf
Inhalt, Ressourcenfreiheit, Layout und Tastaturzugänglichkeit.

## 3. Vorgesehener späterer Edge-Vertrag

Die folgenden Snippets sind ausschließlich ein **Handoff-Vertrag** für den
späteren Heimserver-PR. Sie sind kein laufender Zustand, kein
Deploymentbeweis, keine Provideranweisung und kein DNS-Nachweis.

Für `weltweb.net`:

```caddyfile
http://weltweb.net {
    redir https://weltgewebe.net{uri} 308
}

https://weltweb.net {
    redir https://weltgewebe.net{uri} 308
}
```

Für `weltweberei.org`:

```caddyfile
http://weltweberei.org {
    redir https://weltweberei.org{uri} 308
}

https://weltweberei.org {
    root * /srv/weltgewebe-web/weltweberei
    encode zstd gzip

    header {
        Content-Security-Policy "default-src 'none'; style-src 'self'; img-src 'self' data:; script-src 'none'; connect-src 'none'; font-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "no-referrer"
        X-Frame-Options "DENY"
        Cache-Control "no-cache, must-revalidate"
    }

    file_server
}
```

## 4. Explizit offene Punkte

- aktives `/opt/heimgewebe/edge/Caddyfile` noch nicht als Target-Proof gelesen;
- aktiver Edge-Compose-Stand noch nicht belegt;
- aktiver Mount noch nicht live geprüft;
- Heimserver-PR noch nicht umgesetzt;
- Caddy noch nicht validiert oder neu geladen;
- INWX-Delegation noch nicht geändert;
- öffentlicher HTTPS-Endzustand noch nicht belegt;
- No-Mail-Records noch nicht öffentlich und autoritativ belegt;
- `www.weltweb.net` nicht entschieden;
- `www.weltweberei.org` nicht entschieden;
- DNSSEC-/Parent-DS-Zustand nicht geprüft;
- rechtliche Veröffentlichungsvoraussetzungen der eigenständigen Domain noch
  nicht menschlich freigegeben.

## 5. Rechtliches Publikationsgate

```text
Dieser Slice erstellt ein technisches Informationsartefakt.
Er entscheidet nicht über Anbieterkennzeichnung, Datenschutzseite
oder andere rechtliche Veröffentlichungspflichten.

Vor der öffentlichen Aktivierung von weltweberei.org muss menschlich
entschieden und belegt werden, welche rechtlichen Informationen
erforderlich sind und wo sie bereitgestellt werden.

Der Coding-Agent darf dafür keine Privatdaten oder Rechtstexte erfinden.
```

## 6. Verbotener Claim

```text
infra/caddy/Caddyfile.prod ist für das aktuelle Heimserver-Deployment
nicht als aktive öffentliche Frontdoor belegt und wird in diesem Slice
nicht verändert.
```
