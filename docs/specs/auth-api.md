---
id: specs.auth-api
title: Auth Api Spec
doc_type: reference
status: active
canonicality: derived
---

# Auth API Spec

## Überblick

Das Auth-System basiert auf:

- Magic Links (E-Mail)
- Session Tokens
- optional Passkeys

## Begriffe

- Session: langlebiger Zugangszustand
- Magic Link Token: einmaliger Login-Token
- Step-up Auth: erneute Verifikation bei sensiblen Aktionen

## Endpunkte

### Magic Link anfordern

`POST /auth/magic-link/request`

Request:

```json
{
  "email": "user@example.com"
}
```

Response:

`204 No Content`

### Magic Link konsumieren

`POST /auth/magic-link/consume`

Request:

```json
{
  "token": "..."
}
```

Response:

```json
{
  "session": {
    "expires_at": "...",
    "device_id": "..."
  }
}
```

### Session abrufen

`GET /auth/session`

Response:

```json
{
  "authenticated": true,
  "expires_at": "...",
  "device_id": "..."
}
```

### Logout

`POST /auth/logout`

### Logout alle Geräte

`POST /auth/logout-all`

### Geräte anzeigen

`GET /auth/devices`

Response:

```json
[
  {
    "device_id": "...",
    "last_active": "...",
    "current": true
  }
]
```

### Gerät entfernen

`DELETE /auth/devices/:id`

## Passkeys

### Registrierung starten

`POST /auth/passkeys/register/options`

### Registrierung abschließen

`POST /auth/passkeys/register/verify`

### Login starten

`POST /auth/passkeys/auth/options`

### Login abschließen

`POST /auth/passkeys/auth/verify`

## Step-up Auth

Für sensible Aktionen erforderlich.

Möglichkeiten:

- Passkey
- frischer Magic Link

## Sicherheitsregeln

- Magic Link Tokens:
  - TTL ≤ 15 Minuten
  - single-use
- Sessions:
  - rotierend
  - serverseitig widerrufbar
- Rate limiting:
  - auf `/magic-link/request`
- Logging:
  - Login-Versuche
  - Geräteänderungen
