---
id: reports.auth-status-matrix
title: Auth Status Matrix
doc_type: reference
status: active
canonicality: canonical
summary: Wahrheitsfilter und Statusmatrix der Auth-Architektur (Alt-/Ist-Linie vs Ziel-/Soll-Linie) zur Erkennung von Architekturdrift.
---

# Auth Status Matrix – Weltgewebe

Status: aktiv
Zweck: Verifikation der Auth-Architektur gegen ADR-0006 + Specs
Letzte Aktualisierung: manuell gepflegt
Pflegeregel: Diese Matrix ist bei jedem Auth-bezogenen PR zu aktualisieren, der Zielrahmen, Runtime-Verhalten oder Sicherheitsinvarianten verändert.

> Diese Matrix dient als Diagnoseartefakt zur Roadmap.
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

### Runtime-Belege

- `apps/web/src/routes/login/+page.svelte`
- `verification/verify_magic_link.py`
- `docs/runbook.md`

---

## 1. Gesamtübersicht

| Bereich               | Soll (Spec) | Ist (Beleg) | Status | Risiko |
|-----------------------|-------------|-------------|--------|--------|
| Magic Link            | vorhanden   | ✔ belegt    | OK     | niedrig |
| Session               | required    | Code angelegt, E2E offen | Teil   | hoch    |
| Session Refresh       | required    | Runtime-Beleg offen | Offen  | hoch    |
| Logout                | required    | Code angelegt, E2E offen | Teil   | mittel  |
| Logout All            | required    | Runtime-Beleg offen | Offen  | hoch    |
| Devices               | required    | Runtime-Beleg offen | Offen  | hoch    |
| Step-up Auth          | required    | Runtime-Beleg offen | Offen  | sehr hoch |
| Passkeys              | optional    | Runtime-Beleg offen | Offen  | mittel  |
| Sicherheitsinvarianten| required    | teilweise dokumentiert | Teil   | hoch    |

---

## 2. Detailprüfung

### 2.1 Magic Link

**Soll:** POST `/auth/magic-link/request`, POST `/auth/magic-link/consume`, Anti-Enumeration, Token TTL.
**Ist:** implementiert
**Dokumentationsbelege:** `docs/runbook.md`
**Code-/Runtime-Belege:** `apps/web/src/routes/login/+page.svelte`, `verification/verify_magic_link.py`
**Fehlende Belege:** keine
**Status:** OK
**Risiko:** niedrig

### 2.2 Session

**Soll:** GET `/auth/session`, Session Cookie (secure, httpOnly), belastbares Persistenzmodell.
**Ist:** heutige MVP-/Runtime-Linie nutzt `/auth/me` und einen In-Memory Session-Store; Zielarchitektur (`GET /auth/session` mit echter Persistenz) ist noch nicht end-to-end nachgewiesen.
**Dokumentationsbelege:** `docs/specs/auth-blueprint.md`, `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
**Code-/Runtime-Belege:** `apps/api/src/routes/auth.rs`, `apps/api/src/auth/session.rs`, `apps/web/src/lib/auth/store.ts`
**Fehlende Belege:** Echte Persistenz (nicht In-Memory), sauber verifizierbarer Session-Check (`GET /auth/session`), Cookie-Verhalten, Routen-Tests.
**Status:** Teil
**Risiko:** hoch

### 2.3 Session Refresh

**Soll:** POST `/auth/session/refresh`, verlängert TTL ohne neue Auth.
**Ist:** gegen neuen Zielrahmen noch nicht verifiziert.
**Dokumentationsbelege:** keine
**Code-/Runtime-Belege:** keine
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** hoch

### 2.4 Logout

**Soll:** POST `/auth/logout`
**Ist:** im Code angelegt (`/auth/logout` Route); ein aktueller End-to-End-Beleg gegen den neuen Zielrahmen fehlt jedoch.
**Dokumentationsbelege:** `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
**Code-/Runtime-Belege:** `apps/api/src/routes/auth.rs`
**Fehlende Belege:** End-to-End-Test
**Status:** Teil
**Risiko:** mittel

### 2.5 Logout All

**Soll:** POST `/auth/logout-all`
**Ist:** gegen neuen Zielrahmen noch nicht verifiziert.
**Dokumentationsbelege:** keine
**Code-/Runtime-Belege:** keine
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** hoch

### 2.6 Devices

**Soll:** GET `/auth/devices`, DELETE `/auth/devices/:id`, Device-Bindung an Session.
**Ist:** gegen neuen Zielrahmen noch nicht verifiziert.
**Dokumentationsbelege:** keine
**Code-/Runtime-Belege:** keine
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** hoch

### 2.7 Step-up Auth

**Soll:** Challenge-System, TTL, Intent-Binding, Magic Link + Passkey, keine neue Session.
**Ist:** gegen neuen Zielrahmen noch nicht verifiziert.
**Dokumentationsbelege:** keine
**Code-/Runtime-Belege:** keine
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** sehr hoch

### 2.8 Passkeys

**Soll:** register (options + verify), auth (options + verify), list/remove.
**Ist:** gegen neuen Zielrahmen noch nicht verifiziert.
**Dokumentationsbelege:** keine
**Code-/Runtime-Belege:** keine
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** mittel

### 2.9 Sicherheitsinvarianten

**Soll:** Anti-Enumeration, Rate Limit, Trusted Proxy Handling, CSRF / Origin, Token Leak Prevention.
**Ist:** teilweise im Runbook dokumentiert; Laufzeitnachweise fehlen für alle Aspekte.
**Dokumentationsbelege:** `docs/runbook.md` (Rate Limits, Trusted Proxies), `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
**Code-/Runtime-Belege:** keine
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
