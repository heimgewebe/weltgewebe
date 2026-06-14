---
id: reports.passkey-register-verify-prep
title: Passkey Register-Verify – Vorbereitungsbericht
doc_type: report
status: active
summary: >
  Diagnose- und Vorbereitungsbericht für POST /auth/passkeys/register/verify.
  Dokumentiert den belegten Ist-Zustand, offene Persistenzfragen,
  Testmatrix und die Folge-PR-Entscheidung. Kein Feature-Code.
relations:
  - type: relates_to
    target: docs/blueprints/auth-roadmap.md
  - type: relates_to
    target: docs/specs/auth-api.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
  - type: relates_to
    target: docs/adr/ADR-0006__auth-magic-link-session-passkey.md
---

# Passkey Register-Verify – Vorbereitungsbericht

**Datum:** 2026-05-10
**Autor:** Agent (Diagnose-PR)
**Typ:** Vorbereitungsbericht — kein Feature-Code

---

## 1. Zweck

Dieser Bericht bereitete den Folge-PR für `POST /auth/passkeys/register/verify` vor und dient jetzt zusätzlich als Diagnose- und Nachtragsdokument für den ersten positiven Lauf.

Er enthält ausschließlich:

- den belegten Ist-Zustand aus echten Quellen (kein interpolierter Laufzeit-Beweis)
- offene Persistenz- und Designfragen
- eine Testmatrix für den Folge-PR
- eine begründete Folge-PR-Empfehlung (Pfad A, B oder C)

Er enthält **nicht**:

- WebAuthn-Verify-Implementierung
- Credential-Persistenz
- UI-Aktivierung
- Session-Persistenz
- DbSessionStore

---

## 2. Belegter Ist-Zustand

### 2.1 Existierende Passkey-Dateien und Funktionen

| Datei | Inhalt | Status |
|---|---|---|
| `apps/api/src/auth/passkeys.rs` | `build_webauthn()`, `PasskeyRegistrationStore`, `start_passkey_registration()`, 7 Unit-Tests | implementiert |
| `apps/api/src/routes/auth.rs` | `passkey_register_options` Handler (Zeile 1560 ff.) | implementiert |
| `apps/api/src/routes/accounts.rs` | `webauthn_user_id: Uuid` am `AccountInternal`-Struct (Zeile 84), Lazy-Backfill beim Laden (Zeile 299–315) | implementiert |
| `apps/api/src/config.rs` | `webauthn_rp_id`, `webauthn_rp_origin`, `webauthn_rp_name` | implementiert |
| `apps/web/src/lib/components/AccountSection.svelte` | deaktivierter Passkey-Eintragspunkt (`data-testid="account-section-passkey"`, `data-testid="account-section-passkey-cta"`) | Stub, deaktiviert |
| `apps/web/tests/account-section.spec.ts` | Test „passkey entry stub is present and disabled" (Zeile 216) | belegt |

### 2.2 Register-Options – aktueller Zwischenstand

`POST /auth/passkeys/register/options` ist vorhanden, startet die WebAuthn-Ceremony
aber noch **nicht** aus einer Session allein. Der Endpunkt antwortet derzeit fail-closed:

```json
{
  "error": "STEP_UP_REQUIRED",
  "challenge_id": "<opaque UUID>"
}
```

- Die Response erzwingt einen `BeginPasskeyRegistration`-Challenge-Kontext für dieselbe Session.
- Der Challenge-Store re-used vorhandene aktive Challenges für dieselbe Kombination aus `account_id`, `device_id` und Intent.
- Ohne zusätzlichen Registration-Grant/Handoff erzeugt der Endpunkt **keine** `registration_id` und startet **keine** WebAuthn-Creation-Challenge.
- `PasskeyRegistrationStore` und WebAuthn-Optionserzeugung bleiben vorbereitete Folgearbeit hinter dem noch offenen Handoff.
- Bestehende Credential-IDs werden grundsätzlich aus `PasskeyStore` abgeleitet; ihre reale Wirkung greift aber erst, sobald die Ceremony tatsächlich gestartet werden kann.

**4 Integrationstests belegt** in `apps/api/tests/api_auth.rs` (ab Zeile 3390):

