# Heimserver Integration

## 0. Zweck

Beschreibt die kanonische Integration der Weltgewebe-API auf dem Heimserver.

**Nicht enthalten:**

* Firewall-Details
* WireGuard-Details
* Router-Konfiguration

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

* Kein `.home`
* Kein `.lan`
* Kein `weltgewebe.api`
* Kein direkter Port-Zugriff
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
