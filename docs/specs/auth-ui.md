---
id: specs.auth-ui
title: Auth Ui Spec
doc_type: reference
status: active
canonicality: derived
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
"Öffne deine E-Mail auf diesem Gerät."

## Klare UI-Zustände

- **Du bist eingeloggt:** Ansicht des Gewebes. Option zum Aufrufen der Konto-Einstellungen / Geräteverwaltung.
- **Deine Sitzung ist abgelaufen:** "Bitte melde dich erneut an, um fortzufahren."
- **Bitte bestätige deine Identität:** "Für diese Aktion benötigen wir eine zusätzliche Bestätigung." (Step-up Auth Trigger)

## Erfolgreicher Login

- Weiterleitung in App
- **Nur nach** erfolgreichem Login wird der Passkey als Option ("Schnellere Anmeldung aktivieren") angeboten, falls noch nicht auf dem aktuellen Gerät vorhanden.

CTA:
"Auf diesem Gerät merken" (Passkey Registrierung)

## Wiederkehr

Wenn eine gültige Session vorhanden ist, erfolgt der direkte Einstieg ohne weitere Prompts.
Wenn die Session abgelaufen ist oder fehlt, greifen die Authentifizierungs-Flows (Magic Link oder, falls vorhanden, Passkey).

## Step-up Auth UI

Text:
"Bitte bestätige kurz deine Identität"

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