| Test | Prüft |
|---|---|
| `passkey_register_options_requires_authentication` | Kein Cookie → 401 |
| `passkey_register_options_returns_503_when_not_configured` | WebAuthn nicht konfiguriert → 503 `PASSKEYS_NOT_CONFIGURED` |
| `passkey_register_options_requires_step_up_challenge` | Authentifizierte Session erhält `403 STEP_UP_REQUIRED`; Challenge ist als `BeginPasskeyRegistration` gespeichert |
| `passkey_register_options_reuses_active_step_up_challenge` | Wiederholter Aufruf derselben Session re-used dieselbe aktive Challenge |

### 2.3 PasskeyRegistrationStore

Implementiert in `apps/api/src/auth/passkeys.rs` (Zeile 89–145):

- **Typ:** In-Memory, `Arc<RwLock<HashMap<String, PendingRegistration>>>`
- **TTL:** 5 Minuten (`REGISTRATION_TTL_SECS = 300`)
- **`insert(account_id, PasskeyRegistration)`:** erzeugt opake UUID, legt State ab, gibt `registration_id` zurück
- **`consume(registration_id, account_id)`:** single-use, account-gebunden, gibt `PasskeyRegistration` zurück
  - Abgelaufene Einträge → `None` + Cleanup
  - Falscher Account → `None`, Eintrag bleibt erhalten (non-destructive rejection, belegt durch Unit-Test)
- **Unit-Tests belegt:** insert/consume, wrong-account, wrong-account-does-not-burn-registration

### 2.4 webauthn_user_id – Persistenzstatus

- **Typ:** `Uuid` (v4), dediziert pro Account, **nicht** aus `account_id` abgeleitet
- **Laden:** `accounts.rs` liest `webauthn_user_id` aus der JSON-Datenquelle (falls vorhanden).
  - Nicht vorhanden: Lazy Backfill via `Uuid::new_v4()` — prozessstabil, aber **nicht datenquellen-stabil**
- **Kritisch:** Ein generierter (nicht persistierter) Wert verschwindet nach Neustart. Registrierte Passkeys wären dann nicht mehr ihrem Account zuordenbar.
- **Kommentar in Code** (`accounts.rs` Zeile 301): „Once passkey registration is implemented (register-verify), the generated webauthn_user_id MUST be persisted back to the account data source so that registered passkeys remain bound to the correct identity across restarts."
- **Status:** `AccountStore.update_webauthn_user_id(account_id, uuid)` ist implementiert und getestet; der tatsächliche Datenquellen-Writeback bleibt bis `register/verify` offen.

### 2.5 Credential-Speicher

Es existiert ein langlebiger In-Memory-Credential-Speicher für abgeschlossene Passkey-Registrierungen:

- `PasskeyStore` in `apps/api/src/auth/passkeys.rs` (account-gebunden, duplicate detection, list/find/remove)
- Keine TTL, kein single-use (bewusst **kein** Challenge-Store)
- Kein Datenbankschema
- Credentials bleiben nur bis Prozessneustart erhalten (Phase-4-Minimalpfad)

---

## 3. Pfad-Konvention

Dieser Bericht spricht durchgehend vom kanonischen **Backend-Pfad** aus der API-Spezifikation:

```text
POST /auth/passkeys/register/verify
```

Falls der Endpunkt im Frontend oder durch den Reverse Proxy unter `/api/auth/...` erreichbar ist, gilt das nur als technische Mount- oder Proxy-Ebene. Die fachliche Spezifikation in diesem Bericht meint durchgehend `/auth/passkeys/register/verify` ohne API-Präfix.

---

## 4. Endpoint-Zielbild

### Geplanter Endpoint

```text
POST /auth/passkeys/register/verify
```

### Erwartete Eingabe

```json
{
  "registration_id": "<opaque UUID aus register/options>",
  "credential": { ... }
}
```

`credential` entspricht der `RegisterPublicKeyCredential`-Struktur aus dem WebAuthn-Standard (output von `navigator.credentials.create()`).

### Erwartete Wirkung

Folgende Schritte sind klar:

1. **Session prüfen** — keine aktive Session → `401 UNAUTHORIZED`
2. **`registration_id` auflösen** — `PasskeyRegistrationStore.consume(registration_id, account_id)` aufrufen
   - Nicht gefunden oder abgelaufen → `400 BAD_REQUEST`
   - Account-Mismatch → `400 BAD_REQUEST`
