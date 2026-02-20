# Deployment-Änderungsprotokoll

Dieses Dokument protokolliert Infrastruktur-Änderungen, die Auswirkungen auf das Deployment haben.

---

## 2026-02-20 - Public Magic-Link Login aktiviert (Option C)

**Ursprung / Referenz:** (feat/auth-public-magic-link)

**Geänderte Dateien:**

- `infra/compose/compose.prod.override.yml`
- `docs/deploy/heimserver.deployment.md`

### Added

- Public Magic-Link Login aktiviert (Option C)
- Allowlist deaktiviert (erfordert strikte Rate-Limits im Environment)
- Rate-Limits für Open Registration mandatory gemacht (Code-Enforcement)
- Token-Log-Deaktivierung für Prod stark empfohlen (Warnung im Log)

### Risiko

Mittel bis hoch (öffentlicher Login-Endpunkt)

---

## 2026-02-19 - compose.prod.override.yml: `environment: null` → `environment: {}` (caddy)

**Ursprung / Referenz:** PR #746 (chore: remove bak artifacts, fix compose environment null)

**Geänderte Dateien:**

- `infra/compose/compose.prod.override.yml`

**Beschreibung:**

Der `caddy`-Service-Block in `compose.prod.override.yml` verwendete `environment: null`, was kein gültiger
Docker-Compose-Wert ist (erwartet wird eine Map oder Liste). Dies wurde durch `environment: {}` (leere Map) ersetzt,
was semantisch äquivalent ist (keine Umgebungsvariablen für caddy), aber syntaktisch korrekt.

**Auswirkung auf Deployment:**

Keine funktionalen Änderungen. `docker compose config` läuft ohne Parser-Fehler durch.

**Risiko:** Keine.

---

## 2026-02-10 - compose.prod.yml auf stabilen Stand zurückgesetzt

**Ursprung / Referenz:** f6e19c5 (revert: remove compose topology changes) – (Commit-Hash kann bei Squash abweichen)

**Geänderte Dateien:**

- `infra/compose/compose.prod.yml`
- `policies/limits.yaml`
- `apps/api/Dockerfile`

**Aktueller Stand:**

- Caddy-Service als Gateway (Ports auf localhost)
- DB-Credentials über Umgebungsvariablen
- Keine `NATS_URL` (Service existiert nicht)
- `policies/limits.yaml` mit Schema-konformen Limitwerten
- `Dockerfile` mit optimierter Layer-Caching-Reihenfolge

**Hintergrund der Rücksetzung:**

Die Änderungen aus der damaligen Änderung (Referenz oben) wurden zurückgesetzt, um Risiken zu vermeiden:

- Fehlender Caddy-Service (Gateway-Prinzip verletzt)
- `NATS_URL` ohne NATS-Service gesetzt (Readiness-Checks schlugen fehl)
- Hardcodierte DB-Credentials statt env-basiert
- API auf `0.0.0.0:8081` exponiert (Sicherheitsrisiko)
- `policies/limits.yaml` Semantik geändert (Schema-Bruch)

**Risiko:** Niedrig. Stabiler, bewährter Stand.

---

## 2026-02-10 - Caddy Rate-Limiting vollständig deaktiviert

**Ursprung / Referenz:** 5e94a21 (ops: stabilize prod runtime) – (Commit-Hash kann bei Squash abweichen)

**Geänderte Dateien:**

- `infra/caddy/Caddyfile.prod`

**Beschreibung:**

Rate-Limiting-Konfiguration in Caddy wurde vollständig auskommentiert, da die `rate_limit`-Direktive ein externes
Plugin erfordert, das in der Standard-Caddy-Distribution nicht enthalten ist.

**Syntax-Korrektur (dieser PR):**

Die ursprüngliche Deaktivierung in der damaligen Änderung (Referenz oben) war syntaktisch unvollständig (nur die
öffnende Zeile `rate_limit {` war auskommentiert, während die Subdirektiven aktiv blieben). Dies führte zu einem
Parse-Fehler beim Caddy-Start. Die Syntax wurde vollständig korrigiert, indem der gesamte Block inkl. aller Subdirektiven
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
