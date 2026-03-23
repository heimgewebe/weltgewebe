---
id: blueprints.weltgewebe.auth-and-ui-routing
title: Auth und UI-Routing
doc_type: reference
status: active
canonicality: derived
summary: Blaupause für Auth-Integration und UI-Routing im Weltgewebe.
related_docs:
  - docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - docs/blueprints/ui-blaupause.md
---
# Blueprint: Heim-first Auth & UI Routing

> **Hinweis:** Dieser Blueprint dient primär als Routing-/Diagnose-Werkzeug zur
> Auflösung historischer Split-Brain-Zustände und ist **kein** Bestandteil der
> Endarchitektur für Authentifizierung. Maßgeblich für Auth ist
> [ADR-0006](../adr/ADR-0006__auth-magic-link-session-passkey.md).

## Historischer Kontext (Split-Brain)

Dieser Blueprint löst einen historischen "Split-Brain"-Zustand auf, bei dem die UI
noch über Cloudflare Pages ausgeliefert wurde und Authentifizierungsaufrufe ins Leere (`405 Method Not Allowed`) liefen.
Die Abhängigkeit vom Internet für UI-Assets und die inkonsistente Umgebung wurden
durch die Etablierung des Heimservers als primäre Frontdoor aufgelöst.

## Kanonische Realität

Das Heimnetz (`.home.arpa`) ist die primäre Authority für UI und Identität.

### 1. Routing-Invarianten

- **User Entry:** `https://weltgewebe.home.arpa/`
  → Lokales Frontend (Container `weltgewebe-web` oder statisch via Caddy). Kein Cloudflare-Proxy.
- **User API:** `https://weltgewebe.home.arpa/api/*`
  → Lokales API (Service: `api:8080`).
- **Host Debug (Local Dev Only):** `http://127.0.0.1:8081`
  → Host-Mapped Port (nur in lokalen Entwicklungsumgebungen).
  Weltgewebe publiziert produktiv keine Ports wie 8081.

### 2. Identity & Auth API

Die Identität wird heimisch verwaltet.

- **Status:** **ZIEL / BLUEPRINT**
- **Fehlerbilder (Diagnose):**
  - **405 Method Not Allowed:** Symptom für Non-API Pfade (`/login`), die noch bei Cloudflare/Pages landen
    (Header `server: cloudflare`).
  - **404 Not Found:** Symptom für `/api/auth/*` Pfade, wenn der Reverse-Proxy korrekt ist
    (Header `server: Caddy`), aber die Route im Backend fehlt.
    *Hinweis: Proxy/Upstream kann mit `/api/health/ready` (200 OK) gegengeprüft werden; betroffen sind spezifisch die Auth-Routen.*
  - **Zielzustand:** POST `/api/auth/magic-link/request` liefert **200 OK** oder **429 Too Many Requests**.

- **Auth-Endpunkte (Soll):** Müssen explizit exposed sein.
  *Hinweis: Exakte Auth-Routen im Backend sind gegen `apps/api/src/routes/auth.rs` zu verifizieren (rg),*
  *bevor UI implementiert wird.*
  - `POST /api/auth/magic-link/request` (Magic Link anfordern)
  - `GET/POST /api/auth/magic-link/consume` (Magic Link einlösen)
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