3. **WebAuthn-Antwort prüfen** — `webauthn.finish_passkey_registration(credential, &reg_state)`
   - Mismatch → `400 BAD_REQUEST` oder `422 UNPROCESSABLE_ENTITY`
4. **Credential persistieren** — erzeugtes `Passkey`-Objekt in Credential-Store ablegen (account-gebunden)
5. **`webauthn_user_id` zurückschreiben** — falls lazily generiert, jetzt in Datenquelle persistieren
6. **Antwort:** `200 OK` mit minimaler Bestätigung

**Step-up-Handoff-Entscheidung:** siehe separater Abschnitt unten.

**Keine Login-Semantik** — kein Cookie, kein neuer Session-Token, keine Umleitung.

### Step-up-Handoff — Entscheidung und Scope-Grenze

**Problem:** Passkey-Registrierung ist eine sensitive Operation. Laut `docs/specs/auth-api.md` (Zeile 254) erfordern `POST /auth/passkeys/register/*` einen Step-up-Authentifizierungsnachweis.

Der bestehende Step-up-Mechanismus erzeugt **aktionsgebundene Challenges**: `POST /auth/step-up/magic-link/consume` konsumiert einen Step-up-Token einmalig und **führt dabei direkt die gebundene Aktion aus** (z.B. `LogoutAll`, `RemoveDevice`). Der Mechanismus hinterlässt danach keinen wiederverwendbaren "Step-up ist erledigt"-Marker oder Session-Flag für einen später aufgerufenen Handler.

**Konsequenz:** Für `register/verify` muss **vor der Implementierung** entschieden werden, wie der Step-up-Nachweis erbracht und an den Endpunkt übergeben wird. Es gibt mindestens drei Lösungsansätze:

- **Pfad A (bevorzugt):** Step-up vor `register/options` erzwingen. Der Nutzer durchläuft den Step-up-Pfad (Magic Link, Consume mit Intent `BeginPasskeyRegistration`), bevor die WebAuthn-Ceremony überhaupt beginnt. Dann ist `register/verify` ein reiner Verify-Handler ohne sekundären Step-up-Bedarf.
  
- **Pfad B:** Neuen one-time Step-up-Grant einführen. `register/verify` akzeptiert einen Step-up-Token explizit als Eingabeparameter (z.B. `{ "registration_id": "...", "credential": {...}, "step_up_token": "..." }`). Der Handler prüft den Token und führt Registration + Credential-Persistenz durch. Erfordert neue Semantik im Step-up-System.

- **Pfad C:** Direkte Integration in `consume_step_up`. `POST /auth/step-up/magic-link/consume` mit Intent `RegisterPasskey` würde nicht nur die Challenge verarbeiten, sondern **auch** `registration_id` und `credential` als Payload erhalten und direkt die Registrierung absolvieren. Erfordert erhebliche Umstrukturierung.

**Entscheidung:** Pfad A bleibt Zielbild (Step-up vor `register/options`).

**Umsetzung in diesem PR:** Neuer Intent `BeginPasskeyRegistration` ist im Step-up-System ergänzt und im Consume-Pfad getestet (session-neutral, keine Nebenwirkungen). `register/options` erzwingt bereits fail-closed `STEP_UP_REQUIRED` mit `challenge_id`, startet ohne Registration-Grant aber noch keine Ceremony.

**Stop-Kriterium für diesen PR:** Keine Halb-Integration von `register/options` in den bestehenden Step-up-Flow ohne klaren Handoff-Mechanismus; kein `register/verify`-Handler in diesem Scope.

---

## 5. Persistenzfragen

### 4.1 Credential-Speicher

| Frage | Stand |
|---|---|
| Wo werden `Passkey`-Objekte gespeichert? | In `PasskeyStore` (langlebiger In-Memory-Store, account-gebunden) |
| In-Memory vs. persistiert? | Für Phase 4 (Single-Instance, In-Memory-Arch.) wäre ein In-Memory-Store möglich, aber Neustarts verlieren alle Credentials |
| Datenbankschema? | Nicht vorhanden; ab Phase 4 (DB-Persistenz) nötig |
| Welche Felder? | `account_id`, `credential_id`, `passkey` (serialisiertes `Passkey`-Objekt), `created_at`, optional `nickname` |

