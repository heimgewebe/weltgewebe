# Ops Runbook: Weltgewebe Self-Hosted Deployment

## Kontext

Diese PR dokumentiert die erfolgreiche Migration des Weltgewebe-Deployments von **Netlify**
zu einem **self-hosted Heimserver-Deployment mit edge-caddy**.

Die Migration beinhaltete:

* DNS-Umstellung
* Router-Portfreigaben
* Edge-Gateway-Validierung
* Mail-DNS-Fix

Ziel ist ein reproduzierbares Deployment-Runbook.

## 1 Neues Runbook

### Inhalt

Dokumentiert:

* DNS-Migration
* Router-Portforward
* Caddy-Gateway
* typische Fehler

## 2 DNS-Migration dokumentiert

Domain:

`weltgewebe.net`

### vorher

`Netlify DNS (nsone.net)`

### nachher

`IONOS DNS`
`ns1121.ui-dns.com`
`ns1044.ui-dns.org`
`ns1086.ui-dns.biz`
`ns1036.ui-dns.de`

### notwendige Records

```text
A  weltgewebe.net        → <public-ip>
A  www.weltgewebe.net    → <public-ip>
A  api.weltgewebe.net    → <public-ip>

MX 10 mx00.ionos.de
MX 10 mx01.ionos.de

TXT SPF
DKIM (IONOS)
DMARC
```

## 3 Router-Konfiguration (kritisch)

Für self-hosted Deployments müssen folgende Ports freigegeben werden:

```text
TCP 80  → Heimserver
TCP 443 → Heimserver
```

Beispiel (FritzBox):

```text
Internet → Freigaben → Portfreigaben
HTTP   TCP 80
HTTPS  TCP 443
```

Ohne diese Ports ist das System öffentlich nicht erreichbar.

## 4 Edge Gateway

Edge-Gateway:

`edge-caddy`

Container:

`caddy:2.x`

Ports:

```text
80
443
```

Routing:

```text
weltgewebe.net
api.weltgewebe.net
```

## 5 Hairpin-NAT Hinweis

Lokale Tests können scheitern:

```bash
curl <public-ip>
```

Grund:

`Hairpin NAT`

Lösung:

```bash
curl weltgewebe.net
```

oder extern testen.

## 6 Validierungschecks

### DNS

```bash
dig A weltgewebe.net
dig MX weltgewebe.net
```

### HTTP

```bash
curl -I http://weltgewebe.net
```

Expected:

```text
308 Permanent Redirect
Server: Caddy
```

### HTTPS

```text
https://weltgewebe.net
```

Caddy stellt Zertifikate automatisch aus.

## Ergebnis

Deployment-Kette:

```text
weltgewebe.net
  ↓
IONOS DNS
  ↓
Router Portforward
  ↓
edge-caddy
  ↓
API Container
```

System ist jetzt öffentlich erreichbar.

## Motivation

Ohne diese Dokumentation sind typische Fehlerszenarien schwer zu diagnostizieren:

* DNS korrekt, aber Router blockiert
* NAT-Loopback-Fehler
* fehlende MX-Records
* falsche DNS-Authority

Das Runbook verhindert zukünftige Deployment-Blocker.

## Tests

Validiert durch:

```bash
curl -I http://weltgewebe.net
# → 308 redirect

dig MX weltgewebe.net
# → mx00.ionos.de
# → mx01.ionos.de
```

## Risiko

Dokumentations-only PR.
Keine Laufzeitänderung.

## Follow-ups

Optional:

* DNS Healthcheck CI
* Deploy-Guard für fehlende A-Records
* Mail-Delivery Test
