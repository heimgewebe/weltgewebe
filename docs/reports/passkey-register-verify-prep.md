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

Dieser Bericht bereitet den Folge-PR für `POST /auth/passkeys/register/verify` vor.

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

### 2.2 Register-Options – Was vorhanden ist

`POST /auth/passkeys/register/options` gibt zurück:

```json
{
  "registration_id": "<opaque UUID>",
  "options": { "publicKey": { ... } }
}
```

- `webauthn_user_id` des Accounts wird als `user.id` eingesetzt (Base64url-kodiert).
- `rp.id` und `rp.origin` kommen aus `AppConfig` (Env: `WEBAUTHN_RP_ID`, `WEBAUTHN_RP_ORIGIN`).
- Das `PasskeyRegistration`-State-Objekt wird im `PasskeyRegistrationStore` abgelegt.
- Die `registration_id` ist der opake Schlüssel, den der Client im `register/verify`-Schritt zurückschickt.
- Bestehende Credential-IDs werden noch **nicht** als `excludeCredentials` übergeben (TODO in Zeile 1626 von `auth.rs`).

**4 Integrationstests belegt** in `apps/api/tests/api_auth.rs` (ab Zeile 3390):

| Test | Prüft |
|---|---|
| `passkey_register_options_requires_authentication` | Kein Cookie → 401 |
| `passkey_register_options_returns_503_when_not_configured` | WebAuthn nicht konfiguriert → 503 `PASSKEYS_NOT_CONFIGURED` |
| `passkey_register_options_success` | Vollständige Erfolgsantwort inkl. `registration_id` und `webauthn_user_id`-Stabilität |
| `passkey_register_options_stable_webauthn_user_id` | Gleicher Account liefert konsistente `user.id` über mehrere Aufrufe |

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
- **Status:** Persistenz-Writeback fehlt. Ist Voraussetzung für `register/verify`.

### 2.5 Credential-Speicher

Es existiert **kein** Credential-Speicher für abgeschlossene Passkey-Registrierungen.

- Kein `PasskeyStore` oder vergleichbare Struktur
- Kein Datenbankschema
- Das `webauthn_rs`-Objekt `Passkey` (Ergebnis von `finish_passkey_registration`) hat keinen Ablageort

---

## 3. Pfad-Konvention

Dieser Bericht spricht durchgehend vom kanonischen **Backend-Pfad** aus der API-Spezifikation:

```
POST /auth/passkeys/register/verify
```

Falls der Endpunkt im Frontend oder durch den Reverse Proxy unter `/api/auth/...` erreichbar ist, gilt das nur als technische Mount- oder Proxy-Ebene. Die fachliche Spezifikation in diesem Bericht meint durchgehend `/auth/passkeys/register/verify` ohne API-Präfix.

---

## 4. Endpoint-Zielbild

### Geplanter Endpoint

