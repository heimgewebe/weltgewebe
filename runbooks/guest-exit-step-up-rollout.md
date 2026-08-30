---
id: runbooks.guest-exit-step-up-rollout
title: Gast-Austritt mit Step-up zweiphasig ausrollen
summary: Fail-closed Rolloutvertrag für den neuen ExitGuestAccount-Intent im gemeinsamen PostgreSQL-Challenge-State.
role: runbooks
organ: ops
status: canonical
canonicality: operational
lifecycle_state: active
owner: ops
review_after: 2026-10-30
last_reviewed: 2026-08-30
depends_on:
  - runbooks.readme
relations:
  - type: relates_to
    target: apps/api/src/auth/challenges.rs
  - type: relates_to
    target: apps/api/src/routes/governance.rs
  - type: relates_to
    target: platform/apps/weltgewebe/base/api-deployment.yaml
verifies_with:
  - scripts/platform/validate_platform.py
---

# Gast-Austritt mit Step-up zweiphasig ausrollen

`ExitGuestAccount` ergänzt den gemeinsam in PostgreSQL gespeicherten
`step_up_challenge`-Payload um einen neuen serialisierten Intent. Eine API-Binary
von vor dieser Änderung kann diesen Intent nicht deserialisieren. Die Funktion
wird deshalb zweiphasig ausgerollt, statt den neuen Wire-Wert während einer
gemischten RollingUpdate-Phase bereits zu erzeugen.

## Phase 1 — Kompatibilitäts-Rollout

1. `AUTH_GUEST_EXIT_STEP_UP_ENABLED=0` beibehalten.
2. Die kompatibilitätsfähige API-Binary auf alle API-Replikas ausrollen.
3. Deployment- und ReplicaSet-Livezustand zurücklesen und belegen, dass keine
   API-Binary von vor dieser Änderung mehr Traffic bedient.
4. Solange das Gate aus ist, antwortet `POST /accounts/me/exit` fail-closed mit
   `503`; es gibt keinen Fallback auf die frühere direkte Löschung.

## Phase 2 — Aktivierung

1. `AUTH_GUEST_EXIT_STEP_UP_ENABLED=1` setzen.
2. Die API-Replikas erneut ausrollen, damit jeder Prozess den aktivierten Wert
   übernimmt.
3. Belegen, dass `POST /accounts/me/exit` nun `403 STEP_UP_REQUIRED` mit
   `challenge_id` liefert.
4. Einen Ende-zu-Ende-Bestätigungsbeweis durchführen und prüfen, dass der
   Gast-Account erst nach erfolgreichem Verbrauch des Einmal-Tokens gelöscht
   wird.

## Rollback-Grenze

Nach der Aktivierung niemals auf eine API-Binary von vor dem
Kompatibilitäts-Rollout zurückrollen. Eine solche Binary kann
`ExitGuestAccount`-Challenges nicht lesen und enthält außerdem noch den früheren
Direktlöschpfad. Ein Rollback muss eine kompatibilitätsfähige Binary verwenden.
Soll ausnahmsweise noch weiter zurückgerollt werden, zuerst das Gate deaktivieren,
alle kompatiblen Replikas mit deaktiviertem Gate ausrollen und sämtliche noch
laufenden Step-up-Challenges ablaufen lassen, bevor eine ältere Binary Traffic
bedienen darf.
