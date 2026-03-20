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

## Erfolgreicher Login

- Weiterleitung in App
- Session wird erstellt

Optionaler Hinweis:
"Schnellere Anmeldung aktivieren"

CTA:
"Auf diesem Gerät merken" (Passkey)

## Wiederkehr

### Session aktiv

→ direkter Einstieg

### Session abgelaufen

Optionen:

- Passkey
- Magic Link

## Neues Gerät

Flow:

- E-Mail eingeben
- Magic Link
- optional Passkey aktivieren

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
