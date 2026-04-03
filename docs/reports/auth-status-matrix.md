---
id: reports.auth-status-matrix
title: Auth Status Matrix
doc_type: reference
status: active
summary: Wahrheitsfilter und Statusmatrix der Auth-Architektur (Alt-/Ist-Linie vs Ziel-/Soll-Linie) zur Erkennung von Architekturdrift.
relations:
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
---

# Auth Status Matrix – Weltgewebe

Status: aktiv
Zweck: Verifikation der Auth-Architektur gegen ADR-0006 + Specs
Letzte Aktualisierung: manuell gepflegt
Pflegeregel: Diese Matrix ist bei jedem Auth-bezogenen PR zu aktualisieren, der Zielrahmen, Runtime-Verhalten oder Sicherheitsinvarianten verändert.

> Diese Matrix dient als Diagnoseartefakt zur Roadmap.
> Sie ersetzt nicht den normativen Zielrahmen aus ADR-0006 und den zugehörigen Specs, sondern verdichtet deren Sollzustand gegen den belegten Ist-Zustand.
> Siehe: `docs/blueprints/auth-roadmap.md`

---

## 0. Referenzen & Wahrheitslinien

### Ziel-/Soll-Linie (Kanonischer Zielzustand)

Diese Dokumente beschreiben die finale Architektur, auf die hingearbeitet wird:

- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
- `docs/specs/auth-api.md`
- `docs/specs/auth-state-machine.md`
- `docs/specs/auth-ui.md`

### Brückendokumente / Alt-MVP-Linie

- `docs/blueprints/weltgewebe.auth-and-ui-routing.md`

### Alt-/Ist-Linie (Historische / Implementierte Basis)

Diese Dokumente beschreiben das minimale Fundament und bisher umgesetzte Schritte:

- `docs/adr/ADR-0005-auth.md`
- `docs/specs/auth-blueprint.md`

### Dokumentations- und Betriebsbelege

- `docs/runbook.md`

### Code-, Test- und Verifikationsbelege

- `apps/web/src/routes/login/+page.svelte`
- `verification/verify_magic_link.py`
- `apps/api/src/routes/auth.rs`
- `apps/api/src/auth/session.rs`
- `apps/web/src/lib/auth/store.ts`

---

## 1. Gesamtübersicht

Ein Bereich erhält den Status `Teil` auch dann, wenn ein funktional verwandter Alt-/MVP- oder Codepfad existiert, der Zielcontract aus ADR-0006/Specs aber noch nicht deckungsgleich nachgewiesen ist.

| Bereich               | Soll (Spec) | Ist (Beleg) | Status | Risiko |
|-----------------------|-------------|-------------|--------|--------|
| Magic Link            | vorhanden   | Ziel-Contract migriert, Legacy-Alias aktiv, Runtime-Beleg offen | Teil   | mittel  |
| Session               | required    | API aktiv, In-Memory als bewusste Wahl dokumentiert, E2E offen | Teil   | mittel  |
| Session Refresh       | required    | Route aktiv, Session-Rotation belegt, Token-Split offen | Teil   | mittel  |
| Logout                | required    | verwandter Codepfad vorhanden, Zielrahmen-E2E offen | Teil   | mittel  |
| Logout All            | required    | Challenge belegt, Consume implementiert (LogoutAll-Intent via Step-up-Consume), kein E2E-Email-Flow-Test | Teil   | mittel  |
| Devices               | required    | API aktiv (Liste, Self-Delete), RemoveDevice-Intent via Step-up-Consume implementiert, kein E2E-Email-Flow-Test | Teil   | mittel  |
| Step-up Auth          | required    | Challenge-Store, Request, Consume für Magic-Link implementiert (beide Intents); Passkey-Pfad und UI offen | Teil   | mittel  |
| Passkeys              | optional    | Runtime-Beleg offen | Offen  | mittel  |
| Sicherheitsinvarianten| required    | Codepfade für alle fünf Aspekte implementiert, systematische Smoke-Tests fehlen | Teil   | hoch    |

---

## 2. Detailprüfung

### 2.1 Magic Link

