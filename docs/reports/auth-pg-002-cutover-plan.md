---
id: reports.auth-pg-002-cutover-plan
title: "AUTH-PG-002 Passkey PostgreSQL Cutover Plan"
doc_type: report
status: active
lifecycle_state: active
lifecycle: planning
owner_task: AUTH-PG-002
review_after: 2026-09-30
canonicality: evidence
created: 2026-07-01
lang: de
summary: >
  Cutover-Plan für AUTH-PG-002 nach Store-Slice und Runtime-Facade: beschreibt
  die verbleibenden Gates für Produktionsumschaltung, FK-Integrität,
  Register→Reload→Login-Proof, Rollback und Abgrenzung zu AUTH-PG-003.
relations:
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-db-store.md
  - type: relates_to
    target: docs/reports/auth-pg-002-passkey-runtime-facade.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
---

# AUTH-PG-002 Passkey PostgreSQL Cutover Plan

## 1. Ausgangslage

AUTH-PG-002 ist nach zwei technischen Slices **partial**:

- Slice A: `passkey_credentials`-Migration und isolierter `DbPasskeyStore`.
- Slice B: `passkey_credential_source: in_memory | postgres`, Runtime-Facade
  und Routenanbindung für `register/options`, `register/verify`, `auth/options`
  und `auth/verify`.
- Default bleibt `in_memory`.
- `postgres` ist explizit opt-in und fail-closed: kein Pool, kein Start.
- Kurzlebige WebAuthn-Ceremony-Stores bleiben bewusst in-memory.

Damit ist die technische Tür vorbereitet. Der Produktions-Cutover ist noch
nicht freigegeben.

## 2. Nicht-Ziele dieses Plans

Dieser Plan implementiert noch keine Migration und setzt keinen
Produktionsschalter. Insbesondere nicht:

- kein Default-Wechsel auf `postgres`,
- kein Deploy-Profil mit aktivem `WELTGEWEBE_PASSKEY_CREDENTIAL_SOURCE=postgres`,
- kein Foreign-Key nachträglich auf bestehende Daten,
- kein `webauthn_user_id`-Backfill / `NOT NULL` (AUTH-PG-003),
- keine Passkey-Management-UI.

## 3. Cutover-Gates

### Gate A — Account-Quelle ist PostgreSQL

`passkey_credential_source=postgres` darf nur in einer Umgebung aktiviert
werden, in der `domain_read_source=postgres` gilt und der Account-Read-Path
laufend bewiesen ist.

Warum: Ein Credential in PostgreSQL muss auf eine Account-Zeile zeigen, die bei
Reload zuverlässig aus PostgreSQL rekonstruiert wird. Sonst entsteht ein
restart-stabiler Credential-Datensatz für einen nicht restart-stabilen Account.

### Gate B — Register → Reload → Login Proof

Vor Cutover braucht es einen realistischen Proof:

1. Account aus PostgreSQL laden.
2. Passkey-Registration über Route abschließen.
3. App-/State-Reinitialisierung.
4. `auth/options` findet Credential aus PostgreSQL.
5. `auth/verify` aktualisiert Counter/Backup-Flags in PostgreSQL.
6. Erst danach wird eine Session gemintet.

Wenn echte Browser-/Authenticator-Simulation im API-Test nicht tragfähig ist,
ist ein Playwright-/Browser-Proof gegen eine Testinstanz der richtige Ort. Der
vorhandene Runtime-Facade-DB-Test ist notwendig, aber nicht allein hinreichend
für den Produktions-Cutover.

**Stand 2026-07-03 (AUTH-PG-002-C1):** Die Browser-/Authenticator-Simulation
ist im API-Test tragfähig. Der Route-Level-Proof
`passkey_register_reload_auth_route_proof` in
`apps/api/tests/db_passkey_store_persistence.rs` deckt alle sechs Schritte ab:

1. Account wird ausschließlich in PostgreSQL angelegt und über den produktiven
   Startup-Loader `load_accounts_from_postgres` geladen.
2. Registration läuft über die echten Routen `register/options` +
   `register/verify` hinter der echten Auth-Middleware; ein Test-interner
   Software-Authenticator liefert eine echte ES256-Attestation
   (P-256-Schlüsselpaar, CBOR `none`-Format), die Server-Verifikation
   (`finish_passkey_registration`) läuft ungekürzt.
3. Reinitialisierung: erster Pool wird geschlossen, sämtliche Caches und
   Ceremony-Stores werden neu aufgebaut, Accounts werden erneut aus PostgreSQL
   geladen; In-Memory-Zustand überlebt nicht.
4. `auth/options` findet das Credential aus PostgreSQL (der In-Memory-Store
   bleibt nachweislich leer).
5. `auth/verify` verifiziert eine echte ES256-Assertion und persistiert den
   Signatur-Counter (0 → 1) in `passkey_credentials`.
