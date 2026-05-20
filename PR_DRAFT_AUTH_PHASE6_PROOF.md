# Auth Phase 6 Proof Draft

## These / Antithese / Synthese

**These:** Nach dem gemergten DB-Session-CI-Gate waere der naheliegende naechste Schritt: **Auth Phase 6 weiter schliessen**.

**Antithese:** Nicht sofort Passkey-Feature bauen. Das waere attraktiv, aber wir wuerden neue Auth-Komplexitaet auf eine noch nicht vollstaendig end-to-end belegte Auth-Kette setzen.

**Synthese:** Naechster PR sollte ein **Auth-E2E-/Cookie-Sicherheits-Proof-PR** sein, kein neues Feature.

## Warum

Im aktuellen Stand ist Phase 5 umgesetzt: `DbSessionStore` ist implementiert, direkter SQLx/PostgreSQL-Persistenzpfad ist drin, Phase 6 bleibt offen. Die Statusmatrix nennt fuer Session noch genau diese Restluecken: **Cookie-Sicherheits-Verifikation** und **E2E-Nachweis**. Gleichzeitig ist Step-up Auth funktional weit, aber es fehlt weiterhin ein **UI E2E Test**.

Passkeys sind ebenfalls offen: Register-Verify, Auth-Options, Auth-Verify, persistente Ablage ueber Neustart, List/Remove und E2E-UI. Das ist wichtig, aber als naechster Schritt breiter und riskanter als ein Beweis-PR.

## Empfehlung

test(auth): add E2E proof for persisted session and secure cookie behavior

Scope klein halten:

1. Bestehenden Login-/Magic-Link-Pfad E2E testen.
2. Belegen, dass Session-Cookie gesetzt wird.
3. Belegen, dass `httpOnly`, `SameSite=Lax` und `Secure` korrekt sind.
4. Belegen, dass Session nach API-Neustart bzw. Store-Neuinitialisierung erhalten bleibt, sofern DB aktiv ist.
5. Belegen, dass ohne `DATABASE_URL` der In-Memory-Testpfad weiter funktioniert.
6. Statusmatrix erst nach gruenem Test von "pending/proof fehlt" auf belegten Status nachziehen.

## Nicht tun

Noch nicht:

- Passkey Register-Verify implementieren.
- UI aktivieren.
- Passkey-Persistenz bauen.
- PgBouncer wieder anfassen.
- Auth-Roadmap rhetorisch gruen faerben.

## Alternative Sinnachse

Nicht fragen: "Welches Auth-Feature fehlt als naechstes?"
Besser fragen: **"Welche unbelegte Sicherheitsbehauptung ist nach DbSessionStore am teuersten, wenn sie falsch ist?"**

Antwort: Cookie-/Session-E2E. Wenn dort etwas driftet, nuetzen Passkeys wenig.

## Risiko / Nutzen

**Nutzen:** Schliesst Phase-6-Beweisluecke, stabilisiert Auth-Basis, senkt Risiko vor Passkey-Ausbau.

**Risiko:** Mittel. E2E kann flaky werden, wenn Mailer/Testserver/DB-Setup nicht sauber isoliert sind.

**Praemissencheck:** Diese Empfehlung gilt, wenn das gemergte CI-Gate tatsaechlich gruen war.
**Epistemische Leere:** CI-Endstatus des gemergten PR fehlt. Noetig, um Phase 5b wirklich als "belegt" statt nur "gemergt" zu bewerten.

## Naechster Agentenauftrag

Erstelle einen kleinen Proof-PR:

Titel:
`test(auth): prove persisted session and cookie security E2E`

Ziel:
Schliesse die naechsten Auth-Phase-6-Beweisluecken nach DbSessionStore:
persistierte Session + Cookie-Sicherheitsattribute + E2E-Nachweis.

Nicht-Ziele:
- Kein Passkey Register-Verify.
- Keine neue Auth-Funktion.
- Keine UI-Aktivierung jenseits notwendiger Testnutzung.
- Kein PgBouncer.
- Keine grosse Refaktorierung.

Diagnose zuerst:
- Pruefe bestehende Playwright-/API-Teststruktur fuer Login, Magic Link, Session und Cookies.
- Pruefe, ob ein Mailer-Test-Sink oder Mock-Mailer fuer E2E schon nutzbar ist.
- Pruefe, ob der bestehende DB-Session-Persistence-Test wiederverwendet oder nur referenziert werden soll.
- Liefere vor Patch kurz: betroffene Dateien, vorhandene Testhelfer, geplante Testgrenze.

Umsetzung:
- Ergaenze minimalen E2E/API-Test, der den Magic-Link-Login bis zur gueltigen Session belegt.
- Pruefe Cookie-Attribute: httpOnly, SameSite=Lax, Secure gemaess Konfiguration.
- Pruefe DB-backed Session-Verhalten nur dort, wo DATABASE_URL gesetzt ist.
- Offline-Tests ohne DATABASE_URL muessen gruen bleiben.
- Aktualisiere docs/reports/auth-status-matrix.md und .json nur, wenn der neue Test tatsaechlich gruen ist.

Verifikation:
- cargo test --locked -p weltgewebe-api
- falls Web-E2E betroffen: pnpm --dir apps/web test:e2e oder vorhandenes passendes Playwright-Target
- ggf. gezielter neuer Testbefehl dokumentieren

Lieferung:
1. Belegter Ist-Zustand.
2. Neue Tests mit Zweck.
3. Ausgaben der Verifikation.
4. Statusmatrix-Diff.
5. Restluecken: Passkey Register-Verify, Passkey Auth, List/Remove, E2E-UI falls weiterhin offen.

## Unsicherheit

**Unsicherheitsgrad:** 0,22 — CI-Endstatus des gemergten PR fehlt; Snapshot zeigt den Repo-Zustand, aber nicht GitHub-Run-Ergebnis.
**Interpolationsgrad:** 0,12 — ich ordne die naechsten Schritte aus Roadmap/Statusmatrix ab, ohne aktuellen CI-Run direkt zu sehen.

## Essenz

**Hebel:** Beweise vor Features.
**Entscheidung:** Naechster PR: Auth E2E + Cookie-Sicherheitsproof.
**Naechste Aktion:** Agentenauftrag oben geben; erst danach Passkey Register-Verify.