**Mindestanforderung für `register/verify`:** Ein `PasskeyStore` (analog zu `PasskeyRegistrationStore`, aber langlebig, nicht TTL-basiert), der pro Account eine Liste von `Passkey`-Objekten hält.

### 4.2 webauthn_user_id Writeback

| Frage | Stand |
|---|---|
| Stabil über Neustarts? | **Nein** bei lazy-generierten Werten |
| Wann muss Writeback erfolgen? | Spätestens beim ersten `register/verify` |
| Welche Datei? | `apps/api/src/auth/accounts.rs` — `AccountStore.update_webauthn_user_id(account_id, uuid)` implementiert |
| Folgerisiko ohne Writeback? | Registrierte Passkeys verlieren ihren Account-Anker nach Neustart |

### 4.3 Was darf nicht in-memory bleiben

- `webauthn_user_id` nach erster Passkey-Registrierung — muss in Datenquelle zurückgeschrieben werden
- Credential-Objekte nach `finish_passkey_registration` — müssen dauerhaft abgelegt werden

Solange keine DB-Persistenz existiert (Phase 4 → folgt aus Phase 4/5-Roadmap), ist ein langlebiger In-Memory-`PasskeyStore` die Minimalanforderung. Er verliert Credentials bei Neustart — das ist für Phase 4 akzeptierbar, wenn dokumentiert.

---

## 5. Testmatrix für den Folge-PR

Jeder Test muss im Folge-PR als benannter `#[tokio::test]` in `apps/api/tests/api_auth.rs` belegt sein.

| # | Testfall | Erwartetes Ergebnis |
|---|---|---|
| T1 | Gültige Registrierung (korrekte credential, gültige registration_id, aktive Session) | `200 OK`, Credential im Store, webauthn_user_id stabil |
| T2 | Keine Session | `401 UNAUTHORIZED` |
| T3 | Step-up-Handoff-Semantik (abhängig von Pfad A/B/C aus Abschnitt 4.3) | Ergebnis hängt von der in Abschnitt 4.3 getroffenen Designentscheidung ab |
| T4 | Unbekannte `registration_id` | `400 BAD_REQUEST` |
| T5 | Abgelaufene `registration_id` (TTL > 5 Min) | `400 BAD_REQUEST` |
| T6 | `registration_id` gehört anderem Account | `400 BAD_REQUEST` |
| T7 | Challenge/Credential-Mismatch (manipuliertes `credential`) | `400 BAD_REQUEST` oder `422` |
| T8 | WebAuthn nicht konfiguriert | `503 PASSKEYS_NOT_CONFIGURED` |
| T9 | Credential-Duplikat (selbe `credential_id` bereits registriert) | `409 CONFLICT` oder explizit dokumentierte Semantik |
| T10 | Magic-Link-Pfad nach `register/verify` weiterhin grün | bestehende `passkey_register_options_*`-Tests und Magic-Link-Tests müssen bestehen bleiben |

**Nicht in dieser Matrix:** Passkey-Auth-Flow, Passkey-Remove, UI-E2E-Tests.

---

## 7. Nicht-Ziele

Dieser PR und der direkte Folge-PR decken folgendes **nicht** ab:

- `POST /auth/passkeys/auth/options` — Passkey-Login-Initiation
- `POST /auth/passkeys/auth/verify` — Passkey-Login-Verifikation
- `GET /auth/passkeys` — Passkey auflisten
- `DELETE /auth/passkeys/:id` — Passkey entfernen
- UI-Aktivierung des Passkey-Buttons in `AccountSection.svelte`
- Service Worker
- Session-Persistenz / DbSessionStore
- Datenbankschema (solange Phase 4 In-Memory-Architektur gilt)
- Step-up-Dialog im Frontend

---

## 8. Folge-PR-Entscheidung

### Bewertung der Pfade

#### Pfad A — direkt `feat(auth): implement passkey register verify`

Blockiert durch:

- Kein persistenter (restart-fester) Credential-Store (In-Memory-`PasskeyStore` vorhanden; Persistenz ist Voraussetzung für Produktion, nicht Blocker für Entwicklungsphase)
- Kein finaler Datenquellen-Writeback von `webauthn_user_id` im Register-Verify-Pfad
- Keine festgelegte WebAuthn-Teststrategie für `finish_passkey_registration`

