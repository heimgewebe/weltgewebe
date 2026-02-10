# Deployment Changelog

Dieses Dokument protokolliert Infrastruktur-Änderungen, die Auswirkungen auf das Deployment haben.

---

## 2026-02-10 - Caddy Rate-Limiting deaktiviert

**Geänderte Dateien:**

- `infra/caddy/Caddyfile.prod`

**Beschreibung:**

Rate-Limiting-Konfiguration in Caddy wurde auskommentiert, da die `rate_limit`-Direktive ein externes Plugin erfordert,
das in der Standard-Caddy-Distribution nicht enthalten ist.

**Änderungen im Detail:**

- `order rate_limit before basicauth` → auskommentiert
- `rate_limit { ... }` Block → auskommentiert
- Alle `rate_limit @matcher zone` Direktiven → auskommentiert

**Auswirkung auf Deployment:**

- Keine Änderungen am Deployment-Prozess erforderlich
- Caddy läuft weiterhin mit Standard-Distribution
- Rate-Limiting muss bei Bedarf auf Infrastruktur-Ebene (z.B. Firewall, Load Balancer) implementiert werden

**Risiko:**

- Login-Endpunkte sind ohne Rate-Limiting anfälliger für Brute-Force-Angriffe
- Mitigation: Monitoring der Login-Versuche, ggf. Fail2Ban oder ähnliche Host-Level-Lösungen

**Verifikation:**

```bash
docker compose -f infra/compose/compose.prod.yml config
# Sollte ohne Fehler durchlaufen
```

**Follow-up:**

- Evaluation von Caddy mit custom build inkl. rate_limit Plugin
- Oder: Implementierung von Rate-Limiting auf Applikationsebene (API-Service)