6. Erst danach wird eine Session gemintet (DB-gestützter Session-Store,
   `Set-Cookie`, Session-Zeile account-gebunden).

Ein nicht-ignorierter, DB-freier Selbsttest
(`soft_authenticator_passes_bare_webauthn_ceremonies`) pinnt die
Authenticator-Fixture gegen die volle webauthn-rs-Verifikation, damit sie
nicht stillschweigend verrotten kann. Lokaler Lauf gegen direktes PostgreSQL
ist grün; der maßgebliche Merge-Beleg ist der bestehende PR-CI-Job
`db-passkey-persistence-proof`, der das gesamte Testfile mit
`--include-ignored` ausführt.

**Nicht durch C1 bewiesen:** ein echter OS-Prozess-Neustart mit echtem
Browser-Authenticator (der bestehende Playwright-Proof startet die API genau
einmal und kann sie nicht mitten im Test neu starten — das bleibt ein
möglicher späterer Slice), Produktions-Cutover, FK-Integrität,
`webauthn_user_id`-Backfill.

### Gate C — FK-Readiness

Der spätere Foreign Key `passkey_credentials.account_id -> domain_accounts(id)`
ist erwünscht, aber erst nach Audit/Cutover zulässig.

Vor einer FK-Migration müssen belegt sein:

- alle `passkey_credentials.account_id` haben eine passende `domain_accounts.id`,
- es gibt keine Alt-/Test-Credentials ohne Account-Zeile in repräsentativen
  Umgebungen,
- der Store-/Route-Pfad erzeugt keine Credentials vor erfolgreicher
  Account-Revalidierung,
- Lösch-/Deaktivierungssemantik ist entschieden: hard delete, soft delete oder
  orphan-vermeidender Guard.

Bis diese Bedingungen erfüllt sind, bleibt der FK als Missing Evidence in
AUTH-PG-002 getrackt. Ein vorzeitiger FK wäre keine Sicherheit, sondern eine
Migrationsfalle.

### Gate D — Rollback

Rollback muss vor Cutover beschrieben sein:

- Config-Rollback: `passkey_credential_source=in_memory`.
- Daten bleiben in `passkey_credentials`, werden aber nicht gelesen.
- Bekannte Einschränkung: neue Credentials, die nur in PostgreSQL registriert
  wurden, sind nach Rollback in den In-Memory-Modus nicht automatisch verfügbar.
- Deshalb darf Rollback nur als Betriebsnotfall gelten, nicht als verlustfreie
  Hin-und-zurück-Umschaltung.

### Gate E — Monitoring und Fehlersemantik

Vor Cutover müssen Log-/Metrikpunkte beobachtbar sein:

- Backendfehler im Credential-Store,
- Duplicate-Credential-Konflikte,
- `credential_not_found` vs. `credential_mismatch`,
- fehlgeschlagene Counter-/Credential-State-Updates,
- Session-Mint wird bei Credential-Store-Fehlern verweigert.

Die bestehende Runtime-Facade loggt fail-closed; der Cutover muss zeigen, dass
diese Ereignisse im Betrieb sichtbar sind.

## 4. Abgrenzung zu AUTH-PG-003

AUTH-PG-003 bleibt nach AUTH-PG-002-Cutover separat:

- Audit von `domain_accounts.webauthn_user_id IS NULL`,
- Backfill-Strategie,
- späteres `NOT NULL`,
- kein stilles Neugenerieren von UUIDs bei Reload.

AUTH-PG-002 darf nicht als erledigt gelten, nur weil `webauthn_user_id`
stabiler wird; Credential-Persistenz und User-Handle-Backfill sind getrennte
Invarianten.

## 5. Nächster kleinster technischer Slice

### AUTH-PG-002-C1: Route-level Register→Reload→Auth proof — umgesetzt

Der Slice ist wie geplant geschnitten worden:

- kein Produktionsschalter,
- kein FK,
- kein Default-Wechsel,
- nur ein harter Proof, dass die vorhandene Facade auf Routenebene den
  Restart-Pfad trägt (`passkey_register_reload_auth_route_proof`, Details in
  Gate B oben).

Erst danach sollte ein Deploy-/Config-Cutover diskutiert werden. Der nächste
kleinste Slice nach C1 ist der Runtime-Schema-Preflight plus erneuter
Runtime-Audit (die Zielumgebung hat laut Heimserver-Audit noch keine
`passkey_credentials`-Tabelle), danach die explizite FK-/Deploy-Entscheidung.

## 6. Statusentscheidung

AUTH-PG-002 bleibt **partial**.

Gate B ist auf API-Ebene abgedeckt (lokal grün; PR-CI-Lauf des Jobs
`db-passkey-persistence-proof` ist der maßgebliche Merge-Beleg). Offen bleiben
Gate A in der Zielumgebung, Gate C (FK-Readiness), Gate D/E im Betrieb sowie
der eigentliche Produktions-Cutover.
