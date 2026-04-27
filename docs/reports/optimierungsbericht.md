---
id: reports.optimierungsbericht
title: "Optimierungsbericht Weltgewebe"
doc_type: report
status: active
created: 2026-04-19
lang: de
summary: >
  Umfassende Optimierungsanalyse aller Schichten — API, Frontend, Infrastruktur,
  CI/CD, Dokumentation und Domain-Contracts — mit priorisierten
  Handlungsempfehlungen; operative Status- und Aufwandspflege erfolgt in
  docs/reports/optimierungsstatus.md.
relations:
  - type: relates_to
    target: docs/techstack.md
  - type: relates_to
    target: docs/datenmodell.md
  - type: relates_to
    target: docs/policies/agent-reading-protocol.md
  - type: relates_to
    target: docs/reports/optimierungsstatus.md
---

# Optimierungsbericht Weltgewebe

> Umfassende Analyse aller Schichten: API, Frontend, Infrastruktur, CI/CD, Dokumentation, Domain-Contracts.

---

## Statusführung

Dieser Bericht ist die Diagnosequelle, nicht die operative Fortschrittswahrheit.
Der aktuelle Umsetzungsstand der Maßnahmen wird in
`docs/reports/optimierungsstatus.md` geführt.
`done` darf dort nur vergeben werden, wenn Nachweis, reproduzierbarer Test
und keine Restlücke dokumentiert sind. Ohne Guard-/Schema-Prüfung bleibt die
Statusmatrix eine operative Orientierung, keine maschinell erzwungene Wahrheit.

---

## Gesamtbewertung (Diagnose, nicht Fortschrittswahrheit)

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

**Problem:** Sessions liegen ausschließlich in-memory (`RwLock<HashMap>`). Bei jedem Deployment werden alle Nutzer ausgeloggt.

**Empfehlung:** Redis- oder Datenbank-Backend für Sessions einführen. Alternativ: signierte JWT-Tokens als Fallback.

### 1.2 Hoch: Datenbank-Migrationen fehlen

**Problem:** Kein Migrationssystem vorhanden (sqlx-Migrationen oder refinery). Schema-Änderungen sind nicht versioniert.

**Empfehlung:** `sqlx migrate` oder `refinery` einführen. Migrations-Ordner unter `apps/api/migrations/`.

### 1.3 Hoch: Keine echte Paginierung bei Listen-Endpunkten

**Problem:** `/nodes`, `/edges` und `/accounts` unterstützen bereits `?limit=`, aber kein echtes Weiterblättern über mehrere Seiten (Cursor oder Offset). Bei wachsendem Datenbestand fehlen damit konsistente Folgeabrufe und stabile Abfragen über mehrere Requests hinweg.

**Empfehlung:** Cursor- oder Offset-basierte Paginierung mit stabiler Sortierung implementieren (`?cursor=...&limit=50` oder `?offset=...&limit=50`).

### 1.4 Mittel: WebAuthn/Passkeys unvollständig

**Problem:** Framework integriert, aber Verify/Consume-Endpunkte fehlen. Passkey-Registrierung nicht abschließbar.

**Empfehlung:** Endpoints fertigstellen. Persistenz für `webauthn_user_id` hinzufügen.

### 1.5 Mittel: Kein periodischer Cleanup abgelaufener Tokens

**Problem:** Token-/Session-/Challenge-Stores bereinigen nur bei Schreibzugriffen. Bei niedrigem Traffic sammeln sich abgelaufene Einträge an.

**Empfehlung:** Background-Task (Tokio-Interval) für stündlichen Cleanup.

### 1.6 Mittel: Globale RwLocks als Engpass

**Problem:** Alle Sessions, Tokens, Challenges nutzen je einen einzelnen `RwLock`. Bei hoher Concurrency entsteht Lock-Contention.

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

**Problem:** `/src/routes/map/+page.svelte` hat rund 575 Zeilen — Map-Rendering, Overlays, Keyboard-Shortcuts, Daten-Transformation in einer Datei.

**Empfehlung:** Aufteilen in:

- `MapContainer.svelte` (Rendering + Lifecycle)
- `MapOverlays.svelte` (Layer-Management)
- `MapControls.svelte` (Keyboard + UI-Interaktion)
- `MapDataLoader.svelte` (Daten-Fetching + Transformation)

