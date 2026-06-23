---
id: deploy.secondary-domain-web-surfaces
title: Sekundäre Domain-Webflächen
doc_type: reference
status: active
summary: >
  Definiert das Weltweberei-Webartefakt und den verhaltensorientierten
  Handoff an den externen Heimserver-Edge für weltweb.net und weltweberei.org.
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

`heimgewebe/weltgewebe` besitzt:

- den Inhalt;
- das statische Quellartefakt;
- den Web-Build;
- den Build- und Browser-Proof;
- den verhaltensorientierten Handoff-Vertrag.

`heimgewebe/heimserver` besitzt:

- das operative Edge-Template;
- die konkrete Caddy-Syntax;
- die Validierungs- und Synchronisierungsmechanismen;
- den Runbook-Vertrag für den Edge-Cutover.

Der Operator besitzt:

- die Freigabe der Live-Mutation;
- die Synchronisierung in den aktiven Edge-Pfad;
- Caddy-Validierung und Reload in der Laufzeit;
- Runtime-, TLS-, DNS- und Reachability-Nachweise.

INWX ist als Registrar und als Zielprovider für das autoritative DNS
vorgesehen.

Die aktive autoritative Delegation der Nebendomains auf INWX-Nameserver ist
in diesem Slice nicht belegt und bleibt Operatorarbeit.

## 2. Repo-seitig belegte Ziel-Artefaktkette

Der Quell- und Buildpfad wird durch diesen PR belegt.

Host- und Edge-Mounts werden durch eingecheckte Integrations- und
Deploymentverträge beschrieben. Sie sind in diesem Slice nicht gegen die
aktive Heimserver-Laufzeit verifiziert und stellen daher keinen
Runtime-Nachweis dar.

### Durch diesen PR belegt

- Quelle:
  `apps/web/static/weltweberei/`
- Build-Artefakt:
  `apps/web/build/weltweberei/`
- reproduzierbarer Web-Build;
- Browser-Proof für die statische Informationsfläche.

Der Quell-zu-Build-Schritt ist deterministisch belegt: `apps/web/static/`
wird durch den normalen Web-Build (`CI=true pnpm -C apps/web build`)
unverändert nach `apps/web/build/` kopiert. Der Browser-Proof
(`apps/web/tests/weltweberei-information.spec.ts`) prüft das Artefakt auf
Inhalt, Ressourcenfreiheit, Layout und Tastaturzugänglichkeit.

### Als Zielvertrag beschrieben, aber nicht live verifiziert

- vorgesehener Hostpfad:
  `/opt/weltgewebe/apps/web/build`
- vorgesehener Edge-Mount:
  `/srv/weltgewebe-web`
- vorgesehener Site-Root:
  `/srv/weltgewebe-web/weltweberei`

## 3. Voraktivierungszustand

Das Weltweberei-Artefakt ist Teil des normalen Web-Builds.

Dadurch kann es bereits auf Branch-Previews oder bestehenden Webhosts unter
`/weltweberei/` erreichbar sein. Diese technische Erreichbarkeit ist kein
Beleg für die Aktivierung von `weltweberei.org` und keine rechtliche
Veröffentlichungsfreigabe.

Bis zum abgeschlossenen Aktivierungsgate gilt:

- `robots` bleibt `noindex, nofollow`;
- es wird kein Canonical-Link auf `weltweberei.org` veröffentlicht;
- die Ziel-Domain wird nicht als live ausgegeben;
- das Artefakt bleibt inhaltlich frei von Kontakt- und Privatdaten.

Der spätere Aktivierungs-PR darf `index, follow` und den Canonical-Link erst
nach belegtem HTTPS-, Edge-, DNS- und Publikationsgate setzen.

## 4. Vorgesehener späterer Edge-Vertrag

Die konkrete Edge- und Caddy-Implementierung gehört ausschließlich in das
Owner-Repo `heimgewebe/heimserver`.

Dieses Dokument definiert nur das von außen beobachtbare Zielverhalten und
den Artefakt-Handoff. Es ist weder eine aktive Edge-Konfiguration noch eine
Copy-Paste-Vorlage für den Betrieb.

### `weltweb.net`

Der spätere Heimserver-Edge muss folgendes Verhalten herstellen und
automatisiert prüfen:

- HTTP-Anfragen werden auf das kanonische HTTPS-Ziel umgeleitet.
- Das endgültige Ziel ist `https://weltgewebe.net`.
- Pfad und Queryparameter bleiben erhalten.
- Die Umleitung ist permanent.
- Unter `weltweb.net` wird kein eigener Anwendungsinhalt ausgeliefert.
- Die konkrete Statuscode- und Caddy-Syntax wird im Owner-Repo festgelegt und
  dort getestet.

### `weltweberei.org`

Der spätere Heimserver-Edge muss folgendes Verhalten herstellen und
automatisiert prüfen:

- HTTP-Anfragen werden dauerhaft auf HTTPS derselben Domain umgeleitet.
- HTTPS liefert ausschließlich das statische Weltweberei-Artefakt aus.
- Der vorgesehene Edge-Pfad ist
  `/srv/weltgewebe-web/weltweberei`.
- Die Wurzelroute liefert die Informationsseite.
- Anfragen werden weder an die Weltgewebe-App noch an die API
  weitergereicht.
- Es werden restriktive Sicherheitsheader gesetzt.
- Skripte, Formulare, Frames, externe Ressourcen und Tracking bleiben
  ausgeschlossen.
- Die konkrete Caddy-Syntax wird ausschließlich im Owner-Repo implementiert
  und validiert.

Der spätere Edge muss mindestens folgende Sicherheitseigenschaften
herstellen:

- Einbettung in fremde Frames ist untersagt.
- Referrer-Informationen werden nicht an fremde Ursprünge übertragen.
- Nicht benötigte Browserfähigkeiten sind deaktiviert.
- Inhaltstypen dürfen nicht erraten werden.
- Die Content Security Policy erlaubt ausschließlich die für das statische
  Artefakt erforderlichen lokalen Ressourcen.

### Nicht entschiedene Hostnamen

Für folgende Hostnamen besteht in diesem Slice keine kanonische
Routingentscheidung:

- `www.weltweb.net`
- `www.weltweberei.org`

Sie dürfen im späteren Edge-PR nicht still ergänzt werden.

## 5. Explizit offene Punkte

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

## 6. Rechtliches Publikationsgate

```text
Dieser Slice erstellt ein technisches Informationsartefakt.
Er entscheidet nicht über Anbieterkennzeichnung, Datenschutzseite
oder andere rechtliche Veröffentlichungspflichten.

Vor der öffentlichen Aktivierung von weltweberei.org muss menschlich
entschieden und belegt werden, welche rechtlichen Informationen
erforderlich sind und wo sie bereitgestellt werden.

Der Coding-Agent darf dafür keine Privatdaten oder Rechtstexte erfinden.
```

## 7. Epistemische Grenze

```text
infra/caddy/Caddyfile.prod darf nicht als aktive öffentliche Frontdoor des
aktuellen Heimserver-Deployments ausgegeben werden.

In diesem Slice ist weder seine aktive Verwendung noch seine
Übereinstimmung mit /opt/heimgewebe/edge/Caddyfile belegt.
```
