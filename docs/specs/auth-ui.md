---
id: specs.auth-ui
title: Auth UI Spec
doc_type: reference
status: active
canonicality: derived
summary: Beschreibt Login-, Wiederkehr-, Step-up- und Geräteverwaltungsflüsse für die Auth-UI.
---

# Auth UI Spec

## Ziele

- minimaler Einstieg
- klare Rückkehrpfade
- kein technischer Jargon

## Login Screen

Text:
"Mit E-Mail anmelden"

Input:
[E-Mail-Adresse]

CTA:
"Link zum Anmelden senden"

## Magic Link Screen

Text:
"Wir haben dir einen Link geschickt."

Hinweis:
"Öffne den Link idealerweise auf diesem Gerät.
Öffnest du ihn auf einem anderen Gerät, wird dort eine neue Sitzung erstellt."

## Klare UI-Zustände

- **Du bist eingeloggt:** Ansicht des Gewebes.
  Option zum Aufrufen der Konto-Einstellungen oder Geräteverwaltung.
- **Deine Sitzung ist abgelaufen:** "Bitte melde dich erneut an, um fortzufahren."
- **Bitte bestätige deine Identität:** "Für diese Aktion benötigen wir eine zusätzliche Bestätigung."
  (Step-up Auth Trigger)

## Erfolgreicher Login

- Weiterleitung in App
- **Nur nach** erfolgreichem Login wird der Passkey als Option ("Schnellere Anmeldung aktivieren") angeboten,
  falls noch nicht auf dem aktuellen Gerät vorhanden.

CTA:
"Schnellere Anmeldung aktivieren" oder "Mit Face ID / Fingerabdruck anmelden" (Passkey Registrierung)

## Wiederkehr

Wenn eine gültige Session vorhanden ist, erfolgt der direkte Einstieg ohne weitere Prompts.
Wenn die Session abgelaufen ist oder fehlt, greifen die Authentifizierungs-Flows
(Magic Link oder, falls vorhanden, Passkey).

## Step-up Auth UI

Text:
"Bitte bestätige kurz deine Identität"

Hinweis bei E-Mail-Option:
"Der per E-Mail gesendete Link bestätigt nur diese angefragte Aktion."

Optionen:

- Face ID / Fingerabdruck (Passkey)
- Link per E-Mail

## Geräteverwaltung

Liste:

- aktuelles Gerät
- andere Geräte

Aktionen:

- Gerät entfernen
- alle abmelden

## Fehlerfälle

### Link abgelaufen

"Der Link ist abgelaufen. Fordere einen neuen an."

### Link ungültig

"Dieser Link ist nicht gültig."

## Tonalität

- ruhig
- klar
- nicht technisch
- keine Begriffe wie:
  - Token
  - Credential
  - WebAuthn
