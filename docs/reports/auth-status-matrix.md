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
| Session               | required    | verwandter Codepfad vorhanden, Zielrahmen-E2E offen | Teil   | hoch    |
| Session Refresh       | required    | verwandter Codepfad vorhanden, Zielrahmen-E2E offen | Teil   | hoch    |
| Logout                | required    | verwandter Codepfad vorhanden, Zielrahmen-E2E offen | Teil   | mittel  |
| Logout All            | required    | Guard erzeugt Challenge, Consume fehlt              | Teil   | hoch    |
| Devices               | required    | API implementiert, Guard erzeugt Challenge, Consume fehlt   | Teil   | mittel  |
| Step-up Auth          | required    | Challenge-Store aktiv, Consume offen        | Teil   | hoch      |
| Passkeys              | optional    | Runtime-Beleg offen | Offen  | mittel  |
| Sicherheitsinvarianten| required    | teilweise dokumentiert | Teil   | hoch    |

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
**Ist:** Die MVP-Linie nutzt einen In-Memory Session-Store. `GET /auth/session` wurde als API-Endpoint implementiert (inkl. `expires_at` und `device_id`). Deckt dynamische `device_id` ab, aber Persistenzanforderungen (nicht In-Memory) noch nicht.
**Dokumentationsbelege:** `docs/specs/auth-blueprint.md`, `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/src/routes/mod.rs`, `apps/api/src/middleware/auth.rs`, `apps/api/src/middleware/authz.rs`, `apps/api/tests/api_auth.rs`, `apps/api/src/auth/session.rs`
**Fehlende Belege:** Echte Persistenz (nicht In-Memory), vollumfängliche Cookie-Sicherheits-Verifikation (z.B. Rotation/Leak-Tests).
**Status:** Teil
**Risiko:** hoch

### 2.3 Session Refresh

**Soll:** POST `/auth/session/refresh`, verlängert TTL ohne neue Auth.
**Ist:** POST `/auth/session/refresh` ist im MVP implementiert und durch API-Tests belegt; der Zielrahmen mit Persistenz und Token-Split ist noch offen.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/src/routes/mod.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** Echte E2E Persistenz, Vollständiger Token-Split (Access/Refresh)
**Status:** Teil
**Risiko:** hoch

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
**Ist:** POST `/auth/logout-all` gibt nun bei authentifizierten Requests 403 STEP_UP_REQUIRED mit einer gültigen `challenge_id` zurück. Funktionale Session-Löschung nach Challenge-Consume fehlt noch.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** funktionale Session-Löschung nach Challenge-Consume, End-to-End-Test
**Status:** Teil
**Risiko:** hoch

### 2.6 Devices

**Soll:** GET `/auth/devices`, DELETE `/auth/devices/:id`, Device-Bindung an Session.
**Ist:** Das Device-Management ist funktional implementiert; sicherheitskritische Operationen (Löschung fremder Geräte) sind durch STEP_UP_REQUIRED geschützt und erzeugen eine `challenge_id`. Step-up Consume fehlt.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** `apps/api/src/routes/auth.rs`, `apps/api/src/auth/session.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** E2E Step-up Auth Integration für Löschung fremder Geräte
**Status:** Teil
**Risiko:** mittel

### 2.7 Step-up Auth

**Soll:** Challenge-System, TTL, Intent-Binding, Magic Link + Passkey, keine neue Session.
**Ist:** Challenge-Store (In-Memory) implementiert. `/auth/logout-all` und `DELETE /auth/devices/:id` erzeugen nun Challenges. Consume-Pfade und Intent-Binding-E2E fehlen noch.
**Dokumentationsbelege:** keine
**Code-, Test- und Verifikationsbelege:** `apps/api/src/auth/challenges.rs`, `apps/api/src/routes/auth.rs`, `apps/api/tests/api_auth.rs`
**Fehlende Belege:** Consume-Pfade, UI Integration
**Status:** Teil
**Risiko:** hoch

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
**Ist:** teilweise im Runbook dokumentiert; Laufzeitnachweise fehlen für alle Aspekte.
**Dokumentationsbelege:** `docs/runbook.md` (Rate Limits, Trusted Proxies), `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
**Code-, Test- und Verifikationsbelege:** keine
**Fehlende Belege:** Anti-Enumeration-Nachweis fehlt, CSRF-/Origin-Nachweis fehlt, Token-Leak-Prevention nicht separat verifiziert, Trusted-Proxy-/Rate-Limit-Runtime-Nachweis fehlt.
**Status:** Teil
**Risiko:** hoch

---

## 3. Offene Architekturentscheidungen

### /me/email

**Soll:** Route, Methode, Step-up Pflicht, Session-Verhalten danach.
**Ist:** nicht final festgelegt.
**Status:** Offen

---

## 4. Entscheidungsregel

Kein Feature darf implementiert werden, wenn die Basis (Session) nicht stabil ist oder Step-up/API unklar ist.
Diese Matrix macht Drift sichtbar und verhindert, dass offene Punkte stillschweigend als voll implementiert behandelt werden.
