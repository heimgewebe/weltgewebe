---
id: blueprints.weltgewebe.deploy.plan
title: Weltgewebe.Deploy.Plan
doc_type: reference
status: active
canonicality: derived
summary: Automatisch hinzugefügtes Frontmatter.
---
# Migrationsplan: Heim-first Deployment (Phase 0)

Ziel: Deployment des UI im Heimnetzwerk als kanonischer Einstiegspunkt.

## Phasen

### Phase 0: UI Lokal & Statisch

**Status:** _Geplant_

1. **Frontend Build:**
   - Erstelle lokalen Build (`pnpm build`) für `apps/web`.
   - Da `adapter-static` verwendet wird, entstehen statische Assets.

2. **Containerisierung (Optional):**
   - Ein dedizierter `weltgewebe-web` Service (z.B. Caddy-Container mit statischem HTML) für isolierte Setups.
   - Alternativ (Kanonisch): Direkte Einbindung des Build-Outputs als Volume im Heimserver-Edge.

3. **Routing-Umstellung:**
   - Heimserver-Edge ist die primäre Frontdoor und liefert `weltgewebe.home.arpa`
     primär lokal aus dem Weltgewebe-Build-Pfad aus.

### Phase 1: Frontend API Base Decision

**Status:** _Optional für MVP_

- Validierung: Das Frontend nutzt relative API-Aufrufe (`/api/...`).
- Falls absolute URLs nötig sind, werden diese zur Build-Time (`PUBLIC_GEWEBE_API_BASE`) gesetzt.
  Runtime-Injection (`env.js`) wird vermieden (da `adapter-static`).

### Phase 2: Auth Endpoints & Session Management

**Status:** _Aktiv (MVP)_ / **Route-Status:** _Noch 404/405 (Deployment erforderlich)_

- API Endpunkte (`/auth/login/*`) existieren bereits im Code (siehe `apps/api/src/routes/auth.rs`),
  sind aber deployed noch nicht aktiv/erreichbar (404/405).
- Sicherstellen, dass Caddy `/api/*` korrekt an Backend (`api:8080`) weiterreicht.
- Diagnose: Routen müssen 200/429 liefern, nicht 404.

### Phase 3: Persistenz-Migration (Postgres)

**Status:** _Zukunft_

- SQL-Schema für `accounts`, `sessions`, `tokens` erstellen.
- Migrationstool einführen (z.B. sqlx-cli oder dbmate).
- Code von In-Memory/File-backed auf DB umstellen.

## Verifikation & Abnahme

Nach Deployment von Phase 0 sind folgende Checks durchzuführen:

### 1. UI Verfügbarkeit

```bash
curl -I https://weltgewebe.home.arpa/
# Erwartet: 200 OK (und Server: Caddy)
```

### 2. API Proxy-Beweis

```bash
curl -fsS https://weltgewebe.home.arpa/api/health/ready
# Erwartet: 200 OK (JSON)
# Bestätigt: Caddy -> API Verbindung steht.
```

### 3. Auth Routen-Beweis (Backend)

```bash
# Request Magic Link
curl -i -X POST https://weltgewebe.home.arpa/api/auth/login/request \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'

# IST (derzeit): 404 Not Found
#   (Server: Caddy -> Proxy OK, aber Backend-Route fehlt)
#   Hinweis: Andere API-Routen wie /api/health/ready, /api/nodes, /api/accounts
#   liefern bereits 200 -> Proxy/Upstream ist korrekt; fehlend sind spezifisch die Auth-Routen.

# ZIEL (Blueprint): 200 OK (Request accepted) oder 429 (Rate Limit).
```

## Stop-Kriterien (Rollback)

- UI nicht erreichbar (502/504).
- API liefert 404 auf `/api/*` (außer Auth, das ist bekannt).
