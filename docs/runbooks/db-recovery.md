---
id: runbooks.db-recovery
title: DB Recovery Runbook
doc_type: reference
status: active
summary: >
  Eigenständiger Datenbank-Wiederherstellungsablauf für Weltgewebe: PostgreSQL-PITR
  und JSONL-Domänendaten, Backup-Annahmen, Recovery-Ablauf, Integritätsprüfung,
  Rollback-/Fallback-Pfad, Risiken und Verifikation nach Recovery.
relations:
  - type: relates_to
    target: docs/runbooks/README.md
  - type: relates_to
    target: docs/runbook.md
  - type: relates_to
    target: docs/runbooks/incident-response.md
  - type: relates_to
    target: docs/adr/ADR-0007__auth-persistence-production-db-path.md
  - type: relates_to
    target: docs/datenmodell.md
---
# DB Recovery Runbook

Eigenständiger Ablauf zur Wiederherstellung der persistenten Daten von Weltgewebe
nach Korruption, versehentlicher Löschung, fehlgeschlagener Migration oder
Hostverlust. Der übergeordnete Vorfallprozess steht in
[Incident Response](incident-response.md); der quartalsweise Probelauf in
[`docs/runbook.md` §2](../runbook.md) übt genau dieses Runbook ein.

## 1. Ziel und Anwendungsbereich

Ziel ist ein reproduzierbarer Recovery-Ablauf mit klarer Integritäts- und
Rollback-Logik. Maßgeblich ist die **gespaltene Datenebene** im aktuellen
Architekturstand:

- **PostgreSQL** hält heute **Auth-/Session-Daten** (`sessions`-Tabelle;
  Migrationen aus `apps/api/migrations/`; direkter Zugriff über `DATABASE_URL`,
  Port `5432`, gemäß
  [ADR-0007](../adr/ADR-0007__auth-persistence-production-db-path.md)).
- **JSONL** hält die **Domänendaten** (Nodes, Accounts, Edges) unter
  `GEWEBE_IN_DIR` (Standard `.gewebe/in`). Der In-Memory-Store wird beim
  API-Start aus dem JSONL geladen. Die Migration nach PostgreSQL ist offen
  (Optimierungsticket `OPT-ARC-001`).

Diese Trennung ist entscheidend: **Domänen-Recovery ≠ Session-Recovery**.
Sessionverlust ist tolerierbar (Nutzer melden sich neu an); Domänendatenverlust
ist es nicht.

Zielwerte aus dem DR-Drill ([`docs/runbook.md` §2](../runbook.md)):

- **RTO:** < 4 Stunden
- **RPO:** < 5 Minuten

## 2. Datenquellen

| Datenklasse | Speicher | Restore-Quelle |
|---|---|---|
| Sessions / Auth | PostgreSQL `sessions` | Base-Backup + WAL (PITR); Migrationen `apps/api/migrations/` |
| Nodes / Accounts / Edges (Domäne) | JSONL unter `GEWEBE_IN_DIR` (`.gewebe/in`) | Backup der JSONL-Dateien; In-Memory-Store lädt beim Start neu |
| Outbox / Events (Gate C) | PostgreSQL `outbox` → NATS JetStream | Base-Backup + WAL; Replay über Outbox-Relay + Projektoren |
| Lese-Modelle (`faden_view` etc.) | abgeleitet | Rebuild durch Projektoren aus Events — **keine** primäre Quelle |

Lese-Modelle sind abgeleitet und werden neu aufgebaut, niemals als Wahrheitsquelle
restauriert. Das Domänenmodell beschreibt [`docs/datenmodell.md`](../datenmodell.md).

## 3. Backup-/Restore-Annahmen

- **PostgreSQL:** WAL-Archivierung aktiv; Base-Backups und WAL liegen extern
  (z. B. S3), verschlüsselt (z. B. SSE-KMS) und via Object Lock unveränderbar
  (siehe [`docs/runbook.md` §2 Vorbereitung](../runbook.md)).
