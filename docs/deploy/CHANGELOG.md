# Deployment-Änderungsprotokoll

Dieses Dokument protokolliert Infrastruktur-Änderungen, die Auswirkungen auf das Deployment haben.

---

## 2026-02-10 - compose.prod.yml auf stabilen Stand zurückgesetzt

**Commit-Referenz:** f6e19c5

**Geänderte Dateien:**
- `infra/compose/compose.prod.yml`
- `policies/limits.yaml`
- `apps/api/Dockerfile`

**Aktueller Stand:**
- Caddy-Service als Gateway (Ports auf localhost)
- DB-Credentials über Umgebungsvariablen
- Keine NATS_URL (Service existiert nicht)
- policies/limits.yaml mit Schema-konformen Limitwerten
- Dockerfile mit optimierter Layer-Caching-Reihenfolge

**Risiko:** Niedrig. Stabiler, bewährter Stand.

---

## 2026-02-10 - Caddy Rate-Limiting vollständig deaktiviert

**Commit-Referenz:** 5e94a21 (ops: stabilize prod runtime)

**Geänderte Dateien:**

- `infra/caddy/Caddyfile.prod`

**Beschreibung:**

Rate-Limiting-Konfiguration in Caddy wurde vollständig auskommentiert, da die `rate_limit`-Direktive ein externes
Plugin erfordert, das in der Standard-Caddy-Distribution nicht enthalten ist.

**Syntax-Korrektur (dieser PR):**

Die ursprüngliche Deaktivierung in Commit 5e94a21 war syntaktisch unvollständig (nur die öffnende Zeile
`rate_limit {` war auskommentiert, während die Subdirektiven aktiv blieben). Dies führte zu einem Parse-Fehler
beim Caddy-Start. Die Syntax wurde vollständig korrigiert, indem der gesamte Block inkl. aller Subdirektiven
und schließender Klammer auskommentiert wurde.

**Änderungen im Detail:**

- `order rate_limit before basicauth` → auskommentiert
- `rate_limit { ... }` Block vollständig auskommentiert (alle Zeilen)
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

docker run --rm -v "$PWD/infra/caddy/Caddyfile.prod:/etc/caddy/Caddyfile:ro" caddy:2 caddy validate --config /etc/caddy/Caddyfile
# Sollte "Valid configuration" ausgeben
```

**Follow-up:**

- Evaluation von Caddy mit custom build inkl. rate_limit Plugin
- Oder: Implementierung von Rate-Limiting auf Applikationsebene (API-Service)
