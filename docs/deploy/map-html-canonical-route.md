---
id: deploy.map-html-canonical-route
title: Canonical Map Route Contract
doc_type: runbook
status: active
summary: Produktionsvertrag für die einmalige Kanonisierung der veralteten Kartenadresse /map.html nach /map.
relations:
  - type: relates_to
    target: infra/caddy/Caddyfile.vps
  - type: relates_to
    target: apps/web/Caddyfile.container
  - type: relates_to
    target: docs/deploy/merge-to-live.md
---
# Kanonische Kartenroute `/map`

Stand: 2026-08-06

## Anlass

Die SvelteKit-Ausgabe enthält ein statisches Artefakt `map.html`, obwohl die öffentliche Kartenroute `/map` lautet. Wird das Artefakt direkt unter `/map.html` ausgeliefert, startet es die Anwendung mit einer nichtkanonischen Adresse. Der Client versucht anschließend, dieselbe Adresse erneut zu laden. In einem Produktionsbrowser wurde dadurch eine selbstverstärkende Dokument-Neuladeschleife beobachtet: 99 Hauptdokument-Navigationen in ungefähr acht Sekunden, jeweils HTTP 200 auf `/map.html`, ohne Titel, Karten-Canvas oder Marker.

Dieser Fehler wird am HTTP-Rand abgefangen. Die veraltete Adresse darf die SvelteKit-Anwendung nicht mehr erreichen.

## Produktionsvertrag

Die produktive VPS-Konfiguration `infra/caddy/Caddyfile.vps` und der statische Containerpfad `apps/web/Caddyfile.container` müssen exakt den Pfad `/map.html` abfangen und mit HTTP 308 nach `/map` umleiten.

Die Query-Zeichenkette bleibt unverändert erhalten:

| Anfrage | Erwartetes Ergebnis |
| --- | --- |
| `/map.html` | `308` mit `Location: /map` |
| `/map.html?node=abc&mode=focus` | `308` mit `Location: /map?node=abc&mode=focus` |
| `/map` | normale Kartenanwendung, kein Redirect |
| andere `.html`-Pfade | unveränderte bestehende Routingsemantik |

Caddy verwendet dafür den optionalen Query-Platzhalter `{?query}`. Er fügt das Fragezeichen nur ein, wenn die Anfrage tatsächlich eine Query enthält. Die Query darf nicht durch eine allgemeine Zeichenersetzung verändert werden; ein kodierter Wert wie `next=%2Fmap.html` muss bytegetreu erhalten bleiben.

Die Redirectregel muss vor dem statischen `try_files`- beziehungsweise SPA-Fallback ausgewertet werden. Andernfalls kann `map.html` erneut als vorhandene Datei ausgeliefert werden und die Schleife wieder auftreten.

## Vor dem Merge

Auf dem exakten PR-Head sind mindestens folgende Prüfungen erforderlich:

1. Beide Caddy-Dateien lassen sich mit `caddy adapt` oder `caddy validate` fehlerfrei verarbeiten.
2. Die fokussierten Verträge in `scripts/ci/tests/test_vps_http_route_smoke_docs.py` und `scripts/ci/tests/test_static_app_caddy_csp_adapted_contract.py` sind grün.
3. Ein lokaler Caddy-Lauf belegt sowohl den querylosen als auch den querytragenden Redirect.
4. `/map` bleibt direkt erreichbar.
5. Der Deploy-Drift-Guard erkennt diese Dokumentation zusammen mit der Änderung an `infra/caddy/Caddyfile.vps`.

Ein erfolgreicher Preview-Deploy allein ist kein Produktionsbeweis, da Vercel oder Cloudflare nicht zwingend dieselbe VPS-Caddy-Konfiguration verwenden.

## Produktionsabnahme

Nach Merge und VPS-Deployment müssen Frontend- und API-Versionsendpunkte denselben exakten Mergecommit melden. Anschließend sind die folgenden Prüfungen gegen `https://weltgewebe.net` erforderlich:

```sh
curl -sS -D - -o /dev/null https://weltgewebe.net/map.html
curl -sS -D - -o /dev/null 'https://weltgewebe.net/map.html?node=abc&mode=focus'
```

Erwartet werden jeweils genau ein `308` und die oben beschriebenen `Location`-Werte. Danach muss ein frischer Browserlauf belegen:

- die finale Adresse ist `/map` beziehungsweise `/map` mit unveränderter Query und unverändertem Fragment;
- die Kachel- oder Fallbackkarte besitzt ein sichtbares Canvas;
- Marker und Fäden werden geladen;
- es gibt keine wiederholten Hauptdokument-Navigationen;
- die alte `map.html`-Reload-Datei wird nicht ausgeführt.

## Rollback

Ein Rollback entfernt die exakt begrenzte `/map.html`-Redirectregel aus beiden Caddy-Dateien und spielt die vorherige geprüfte Release-Revision aus. Vor einem Rollback ist zu beachten, dass HTTP 308 von Browsern und Zwischenstellen dauerhaft zwischengespeichert werden kann. Daher beweist ein bereits umgeleiteter Browser nicht, dass die Serverregel noch aktiv ist; maßgeblich sind ein frischer HTTP-Readback und die ausgelieferte Caddy-Konfiguration.

Die alte direkte Auslieferung von `map.html` darf nicht als akzeptabler Rollbackzustand gelten, solange sie die Neuladeschleife reproduziert. Falls der Redirect selbst eine Regression verursacht, muss `/map.html` stattdessen terminal und stabil mit 404 beantwortet werden, bis ein neuer geprüfter Kanonisierungsvertrag vorliegt.

## Claim-Grenze

Dieser Vertrag belegt ausschließlich die Kanonisierung der veralteten Kartenadresse. Er beweist nicht automatisch:

- die visuelle Qualität der Fadenkurven;
- die Vollständigkeit der Kartendaten;
- die Funktion sämtlicher API- oder Authentifizierungswege;
- einen erfolgreichen Produktionsdeploy ohne commitgenauen Readback und frischen Browserbeleg.
