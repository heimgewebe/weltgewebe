# Blueprint: Heim-first Auth & UI Routing

## Problemstatement

Der aktuelle Zustand leidet unter einem "Split-Brain":

- **UI:** `weltgewebe.home.arpa` liefert HTML identisch zu `weltgewebe.pages.dev` (Cloudflare Pages).
- **API:** `weltgewebe.home.arpa/api/*` proxyt zur lokalen API.
- **Identity:** Auth-Versuche (Login/Magic-Link) enden in 405 (Method Not Allowed) von Cloudflare ("server: cloudflare"),
  da die UI versucht, Auth-Endpunkte gegen Cloudflare zu feuern, oder Cloudflare diese Routen nicht kennt.
- **Folge:** Keine funktionierende Anmeldung im Heimnetz, Abhängigkeit vom Internet für UI-Assets, inkonsistente Umgebung.

## Zielzustand (Kanonisch)

Das Heimnetz (`.home.arpa`) ist die primäre Authority für UI und Identität.
Cloudflare Pages dient nur als optionaler öffentlicher Spiegel ("Schaufenster").

### 1. Routing-Invarianten

- **User Entry:** `https://weltgewebe.home.arpa/`
  → Lokales Frontend (Container `weltgewebe-web` oder statisch via Caddy). Kein Cloudflare-Proxy.
- **User API:** `https://weltgewebe.home.arpa/api/*`
  → Lokales API (Service: `api:8080`).
- **Host Debug:** `http://127.0.0.1:8081`
  → Host-Mapped Port (nur für lokale Diagnose, nicht für User-Traffic oder Browser).
- **Public Mirror:** `weltgewebe.pages.dev`
  → Nur statisches Schaufenster, keine Heim-Login-Funktionalität.

### 2. Identity & Auth API

Die Identität wird heimisch verwaltet.

- **Status:** **ZIEL / BLUEPRINT**
- **Fehlerbilder (Diagnose):**
  - **405 Method Not Allowed:** Symptom für Non-API Pfade (`/login`), die noch bei Cloudflare/Pages landen
    (Header `server: cloudflare`).
  - **404 Not Found:** Symptom für `/api/auth/*` Pfade, wenn der Reverse-Proxy korrekt ist
    (Header `server: Caddy`), aber die Route im Backend fehlt.
  - **Zielzustand:** POST `/api/auth/login/request` liefert **200 OK** oder **429 Too Many Requests**.

- **Auth-Endpunkte (Soll):** Müssen explizit exposed sein.
  *Hinweis: Exakte Auth-Routen im Backend sind gegen `apps/api/src/routes/auth.rs` zu verifizieren (rg),*
  *bevor UI implementiert wird.*
  - `POST /api/auth/login/request` (Magic Link anfordern)
  - `GET/POST /api/auth/login/consume` (Magic Link einlösen)
  - `POST /api/auth/logout`
  - `GET /api/auth/me` (Session-Check)
- **Session-Management:**
  - Status: MVP (In-Memory Sessions & Tokens).
  - Neustart der API beendet alle Sessions.

### 3. API Base & Environment

Das Frontend darf keine fix codierte API-URL haben.

- **Invariant:** Da `adapter-static` verwendet wird (belegt), sind `PUBLIC_` Variablen Build-time.
- **Strategie:** Das Frontend nutzt relative Pfade (`/api/...`).
  Dies garantiert Same-Origin-Requests und vermeidet CORS-Probleme im Heimnetz, ohne Runtime-Injection (`env.js`) zu erzwingen.

### 4. Daten-Persistenz

Aktueller Status:

- **Accounts:** File-backed (`demo.accounts.jsonl`).
- **Nodes/Edges:** File-backed (`nodes.jsonl`).
- **Postgres:** Vorhanden, aber leer (keine Tabellen, keine Migrationen).

**Phasen-Plan:**

- **Phase 0:** UI lokal (Heim-first), Routing weg von Cloudflare. File-backed Persistence.
- **Phase 1:** Frontend API Base Decision (relative Pfade validieren).
- **Phase 2:** Auth API & Sessions (MVP). Implementierung/Freischaltung der Routen.
- **Phase 3:** Migration zu Postgres für Accounts und Sessions.

## Sicherheitsnotizen

- **Token Handling:** Magic Links werden per SMTP versendet
  (oder im Log ausgegeben, wenn `AUTH_LOG_MAGIC_TOKEN=true` für Dev).
- **Proxy Trust:** `AUTH_TRUSTED_PROXIES` muss korrekt konfiguriert sein,
  damit Rate-Limits (IP-basiert) hinter Caddy funktionieren.
- **Abuse:** Rate-Limits für Login-Requests sind in `AppConfig` vorhanden und müssen > 0 sein.
