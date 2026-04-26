---
title: "Optimierungsbericht Weltgewebe"
doc_type: report
status: active
created: 2026-04-19
lang: de
---

# Optimierungsbericht Weltgewebe

> Umfassende Analyse aller Schichten: API, Frontend, Infrastruktur, CI/CD, Dokumentation, Domain-Contracts.

---

## Gesamtbewertung

| Bereich | Score | Einordnung |
|---------|-------|------------|
| Rust API | 8.0/10 | Solide, produktionsreif |
| SvelteKit Frontend | 7.5/10 | Gut strukturiert, Modernisierung offen |
| Infrastruktur & Docker | 7.5/10 | Robuste Guards, kleine Lücken |
| CI/CD Workflows | 7.0/10 | Umfassend, aber redundant |
| Dokumentation | 7.5/10 | Exzellente Governance, operative Lücken |
| Domain Contracts | 7.0/10 | Gute Basis, Validierung unvollständig |
| **Gesamt** | **7.4/10** | **Stabile Basis mit klarem Verbesserungspotenzial** |

---

## 1. Rust API (`apps/api/`)

### 1.1 Kritisch: Session-Persistenz fehlt

**Problem:** Sessions liegen ausschliesslich in-memory (`RWLock<HashMap>`). Bei jedem Deployment werden alle Nutzer ausgeloggt.

**Empfehlung:** Redis- oder Datenbank-Backend für Sessions einführen. Alternativ: signierte JWT-Tokens als Fallback.

### 1.2 Hoch: Datenbank-Migrationen fehlen

**Problem:** Kein Migrationssystem vorhanden (sqlx-Migrationen oder refinery). Schema-Änderungen sind nicht versioniert.

**Empfehlung:** `sqlx migrate` oder `refinery` einführen. Migrations-Ordner unter `apps/api/migrations/`.

### 1.3 Hoch: Keine Paginierung bei Listen-Endpunkten

**Problem:** `/nodes`, `/edges`, `/accounts` liefern alle Einträge auf einmal zurück. Bei wachsendem Datenbestand explodiert der Speicher- und Netzwerkverbrauch.

**Empfehlung:** Cursor-basierte Paginierung implementieren (`?cursor=...&limit=50`).

### 1.4 Mittel: WebAuthn/Passkeys unvollständig

**Problem:** Framework integriert, aber Verify/Consume-Endpunkte fehlen. Passkey-Registrierung nicht abschliessbar.

**Empfehlung:** Endpoints fertigstellen. Persistenz für `webauthn_user_id` hinzufügen.

### 1.5 Mittel: Kein periodischer Cleanup abgelaufener Tokens

**Problem:** Token-/Session-/Challenge-Stores bereinigen nur bei Schreibzugriffen. Bei niedrigem Traffic sammeln sich abgelaufene Einträge an.

**Empfehlung:** Background-Task (Tokio-Interval) für stündlichen Cleanup.

### 1.6 Mittel: Globale RWLocks als Engpass

**Problem:** Alle Sessions, Tokens, Challenges nutzen je einen einzelnen `RWLock`. Bei hoher Concurrency entsteht Lock-Contention.

**Empfehlung:** Sharding nach Account-ID oder `dashmap` / `concurrent-hashmap` evaluieren.

### 1.7 Niedrig: Keine OpenAPI-Spezifikation

**Problem:** API-Dokumentation nur manuell in Markdown. Keine maschinenlesbare Schnittstellenbeschreibung.

**Empfehlung:** `utoipa` oder `aide` für automatische OpenAPI-Generierung aus Axum-Routen.

### 1.8 Niedrig: Hartcodierte TTLs

**Problem:** Session-Dauer (1 Tag), Magic-Link-TTL (15 Min), Challenge-TTL (5 Min) sind hardcoded.

**Empfehlung:** In `AppConfig` externalisieren (ENV-Variablen).

---

## 2. SvelteKit Frontend (`apps/web/`)

### 2.1 Hoch: Svelte 5 Runes nicht genutzt

**Problem:** Svelte 5.53.5 ist installiert, aber die gesamte Codebasis nutzt Legacy-Patterns (Svelte-4-Stores, `$:` Reactive Statements, `createEventDispatcher`). Runes (`$state`, `$derived`, `$effect`, `$props`) kommen nirgends vor.

**Empfehlung:** Schrittweise Migration zu Runes. Priorisierung:
1. Neue Komponenten direkt mit Runes schreiben
2. Stores durch `$state` + `$derived` ersetzen
3. `$:` Blöcke durch `$effect` / `$derived` ablösen

