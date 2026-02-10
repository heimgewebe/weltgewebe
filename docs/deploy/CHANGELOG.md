# Deployment-Änderungsprotokoll

Dieses Dokument protokolliert Infrastruktur-Änderungen, die Auswirkungen auf das Deployment haben.

---

## 2026-02-10 - compose.prod.yml auf stabilen Stand zurückgesetzt (Revert)

**Commit-Referenz:** f6e19c5 (revert: remove compose topology changes)

**Geänderte Dateien:**

- `infra/compose/compose.prod.yml`
- `policies/limits.yaml`
- `apps/api/Dockerfile`

**Beschreibung:**

Die Änderungen aus Commit 5e94a21 an compose.prod.yml, policies/limits.yaml und Dockerfile wurden zurückgesetzt,
um den PR auf die Caddy-Dokumentation zu fokussieren. Die compose-Änderungen führten zu mehreren Problemen:

- Fehlender Caddy-Service (Gateway-Prinzip verletzt)
- NATS_URL ohne NATS-Service gesetzt (Readiness-Checks schlugen fehl)
- Hardcodierte DB-Credentials statt env-basiert
- API auf 0.0.0.0:8081 exponiert (Sicherheitsrisiko)
- policies/limits.yaml Semantik geändert (Schema-Bruch)

**Wiederhergestellter Stand:**

- Caddy-Service mit Gateway-Funktion (Ports auf localhost gebunden)
- DB-Credentials über Umgebungsvariablen (${DATABASE_URL}, ${POSTGRES_PASSWORD})
- Keine NATS_URL in Umgebung (Service existiert nicht)
- policies/limits.yaml mit echten Limitwerten (max_nodes_jsonl_mb, max_edges_jsonl_mb)
- Dockerfile mit korrekter Layer-Caching-Reihenfolge

**Auswirkung auf Deployment:**

- compose.prod.yml entspricht wieder dem bewährten Setup
- Keine Auswirkung auf laufende Deployments (keine Breaking Changes)
- compose.heimserver.override.yml bleibt kompatibel (referenziert Caddy-Service)

**Risiko:**

Niedrig. Revert auf bekannten funktionierenden Stand.

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
