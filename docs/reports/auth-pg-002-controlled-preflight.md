---
id: reports.auth-pg-002-controlled-preflight
title: "AUTH-PG-002 Controlled Preflight"
doc_type: report
status: active
lifecycle_state: active
lifecycle: planning
owner_task: AUTH-PG-002
review_after: 2026-09-30
created: 2026-07-01
lang: de
summary: >
  Dokumentiert die Review-before-effect-Grenze fuer den naechsten AUTH-PG-002
  Runtime-Schritt. Dieser Slice ist dokumentarisch und fuehrt keine Runtime-
  Aenderung aus.
relations:
  - type: depends_on
    target: docs/reports/auth-pg-002-runtime-schema-readiness-heimserver-2026-07-01.md
  - type: relates_to
    target: docs/reports/auth-status-matrix.md
---

# AUTH-PG-002 Controlled Preflight

## Zweck

Dieser Report haelt fest: Der naechste AUTH-PG-002-Schritt braucht zuerst eine
kontrollierte Review-Grenze. Der Befund vom 2026-07-01 zeigt, dass die Runtime
noch nicht auf dem erwarteten Passkey-Schema-Stand ist.

Nach PR #1341 ist der Route-Level-Proof fuer Register -> Reload -> Auth auf
API-Ebene belegt. Der naechste Engpass ist deshalb nicht ein weiterer Test des
Routenpfads, sondern der Schemastand der Zielumgebung.

## Grenzen

Dieser Slice ist ohne Runtime-Wirkung:

- keine Datenbank-Aenderung,
- kein Foreign Key,
- kein Cutover,
- kein Umschalten der Credential-Quelle,
- keine Ablage vertraulicher Runtime-Daten im Repo.

## Befundbasis

Belegt ist:

- Die Repo-Migration fuer `passkey_credentials` existiert.
- Die Migration erzeugt die Tabelle und einen Account-Index.
- Sie setzt keinen Foreign Key.
- Sie schaltet die Passkey-Credential-Quelle nicht um.
- Der Runtime-Audit vom 2026-07-01 fand `domain_accounts`, aber keine
  `passkey_credentials`.

## Prueffragen vor einer spaeteren Wirkung

1. Ist das Zielsystem eindeutig benannt?
2. Ist der aktuelle Runtime-Stand erneut read-only geprueft?
3. Ist der erwartete Repo-Stand gelesen?
4. Ist der Rueckweg bekannt?
5. Bleibt der Cutover getrennt?
6. Ist ein read-only Nachaudit definiert?
7. Ist klar dokumentiert, dass ein erfolgreicher Schema-Schritt kein
   Produktions-Cutover ist?

## Freigabeform

```text
AUTH-PG-002 Runtime-Schritt freigegeben: ja/nein
Zielsystem geprueft: ja/nein
Rueckweg bekannt: ja/nein
Vorab-Audit gelesen: ja/nein
Kein Cutover in diesem Schritt: ja/nein
```

Ohne diese Freigabe bleibt der Vorgang ein Plan.

## Entscheidung

Die naechste Wirkung darf nur das Schema bereitstellen. Sie darf noch keine
Produktionswahrheit ueber gespeicherte Passkey-Credentials behaupten.

Naechste Aktion nach menschlicher Freigabe: kontrollierter Runtime-Schritt,
danach erneuter read-only Audit und erst danach FK-Readiness erneut bewerten.