### 2.2 Hoch: Monolithische Map-Komponente

**Problem:** `/src/routes/map/+page.svelte` hat 575 Zeilen — Map-Rendering, Overlays, Keyboard-Shortcuts, Daten-Transformation in einer Datei.

**Empfehlung:** Aufteilen in:
- `MapContainer.svelte` (Rendering + Lifecycle)
- `MapOverlays.svelte` (Layer-Management)
- `MapControls.svelte` (Keyboard + UI-Interaktion)
- `MapDataLoader.svelte` (Daten-Fetching + Transformation)

### 2.3 Mittel: Keine Error Boundaries / Fehleranzeigen

**Problem:** Fehlgeschlagene Ressourcen-Fetches fallen stillschweigend auf leere Arrays zurück. Nutzer sehen keinen Fehlerhinweis.

**Empfehlung:** Error-Toasts oder Banner-Komponente bei `MapResourceStatus !== "ok"`.

### 2.4 Mittel: Typ-Sicherheitslücken

**Problem:** `data?: any` in Selection-Type. API-Responses werden nur mit `isRecord()` geprüft — keine Schema-Validierung.

**Empfehlung:**
- `any` durch konkrete Typen ersetzen
- Zod oder valibot für Runtime-Validierung von API-Responses

### 2.5 Mittel: Zu wenige Unit-Tests

**Problem:** Nur 3 Unit-Test-Dateien (governance, uiInvariants, guards). Stores, Utils und Komponenten-Logik sind untested.

**Empfehlung:** Test-Coverage auf alle Stores und kritische Utils ausweiten. Ziel: >60% Coverage für `/lib/`.

### 2.6 Niedrig: Veraltete/Deprecated Types exportiert

**Problem:** `MapPoint` und `RenderableMapPoint` sind als deprecated markiert, werden aber weiterhin exportiert.

**Empfehlung:** Consumer migrieren, dann entfernen.

### 2.7 Niedrig: Hardcodierte Routen und Magic Strings

**Problem:** Pfade (`/settings`, `/login`) und Rollen-Strings (`"admin"`, `"weber"`) direkt in Komponenten.

**Empfehlung:** Zentrales `routes.ts` und `constants.ts` erstellen.

### 2.8 Niedrig: Console-Logging in Produktion

**Problem:** `console.error`/`console.warn` in mehreren Modulen. Kann sensible Informationen leaken.

**Empfehlung:** Logger-Service mit Environment-Awareness.

---

## 3. Infrastruktur & Docker

### 3.1 Hoch: Rate-Limiting in Caddy-Produktion deaktiviert

**Problem:** `rate_limit`-Direktiven in `Caddyfile.prod` auskommentiert (benötigt Plugin). Login-Endpunkte sind auf Applikationsebene ungeschützt — Schutz wird an Upstream-LB/WAF delegiert, ist aber nicht garantiert.

**Empfehlung:** Entweder Caddy-Rate-Limit-Plugin aktivieren oder API-seitiges Rate-Limiting für Auth-Endpunkte sicherstellen (bereits vorhanden via `governor`, aber Caddy-Layer fehlt).

### 3.2 Hoch: Kein Container-Image-Scanning

**Problem:** `security.yml` generiert SBOM (syft), aber scannt keine Container-Images auf Schwachstellen.

**Empfehlung:** Trivy-Step in `security.yml` hinzufügen:
```yaml
- name: Trivy scan
  uses: aquasecurity/trivy-action@master
```

### 3.3 Mittel: PgBouncer fehlt im Dev-Stack

**Problem:** `compose.core.yml` (dev) verbindet direkt zu PostgreSQL. Produktion nutzt PgBouncer. Dev/Prod-Parität verletzt.

**Empfehlung:** PgBouncer zum Dev-Profil hinzufügen (mit niedrigerem Pool-Size).

### 3.4 Mittel: Relative Volume-Mounts in Produktion

**Problem:** `compose.prod.yml` nutzt `../caddy/Caddyfile.prod` — bricht, wenn aus anderem Verzeichnis gestartet.

**Empfehlung:** Absolute Pfade oder Docker Configs nutzen.

### 3.5 Mittel: Kein Secrets-Management

**Problem:** `.env.prod.example` zeigt `POSTGRES_PASSWORD=change_me`. Keine Vault-Integration, kein Rotationskonzept.

**Empfehlung:** HashiCorp Vault, Docker Secrets oder mindestens dokumentierte Rotationsrichtlinie.

### 3.6 Niedrig: Heterogene Health-Checks

