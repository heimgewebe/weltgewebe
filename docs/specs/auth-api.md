---
id: specs.auth-api
title: Auth API Spec
doc_type: reference
status: active
canonicality: derived
summary: Spezifiziert Endpunkte, Token-Typen, Geräteverwaltung, Passkeys und Step-up Auth für das Auth-System.
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
- `challenge_id`: serverseitig erzeugte Kennung einer ausstehenden sensiblen Aktion, an die eine Step-up-Bestätigung gebunden wird

## Token-Typen

- `magic_link_token`: Einmal-Token für den Login via E-Mail.
- `session_access_token`: Kurzlebiger Access-Token für API-Anfragen.
  Wird bevorzugt über einen sicheren HttpOnly-Mechanismus transportiert.
- `session_refresh_token`: Langlebiger Token für die Erneuerung der Session ohne erneuten Login.

## Fehlercodes

Bei Validierungs- oder Status-Fehlern antwortet die API mit einem der folgenden Codes
(z.B. als Teil eines 400, 401 oder 403 Responses):

- `TOKEN_EXPIRED`: Der übermittelte Token ist nicht mehr gültig.
- `TOKEN_INVALID`: Der Token ist strukturell falsch, nicht (mehr) in der DB oder anderweitig ungültig.
- `SESSION_EXPIRED`: Die Session (bzw. der Refresh-Token) ist abgelaufen.
- `STEP_UP_REQUIRED`: Für diese Aktion ist eine stärkere Authentifizierung nötig (siehe Step-up Auth).

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

*Anti-Enumeration:*
Die Antwort ist stets generisch (`204 No Content`), unabhängig davon, ob zur E-Mail ein Account existiert,
neu provisioniert wird oder die Anfrage ignoriert wurde.
Dies verhindert, dass die API zur Benutzer-Existenzprüfung (Enumeration) missbraucht werden kann.
Rate Limiting ist hierbei ein integraler Bestandteil des Abuse-Schutzes.

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

### Session erneuern

`POST /auth/session/refresh`

Request:

Der Request enthält den `session_refresh_token` (typischerweise über ein HttpOnly-Cookie).

Response:

```json
{
  "session": {
    "expires_at": "...",
    "device_id": "..."
  }
}
```

Verhalten:

- Ein erfolgreicher Refresh generiert einen neuen `session_access_token` und rotiert den `session_refresh_token`.
- Der alte `session_refresh_token` wird serverseitig invalidiert.
- Bei einem ungültigen oder abgelaufenen Refresh-Token antwortet die API mit `401 Unauthorized`.
  Der Payload enthält dabei den Fehlercode `SESSION_EXPIRED`.

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

### Passkeys auflisten

`GET /auth/passkeys`

Response:

```json
[
  {
    "id": "...",
    "label": "iPhone",
    "created_at": "...",
    "last_used_at": "..."
  }
]
```

### Registrierung starten

`POST /auth/passkeys/register/options`

### Registrierung abschließen

`POST /auth/passkeys/register/verify`

### Login starten

`POST /auth/passkeys/auth/options`

### Login abschließen

`POST /auth/passkeys/auth/verify`

### Passkey entfernen

`DELETE /auth/passkeys/:id`

## Step-up Auth

Step-up Auth wird erzwungen für folgende Endpunkte / Aktionen:

- `PUT /me/visibility` (Verortung hinzufügen/ändern)
- `/me/email` (E-Mail ändern; konkrete HTTP-Methode noch offen, nötig für finalen API-Contract)
- `POST /auth/passkeys/register/*` und `DELETE /auth/passkeys/:id` (Passkey hinzufügen/entfernen)
- `DELETE /auth/devices/:id` (sofern es sich **nicht** um das aktuell anfragende Gerät handelt)
- `POST /auth/logout-all` (alle Sessions widerrufen)

API Response bei fehlender Berechtigung für diese Endpunkte:

`403 Forbidden` mit Payload: `{"error": "STEP_UP_REQUIRED", "challenge_id": "..."}`

