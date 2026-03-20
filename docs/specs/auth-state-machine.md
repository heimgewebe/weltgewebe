---
id: specs.auth-state-machine
title: Auth State Machine
doc_type: reference
status: active
canonicality: canonical
---

# Auth State Machine

## Zustände

- `unauthenticated`: Kein gültiger Zugang auf dem Gerät.
- `link_requested`: Ein Magic Link wurde erfolgreich angefordert und per E-Mail versendet.
- `authenticated_session`: Eine gültige `session` ist etabliert (sowohl access_token als auch refresh_token sind aktiv).
- `session_expired`: Die Session ist nicht mehr gültig. Eine Neuanmeldung ist notwendig.
- `step_up_required`: Eine aktive Session liegt vor, jedoch wurde eine geschützte Route oder Aktion angefragt.
- `recovery_pending`: Wiederherstellung oder erster Login auf neuem Gerät gestartet.

## Transitionen (Trigger -> Pfad)

- **`unauthenticated` -> `link_requested`:**
  - *Trigger*: User gibt E-Mail ein und klickt "Senden".
  - *Aktion*: System schickt Magic Link E-Mail und geht in Wartezustand.

- **`link_requested` -> `authenticated_session`:**
  - *Trigger*: User klickt auf gültigen Magic Link (`consume`).
  - *Aktion*: System etabliert Session für das jeweilige Device, validiert Hash, und invalidiert Token für weitere Versuche.

- **`unauthenticated` -> `authenticated_session`:**
  - *Trigger*: User authentifiziert sich via Passkey.
  - *Aktion*: System validiert Passkey Response und etabliert Session.

- **`authenticated_session` -> `step_up_required`:**
  - *Trigger*: User versucht eine sensible Aktion (z.B. Verortung, E-Mail-Änderung) auszuführen.
  - *Aktion*: System antwortet mit `403` und Payload `{"error": "STEP_UP_REQUIRED"}`.

- **`step_up_required` -> `authenticated_session`:**
  - *Trigger*: User validiert erfolgreich über Passkey oder einen frischen Magic Link.
  - *Aktion*: Aktion wird freigegeben, System notiert Step-up Event.

- **`authenticated_session` -> `session_expired`:**
  - *Trigger*: Zeitlicher Ablauf des refresh_tokens ODER manueller / serverseitiger Widerruf (Logout / Invalidierung).
  - *Aktion*: Sämtliche zugehörigen Access Tokens auf dem Gerät werden ungültig.

- **`session_expired` -> `link_requested` / `unauthenticated`:**
  - *Trigger*: Nächster Nutzer-Interaktionsversuch (z.B. App öffnen).
  - *Aktion*: Prompt zur Anmeldung (Magic Link oder Passkey, falls konfiguriert).

## Fehlerpfade

- **`link_requested` -> `unauthenticated`:**
  - *Fehler*: Link abgelaufen (TTL > 15m), bereits genutzt, oder strukturell invalid.
  - *Ergebnis*: Token-Konsumierung scheitert mit `401 Unauthorized` und `TOKEN_INVALID` / `TOKEN_EXPIRED`.

- **`step_up_required` -> `session_expired`:**
  - *Fehler*: Step-up schlägt mehrfach fehl oder wurde vom Admin als verdächtig eingestuft.
  - *Ergebnis*: Session-Widerruf, Fallback zu `unauthenticated` via Neuanmeldung.