**Problem:** Teils `wget`, teils `curl`. Intervalle variieren (5s, 10s).

**Empfehlung:** Standardisieren auf `curl` + 5s Intervall + 3s Timeout.

### 3.7 Niedrig: Keine Pre-Commit-Hooks

**Problem:** Guards existieren, laufen aber nur in CI. Kein lokales Feedback.

**Empfehlung:** `husky` oder `.git/hooks/pre-commit` mit token-leak-guard und shellcheck.

---

## 4. CI/CD Workflows

### 4.1 Hoch: Workflow-Redundanz

**Problem:** 27 Workflows mit Überschneidungen:
- `web.yml` + `heavy.yml` duplizieren Playwright-Tests
- `ci.yml` + `web.yml` + `api.yml` + `api-smoke.yml` überlappen
- Lychee-Link-Check läuft in `ci.yml`, `docs-guard.yml` und `links.yml`

**Empfehlung:** Workflow-Komposition via `workflow_call` (Setup-once, Run-multiple-Gates). `heavy.yml` nur manuell/label-basiert.

### 4.2 Mittel: Bundle-Budget nicht integriert

**Problem:** `ci/budget.json` definiert JS-Budget (60KB), TTI (2s), INP (200ms) — aber `assert-web-budget.mjs` ist Platzhalter, nicht in Pipeline integriert.

**Empfehlung:** Budget-Assertion in `web.yml` nach Build-Step einhängen.

### 4.3 Mittel: Kein Dependency-Update-Automation

**Problem:** Keine Dependabot- oder Renovate-Konfiguration sichtbar.

**Empfehlung:** Renovate einrichten für automatische Dependency-PRs (Rust + Node).

### 4.4 Niedrig: Kein Branch-Protection dokumentiert

**Problem:** GitHub Branch-Protection-Rules sind nicht in der Repo-Dokumentation erfasst.

**Empfehlung:** In `docs/policies/` oder `.github/` dokumentieren.

---

## 5. Domain Contracts (`contracts/domain/`)

### 5.1 Hoch: `additionalProperties` nicht gesetzt

**Problem:** Die meisten Schemas erlauben implizit unbekannte Properties. Unerwartete Felder werden nicht abgefangen.

**Empfehlung:** `"additionalProperties": false` auf allen Top-Level-Objekten setzen.

### 5.2 Hoch: Keine String-Constraints

**Problem:** Felder wie `title`, `body`, `display_name` haben keine `minLength`, `maxLength` oder `pattern`-Validierung. Leere Strings und unbegrenzte Längen sind möglich.

**Empfehlung:**
- `minLength: 1` für Pflichtfelder
- `maxLength` je nach Feld (z.B. title: 255, body: 10000)
- `pattern` für strukturierte Felder (E-Mail, Domains)

### 5.3 Mittel: Permissions-Feld im Role-Schema zu permissiv

**Problem:** `"additionalProperties": true` ohne Shape-Contract. Jede beliebige Struktur ist gültig.

**Empfehlung:** Permissions-Schema definieren oder mindestens `role.example.json` erstellen.

### 5.4 Mittel: Keine Schema-Versionierung

**Problem:** Kein `$version` oder `$id` mit Versions-URI. Schema-Evolution nicht nachvollziehbar.

**Empfehlung:** `"$id": "https://weltgewebe.net/schemas/node/v1"` + Changelog.

### 5.5 Mittel: Fehlende Audit-Felder

**Problem:** Kein `created_by`, `updated_by` in den meisten Schemas. Keine Basis für Audit-Trails.

**Empfehlung:** Audit-Felder in alle mutierbaren Entitäten aufnehmen.

### 5.6 Niedrig: Keine Field-Descriptions

**Problem:** Die meisten Properties haben keine `description`. Schemas sind ohne externe Dokumentation schwer verständlich.

**Empfehlung:** `description` für jedes Property hinzufügen.

### 5.7 Niedrig: Account-Location-Redundanz

**Problem:** `location` (exakt) und `public_pos` (gefuzzt) sind separate Objekte ohne Constraint, der die Ableitung sicherstellt.

**Empfehlung:** Conditional Schema, das `public_pos` Konsistenz mit `location + radius_m` erzwingt.

---

## 6. Dokumentation

### 6.1 Hoch: Runbooks unvollständig

**Problem:** Nur 3 Runbooks (Codespaces-Recovery, Ops, uv-Tooling). Es fehlen:
- Deployment-Runbook (Blue-Green, Rollback)
- Incident-Response-Runbook
- Monitoring/Alerting-Runbook
- Datenbank-Recovery-Runbook