**Soll:** POST `/auth/magic-link/request`, POST `/auth/magic-link/consume`, Anti-Enumeration, Token TTL.
**Ist:** Kanonischer Zielcontract ist auf `/auth/magic-link/*` migriert. Der Legacy-Consume-Pfad `/auth/login/consume` bleibt temporär als Rollout-Migrationsbrücke für in-flight Tokens bestehen. Ein belastbarer Runtime-/E2E-Nachweis des vollständigen Flows unter den neuen Zielrouten ist noch separat zu führen.
**Dokumentationsbelege:** `docs/runbook.md`
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/web/src/routes/login/+page.svelte`, `verification/verify_magic_link.py`
**Fehlende Belege:** erfolgreicher Runtime-/E2E-Nachweis des vollständigen Flows unter den neuen Zielrouten
**Status:** Teil
**Risiko:** mittel

### 2.2 Session

**Soll:** GET `/auth/session`, Session Cookie (secure, httpOnly), belastbares Persistenzmodell.
**Ist:** `GET /auth/session` ist implementiert (inkl. `expires_at` und `device_id`) und durch API-Tests belegt. In-Memory `SessionStore` ist als bewusste Architekturentscheidung für Single-Instance-Betrieb dokumentiert (`auth-roadmap.md`, Phase 2 Persistenzentscheidung). Die `SessionStore`-Schnittstelle erlaubt Migration auf persistenten Adapter ohne Route-Änderungen. Cookie-Transport aktiv; `httpOnly` und `SameSite=Lax` bedingungslos gesetzt; `Secure` standardmäßig aktiv, konfigurierbar über `AUTH_COOKIE_SECURE`.
**Dokumentationsbelege:** `docs/blueprints/auth-roadmap.md` (Persistenzentscheidung), `docs/specs/auth-blueprint.md`, `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/src/routes/mod.rs`, `apps/api/src/middleware/auth.rs`, `apps/api/src/middleware/authz.rs`, `apps/api/tests/api_auth.rs`, `apps/api/src/auth/session.rs`
**Fehlende Belege:** Vollumfängliche Cookie-Sicherheits-Verifikation (z.B. Rotation/Leak-Tests), E2E-Nachweis.
**Status:** Teil
**Risiko:** mittel

### 2.3 Session Refresh

**Soll:** POST `/auth/session/refresh`, verlängert TTL ohne neue Auth.
**Ist:** POST `/auth/session/refresh` ist implementiert und durch API-Tests belegt. Aktuell wird die Session rotiert (alte gelöscht, neue mit gleichem `account_id`/`device_id` erstellt); der Zielrahmen mit separatem Access/Refresh-Token-Split ist noch offen. Die In-Memory-Persistenzentscheidung (siehe Phase 2 Roadmap) gilt auch hier.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/src/routes/mod.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** Vollständiger Token-Split (Access/Refresh), E2E-Nachweis.
**Status:** Teil
**Risiko:** mittel

### 2.4 Logout

**Soll:** POST `/auth/logout`
**Ist:** Ein Logout-Codepfad ist im aktuellen Code vorhanden (`/auth/logout`) und durch API-Tests verifiziert. Ein belastbarer End-to-End-Nachweis gegen den neuen Zielrahmen fehlt jedoch noch.
**Dokumentationsbelege:** `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** End-to-End-Test
**Status:** Teil
**Risiko:** mittel

### 2.5 Logout All

**Soll:** POST `/auth/logout-all`
**Ist:** POST `/auth/logout-all` gibt bei authentifizierten Requests 403 STEP_UP_REQUIRED mit einer gültigen `challenge_id` zurück. Challenge-Erzeugung und Gerätebindung belegt. Die tatsächliche Session-Löschung erfolgt über `POST /auth/step-up/magic-link/consume` mit Intent `LogoutAll` — dieser Pfad ist implementiert und durch Tests belegt.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** End-to-End-Test (logout-all → step-up-request → consume via E-Mail-Flow), keine echte E-Mail in Tests
**Status:** Teil
**Risiko:** mittel

### 2.6 Devices

**Soll:** GET `/auth/devices`, DELETE `/auth/devices/:id`, Device-Bindung an Session.
**Ist:** Device-Management (Liste, Self-Delete) funktional implementiert. Fremdgeräte-Guard erzeugt Challenge mit Ziel- und Gerätebindung. Die Ausführung der Fremdgeräte-Löschung erfolgt über `POST /auth/step-up/magic-link/consume` mit Intent `RemoveDevice` — dieser Pfad ist implementiert und durch Tests belegt.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/src/auth/session.rs`, `apps/api/src/auth/challenges.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** E2E Step-up Auth Integration für Löschung fremder Geräte (vollständiger E-Mail-Flow im Test)
**Status:** Teil
**Risiko:** mittel

### 2.7 Step-up Auth

