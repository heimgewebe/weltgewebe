---
id: blueprints.auth-roadmap
title: Auth Roadmap
doc_type: roadmap
status: active
canonicality: canonical
summary: >
  Exekutive Roadmap zur schrittweisen Kanonisierung, Verifikation und
  Vollendung der Auth-Architektur im Weltgewebe.
---

# Auth Roadmap – Weltgewebe

> Diese Roadmap ist der exekutive Pfad für Auth im Weltgewebe.
> Sie ergänzt den normativen Zielrahmen aus ADR-0006 und den zugehörigen
> Specs um Reihenfolge, Stop-Kriterien, Drift-Schutz und
> Implementierungsprioritäten.
>
> Ziel ist nicht, Auth neu zu erfinden, sondern:
> **alte und neue Wahrheitsschichten zu ordnen, Runtime gegen Zielzustand
> zu prüfen und danach die realen Lücken systematisch zu schließen.**

## 0. Ziel dieses Dokuments

Diese Roadmap dient zugleich als:

- Integrationspunkt für alle Auth-Dokumente
- exekutiver Pfad zwischen Soll und Ist
- Drift-Detektor zwischen ADRs, Specs, Runtime und Betrieb
- Priorisierungsgrundlage für Implementierung und Review

---

## 1. Kanonische Referenzen

### Führender Zielrahmen

Diese Dokumente definieren den kanonischen Zielzustand:

- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
- `docs/specs/auth-api.md`
- `docs/specs/auth-state-machine.md`
- `docs/specs/auth-ui.md`

### Basis / Historie

Diese Dokumente bleiben relevant, sind aber nicht mehr alleiniger Zielrahmen:

- `docs/adr/ADR-0005-auth.md`
- `docs/specs/auth-blueprint.md`

### Brückendokumente / Betriebs- und Routing-Kontext

Diese Dokumente müssen berücksichtigt, aber nicht mit der Zielarchitektur verwechselt werden:

- `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
- `docs/runbook.md`
- `apps/api/README.md`
- `docs/index.md`

### Runtime- / Belegquellen

Diese Artefakte liefern reale Nachweise des implementierten Zustands:

- `apps/api/src/routes/auth.rs`
- `apps/api/src/auth/session.rs`
- `apps/api/src/mailer.rs`
- `apps/web/src/routes/login/+page.svelte`
- `apps/web/src/lib/auth/store.ts`
- `verification/verify_magic_link.py`

### Diagnoseartefakte

- `docs/reports/auth-status-matrix.md`
- `docs/reports/auth-status-matrix.json`

---

## 2. Leitprinzipien

- Magic Link ist Einstieg und Recovery, nicht die gesamte Auth-Architektur.
- Session ist der primäre Alltagszustand.
- Passkey ist optionaler Komfort- und Sicherheitsgewinn, nicht Pflicht.
- Step-up Auth ist aktionsgebunden und session-neutral.
- Auth ist strikt getrennt vom Identitätsmodus (RoN vs. verortet).
- Keine Architekturentscheidung ohne Runtime-Beleg oder explizite Offen-Markierung.
- Kein Feature-Ausbau auf unstabiler Session-Basis.
- Drift-Sichtbarkeit geht vor Vollständigkeitsrhetorik.

---

## 3. Statuslogik

Alle Auth-Bereiche werden in der Statusmatrix mit genau einem der folgenden Zustände geführt:

- `OK` — durch Code, Test oder Runtime ausreichend belegt
- `Teil` — teilweise belegt, aber nicht end-to-end
- `Offen` — Zielzustand dokumentiert, Runtime-Beleg fehlt
- `Drift` — Docs widersprechen sich oder der Runtime

### Mindestregel für OK

Ein Bereich darf nur dann als `OK` gelten, wenn mindestens zwei der folgenden Belegtypen vorliegen:

- Route / Code
- Test / Verification
- Runbook / Betriebsbeleg
- Runtime-Proof / Smoke / Log / UI-Nachweis

---

## 4. Phase 0 — Kanonisierung und Drift-Stopp

**Ziel:** Eine eindeutige Auth-Wahrheitsordnung herstellen.

### Maßnahmen

1. `ADR-0006` als führendes Auth-Zieldokument explizit behandeln.
2. `ADR-0005` als historisches Fundament / Minimalbasis markieren.
3. `auth-blueprint.md` als ältere, an `ADR-0005` gebundene Implementierungslinie kenntlich machen.
4. `weltgewebe.auth-and-ui-routing.md` als Routing-/Diagnose-Blueprint einordnen, nicht als Endarchitektur.
5. `docs/index.md` und weitere Übersichtsseiten so anpassen, dass keine gleichrangigen Auth-Wahrheiten nebeneinander stehen.

### Artefakte

- diese Roadmap
- `docs/reports/auth-status-matrix.md`
- `docs/reports/auth-status-matrix.json`

### Stop-Kriterium für Phase 0

- Es ist eindeutig sichtbar, welches Dokument Zielrahmen ist.
- Historische Dokumente sind weiterhin referenzierbar, aber nicht mehr missverständlich führend.

---

## 5. Phase 1 — Ist-Zustand gegen Zielzustand beweisen

**Ziel:** Keine Annahmen, nur belegter Zustand.

### Pflichtachsen

- Magic-Link-Request / Consume
- Session-Check
- Session-Refresh
- Logout / Logout-All
- Device-Liste / Device-Removal
- Passkey register / auth / list / remove
- Step-up challenge / request / consume
- UI-Reaktionen auf Session, Step-up, Devices, Passkey
- Sicherheitsmechaniken:
  - Anti-Enumeration
  - CSRF / Origin
  - Trusted Proxy
  - Rate Limit
  - session-neutraler Step-up-Link

### Artefakt für Phase 1

- `docs/reports/auth-status-matrix.md`
- `docs/reports/auth-status-matrix.json`

### Stop-Kriterium für Phase 1

Jeder relevante Bereich ist entweder:

- mit Belegen als `OK` / `Teil` markiert,
- oder explizit als `Offen`,
- oder als `Drift` mit benanntem Widerspruch.

---

## 6. Phase 2 — Session- und Device-Modell vervollständigen

**Ziel:** Vom Magic-Link-MVP zur alltagstauglichen Auth.

### Arbeitspakete Phase 2

1. `GET /auth/session` belegen oder implementieren
2. `POST /auth/session/refresh` belegen oder implementieren
3. Device-ID-Strategie vereinheitlichen
4. Device-Liste bereitstellen
5. Current-Device-Markierung einführen
6. `DELETE /auth/devices/:id`
7. `POST /auth/logout-all`
8. Session-Persistenzentscheidung explizit festziehen

### Risiken

- inkonsistente Session-Realität
- fehlende Gerätehoheit
- spätere Sicherheits- und UX-Drift

### Stop-Kriterium für Phase 2

- Session, Refresh, Logout-All und Devices sind nicht mehr `Offen`
- Device-Bindung ist technisch und dokumentarisch konsistent

---

## 7. Phase 3 — Step-up Auth vollständig realisieren

**Ziel:** Sensitive Aktionen sauber absichern.

### Arbeitspakete Phase 3

1. Challenge-Erzeugung
2. TTL für Challenges
3. Intent-Bindung
4. `POST /auth/step-up/magic-link/request`
5. `POST /auth/step-up/magic-link/consume`
6. Passkey als bevorzugter Step-up-Pfad
7. Step-up-Dialog in der UI
8. Fehlerpfade ohne unnötigen Session-Abbruch
9. Nachweis, dass Step-up keine neue allgemeine Session erzeugt

### Nicht verhandelbare Regel

Step-up bleibt aktionsgebunden und session-neutral.

### Stop-Kriterium für Phase 3

- `challenge_id`-Pfad ist end-to-end nachgewiesen
- sensitive Aktionen können nicht mehr ohne Step-up ausgeführt werden

---

## 8. Phase 4 — Passkeys/WebAuthn realisieren

**Ziel:** Komfort und Sicherheit erhöhen, ohne Recovery zu opfern.

### Arbeitspakete Phase 4

1. Statusbeweis: Was existiert bereits?
2. Register-Options
3. Register-Verify
4. Auth-Options
5. Auth-Verify
6. Passkeys auflisten
7. Passkey entfernen
8. UI-Aktivierung erst nach erfolgreichem Login anbieten

### Voraussetzungen

- stabile Session
- definierter Geräte- und Step-up-Pfad

### Stop-Kriterium für Phase 4

- Passkeys sind nicht mehr nur dokumentiert, sondern in Runtime und UI belegbar
- Magic Link bleibt Recovery-/Neugerät-Pfad

---

## 9. Phase 5 — UI von Minimal-Login zu Wiederkehr-UX ausbauen

**Ziel:** Alltagstauglichkeit.

### Arbeitspakete Phase 5

1. Session-Status sichtbar machen
2. Zustand „Session abgelaufen“
3. Passkey-Aktivierung mit verständlicher Erklärung
4. Step-up-Dialog
5. Geräteansicht / Geräteverwaltung
6. AuthStore / AuthStatus auf reale Zustände erweitern

### Leitfrage

Die UI darf nicht nur wissen:

- „eingeloggt / ausgeloggt“

Sie muss auch wissen:

- Session gültig?
- Step-up nötig?
- Passkey verfügbar?
- Device-Management erreichbar?

### Stop-Kriterium für Phase 5

- `auth-ui.md` ist in den wesentlichen Zuständen nicht mehr nur Soll, sondern durch UI-Pfade gedeckt

---

## 10. Phase 6 — Sensitive Intents finalisieren

**Ziel:** offene API-Semantik schließen.

### Offener Kernpunkt

- `/me/email`

### Zu klären

- exakte Route
- HTTP-Methode
- Verifikationsbedarf
- Step-up-Pflicht
- Session-Verhalten nach Änderung
- Audit-/Logging-Level

### Stop-Kriterium für Phase 6

- `/me/email` ist nicht mehr offene Architekturentscheidung
- Matrix führt diesen Punkt nicht mehr als `Offen`

---

## 11. Phase 7 — Sicherheits- und Betriebsnachweise als Guard / Smoke etablieren

**Ziel:** Sicherheit nicht nur besitzen, sondern reproduzierbar beweisen.

### Check-Gruppen

- Anti-Enumeration
- Trusted Proxy
- Rate Limit
- SMTP-/Magic-Link-Delivery
- CSRF / Origin
- Step-up Challenge
- Devices / Logout-All
- Passkey-Smoke (sobald vorhanden)

### Artefakte für Phase 7

- `scripts/guards/auth_status_guard.py`
- `verification/verify_auth_status.py`
- ggf. zusätzliche Smoke-/Guard-Hooks

### Stop-Kriterium für Phase 7

- die wichtigsten Auth-Invarianten sind automatisiert prüfbar

---

## 12. Phase 8 — Dokumentationsdrift bereinigen

**Ziel:** Nach der Umsetzung keine höflich widersprechenden Dokumente zurücklassen.

### Zu synchronisieren

- `docs/adr/ADR-0005-auth.md`
- `docs/adr/ADR-0006__auth-magic-link-session-passkey.md`
- `docs/specs/auth-blueprint.md`
- `docs/specs/auth-api.md`
- `docs/specs/auth-state-machine.md`
- `docs/specs/auth-ui.md`
- `docs/blueprints/weltgewebe.auth-and-ui-routing.md`
- `docs/runbook.md`
- `apps/api/README.md`
- `docs/index.md`

### Stop-Kriterium für Phase 8

- Keine relevante Auth-Datei behauptet still einen anderen Zielzustand als der führende Rahmen.

---

## 13. Empfohlene Reihenfolge

1. Kanonisierung / Drift-Stopp
2. Statusmatrix / Ist-Beleg
3. Session / Devices
4. Step-up Auth
5. Passkeys
6. UI-Wiederkehr
7. Sensitive Intents finalisieren
8. Guards / Smokes
9. Dokumentations-Sync

---

## 14. Alternative Priorisierung: drift-risikogetrieben

Statt nach Features kann auch nach Lügenpotenzial priorisiert werden:

### Höchstes Drift-Risiko

- konkurrierende Auth-Dokumente
- Session / Devices
- Step-up
- `/me/email`

### Mittleres Drift-Risiko

- Passkeys
- Wiederkehr-UX

### Niedrigeres Drift-Risiko

- Formulierungs- und Glossarpolitur

---

## 15. Entscheidungsregel

Kein Ausbau von Passkeys, UI-Polish oder anderen Komfortpfaden, wenn:

- Session-Modell unklar,
- Step-up nicht belastbar,
- offene API-Fragen nicht sichtbar markiert,
- oder Drift zwischen Docs und Runtime unerklärt bleibt.

---

## 16. Essenz

Auth ist im Weltgewebe kein einzelnes Feature.
Auth ist ein Systemzustand.

Der größte Fehler wäre, neue Auth-Teile zu bauen,
ohne den bestehenden Zustand sauber zu ordnen, zu belegen und zu schließen.
