# Weltgewebe API – Heimserver Integration

## 0. Zweck

**Status:** Temporäre Integrationsumgebung.
Dieses Dokument beschreibt die Integration der API im Rahmen der aktuellen Entwicklungsphase auf dem Heimserver.
Es definiert den Contract, nicht die endgültige Produktionsinfrastruktur.

Beschreibt die referenzielle Integration der Weltgewebe-API auf dem Heimserver.
Dieses Dokument ist ein normativer Contract; die Heimserver-Enforcement-Details liegen außerhalb des Repos.

> **Hinweis:** Dieses Repo definiert nur den Contract; DNS/Caddy-Enforcement liegt im ops/heimserver Repo.

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

`https://api.weltgewebe.home.arpa`

**Invarianten:**

* Kein `.home` als TLD (erlaubt ist ausschließlich `.home.arpa`; RFC 8375).
* Kein `.lan`
* Kein `weltgewebe.api`
* Kein direkter Port-Zugriff (Direct :8080 access is not part of the supported contract; use reverse proxy FQDN).
* Kein http-only Betrieb

---

## 2. Reverse-Proxy-Vertrag

Der Reverse-Proxy (Caddy) nutzt im Heimserver-Betrieb die Referenzkonfiguration als primären Caddyfile.
Technisch wird `docs/reference/caddy.heimserver.caddy` via `infra/compose/compose.heimserver.override.yml`
nach `/etc/caddy/Caddyfile` gemountet.

```caddy
api.weltgewebe.home.arpa {
    reverse_proxy api:8080
    tls internal
}
```

> **Hinweis:** Der Upstream-Name (z.B. `api`) ist exemplarisch und folgt der jeweiligen Compose-Benennung.

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

---

## 9. Data Seeding (Heimserver)

Die Heimserver-Umgebung aktiviert explizit `GEWEBE_SEED_DEMO=true`.
Dies stellt sicher, dass für Integrationstests und manuelle Prüfung definierte Test-Entitäten
(z.B. Garnrolle, Knoten) vorhanden sind.

---

## 10. SMTP Authentication Policy

Der API-Mailer unterstützt eine explizite Steuerung der SMTP-Authentifizierung via `SMTP_AUTH`.
Dies verhindert Authentifizierungsfehler bei lokalen Relays (z.B. auf Port 1025), wenn Credentials konfiguriert,
aber nicht gewünscht sind.

* `auto` (Default): Nutzt Credentials (`SMTP_USER`/`SMTP_PASS`), wenn diese vorhanden sind.
* `on`: Erzwingt Authentifizierung; Fehler, wenn Credentials fehlen.
* `off`: Ignoriert Credentials, auch wenn diese gesetzt sind (nützlich für lokale Dev-Relays).

**Beispiel (Mailpit/Mailhog):**
`SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_AUTH=off`

---

## 11. Interne DNS-Identität

Invariante: Der interne Docker-DNS-Name `weltgewebe-api` MUSS stabil auflösbar sein.
Edge Caddy und andere Dienste hängen davon ab.
Service-Suffixe wie `weltgewebe-api-1` sind nicht zulässig als Routing-Ziel.
Diese Invariante wird durch Guard + weltgewebe-up verifiziert.
In Ausnahmefällen kann die Verifikation im Deploy per ALLOW_UNSTABLE_API_DNS=1 übersteuert werden (nicht empfohlen).
