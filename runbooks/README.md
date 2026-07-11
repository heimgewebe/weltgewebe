---
id: runbooks.readme
title: Runbooks
summary: Einstieg in die operativen Runbooks und die Reihenfolge sicherer Diagnose- und Änderungsschritte.
role: runbooks
organ: ops
status: canonical
canonicality: operational
lifecycle_state: active
owner: ops
review_after: 2026-10-11
last_reviewed: 2026-07-11
depends_on: []
relations:
  - type: relates_to
    target: docs/deploy/README.md
  - type: relates_to
    target: docs/runbook.md
  - type: relates_to
    target: docs/runbook.observability.md
verifies_with: []
---

# Runbooks

## Grundregel

Erst beobachten, dann entscheiden, dann verändern, danach erneut beobachten.
Ein grünes Repository oder ein erfolgreiches Deploymentskript ersetzt keinen
Livebeleg.

## Einstieg nach Situation

| Situation | Einstieg |
|---|---|
| öffentlicher VPS deployen oder prüfen | [`docs/deploy/vps.md`](../docs/deploy/vps.md) |
| Deploymentvertrag und Profile verstehen | [`docs/deploy/README.md`](../docs/deploy/README.md) |
| Migrationen auf VPS einordnen | [`docs/deploy/vps-db-initialization-boundary.md`](../docs/deploy/vps-db-initialization-boundary.md) |
| migrationssicheren Runtime-Smoke ausführen | [`docs/deploy/vps-migration-safe-runtime-smoke.md`](../docs/deploy/vps-migration-safe-runtime-smoke.md) |
| Public Login und SMTP vorbereiten | [`docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md`](../docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md) |
| Sicherheitsgrenzen prüfen | [`docs/deploy/security.md`](../docs/deploy/security.md) |
| allgemeine Anwendungsvorfälle | [`docs/runbook.md`](../docs/runbook.md) |
| Metriken und Diagnose | [`docs/runbook.observability.md`](../docs/runbook.observability.md) |
| Drift klassifizieren | [`docs/deploy/DRIFT_POLICY.md`](../docs/deploy/DRIFT_POLICY.md) |

## Sichere Reihenfolge für Deployarbeit

1. Zielhost, Repository, Commit und Arbeitsbaum prüfen.
2. offene PRs, laufende Deploys und Leases prüfen.
3. Env nur auf Vorhandensein und Quelle prüfen; keine Secretwerte ausgeben.
4. Compose rendern und Zielprofil verifizieren.
5. Datenbankhistorie und Migrationsmodus prüfen.
6. kanonischen Deploypfad ausführen.
7. Health, Routing, Auth und Logs nach dem Effekt prüfen.
8. Revision, Ergebnis und Restunsicherheit als Beleg festhalten.

## Diagnose vor Reparatur

- **502/Proxyfehler:** Caddy-Ziel, Upstream, TLS und Headervertrag prüfen.
- **Loginfehler:** Public-Login-Schalter, SMTP-Bereitschaft, Sessionstore und
  Cookie-Scope getrennt prüfen.
- **Daten fehlen nach Neustart:** Lese- und Schreibquelle vergleichen; keine
  JSONL/PostgreSQL-Mischung zulassen.
- **Migration schlägt fehl:** nicht wiederholt blind starten; Verlauf und
  Preflightgrenze lesen.
- **Karte bleibt leer:** Web-Build, Basemap-Konfiguration, PMTiles-Range und
  API-Fallback getrennt prüfen.

## Destruktive Grenzen

Die folgenden Schritte brauchen einen eigenen autorisierten Vorgang und einen
Wiederherstellungsplan:

- Datenbankmigrationen oder Datenbereinigung,
- Secretrotation,
- DNS-/Provideränderungen,
- Volume- oder Datenlöschung,
- Zwangsentfernung fremder Compose-Projekte,
- irreversible Entfernung der Legacy-`mode`-Rollbackbrücke.

## Veraltete Runbooks

Historische Heimserver- und Übergangsdokumente können weiterhin nützliche
Verträge enthalten. Sie dürfen nicht als aktueller Produktionspfad behandelt
werden, wenn ihr Dokumentkopf oder die Deploymentübersicht sie als retired oder
Referenz ausweist.