- **JSONL:** wird **separat** gesichert. `.gewebe/in/` ist git-ignored und daher
  **nicht** Teil des Repos — ein eigener Backup-Job ist Voraussetzung. Fehlt er,
  ist der Domänen-RPO der letzte manuelle Export (siehe [§7 Risiken](#7-risiken)).
- **Zielpfad:** Produktion nutzt direkten PostgreSQL-Zugriff (`5432`,
  [ADR-0007](../adr/ADR-0007__auth-persistence-production-db-path.md)). PgBouncer
  (`6432`) ist Dev-/Spezialpfad und **kein** Restore-Ziel-Gate.
- **Forensik vor Promotion:** Wenn die Integrität fraglich ist, zuerst in eine
  **saubere, quarantänisierte** Instanz restaurieren; das korrupte Primary erst
  nach Evidenzsicherung überschreiben (siehe
  [Incident Response §8](incident-response.md)).

## 4. Recovery-Ablauf

1. **Vorfall sichern:** Evidenz nach [Incident Response §8](incident-response.md)
   ziehen. **Niemals `just down`** (entfernt Volumes).
2. **Schreiber stoppen:** API in Wartung nehmen (API-Container anhalten), damit
   während des Restores keine neuen Schreibvorgänge laufen.
3. **Saubere PostgreSQL-Instanz bereitstellen** (neues Volume, keine Altdaten).
4. **PITR durchführen:** Base-Backup einspielen, dann WAL bis zum Zielzeitpunkt
   **kurz vor** dem Vorfall nachfahren. Die konkreten Kommandos hängen vom
   Backup-Tooling ab und sind hier als Platzhalter zu verstehen:

   ```bash
   # Beispiel/Platzhalter — abhängig vom eingesetzten Backup-Tooling.
   # Recovery-Zielzeit (recovery_target_time) bewusst vor den Vorfall legen.
   # restore_base_backup <basis-backup>
   # configure_recovery_target_time "<JJJJ-MM-TT HH:MM:SS>"
   # start_postgres_in_recovery
   ```

5. **Migrationen anwenden:** Schemastand gegen den Code sicherstellen.

   ```bash
   just db-wait
   just db-migrate
   ```

   Die API führt `sqlx::migrate!("./migrations")` zusätzlich beim Start aus.
6. **JSONL-Domänendaten zurückspielen:** Gesichertes JSONL nach `GEWEBE_IN_DIR`
   (`.gewebe/in`) legen.
7. **API starten:** Der In-Memory-Store lädt die Domänendaten aus dem JSONL;
   Sessions kommen aus PostgreSQL.
8. **Event-Pfad neu starten (nur Gate C / NATS):** Outbox-Relay starten, dann
   Projektoren — diese bauen die Lese-Modelle (`faden_view` etc.) neu auf.
9. **Service freigeben:** Edge/Caddy wieder auf den Stack zeigen lassen.

## 5. Integritätsprüfung

**PostgreSQL:**

```bash
just db-wait
```

- Migrationsstand prüfen (Tabelle `_sqlx_migrations` vollständig angewendet).
- Zeilenzahlen in `sessions` plausibilisieren.
- `outbox` auf unverarbeitete Events prüfen (Backlog für [§4 Schritt 8](#4-recovery-ablauf)).

**JSONL-Domänendaten:**

- Jede Zeile ist valides JSON; Datensätze entsprechen
  `contracts/domain/*.schema.json`.
- Schema-Härtung selbst prüfen: `just contracts-domain-check`.
- Keine doppelten IDs; `public_pos` aus `location`/`radius_m` ableitbar.
- Stichprobe bekannter Accounts gegen den letzten guten Stand.

**Querschnitt:**

- Zeilen-/Datensatzzahlen gegen Last-Known-Good vergleichen.
- Lese-Modelle stimmen mit den replayten Events überein.

## 6. Rollback-/Fallback-Pfad

Schlägt der Restore oder die Integritätsprüfung fehl, die restaurierte Instanz
**nicht** in Produktion promoten. Optionen:

1. **Früheren/anderen Zielzeitpunkt wählen** und PITR erneut fahren.
2. **Domänendaten aus letztem guten JSONL-Export** wiederherstellen und einen
   etwaigen **Sessionverlust akzeptieren** (Nutzer melden sich neu an —
   Sessions sind regenerierbar).
3. **Degradierter Betrieb:** Service read-only/eingeschränkt zurückbringen, bis
   ein sauberer Restore vorliegt.

Das fehlgeschlagene Restore-Artefakt zur Analyse aufbewahren. Leitlinie:
Sessionverlust ist tolerierbar, Domänendatenverlust nicht — bei Konflikt hat die
Integrität der Domänendaten Vorrang.

## 7. Risiken

- **Einzige Domänenquelle ist JSONL:** Fehlt oder veraltet das JSONL-Backup, ist
  der Domänen-RPO schlecht (offenes Ticket `OPT-ARC-001`).
- **`.gewebe/in/` ist git-ignored:** leicht aus dem Backup-Scope zu vergessen.
- **`just down` entfernt Volumes:** im Incident destruktiv — nicht verwenden.
- **Port-Verwechslung:** Restore-Ziel ist direktes PostgreSQL (`5432`), nicht
  PgBouncer (`6432`) — siehe
  [ADR-0007](../adr/ADR-0007__auth-persistence-production-db-path.md).
- **DSGVO:** Backups und Restores enthalten personenbezogene Daten (E-Mails,
  Koordinaten, Token). Restore nur in eine zugriffsbeschränkte Umgebung; keine
  Produktionsdaten in Dev-/geteilte/Ticket-Kontexte kopieren (siehe
  [Incident Response §8](incident-response.md)).
- **PITR-Zielwahl:** zu spätes Ziel holt die Korruption zurück, zu frühes
  verliert Daten.
- **Migrations-Drift:** Ein alter DB-Stand mit neuerem Code setzt
  vorwärtskompatible Migrationen voraus (`apps/api/migrations/`).

## 8. Verifikation nach Recovery

- **Health:** `curl -fsS https://<domain>/api/health/live` (lokal
  `http://localhost:8081/api/health/live`).
- **Smoke:** Bootstrap-Account und Account-Erstellung gegen den wiederher­
  gestellten Stand (siehe [`docs/runbook.md` §4](../runbook.md)):

  ```bash
  just smoke-seed
  just smoke-account-create
  ```

- **Funktionspfad:** Login (Magic-Link oder Dev-Login) funktioniert; Karte zeigt
  Accounts.
- **Event-Pfad:** kein unverarbeiteter `outbox`-Backlog; Projektoren aufgeschlossen.
- **Zielwerte:** Wiederherstellzeit gegen **RTO < 4 h** und Datenverlust gegen
  **RPO < 5 min** prüfen. War dies ein Drill, die Ergebnistabelle in
  [`docs/runbook.md` §2](../runbook.md) ausfüllen.
- **Dokumentation:** Ergebnis in der Incident-Timeline festhalten.