Pfad A war nicht direkt gangbar wegen offenem Step-up-Handoff — **dieser ist nun implementiert**. Verbleibende Offenposten für den nächsten `register/verify`-PR: Verify-Implementierung, Datenquellen-Writeback im Verify-Pfad und offene WebAuthn-Teststrategie.

---

#### Pfad B — Datenmodell-/Store-PR *(umgesetzt durch diesen PR)*

Pfad B ist implementiert:

1. `PasskeyStore` (in-memory, langlebig, account-gebunden) in `apps/api/src/auth/passkeys.rs` ✅
2. `AccountStore`-Mutation: `update_webauthn_user_id(account_id, uuid)` in `apps/api/src/auth/accounts.rs` ✅
3. Step-up-Handoff-Zielbild entschieden (Pfad A: Step-up vor `register/options`) ✅
4. `BeginPasskeyRegistration`-Intent ergänzt; Consume erzeugt `registration_grant_id` ✅
5. Unit-Tests für `PasskeyStore`, `AccountStore`-Mutation und WebAuthn-Builder ✅

Abgeschlossen aus Pfad B: vollständiger Step-up-Handoff (Grant/State-Erzeugung für `register/options`) — **implementiert durch `feat(auth): add passkey registration step-up grant handoff`**.

---

#### Pfad C — zuerst WebAuthn-Test-Fixtures/Mocks

Das `webauthn_rs`-Crate erfordert echte kryptografische Operationen. Test-Fixtures (vorberechnete `RegisterPublicKeyCredential`-Objekte) müssten generiert und festgekodiert werden. Das ist möglich, aber aufwendig und fragil bei Library-Updates.

Pfad C ist nachgelagert — sinnvoll als Teil des Folge-PR, nicht als separater vorgelagerter PR.

---

### Empfehlung

**Pfad B ist umgesetzt.** Damit ist Pfad A jetzt gangbar. Der nächste sinnvolle Schritt ist:

```text
feat(auth): implement passkey register verify endpoint
```

**Status:** Umgesetzt durch den genannten Folge-PR. Endpunkt `POST /auth/passkeys/register/verify` ist registriert, ruft `webauthn.finish_passkey_registration(...)` mit echter Kryptoprüfung auf, konsumiert die `registration_id` single-use, legt das Credential im `PasskeyStore` ab (mit Duplicate-Detection → `409 CONFLICT`) und schreibt `webauthn_user_id` zurück. Erfolg liefert `200 OK {"ok": true}` ohne Session/Cookie. Negativpfade (T2 401, T4/T6/T7 400, T8 503) sind getestet. T1 (positiver Pfad) ist durch CI belegt; T9 (expliziter API-Proof für Credential-Duplikate) bleibt offen; die Implementierung enthält bereits Duplicate-Detection im `PasskeyStore` mit `409 CONFLICT`.

---

## 9. Stop-Kriterium für den Folge-PR

Der `register/verify`-Implementierungs-PR darf erst starten, wenn:

| Kriterium | Status |
|---|---|
| `PasskeyStore` mit Insert/Get/Remove implementiert und getestet | **belegt** |
| `AccountStore.update_webauthn_user_id()` implementiert | **belegt** |
| Step-up-Handoff-Zielbild entschieden | **belegt (Pfad A: Step-up vor `register/options`)** |
| Step-up-Handoff technisch realisiert | **belegt** — `PasskeyRegistrationGrantStore` (TTL 5 Min, single-use, account/device-gebunden); `BeginPasskeyRegistration`-Consume erzeugt Grant; `register/options` konsumiert Grant und startet Ceremony |
| Test-Fixtures-Strategie für `finish_passkey_registration` entschieden | **teilweise obsolet** — lokaler Browser-/Virtual-Authenticator-Proof existiert; für CI bleibt die Stabilisierung des Browser-Pfads offen |
| UI bleibt deaktiviert (`account-section-passkey-cta` disabled, Test grün) | **belegt** (Zeile 227 in account-section.spec.ts) |
| Magic-Link-Pfad bleibt grün | **belegt** (api_auth.rs) |

---

