# Heimserver Integration

## 0. Zweck

**Status:** Temporäre Integrationsumgebung.
Dieses Dokument beschreibt die Integration der API im Rahmen der aktuellen Entwicklungsphase auf dem Heimserver.
Es definiert den Contract, nicht die endgültige Produktionsinfrastruktur.

Beschreibt die referenzielle Integration der Weltgewebe-API auf dem Heimserver.
Dieses Dokument ist ein normativer Contract; die Heimserver-Enforcement-Details liegen außerhalb des Repos.

**Nicht enthalten:**

* Enforcement (Firewall/WireGuard/Router) ist out of scope dieses Repos.

**Nur:**

* API-Entry-Point
* DNS
* Reverse Proxy
* TLS
* CORS

---

## 1. Kanonischer API-Endpunkt

`https://api.heimgewebe.home.arpa`

**Invarianten:**

* Kein `.home` (als TLD)
* Erlaubt: `home.arpa` (RFC 8375)
* Kein `.lan`
* Kein `weltgewebe.api`
* Kein direkter Port-Zugriff (Direct :8080 access is not part of the supported contract; use reverse proxy FQDN).
* Kein http-only Betrieb

---

## 2. Reverse-Proxy-Vertrag

Caddy leitet weiter an:

```caddy
reverse_proxy api:8080
```

**Upstream darf:**

* Nicht öffentlich gebunden sein
* Nur Container-intern erreichbar sein
* Host-Match erforderlich (sonst 404/Drift).

---

## 3. TLS-Policy

* `tls internal`
* Interne CA
* Keine öffentliche ACME-Integration

---

## 4. CORS-Vertrag

Falls CORS verwendet wird:

**Erlaubte Origin:**

`https://leitstand.heimgewebe.home.arpa`

* Kein Wildcard-`*`
* Keine parallelen Domains

---

## 5. Runtime-Annahmen

Die API erwartet:

* DNS-Auflösung über Pi-hole
* Kein Splitbrain
* Keine parallelen Domains
* Kein HTTP/3 ohne Dokumentation

---

## 6. Drift-Indikatoren

| Symptom | Ursache |
| :--- | :--- |
| TLS Fehler | falscher Host |
| CORS Fehler | falsche Domain |
| 502 | Container nicht im selben Docker-Netz |
| 404 | Host-Mismatch |

---

## 7. Essenz

API ist kein Server.
Sie ist ein hinter dem Proxy lebender Dienst mit exakt einem kanonischen Namen.

---

## 8. Contract Checks

* HTTPS only + `tls internal`
* FQDN Host-Match (404 bei falschem Host)
* Kein direkter :8080 Zugriff (Proxy-FQDN ist der Contract)
