---
id: adr.ADR-0006-auth-magic-link-session-passkey
title: Adr 0006 Auth Magic Link Session Passkey
doc_type: reference
status: active
canonicality: derived
---

# ADR-0006 — Auth: Magic Link + Session + optionaler Passkey

## Status

Proposed

## Kontext

Weltgewebe benötigt ein Authentifizierungsmodell, das:

- niedrige Einstiegshürde ermöglicht
- wiederkehrende Nutzung ohne Reibung erlaubt
- sichere Recovery garantiert
- nicht auf Passwörtern basiert
- mit dem RoN-Startmodus kompatibel ist

Das bisher implizite Modell (Magic Link) ist als alleinige Lösung für den Alltag nicht ausreichend, da es zu wiederholter Interaktion zwingt.

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

## Prinzipien

- Kein Passwort als primärer Auth-Faktor
- Authentifizierung ist getrennt vom Identitätsmodus (RoN vs. verortet)
- Recovery muss immer möglich bleiben
- Sicherheit wird kontextuell erhöht (step-up auth)

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