### 2.3 Mittel: Fehlerbehandlung nicht als wiederverwendbare Infrastruktur abstrahiert

**Problem:** Fehlgeschlagene Ressourcen-Fetches geben `loadState`/`resourceStatus` aus, und die Map-UI zeigt bei `partial`/`failed`-Zuständen sichtbare Warnbanner (`role="alert"`). Die Fehlerbehandlung ist jedoch eng an die Map-Route gekoppelt und nicht als generische Error-Boundary oder Toast-Infrastruktur abstrahiert.

**Empfehlung:** Wiederverwendbare Error-Boundary/Toast-Komponente extrahieren, die über alle Routen einsetzbar ist.

### 2.4 Mittel: Typ-Sicherheitslücken

**Problem:** `data?: any` in Selection-Type. API-Responses werden nur mit `isRecord()` geprüft — keine Schema-Validierung.

**Empfehlung:**

- `any` durch konkrete Typen ersetzen
- Zod oder valibot für Runtime-Validierung von API-Responses

### 2.5 Mittel: Zu wenige Unit-Tests

**Problem:** Unit-Tests decken Governance, UI-Invarianten und Guards ab; Map-nahe Module (`basemap.test.ts`, `scene.test.ts`) sind vorhanden. Stores, allgemeine Utils und der größte Teil der Komponenten-Logik sind aber noch nicht ausreichend getestet.

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

**Problem:** `rate_limit`-Direktiven in `Caddyfile.prod` auskommentiert (benötigt Plugin). API-seitiges Rate-Limiting für Login-Requests ist über `governor` vorhanden (`AuthRateLimiter` prüft IP und E-Mail-Hash, gibt bei Limit `429` zurück). Ein zusätzlicher Edge-/Proxy-Layer fehlt jedoch und der Schutz hängt damit von Upstream-LB/WAF ab.

**Empfehlung:** Caddy-Rate-Limit-Plugin aktivieren oder Upstream-Absicherung dokumentieren und als bewusste Architekturentscheidung festhalten.

### 3.2 Hoch: Kein Container-Image-Scanning

**Problem:** `security.yml` generiert SBOM (syft), aber scannt keine Container-Images auf Schwachstellen.

**Empfehlung:** Trivy-Step in `security.yml` hinzufügen (gepinnter Release-Tag oder Commit-SHA — kein `@master`, das ist ein Supply-Chain-Risiko):

```yaml
- name: Trivy scan
  uses: aquasecurity/trivy-action@<gepinnter-release-tag-oder-commit-sha>
```

### 3.3 Niedrig: Dev/Prod PgBouncer-Konfiguration nicht validiert

**Problem:** PgBouncer ist im Dev-Stack vorhanden — `compose.core.yml` verbindet die API über `pgbouncer:6432`. Offen bleibt, ob Dev- und Prod-Konfiguration (Pool-Mode, Pool-Size, Timeouts) regelmäßig auf Parität geprüft werden.

**Empfehlung:** Prod- und Dev-PgBouncer-Konfigurationen explizit vergleichen und Abweichungen dokumentieren oder angleichen.

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

### 4.2 Niedrig: Bundle-Budget-Assertion in `web.yml` nicht als eigener Schritt sichtbar

**Problem:** `ci/budget.json` definiert JS-Budget, TTI und INP. `assert-web-budget.mjs` ist kein Platzhalter — es prüft konkrete Budgetwerte und ist über `apps/web/package.json` im `ci`-Script eingebunden (`node ../../ci/scripts/assert-web-budget.mjs`). Das Script läuft damit bei `pnpm run ci`, ist aber kein benannter, eigenständiger Schritt in `.github/workflows/web.yml`.

**Empfehlung:** Budget-Assertion als expliziten, benannten Step in `web.yml` sichtbar machen, damit Budget-Überschreitungen im CI-Log klar zuordenbar sind.

### 4.3 Mittel: Kein Dependency-Update-Automation

**Problem:** Keine Dependabot- oder Renovate-Konfiguration sichtbar.

**Empfehlung:** Renovate einrichten für automatische Dependency-PRs (Rust + `Node.js`).

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
- `maxLength` je nach Feld (z. B. title: 255, body: 10 000)
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

### 6.1 Hoch: Runbooks vorhanden, aber verstreut und operativ unvollständig