**Empfehlung:** Mindestens Deployment- und Incident-Response-Runbooks erstellen.

### 6.2 Mittel: Blueprint-Status inkonsistent

**Problem:** 6 Blueprints seit 6+ Monaten im Status "draft", werden aber als kanonisch referenziert (z.B. `map-blaupause`, `kartenklarheit`).

**Empfehlung:** Status-Review: Entweder auf "active" setzen oder als explizit unfertig markieren mit Fortschrittsindikator.

### 6.3 Mittel: Verwaiste Dokumente

**Problem:** `cost-report.md` nicht im Index verlinkt. `garnrolle.md` als deprecated markiert, aber in ADR-0003 referenziert.

**Empfehlung:** Orphan-Report auswerten und Referenzen bereinigen.

### 6.4 Mittel: Worker/Projector-Schicht nicht dokumentiert

**Problem:** Event-Projection-Pipeline und JetStream-Integration sind geplant, aber ohne Spezifikation.

**Empfehlung:** Spec erstellen, bevor `apps/worker/` implementiert wird.

### 6.5 Mittel: Keine SLI/SLO-Definitionen

**Problem:** Kein definiertes Verfügbarkeits-, Latenz- oder Fehlerraten-Ziel. Prometheus-Alerting-Rules nicht dokumentiert.

**Empfehlung:** SLI/SLO-Dokument in `docs/specs/` erstellen.

### 6.6 Niedrig: AGENTS.md ohne Rust/Svelte-Richtlinien

**Problem:** Coding-Guidelines behandeln primär JavaScript/Bash. Keine expliziten Regeln für Rust oder Svelte/TypeScript.

**Empfehlung:** Rust- und Svelte-Abschnitte ergänzen.

---

## 7. Architektur & Übergreifendes

### 7.1 Hoch: Kein Offline-/Resilience-Konzept

**Problem:** Frontend ist eine SPA mit statischem Build, aber kein Service Worker, kein Offline-Cache, kein Retry-Mechanismus bei Netzwerkfehlern.

**Empfehlung:** Service Worker mit Cache-First-Strategie für statische Assets. Retry-Logic für API-Calls.

### 7.2 Mittel: Keine Internationalisierung (i18n)

**Problem:** UI-Texte sind hardcoded (deutsch). Keine i18n-Infrastruktur vorhanden.

**Empfehlung:** Falls mehrsprachigkeit geplant: i18n-Framework frühzeitig einführen (z.B. `svelte-i18n` oder `paraglide`). Falls nicht: bewusst dokumentieren.

### 7.3 Mittel: JSONL als Datenquelle nicht skalierbar

**Problem:** Nodes, Edges, Accounts werden aus JSONL-Dateien geladen. PostgreSQL ist konfiguriert, wird aber nicht genutzt. Bei wachsendem Datenbestand wird das unhaltbar.

**Empfehlung:** Migration auf PostgreSQL als primäre Datenquelle. JSONL nur noch für Seed/Demo-Daten.

### 7.4 Niedrig: Kein Structured Logging im Frontend

**Problem:** `console.error` statt strukturiertem Logging. Keine Fehler-Telemetrie (Sentry, LogRocket etc.).

**Empfehlung:** Error-Boundary mit Telemetrie-Integration evaluieren.

### 7.5 Niedrig: Kein A11y-Audit

**Problem:** Playwright-Tests prüfen aria-Labels, aber kein systematischer Accessibility-Audit (axe-core, Lighthouse).

**Empfehlung:** `@axe-core/playwright` in E2E-Suite integrieren.

---

## Zusammenfassung: Top-10-Prioritäten

| # | Bereich | Massnahme | Aufwand |
|---|---------|-----------|---------|
| 1 | API | Session-Persistenz (Redis/DB) | Mittel |
| 2 | Frontend | Svelte 5 Runes Migration starten | Hoch |
| 3 | API | Datenbank-Migrationen einführen | Niedrig |
| 4 | Contracts | `additionalProperties: false` + String-Constraints | Niedrig |
| 5 | Infra | Container-Image-Scanning (Trivy) | Niedrig |
| 6 | API | Paginierung für Listen-Endpunkte | Mittel |
| 7 | Frontend | Map-Komponente aufteilen (575 Zeilen) | Mittel |
| 8 | CI/CD | Workflow-Redundanz reduzieren | Mittel |
| 9 | Docs | Deployment- und Incident-Runbooks | Niedrig |
| 10 | Architektur | JSONL zu PostgreSQL Migration planen | Hoch |