```
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

**Offene Designentscheidung: Step-up-Handoff** — siehe separater Abschnitt unten.

**Keine Login-Semantik** — kein Cookie, kein neuer Session-Token, keine Umleitung.

### Step-up-Handoff — Offene Designentscheidung

**Problem:** Passkey-Registrierung ist eine sensitive Operation. Laut `docs/specs/auth-api.md` (Zeile 254) erfordern `POST /auth/passkeys/register/*` einen Step-up-Authentifizierungsnachweis.

Der bestehende Step-up-Mechanismus erzeugt **aktionsgebundene Challenges**: `POST /auth/step-up/magic-link/consume` konsumiert einen Step-up-Token einmalig und **führt dabei direkt die gebundene Aktion aus** (z.B. `LogoutAll`, `RemoveDevice`). Der Mechanismus hinterlässt danach keinen wiederverwendbaren "Step-up ist erledigt"-Marker oder Session-Flag für einen später aufgerufenen Handler.

**Konsequenz:** Für `register/verify` muss **vor der Implementierung** entschieden werden, wie der Step-up-Nachweis erbracht und an den Endpunkt übergeben wird. Es gibt mindestens drei Lösungsansätze:

- **Pfad A (bevorzugt):** Step-up vor `register/options` erzwingen. Der Nutzer durchläuft den Step-up-Pfad (Magic Link, Consume mit Intent `BeginPasskeyRegistration`), bevor die WebAuthn-Ceremony überhaupt beginnt. Dann ist `register/verify` ein reiner Verify-Handler ohne sekundären Step-up-Bedarf.
  
- **Pfad B:** Neuen one-time Step-up-Grant einführen. `register/verify` akzeptiert einen Step-up-Token explizit als Eingabeparameter (z.B. `{ "registration_id": "...", "credential": {...}, "step_up_token": "..." }`). Der Handler prüft den Token und führt Registration + Credential-Persistenz durch. Erfordert neue Semantik im Step-up-System.

- **Pfad C:** Direkte Integration in `consume_step_up`. `POST /auth/step-up/magic-link/consume` mit Intent `RegisterPasskey` würde nicht nur die Challenge verarbeiten, sondern **auch** `registration_id` und `credential` als Payload erhalten und direkt die Registrierung absolvieren. Erfordert erhebliche Umstrukturierung.

**Status:** Diese Entscheidung muss im nächsten PR (Pfad B) geklärt und dokumentiert werden, bevor der `register/verify`-Handler Logik erhält.

---

## 5. Persistenzfragen

### 4.1 Credential-Speicher

| Frage | Stand |
|---|---|
| Wo werden `Passkey`-Objekte gespeichert? | **Offen** — kein Store vorhanden |
| In-Memory vs. persistiert? | Für Phase 4 (Single-Instance, In-Memory-Arch.) wäre ein In-Memory-Store möglich, aber Neustarts verlieren alle Credentials |
| Datenbankschema? | Nicht vorhanden; ab Phase 4 (DB-Persistenz) nötig |
| Welche Felder? | `account_id`, `credential_id`, `passkey` (serialisiertes `Passkey`-Objekt), `created_at`, optional `nickname` |

**Mindestanforderung für `register/verify`:** Ein `PasskeyStore` (analog zu `PasskeyRegistrationStore`, aber langlebig, nicht TTL-basiert), der pro Account eine Liste von `Passkey`-Objekten hält.

### 4.2 webauthn_user_id Writeback

| Frage | Stand |
|---|---|
| Stabil über Neustarts? | **Nein** bei lazy-generierten Werten |
| Wann muss Writeback erfolgen? | Spätestens beim ersten `register/verify` |
| Welche Datei? | `apps/api/src/routes/accounts.rs` — `AccountStore` braucht eine Mutationsmethode |
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

**Pfad A — direkt `feat(auth): implement passkey register verify`**

Blockiert durch:
- Kein `PasskeyStore` (langlebiger Credential-Speicher)
- Kein `webauthn_user_id`-Writeback-Mechanismus im `AccountStore`
- Kein Step-up-Intent für Passkey-Registration definiert

Pfad A ist **nicht** direkt gangbar ohne die fehlenden Store-Strukturen.

---

**Pfad B — zuerst Datenmodell-/Store-PR**

Inhalt eines Pfad-B-PR:
1. `PasskeyStore` (in-memory, langlebig, account-gebunden) in `apps/api/src/auth/passkeys.rs`
2. `AccountStore`-Mutation: `update_webauthn_user_id(account_id, uuid)` in `apps/api/src/routes/accounts.rs`
3. **Entscheidung und dokumentation des Step-up-Handoff-Pfads** — siehe Abschnitt 4.3. Wahl aus A (Step-up vor register/options), B (one-time-grant), oder C (Intent-direkt). ADR-0006 aktualisieren, falls notwendig.
4. Ggf. minimale Implementierung des gewählten Step-up-Pfads (z.B. neuer Intent-Typ)
5. Unit-Tests für `PasskeyStore` und Step-up-Handoff

Pfad B schafft die minimalen Voraussetzungen ohne WebAuthn-Verify-Logik.

---

**Pfad C — zuerst WebAuthn-Test-Fixtures/Mocks**

Das `webauthn_rs`-Crate erfordert echte kryptografische Operationen. Test-Fixtures (vorberechnete `RegisterPublicKeyCredential`-Objekte) müssten generiert und festgekodiert werden. Das ist möglich, aber aufwendig und fragil bei Library-Updates.

Pfad C ist nachgelagert — sinnvoll als Teil des Folge-PR, nicht als separater vorgelagerter PR.

---

### Empfehlung

**Pfad B** ist der richtige nächste Schritt.

Der Folge-PR nach diesem Bericht soll lauten:

```
feat(auth): add PasskeyStore and step-up-handoff for passkey registration
```

Inhalt: Credential-Store-Struktur + `AccountStore`-Mutation + Step-up-Handoff-Entscheidung + Unit-Tests. Kein `register/verify`-Handler, keine WebAuthn-Verify-Route.

Erst danach ist Pfad A gangbar:

```
feat(auth): implement passkey register verify
```

---

## 9. Stop-Kriterium für den Folge-PR

Der `register/verify`-Implementierungs-PR darf erst starten, wenn:

| Kriterium | Status |
|---|---|
| `PasskeyStore` mit Insert/Get/Remove implementiert und getestet | **offen** |
| `AccountStore.update_webauthn_user_id()` implementiert | **offen** |
| Step-up-Handoff-Pfad entschieden (Pfad A vor register/options, Pfad B one-time-grant, oder Pfad C intent-direkt) — siehe Abschnitt 4.3 | **offen** |
| Step-up-Handoff-Pfad implementiert und getestet | **offen** |
| Test-Fixtures-Strategie für `finish_passkey_registration` entschieden | **offen** |
| UI bleibt deaktiviert (`account-section-passkey-cta` disabled, Test grün) | **belegt** (Zeile 227 in account-section.spec.ts) |
| Magic-Link-Pfad bleibt grün | **belegt** (api_auth.rs) |

---

## 10. Diagnoseausgaben (Rohdaten)

### git status --short

```
(clean — keine uncommitted changes vor diesem PR)
```

### rg passkey/webauthn (Relevante Treffer)

**Backend:**
- `apps/api/src/auth/passkeys.rs` — Hauptmodul (7 Unit-Tests)
- `apps/api/src/routes/auth.rs` — `passkey_register_options` (Zeile 1560), Step-up-Infrastruktur
- `apps/api/src/routes/accounts.rs` — `webauthn_user_id: Uuid` (Zeile 84), Lazy-Backfill (Zeile 299–315)
- `apps/api/tests/api_auth.rs` — 4 Integrationstests für `register/options` (ab Zeile 3390)
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

**Step-up für Passkey-Register:** In `auth-api.md` Zeile 254 gelistet als step-up-pflichtige Operation. Kein Handler implementiert. Klärung im Folge-PR (Pfad B).

### make docs-guard (ci-validate)

Vor diesem Bericht:

```
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
| Step-up-Intent für Passkey-Register nicht definiert | Pfad B muss klären: braucht `register/verify` einen Step-up-Challenge-Typ? Oder reicht aktive Session? ADR-0006 prüfen. |
| Kein `PasskeyStore` | Folge-PR (Pfad B) muss ihn einführen, bevor `register/verify` implementiert wird |
| `webauthn_user_id`-Writeback nicht implementiert | Pfad B; bis dahin: Credentials sind nach Neustart nicht mehr zuordenbar |
| Test-Fixtures für `finish_passkey_registration` | `webauthn_rs` benötigt kryptografisch korrekte Antworten; Strategie für realistische Tests im Folge-PR festlegen |
| `excludeCredentials` im `register/options` | TODO in `auth.rs` Zeile 1626; erst nach `PasskeyStore` füllbar |
| E2E-Test für vollständige Register-Ceremony | Folgt aus Implementierung, nicht Vorbereitung |