**Problem:** Runbooks existieren (allgemeines Runbook, Observability-Runbook, Selfhost-Deploy-Runbook, Codespaces-Recovery), sind aber nicht als kohärenter Betriebssatz strukturiert. Offen bleiben: standardisierte Rollback-Prozeduren, Incident-Response-Ablauf, Datenbank-Recovery und Alert-Eskalation.

**Empfehlung:** Runbooks unter `docs/runbooks/` konsolidieren; mindestens Incident-Response und Datenbank-Recovery hinzufügen.

### 6.2 Mittel: Blueprint-Status inkonsistent

**Problem:** 6 Blueprints seit 6+ Monaten im Status "draft", werden aber als kanonisch referenziert (z. B. `map-blaupause`, `kartenklarheit`).

**Empfehlung:** Status-Review: Entweder auf "active" setzen oder als explizit unfertig markieren mit Fortschrittsindikator.

### 6.3 Mittel: Statusunklare und verwaiste Dokumente

**Problem:** `cost-report.md` war nicht im Index verlinkt und wird mit diesem PR nachgetragen. Offen bleibt `garnrolle.md`: als deprecated markiert, aber noch in ADR-0003 referenziert — ohne klare Supersession.

**Empfehlung:** Orphan-Report regelmäßig auswerten; für deprecated Dokumente eine Supersession-Relation (`supersedes`) eintragen oder die verweisenden ADRs aktualisieren.

### 6.4 Mittel: Worker/Projector-Schicht nicht dokumentiert

**Problem:** Event-Projection-Pipeline und JetStream-Integration sind geplant, aber ohne Spezifikation.

**Empfehlung:** Spec erstellen, bevor `apps/worker/` implementiert wird.

### 6.5 Mittel: SLOs vorhanden, Alerting-Ableitung fehlt

**Problem:** `policies/slo.yaml` definiert bereits Availability-, Latenz- und Error-Budget-Ziele. Offen ist die operative Ableitung: Prometheus-Alerting-Rules, Eskalationswege und Runbook-Verknüpfung sind nicht dokumentiert bzw. nicht sichtbar verdrahtet.

**Empfehlung:** SLO-Policy mit Prometheus-Alerting-Rules und Observability-Runbook verbinden.

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

**Empfehlung:** Falls Mehrsprachigkeit geplant: i18n-Framework frühzeitig einführen (z. B. `svelte-i18n` oder `paraglide`). Falls nicht: bewusst dokumentieren.

### 7.3 Mittel: JSONL als Datenquelle nicht skalierbar

**Problem:** Knoten, Fäden und Garnrollen werden aus JSONL-Dateien geladen. PostgreSQL ist konfiguriert, wird aber nicht genutzt. Bei wachsendem Datenbestand wird das unhaltbar.

**Empfehlung:** Migration auf PostgreSQL als primäre Datenquelle. JSONL nur noch für Seed/Demo-Daten.

### 7.4 Niedrig: Kein Structured Logging im Frontend

**Problem:** `console.error` statt strukturiertem Logging. Keine Fehler-Telemetrie (Sentry, LogRocket etc.).

**Empfehlung:** Error-Boundary mit Telemetrie-Integration evaluieren.

### 7.5 Niedrig: Kein A11y-Audit

**Problem:** Playwright-Tests prüfen aria-Labels, aber kein systematischer Accessibility-Audit (axe-core, Lighthouse).

**Empfehlung:** `@axe-core/playwright` in E2E-Suite integrieren.

---

## Zusammenfassung: priorisierte nächste Schritte

1. Die operative Statusmatrix in `docs/reports/optimierungsstatus.md` pflegen (mit `nachweis`, `test`, `restlücke`, `zuletzt_geprüft`); verbindlich wird sie erst mit Guard-/Schema-Prüfung.
2. Bereits teilumgesetzte Punkte explizit auf `partial` setzen statt erneut als unqualifiziert „offen“ zu führen.
3. Kritische offene Risiken zuerst bearbeiten: Session-Persistenz, DB-Migrationen, Produktions-Guards, Runtime-Proofs.
4. `done` nur mit reproduzierbarem Code-/Test-/Doku-Nachweis vergeben.
5. Bei fehlender Evidenz den Status als `open` lassen und Lücke explizit benennen (keine stille Interpolation).
