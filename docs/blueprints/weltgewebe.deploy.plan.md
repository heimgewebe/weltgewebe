# Migrationsplan: Heim-first Deployment (Phase 0)

Ziel: Deployment des UI im Heimnetzwerk als kanonischer Einstiegspunkt.

## Phasen

### Phase 0: UI Lokal & Statisch

**Status:** _Geplant_

1. **Frontend Build:**
   - Erstelle lokalen Build (`pnpm build`) für `apps/web`.
   - Da `adapter-static` verwendet wird, entstehen statische Assets.

2. **Containerisierung (Optional):**
   - Ein dedizierter `weltgewebe-web` Service (z.B. Caddy-Container mit statischem HTML) serviert die Assets.
   - Alternativ: Einbindung als Volume im existierenden Caddy (`infra/caddy`).

3. **Routing-Umstellung:**
   - Caddy (lokal oder Edge) routet `weltgewebe.home.arpa` auf den lokalen Web-Service (z.B. `web:80` oder Volume)
     statt auf Cloudflare.

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
# Erwartet: 200 OK (und Server: Caddy, NICHT cloudflare)
# Falls 'cf-ray' Header vorhanden ist, kommt es noch von Cloudflare!
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
#   (Server: Caddy ohne Cloudflare-Header -> Proxy OK, aber Backend-Route fehlt)

# ZIEL (Blueprint): 200 OK (Request accepted) oder 429 (Rate Limit).
```

### 4. Cloudflare-Indikator (Non-API)

```bash
# Request auf Login-Seite (sollte im Ziel lokal sein, aktuell Pages)
curl -i -X POST https://weltgewebe.home.arpa/login

# IST (Cloudflare): 405 Method Not Allowed + Header 'server: cloudflare'
# ZIEL (Lokal): 405 (Static File Server allow GET only) + Server: Caddy
```

## Stop-Kriterien (Rollback)

- UI nicht erreichbar (502/504).
- API liefert 404 auf `/api/*` (außer Auth, das ist bekannt).
- Cloudflare interceptet weiterhin Requests (Check `cf-ray`).