**Soll:** Challenge-System, TTL, Intent-Binding, Magic Link + Passkey, keine neue Session.
**Ist:** Challenge-Store (In-Memory) implementiert. `/auth/logout-all` und `DELETE /auth/devices/:id` erzeugen Challenges. `POST /auth/step-up/magic-link/request` validiert die Challenge gegen die aktuelle Session und nutzt einen separaten Step-up-Token-Pfad; Mailer-Codepfad ist implementiert. `POST /auth/step-up/magic-link/consume` konsumiert den Step-up-Token (single-use, SHA256-gehasht, 5-Min-TTL), prüft Challenge-Bindung und Session-Bindung, führt den Intent aus (LogoutAll / RemoveDevice), erzeugt dabei keine neue Session. Passkey-Pfad und UI-Integration offen.
**Dokumentationsbelege:** `docs/specs/auth-api.md`
**Code-, Test- und Verifikationsbelege:** `apps/api/src/auth/challenges.rs`, `apps/api/src/routes/auth.rs`, `apps/api/tests/api_auth.rs`, `apps/api/src/auth/step_up_tokens.rs`, `apps/api/src/mailer.rs`
**Fehlende Belege:** Passkey-Pfad, UI Integration
**Status:** Teil
**Risiko:** mittel

### 2.8 Passkeys

**Soll:** register (options + verify), auth (options + verify), list/remove.
**Ist:** Fehlt vollständig im Repo; gegen den neuen Zielrahmen noch nicht verifiziert.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** keine
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** mittel

### 2.9 Sicherheitsinvarianten

**Soll:** Anti-Enumeration, Rate Limit, Trusted Proxy Handling, CSRF / Origin, Token Leak Prevention.
**Ist:** Codepfade für alle fünf Aspekte sind implementiert. Anti-Enumeration: `request_login` gibt identische 200-Responses unabhängig von der Account-Existenz. Rate Limiting: Dual-Layer (IP + E-Mail-Hash) via `AuthRateLimiter`. CSRF: Origin-/Referer-Middleware (`middleware/csrf.rs`) implementiert; punktuell durch API-Test belegt. Trusted Proxy: `effective_client_ip()` mit RFC-7239-Forwarded-Parsing und konfigurierbarer Allowlist (`AUTH_TRUSTED_PROXIES`). Token Leak Prevention: SHA-256-Hashing für Magic-Link- und Step-up-Tokens; Constant-Time-Vergleich punktuell im Magic-Link-Consume-Flow (`routes/auth.rs`). Systematische Sicherheits-Smoke-Tests fehlen.
**Dokumentationsbelege:** `docs/runbook.md` (Rate Limits, Trusted Proxies), `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs` (Anti-Enumeration in `request_login`, Trusted Proxy in `effective_client_ip`, Constant-Time-Vergleich in `consume_login_post`), `apps/api/src/middleware/csrf.rs`, `apps/api/tests/api_auth.rs` (`test_session_refresh_csrf_rejected`), `apps/api/src/auth/rate_limit.rs`, `apps/api/src/auth/tokens.rs` (SHA-256-Hashing), `apps/api/src/auth/step_up_tokens.rs` (SHA-256-Hashing)
**Fehlende Belege:** Kein dedizierter Anti-Enumeration-Test (identische Response für bekannte vs. unbekannte Accounts), keine systematische CSRF-Abdeckung aller mutierenden Endpunkte, kein Runtime-Smoke-Test für Rate Limiting, kein dedizierter Token-Leak-Prevention-Test.
**Status:** Teil
**Risiko:** hoch

---

## 3. Offene Architekturentscheidungen

### /me/email

**Soll:** Route, Methode, Step-up Pflicht, Session-Verhalten danach.
**Ist:** `PUT /auth/me/email` validiert und normalisiert die E-Mail (Format, Eindeutigkeit). Erfordert Step-up Auth (`403 STEP_UP_REQUIRED` mit `challenge_id`). `request_step_up` routet den Token an die NEUE E-Mail. Consume des Intents `UpdateEmail` prüft Eindeutigkeit erneut und ändert die E-Mail der aktuellen Session. Session bleibt erhalten. Damit ist der doppelte Besitznachweis aus bestehender Session und neuer E-Mail-Adresse erbracht.
**Status:** OK

---

## 4. Entscheidungsregel

Kein Feature darf implementiert werden, wenn die Basis (Session) nicht stabil ist oder Step-up/API unklar ist.
Diese Matrix macht Drift sichtbar und verhindert, dass offene Punkte stillschweigend als voll implementiert behandelt werden.
