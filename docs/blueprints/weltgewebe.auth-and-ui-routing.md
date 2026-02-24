# Blueprint: Heim-first Auth & UI Routing

## Problemstatement
Der aktuelle Zustand leidet unter einem "Split-Brain":
- **UI:** `weltgewebe.home.arpa` liefert HTML identisch zu `weltgewebe.pages.dev` (Cloudflare Pages).
- **API:** `weltgewebe.home.arpa/api/*` proxyt zur lokalen API.
- **Identity:** Auth-Versuche (Login/Magic-Link) enden in 405 (Method Not Allowed) von Cloudflare ("server: cloudflare"), da die UI versucht, Auth-Endpunkte gegen Cloudflare zu feuern, oder Cloudflare diese Routen nicht kennt.
- **Folge:** Keine funktionierende Anmeldung im Heimnetz, Abhängigkeit vom Internet für UI-Assets, inkonsistente Umgebung.

## Zielzustand (Kanonisch)

Das Heimnetz (`.home.arpa`) ist die primäre Authority für UI und Identität. Cloudflare Pages dient nur als optionaler öffentlicher Spiegel ("Schaufenster").

### 1. Routing-Invarianten
- `https://weltgewebe.home.arpa/` → **Lokales Frontend** (Container `weltgewebe-web` oder statisch via Caddy). Kein Cloudflare-Proxy.
- `https://weltgewebe.home.arpa/api/*` → **Lokales API** (`weltgewebe-api-1:8080`).
- `https://api.weltgewebe.home.arpa/*` → **Lokales API** (Alias via Caddy-Referenz).
- `weltgewebe.pages.dev` → Nur Public Mirror, keine Heim-Login-Funktionalität.

### 2. Identity & Auth API
Die Identität wird heimisch verwaltet.
- **Auth-Endpunkte:** Müssen explizit exposed sein.
  - `POST /api/auth/login/request` (Magic Link anfordern)
  - `GET/POST /api/auth/login/consume` (Magic Link einlösen)
  - `POST /api/auth/logout`
  - `GET /api/auth/me` (Session-Check)
- **Session-Management:**
  - Status: MVP (In-Memory Sessions & Tokens).
  - Neustart der API beendet alle Sessions.

### 3. API Base & Environment
Das Frontend darf keine fix codierte API-URL haben.
- **Invariant:** `env.js` (oder Äquivalent) muss im lokalen Deployment vorhanden sein und `PUBLIC_GEWEBE_API_BASE="/api"` setzen.
- Dies garantiert Same-Origin-Requests und vermeidet CORS-Probleme im Heimnetz.

### 4. Daten-Persistenz
Aktueller Status:
- **Accounts:** File-backed (`demo.accounts.jsonl`).
- **Nodes/Edges:** File-backed (`nodes.jsonl`).
- **Postgres:** Vorhanden, aber leer (keine Tabellen, keine Migrationen).

**Entscheidung:**
- **Phase 0 (Jetzt):** Beibehaltung File-backed für MVP. Auth nutzt In-Memory Sessions.
- **Phase 1 (Zukunft):** Migration zu Postgres für Accounts und Sessions, um Persistenz über Neustarts zu sichern.

## Sicherheitsnotizen
- **Token Handling:** Magic Links werden per SMTP versendet (oder im Log ausgegeben, wenn `AUTH_LOG_MAGIC_TOKEN=true` für Dev).
- **Proxy Trust:** `AUTH_TRUSTED_PROXIES` muss korrekt konfiguriert sein, damit Rate-Limits (IP-basiert) hinter Caddy funktionieren.
- **Abuse:** Rate-Limits für Login-Requests sind in `AppConfig` vorhanden und müssen > 0 sein.
