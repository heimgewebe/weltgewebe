---
id: docs.runbook
title: Runbook
doc_type: runbook
status: active
summary: Aktuelle lokale, diagnostische und wiederherstellungsbezogene Betriebsabläufe.
relations:
  - type: relates_to
    target: runbooks/README.md
  - type: relates_to
    target: docs/runbook.observability.md
  - type: relates_to
    target: docs/deploy/README.md
---

# Allgemeines Runbook

Dieses Dokument enthält nur Abläufe, die mit der aktuellen Repositorystruktur
vereinbar sind. Für öffentliche Deployments, Migrationen und Mailbetrieb gelten
die spezialisierten Runbooks unter [`docs/deploy/`](deploy/README.md).

## 1. Lokales Onboarding

### Voraussetzungen

- Git
- Docker mit Compose
- `just`
- Node.js und pnpm gemäß den versionierten Repositorymetadaten
- Rust nur für direkte API-Entwicklung außerhalb des Containerpfads

### Start

```bash
git clone <repo-url>
cd weltgewebe
cp .env.example .env
just up
```

Prüfen:

```bash
curl -fsS http://127.0.0.1:8081/api/health/live
curl -fsS http://127.0.0.1:8081/api/health/ready
```

Die Web-/Caddy-Frontdoor liegt im Standard-Core-Profil auf Port `8081`. Der
SvelteKit-Devserver kann für direkte Webentwicklung separat gestartet werden;
er ist nicht mit dem Compose-Frontdoor gleichzusetzen.

### Qualitätsprüfung

```bash
just check
just ci
```

`just ci` ist der breitere lokale Spiegel. Datenbank-, Browser- und
Deploybeweise besitzen zusätzliche Workflows und können externe Dienste oder
Container benötigen.

## 2. Diagnose

### Vor jeder Änderung

1. Git-Head, Branch und Dirty-State prüfen.
2. laufende Compose-Projekte und Zielprofile prüfen.
3. effektive Env nur redigiert beziehungsweise als Vorhandenseinsmetadaten
   lesen.
4. Datenquellschalter und Migrationsmodus prüfen.
5. erst danach einen Reparaturpfad wählen.

### Health und Logs

```bash
docker compose -f infra/compose/compose.core.yml ps
curl -fsS http://127.0.0.1:8081/api/health/live
curl -fsS http://127.0.0.1:8081/api/health/ready
docker compose -f infra/compose/compose.core.yml logs --tail=200 api caddy
```

Logs dürfen nicht unredigiert weitergegeben werden, wenn Token-, Mail- oder
Secretwerte enthalten sein könnten.

### Typische Fehlerklassen

| Symptom | zuerst prüfen |
|---|---|
| `502` oder leere Frontdoor | Caddy-Upstream, Compose-Netz, TLS-/Hostvertrag |
| Loginmail fehlt | Public-Login-Schalter, SMTP-Bereitschaft, Absender und redigierte Logs |
| Login gilt nur scheinbar lokal | Cookie-Scope, Sessionstore, `/auth/me`, Browserprofil |
| Änderung verschwindet nach Neustart | Domain-Lese- und Schreibquelle |
| API startet nicht | Konfigurationsvalidierung, Proxyentscheidung, Migrationsmodus |
| Karte bleibt leer | Web-Build, Basemap-Konfiguration, PMTiles-Range und API-Daten getrennt |

## 3. Datenquellen und Migrationen

Im belegten Produktionspfad `wg-prod-1` ist PostgreSQL die Lese- und
Schreibwahrheit für Accounts/Garnrollen, Knoten und Fäden. JSONL bleibt für
lokale Entwicklung, Legacy-Daten, Import/Export und explizite Rollbacks
erhalten, ist aber keine offene Produktions-Cutover-Behauptung mehr. Vor jeder
Änderung an Datenquellen:

1. Backfill-/Orphan-Belege lesen,
2. PostgreSQL-Lese- und Schreibquellen gemeinsam prüfen,
3. JSONL nur als bewusst dokumentierten Legacy-/Rollbackpfad verwenden,
4. Migrationen separat autorisieren,
5. Restart- und Readback-Verhalten prüfen.