## 10. Nachtrag 2026-05-27 — Positiver Lokalbeweis

Der zuvor offene positive Register-Verify-Pfad wurde in diesem Schritt lokal mit einem echten Browser-/Authenticator-Flow belegt. Der spätere CI-Beleg ist in Abschnitt 10b dokumentiert.

- Proof-Pfad: Step-up-/Grant-Handoff zu `POST /auth/passkeys/register/options`, echte Browser-Credential über `navigator.credentials.create(...)`, danach `POST /auth/passkeys/register/verify`
- Transport: Playwright + Chromium, CDP-`WebAuthn.enable` und `WebAuthn.addVirtualAuthenticator`
- Belegt: `200 OK {"ok": true}`, kein `Set-Cookie` auf `register/verify`, Session-Cookie bleibt unverändert, Credential wird im `PasskeyStore` sichtbar
- Einstufung zum Zeitpunkt dieses Nachtrags: lokaler Browser-/Authenticator-Proof; der spätere CI-Beleg ist in Abschnitt 10b dokumentiert.

---

## 10a. Nachtrag 2026-05-28 — CI-Job hinzugefügt

Der dedizierte CI-Job für denselben positiven Browser-Proof ist hinzugefügt.

- Workflow: `.github/workflows/auth-passkey-register-proof.yml`
- Job: `auth-passkey-register-proof`
- Trigger: `pull_request` und `push` auf `main` mit Pfaden, die den Proof-Stack betreffen (kein `if:`-Guard, kein workflow_dispatch-only)
- Schritt: `pnpm test:proof:auth-passkey-register` aus `apps/web`
- API-Start: über `playwright.auth.proof.config.ts` mit `cargo run --locked --features integration-testing` (Pre-Build-Schritt im Workflow)
- Toolchain: Rust aus `toolchain.versions.yml`, Node aus `.node-version`, pnpm 9.11.0, Playwright Chromium mit System-Deps
- Scope-Trennung: der Job führt ausschließlich `passkey-register-positive.proof.ts` aus. Der Basemap-Proof bleibt in `.github/workflows/basemap-runtime-proof.yml`; `playwright.proof.config.ts` bleibt auf `basemap-real-hamburg-visual.proof.ts` beschränkt.
- Erwartete Proof-Summary: `register_options_status: 200`, `register_verify_status: 200`, `register_verify_set_cookie: null`, `session_cookie_unchanged: true`, `stored_credential_reflected: true`, `virtual_authenticator_credentials > 0`
- Statuslogik zum Zeitpunkt dieses Nachtrags: CI-Job hinzugefügt; grüner Lauf stand noch aus. Der spätere erfolgreiche CI-Lauf ist in Abschnitt 10b dokumentiert.

## 10b. Nachtrag 2026-06-14 — CI-Proof erfolgreich