Möglichkeiten zur Auflösung:

- Passkey (bevorzugt, falls registriert)
- frischer Magic Link (als Step-up-Magic-Link)

### Step-up-Magic-Link anfordern

`POST /auth/step-up/magic-link/request`

Request:

```json
{
  "challenge_id": "..."
}
```

Response:

`204 No Content`

### Step-up-Magic-Link konsumieren

`POST /auth/step-up/magic-link/consume`

Request:

```json
{
  "token": "...",
  "challenge_id": "..."
}
```

Response:

`204 No Content` (Freigabe erteilt)

**Mechanik des Step-up-Magic-Links:**

Ein Step-up-Magic-Link unterscheidet sich von einem normalen Login-Link dadurch,
dass er kryptografisch an die ausstehende sensible Aktion bzw. eine serverseitige `challenge_id` gebunden ist.
Ein Step-up-Request ist nur aus einer aktiven Session heraus zulässig.
Die `challenge_id` ist kurzlebig, strikt single-use und an die aktuelle Session und den Intent gebunden.
Die Konsumierung dieses Links **etabliert keine neue Session**, sondern berechtigt ausschließlich zur Ausführung
des ausstehenden Intents oder öffnet ein sehr kurzlebiges Zeitfenster (z.B. wenige Minuten).
Es entsteht kein impliziter "Superuser"-Zustand.
Ungültige oder abgelaufene Step-up-Links werfen ein generisches `401 Unauthorized` (`TOKEN_INVALID` / `TOKEN_EXPIRED`),
um keine semantisch reichhaltigen Fehlerdetails über abgelaufene oder fremde Challenges preiszugeben.

## Magic Link Details

- Token wird serverseitig **nur gehasht** gespeichert (Vergleich via Hash).
- Token ist strikt **einmalig nutzbar**.
- Mehrfachverwendung führt zu `401 Unauthorized`.
  Falls noch in der DB vermerkt, wird der Token sofort invalidiert.
- TTL ≤ 15 Minuten.

## Session-Modell

- **Access Token TTL**: z. B. 15 Minuten.
- **Refresh Token TTL**: z. B. 30 Tage.
- **Rotation-Regel**:
  - Der Refresh Token wird bei erfolgreicher Nutzung zur Generierung eines neuen Access Tokens ersetzt.
  - Alte, bereits benutzte Refresh Tokens werden serverseitig invalidiert.

## Device Modell

- Jede Session gehört exakt zu einem `device_id` (serverseitig generiert).
- Felder eines Devices:
  - `device_id`
  - `last_active`
  - `created_at`
- Beim Logout wird primär die dem anfragenden `device_id` zugehörige Session (inkl. Refresh Token) gelöscht.

## Session-Transport und Request-Schutz

Sobald die Session (speziell der `session_refresh_token` oder `session_access_token`)
über HttpOnly-Cookies transportiert wird, muss die API zwingend vor Cross-Site-Angriffen geschützt werden:

- Mutierende Auth-Endpunkte (wie `/auth/logout`, `/auth/logout-all`, `/auth/session/refresh`, `/auth/step-up/...`)
  und alle entsprechenden `/me/...`-Änderungen dürfen nicht ausschließlich auf die Präsenz eines Cookies vertrauen.
- Der Schutz erfolgt architekturkonform (z.B. durch SameSite-Policy `Strict`/`Lax` kombiniert mit
  expliziten CSRF-Tokens oder strengen Origin/Referer-Checks).
- Die konkrete technische Festlegung dieses Schutzes ist eine offene Architekturentscheidung,
  die zwingende Invariante lautet jedoch: Eine cookiebasierte Session ohne Request-Schutz ist unzulässig.

## Sicherheitsregeln

- Rate Limiting:
  - auf `/auth/magic-link/request` (als integraler Abuse- und Enumeration-Schutz)
- Logging:
  - Login-Versuche (Erfolg, Fehler)
  - Geräteänderungen
  - Step-up-Events