Ein Health-Smoke, Compose-Start oder erfolgreicher Build erteilt keine
Migrationsfreigabe. Siehe
[`docs/deploy/vps-db-initialization-boundary.md`](deploy/vps-db-initialization-boundary.md).

## 4. Wiederherstellung

### Heute belegbarer Rahmen

Das Repository enthält jetzt einen kanonischen logischen PostgreSQL-Backup- und
Restore-Proof-Vertrag unter `scripts/ops/`. Es enthält weiterhin keinen
implementierten WAL-/PITR-, Object-Lock-, Outbox-Replay- oder
Projector-Rebuild-Vertrag. RTO/RPO-Werte dürfen deshalb nur für den tatsächlich
betriebenen logischen Backup-Pfad behauptet werden.

Ein sicherer Wiederherstellungstest muss in einer entbehrlichen Umgebung:

1. den exakten Repository-/Image-Stand festhalten,
2. `scripts/ops/postgres-backup.sh` mit Retention, Gzip-Test und
   SHA256-Manifest ausführen,
3. `scripts/ops/postgres-restore-latest-proof.sh` einen netzlosen
   PostgreSQL-Wegwerfcontainer erstellen und wieder entfernen lassen,
4. Migrationen über `_sqlx_migrations` und den konfigurierten
   `WELTGEWEBE_API_STARTUP_MIGRATIONS`-Modus prüfen,
5. die effektiven Domainquellen dokumentieren,
6. den Off-Host-Pull nach `~/merges/weltgewebe-production-backups` und den
   nachfolgenden Restic-Snapshot belegen,
7. API-Readiness, Auth-Sitzung, Passkey-Credential-Store und repräsentative
   Domänenlesevorgänge testen,
8. Ergebnis, Dauer, Datenstand und Restlücken festhalten.

Ohne registrierte Sicherungsquelle wird kein hypothetisches S3-, WAL-, Nomad-,
Outbox- oder JetStream-Verfahren erfunden.

### Noch nötig für weitergehende Wiederherstellungsziele

- ausdrücklich beschlossene RTO/RPO-Ziele;
- WAL-/PITR nur bei einem belegten Bedarf an feinerem RPO;
- regelmäßige Auswertung von Timer-, Pull- und Restic-Belegen;
- wiederholte Drills nach Änderungen am Schema oder Betriebsweg.

## 5. Public Login und SMTP

Der aktuelle Produktionsablauf steht in
[`docs/deploy/vps.md`](deploy/vps.md) und im Mail-Migrationsrunbook. Mindestregeln:

- `AUTH_PUBLIC_LOGIN` erst nach grünem SMTP-Readiness-Preflight aktivieren,
- `AUTH_LOG_MAGIC_TOKEN` in Produktion deaktiviert halten,
- `AUTH_TRUSTED_PROXIES` ausdrücklich setzen,
- Secretwerte nicht ausgeben,
- nach Änderung API-Readiness und reale Mailzustellung prüfen.

Die API erzwingt IP- und E-Mail-basierte Ratelimits. Caddy bereinigt fremde
Forwardingheader und setzt die beobachtete Remote-Adresse neu. Ein alternativer
Proxy muss denselben Vertrag erfüllen.

## 6. Account- und Produkt-Smokes

Der erste Admin kann über den ausdrücklich aktivierten Bootstrap-Pfad erzeugt
werden. Weitere Accounts entstehen über den administrativen API-Pfad. Die
konkreten Befehle und Variablen stehen in den Dev-/Deployskripten; echte Namen,
Adressen und E-Mail-Adressen gehören nicht in Repositorybeispiele oder Logs.

Der erste durchgängige persistente Produkt-Smoke ist belegt: Anmeldung,
Garnrolle, Knoten, Faden, Neuladen und API-Neustart erhalten denselben
PostgreSQL-Stand. Nach relevanten Deploys wird dieser Pfad erneut geprüft.
Weitere Produkt-Smokes betreffen repräsentative Datenmengen, Geräteparität,
Edge-Referenzintegrität und zusätzliche Produktbereiche.

## 7. Stoppen und Aufräumen

```bash
just down
```

Volumes, Daten, fremde Compose-Projekte oder Runtime-Secrets werden nicht als
Routine-Aufräumaktion gelöscht. Solche Eingriffe brauchen einen eigenen
Wiederherstellungs- und Autorisierungsbeleg.
