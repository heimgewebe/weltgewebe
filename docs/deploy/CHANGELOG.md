---
id: deploy.CHANGELOG
title: Changelog
doc_type: reference
status: active
canonicality: derived
summary: Automatisch hinzugefügtes Frontmatter.
---
# Deployment-Änderungsprotokoll

Dieses Dokument protokolliert Infrastruktur-Änderungen, die Auswirkungen auf das Deployment haben.

---

## 2026-03-08 - NATS Healthcheck & JetStream-Persistenz korrigiert

**Ursprung / Referenz:** Heimserver-Entscheidung (vollwertiger Stack)

**Geänderte Dateien:**

- `infra/compose/compose.prod.yml`

**Beschreibung:**

Der NATS-Healthcheck wurde korrigiert, da das bisherige `nats:2.10`-Image als Scratch-Image keine Shell
(`sh`) oder Utilities (`wget`) enthielt, was dazu führte, dass der `CMD-SHELL` Healthcheck fehlschlug.
Zur Lösung wurde auf `nats:2.10-alpine` umgestellt und ein strikt image-kompatibler Exec-Form-Healthcheck
(`["CMD", "wget", "-qO-", "http://localhost:8222/healthz"]`) implementiert.
Zusätzlich wurde die JetStream-Speicherpfad-Konfiguration (`-sd /data`) zum `command` hinzugefügt,
sodass persistierte Daten nun korrekt in das gemountete Docker-Volume `nats_js:/data` fließen.

---

## 2026-03-07 - NATS wieder als kanonischer Stack-Bestandteil integriert

**Ursprung / Referenz:** Heimserver-Entscheidung (vollwertiger Stack)

**Geänderte Dateien:**

- `infra/compose/compose.prod.yml`
- `infra/compose/compose.prod.override.yml`

**Beschreibung:**

Die Infrastruktur-Konfiguration wies einen Drift bezüglich des Message Brokers NATS auf:
Während Dokumentation und API-Health-Checks (bei Konfiguration von `NATS_URL`) bereits von NATS als integralem
Bestandteil ausgingen und der Service temporär nur über Overrides bereitgestellt wurde, fehlte er im primären
Produktions-Compose-File.
Zur Wiederherstellung der kanonischen Deckungsgleichheit (gemäß der Entscheidung: "Weltgewebe auf dem Heimserver soll
als vollwertiger Stack mit NATS/JetStream betrieben werden") wurde der `nats`-Service nun wieder fest in die
`compose.prod.yml` integriert. Die API bezieht `NATS_URL` nun per Default.
Redundante Deklarationen in der `compose.prod.override.yml` wurden bereinigt. Der Deployment-Pfad (`weltgewebe-up`)
startet somit den vollständigen, in sich konsistenten Stack und verifiziert NATS implizit mit über den API-Health-Check.
Zudem wurde die Startup-Robustheit verbessert: NATS verfügt nun über einen eigenen HTTP-Healthcheck auf Port 8222,
und die API wartet via `condition: service_healthy` explizit auf die Readiness von NATS.
Die `NATS_URL` ist zudem default-basiert overridefähig, ohne den kanonischen lokalen Stack zu verändern.

**Risiko:** Niedrig. (Auflösung von Drift / Konsistenzherstellung).

---

## 2026-03-05 - Fix CSP for SvelteKit Inline Bootstrap

**Ursprung / Referenz:** Fix für Whitepage (CSP-Problem)

**Geänderte Dateien:**

- `infra/caddy/Caddyfile`

**Beschreibung:**

Die Content-Security-Policy (CSP) in Caddy wurde angepasst, um SvelteKit's Inline-Bootstrap-Script zu
erlauben. Der Direktive `script-src` wurde `'unsafe-inline'` hinzugefügt, da andernfalls das
Svelte-Frontend mit einer leeren Seite (Whitepage) blockiert wurde.

Ein Preflight-Guard (`csp_contract_static.sh`) wurde ebenfalls dem Deployment hinzugefügt, um sicherzustellen, dass
Inline-Scripts zukünftig nicht versehentlich wieder durch die CSP blockiert werden.

**Risiko:** Mittel. Die CSP ist weniger streng (`'unsafe-inline'`), was XSS-Risiken potenziell erhöht, jedoch
im aktuellen Kontext (Heimnetz, funktionierendes UI priorisiert) als pragmatische Lösung akzeptiert wurde.
Hardening via Nonce/Hash sollte später folgen.

---

## 2026-02-21 - Fix: SMTP Env Injection via `env_file`

**Ursprung / Referenz:** Fix für AUTH_PUBLIC_LOGIN (Deployment-Drift)

**Geänderte Dateien:**

- `infra/compose/compose.prod.override.yml`

**Beschreibung:**

Um sicherzustellen, dass SMTP-Variablen (und andere Secrets) zuverlässig im `weltgewebe-api`-Container ankommen,
wurde dem Service `api` die Direktive `env_file: - /opt/weltgewebe/.env` hinzugefügt.

Hintergrund: `docker compose --env-file` stellt Variablen primär für die Interpolation im Compose-File bereit.
Ohne explizites Mapping im `environment`-Block landen diese nicht automatisch im Container-Runtime-Environment.
Die Ergänzung von `env_file:` im Service stellt sicher, dass alle Variablen aus der Datei in den Container injiziert werden.
Annahme: Der Pfad `/opt/weltgewebe/.env` ist eine bewusste Heimserver-Layout-Abhängigkeit.
Override: `WELTGEWEBE_ENV_FILE` kann den Pfad überschreiben.

Zusätzlich wurde im CI-Workflow das ungültige Argument `--max-cache-age` für den `lychee` Link-Checker entfernt,
um Build-Fehler zu beheben.

**Risiko:** Niedrig (Deployment-Korrektur).

---

## 2026-02-20 - Option C vollständig implementiert (Auto-Provision im Auth-Flow)

**Ursprung / Referenz:** (feat/auth-open-registration)

**Geänderte Dateien:**

- `apps/api/src/config.rs`
- `apps/api/src/routes/auth.rs`

**Beschreibung:**

Option C war bisher nur im Config-Layer aktiv. Unknown emails wurden weiterhin mit `policy_denied` behandelt.
Jetzt wird Auto-Provision + Magic-Link-Versand im Auth-Flow durchgeführt, wenn `is_open_registration()` true ist.
Damit entspricht Runtime-Verhalten der Konfigurationsvalidierung.

**Risiko:** Mittel–Hoch (öffentlicher Login-Endpunkt).

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

**Risiko:** Niedrig.

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

## 2026-03-08 - Parameterized policy bind path in compose.prod.override.yml

**Ursprung / Referenz:** Fix für Deployment-Drift (REPO_DIR)

**Geänderte Dateien:**

- `infra/compose/compose.prod.override.yml`

**Beschreibung:**

Der harte Pfad `/opt/weltgewebe/policies/limits.yaml` für den Volume-Mount in der Datei
`infra/compose/compose.prod.override.yml` wurde durch dynamische Interpolation mittels der `REPO_DIR`-Variable ersetzt
(`${REPO_DIR:-/opt/weltgewebe}/policies/limits.yaml`).
Dies ermöglicht ein flexibles Deployment in beliebigen Verzeichnissen, wenn `weltgewebe-up` die `REPO_DIR` exportiert,
während die Rückwärtskompatibilität zum bisherigen Standardpfad (`/opt/weltgewebe`) für native Docker Compose Aufrufe
erhalten bleibt.

**Risiko:** Niedrig. (Flexibilisierung des Deployments ohne funktionale Änderungen für bestehende Setups).
