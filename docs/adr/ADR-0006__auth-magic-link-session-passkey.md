---
id: adr.ADR-0006-auth-magic-link-session-passkey
title: ADR-0006 — Auth: Magic Link, Session und optionaler Passkey
doc_type: reference
status: active
canonicality: canonical
summary: Beschreibt das kanonische Auth-Modell aus Magic Link, persistenter Session, optionalem Passkey und Step-up Auth.
---

# ADR-0006 — Auth: Magic Link + Session + optionaler Passkey

## Status

Accepted

## Kontext

Weltgewebe benötigt ein Authentifizierungsmodell, das:

- niedrige Einstiegshürde ermöglicht
- wiederkehrende Nutzung ohne Reibung erlaubt
- sichere Recovery garantiert
- nicht auf Passwörtern basiert
- mit dem RoN-Startmodus kompatibel ist

Das bisher implizite Modell (Magic Link) ist als alleinige Lösung für den Alltag nicht ausreichend.
Es zwingt zu wiederholter Interaktion und erzeugt Reibung.

## Entscheidung

Das System verwendet ein gestuftes Auth-Modell:

### 1. Magic Link (E-Mail)

Zweck:

- Erstzugang
- Recovery
- Anmeldung auf neuen Geräten

### 2. Persistente Session

Zweck:

- wiederkehrende Nutzung ohne erneute Authentifizierung
- Gefühl eines kontinuierlichen „Raums“

### 3. Optionaler Passkey

Zweck:

- komfortable und sichere Wiederanmeldung
- step-up authentication bei sensiblen Aktionen
- vollständiges Passkey-Management (hinzufügen, auflisten, entfernen)

## Prinzipien

- Kein Passwort als primärer Auth-Faktor
- Authentifizierung ist getrennt vom Identitätsmodus (RoN vs. verortet)
- Recovery muss immer möglich bleiben
- Sicherheit wird kontextuell erhöht (step-up auth)

## System-Invarianten

- Magic Link ist single-use und serverseitig nicht replaybar.
- Jede Session ist eindeutig einer `device_id` zugeordnet.
- Jede sensitive Aktion erfordert zwingend Step-up Auth.
  Ein Step-up-Magic-Link ist strikt aktionsgebunden und session-neutral.
- Auth (Wie komme ich rein?) ist strikt getrennt vom Identitätsmodus.
  Der Identitätsmodus beantwortet die Frage, ob ein Nutzer RoN oder verortet ist.

## Zustandsmodell

Das System basiert auf folgenden expliziten Zuständen:

- `unauthenticated`: Kein gültiger Zugang vorhanden (Startzustand oder nach Logout/Ablauf).
- `link_requested`: Magic Link wurde angefordert (für Erstlogin, Recovery oder Neugerät). System wartet auf Bestätigung.
- `authenticated_session`: Gültige, aktive Session für das aktuelle Gerät.
- `step_up_required`: Aktive Session, aber die anstehende Aktion erfordert eine kurzzeitige höhere Vertrauensstufe.

## Konsequenzen

### Vorteile

- sehr niedrige Einstiegshürde
- hohe Alltagstauglichkeit
- starke Sicherheit ohne Passwort-Last
- gute mobile UX

### Nachteile

- E-Mail bleibt kritischer Faktor
- Session-Management wird komplexer
- Passkey-Support benötigt zusätzliche Implementierung

## Abgelehnte Alternativen

### Passwort-basierter Login

- hohe Reibung
- bekannte Sicherheitsprobleme

### Magic-Link-only

- zu hohe Wiederkehr-Reibung

### Passkey-only

- unzureichende Recovery

## Sicherheit

- Magic Links sind:
  - kurzlebig
  - einmalig nutzbar
- Sessions:
  - rotierend
  - widerrufbar
- Step-up Auth bei:
  - Verortung
  - Mailänderung
  - sicherheitskritischen Aktionen

## Zusammenhang mit RoN

RoN ist ein Identitätsmodus, kein Authentifizierungsmechanismus.

Das Auth-System beeinflusst nicht:

- ob ein Nutzer verortet ist
- welche personenbezogenen Daten vorliegen

## Statusentscheidung

Dieses Modell definiert den kanonischen Zielzustand für Auth in Weltgewebe.