- Workflow: `auth-passkey-register-proof`
- Run: [`27487642565`](https://github.com/heimgewebe/weltgewebe/actions/runs/27487642565)
- Commit: `cc54460`
- Branch: `main`
- Conclusion: `success`
- Im Run gelistete Artefakte:
  - `auth-passkey-register-proof-summary`
  - `auth-passkey-register-proof-report`
  - `auth-passkey-register-proof-traces`

Dieser CI-Proof belegt den positiven Passkey-Register-Verify-Pfad mit Browser-/Authenticator-Flow. Er belegt nicht den Passkey-Login-Flow (`auth/options`, `auth/verify`), UI-Aktivierung, Passkey-Management oder dauerhafte Runtime-Credential-Persistenz.

---

## 11. Diagnoseausgaben (Rohdaten)

### git status --short

```text
(clean — keine uncommitted changes vor diesem PR)
```

### rg passkey/webauthn (Relevante Treffer)

**Backend:**

- `apps/api/src/auth/passkeys.rs` — Hauptmodul (7 Unit-Tests)
- `apps/api/src/routes/auth.rs` — `passkey_register_options` (Zeile 1560), Step-up-Infrastruktur
- `apps/api/src/routes/accounts.rs` — `webauthn_user_id: Uuid` (Zeile 84), Lazy-Backfill (Zeile 299–315)
- `apps/api/tests/api_auth.rs` — 4 Integrationstests für `register/options` und den fail-closed-Step-up-Gate
- `apps/api/tests/auth_ratelimit_proxy_untrusted.rs` — `webauthn: None`, `passkey_registrations: Default::default()` (Test-Fixtures)
- `apps/api/tests/api_nodes.rs` — `webauthn_user_id: uuid::Uuid::new_v4()` (Test-Fixtures)

**Frontend:**

- `apps/web/src/lib/components/AccountSection.svelte` — deaktivierter Passkey-Stub
- `apps/web/tests/account-section.spec.ts` — Tests für Passkey-Stub (Zeile 114, 216, 227)

**Dokumentation:**

- `docs/blueprints/auth-roadmap.md` — Phase 4 (Zeile 257 ff.)
- `docs/specs/auth-api.md` — `register/verify` als geplanter Endpoint (Zeile 234)
- `docs/reports/auth-status-matrix.md` — Passkey-Abschnitt (2.8)
- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md` — kanonischer Zielrahmen

### rg STEP_UP_REQUIRED / step-up / devices

**Backend:**

- `apps/api/src/routes/auth.rs` — Step-up erzeugt bei `logout-all` (Zeile 910, 918), `devices/:id` (Zeile 1234), `me/email` (Zeile 1013)
- `apps/api/tests/api_auth.rs` — umfangreiche Integrationstests für alle Step-up-Pfade

**Frontend:**

- `apps/web/src/lib/components/AccountSection.svelte` — Step-up-Request bei logout-all (Zeile 109–113), devices-Liste (Zeile 56–77)
- `apps/web/tests/account-section.spec.ts` — `STEP_UP_REQUIRED` (Zeile 30), `logout-all` (Zeile 79), `devices` (Zeile 53)

**Step-up für Passkey-Register:** In `auth-api.md` Zeile 254 gelistet als step-up-pflichtige Operation. Intent `BeginPasskeyRegistration` ergänzt (Consume-Pfad, ohne Grant/State-Erzeugung). Vollständiger Handoff vor `register/options` ist eigenständiger Folge-PR.

### make docs-guard (ci-validate)

Vor diesem Bericht:

```text
validate_schema:    PASS (0 errors)
check_repo_index:   PASS (0 errors, 0 warnings)
validate_relations: FAIL (1 error, pre-existing)
  → docs/reports/auth-persistence-next-step.md: relations[0]: unknown relation type 'updates'
```

Der `validate_relations`-Fehler ist **pre-existing** und nicht durch diesen PR verursacht. Er betrifft `auth-persistence-next-step.md`, nicht diese Datei. Die vorliegende Datei verwendet ausschließlich erlaubte Relationstypen (`relates_to`).

---

## 11. Restlücken

| Lücke | Konsequenz |
|---|---|
| Finaler Step-up-Handoff vor `register/options` fehlt | Geschlossen — `BeginPasskeyRegistration`-Consume erzeugt `registration_grant_id`; `register/options` konsumiert den Grant und startet die Ceremony |
| Kein persistenter Passkey-Store | In-Memory-Store ist vorhanden, verliert Daten bei Neustart — `register/verify` legt Credentials ab, aber persistente Ablage bleibt offen |
| Datenquellen-Writeback für `webauthn_user_id` im Register-Verify-Pfad fehlt | Mutation wird im Verify-Pfad aktiv aufgerufen; reale Datenquellen-Persistenz folgt mit persistenter Account-Ablage |
| Test-Fixtures für `finish_passkey_registration` | `webauthn-rs 0.5.4` enthält keinen Soft-Authenticator (kein `softpasskey`-Modul, kein `SoftToken`); eine seriöse positive Verifikation benötigt entweder einen Browser-E2E oder eine separate Authenticator-Crate (z.B. `webauthn-authenticator-rs`) — beides ist nicht Teil des Folge-PR. Negativpfade nutzen strukturell gültige aber kryptografisch ungültige `RegisterPublicKeyCredential`-JSON-Payloads und treffen `finish_passkey_registration` echt. |
| `excludeCredentials` im `register/options` | Grundsätzlich an `PasskeyStore` angebunden; reale Wirkung greift erst, sobald positiv verifizierte Credentials abgelegt sind |
| E2E-Test für vollständige Register-Ceremony | Folgt aus Browser-/Authenticator-Beleg — bleibt offene Folgearbeit |
