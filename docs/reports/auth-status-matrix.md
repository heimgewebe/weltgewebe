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
Letzte Aktualisierung: aktuell (geprüft über CI-Guard)

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
| Session               | required    | MVP in-memory | Teil   | hoch    |
| Session Refresh       | required    | unbekannt   | Offen  | hoch    |
| Logout                | required    | MVP Code    | Teil   | mittel  |
| Logout All            | required    | unbekannt   | Offen  | hoch    |
| Devices               | required    | unbekannt   | Offen  | hoch    |
| Step-up Auth          | required    | unbekannt   | Offen  | sehr hoch |
| Passkeys              | optional    | unbekannt   | Offen  | mittel  |
| Sicherheitsinvarianten| required    | tlw. belegt | Teil   | hoch    |

---

## 2. Detailprüfung

### 2.1 Magic Link

**Soll:** POST `/auth/magic-link/request`, POST `/auth/magic-link/consume`, Anti-Enumeration, Token TTL.
**Ist:** implementiert
**Belege:** `apps/web/src/routes/login/+page.svelte`, `verification/verify_magic_link.py`, `docs/runbook.md`
**Fehlende Belege:** keine
**Status:** OK
**Risiko:** niedrig

### 2.2 Session

**Soll:** GET `/auth/session`, Session Cookie (secure, httpOnly), Persistenz.
**Ist:** laut `auth-blueprint.md` abgeschlossen (Phase 3 Session Kern, Phase 4 Middleware), laut `auth-and-ui-routing.md` existiert ein In-Memory MVP. Eine End-to-End-Verifikation fehlt.
**Belege:** `docs/specs/auth-blueprint.md`, `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
**Fehlende Belege:** Echte Persistenz (nicht In-Memory), Cookie-Verhalten, Routen-Tests.
**Status:** Teil
**Risiko:** hoch

### 2.3 Session Refresh

**Soll:** POST `/auth/session/refresh`, verlängert TTL ohne neue Auth.
**Ist:** unbekannt
**Belege:** -
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** hoch

### 2.4 Logout

**Soll:** POST `/auth/logout`
**Ist:** im MVP dokumentiert als implementiert.
**Belege:** `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
**Fehlende Belege:** End-to-End-Test
**Status:** Teil
**Risiko:** mittel

### 2.5 Logout All

**Soll:** POST `/auth/logout-all`
**Ist:** unbekannt
**Belege:** -
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** hoch

### 2.6 Devices

**Soll:** GET `/auth/devices`, DELETE `/auth/devices/:id`, Device-Bindung an Session.
**Ist:** unbekannt
**Belege:** -
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** hoch

### 2.7 Step-up Auth

**Soll:** Challenge-System, TTL, Intent-Binding, Magic Link + Passkey, keine neue Session.
**Ist:** unbekannt
**Belege:** -
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** sehr hoch

### 2.8 Passkeys

**Soll:** register (options + verify), auth (options + verify), list/remove.
**Ist:** unbekannt
**Belege:** -
**Fehlende Belege:** Routen-Code, Test-Case
**Status:** Offen
**Risiko:** mittel

### 2.9 Sicherheitsinvarianten

**Soll:** Anti-Enumeration, Rate Limit, Trusted Proxy Handling, CSRF / Origin, Token Leak Prevention.
**Ist:** Teilweise in Runbook dokumentiert (Rate Limits, Proxies) und laut ADR-0006 vorgesehen, aber Laufzeitnachweise fehlen für alle Aspekte.
**Belege:** `docs/runbook.md` (Rate Limits, Trusted Proxies), `ADR-0006`
**Fehlende Belege:** Automatisierte Tests für CSRF, Anti-Enumeration.
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
Diese Matrix blockiert Drift. Alles was nicht grün (OK) ist, existiert nur als Annahme.
