# Migrationsplan: Heim-first Deployment (Phase 0)

Ziel: Deployment des UI im Heimnetzwerk als kanonischer Einstiegspunkt.

## Phasen

### Phase 0: UI Lokal & Statisch

**Status:** _Geplant_

1. **Frontend Build:**
   - Erstelle lokalen Build (`pnpm build`) für `apps/web`.
   - Das Ergebnis (statische Assets) wird im Heimserver verfügbar gemacht.

2. **Containerisierung (Optional):**
   - Ein dedizierter `weltgewebe-web` Service (Nginx oder Caddy) serviert die Assets.
   - Alternativ: Einbindung als Volume im existierenden Caddy (`infra/caddy`).

3. **Config Injection:**
   - Beim Start des Web-Containers wird `env.js` generiert/kopiert,
     das `PUBLIC_GEWEBE_API_BASE` auf `/api` setzt.

4. **Routing-Umstellung:**
   - Caddy (lokal oder Edge) routet `weltgewebe.home.arpa` auf den lokalen Web-Service
     statt auf Cloudflare.

### Phase 1: API Manifest & Discovery

**Status:** _Optional für MVP_

- Bereitstellung von `/api/meta` oder `/api/openapi.json` zur Laufzeit-Verifikation der Routen.
- Frontend kann beim Start API-Version prüfen.

### Phase 2: Auth Endpoints & Session Management

**Status:** _Aktiv (MVP)_

- API Endpunkte (`/auth/login/*`) existieren bereits im Code.
- Sicherstellen, dass Caddy `/api/*` korrekt an Backend weiterreicht (Prefix-Handling beachten).
- Testen des Magic-Link Flows (SMTP oder Log).

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
```

### 2. Config Injection

```bash
curl https://weltgewebe.home.arpa/_app/env.js
# Erwartet: window.env = { PUBLIC_GEWEBE_API_BASE: "/api", ... }
```

(Pfad kann variieren je nach Implementierung)

### 3. API Routing

```bash
curl https://weltgewebe.home.arpa/api/health
# Erwartet: 200 OK (JSON)
```

### 4. Auth Flow (Smoke Test)

```bash
# Request Magic Link
curl -X POST https://weltgewebe.home.arpa/api/auth/login/request \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com"}'
# Erwartet: 200 OK oder 429 (Rate Limit) oder 403 (Allowlist), aber KEIN 404/405.
```

## Stop-Kriterien (Rollback)

- UI nicht erreichbar (502/504).
- API liefert 404 auf `/api/*`.
- Auth liefert 405 (Cloudflare Intercept).
