---
id: deploy.DRIFT_POLICY
title: Drift Policy
doc_type: reference
status: active
canonicality: derived
summary: Richtlinie zur Erkennung und Behandlung von Deployment-Drift.
related_docs:
  - docs/deploy/README.md
  - docs/deployment.md
---
# Drift-Taxonomie & Guard-Policy

> **Status:** Entwurf (Jan 2026)
> **Kontext:** Heimserver Deployment

Dieses Dokument klassifiziert Infrastruktur-Drift (Abweichung zwischen Code/Doku und Realität).
Ziel ist nicht, jede Abweichung zu verhindern, sondern sie **sichtbar** zu machen und zu bewerten.

---

## 1. Drift-Taxonomie

Wir unterscheiden Drift nicht nach "gut/schlecht", sondern nach Risiko und Intention.

### 🟢 Erlaubt (Grün)

*Zustandsänderungen, die zum normalen Betrieb gehören.*

* **Runtime-Daten**: Füllstände von Datenbank-Volumes (`pg_data_prod`), Logs.
* **Transiente Artefakte**: Temporäre Dateien in Containern (`/tmp`, Caches).
* **Lokale Env-Overrides**: Bewusste `.env`-Anpassungen für Secrets, die nicht im Repo stehen
  (solange sie Schema-konform sind).

### 🟡 Verdächtig (Gelb)

*Abweichungen, die auf Konfigurationsfehler oder unsauberen Betrieb hindeuten.*

* **Unbekannte Volumes**: Volumes, die dem Prefix-Schema entsprechen (`compose_*`),
  aber nicht im `compose.prod.yml` definiert sind (mögliche "Leichen").
* **Restart-Zyklen**: Container, die im Snapshot als "Running" erscheinen, aber kurze Uptime haben (Instabilität).
* **Render-Warnings**: `render_degraded: true` im Snapshot (fehlende Env-Vars im CI/Dry-Run), wenn dies in Prod auftritt.

### 🔴 Kritisch (Rot)

*Sicherheits- oder Architekturverletzungen. Sofortiger Handlungsbedarf.*

* **Port-Exposure**: Ein Container bindet auf `0.0.0.0`, obwohl er `127.0.0.1` sein sollte (oder umgekehrt).
* **Container-Injektion**: Laufende Container im Project-Namespace, die nicht im Compose-File stehen
  (mögliche Backdoors oder manuelle Eingriffe).
* **Hash-Mismatch**: Die Hashsumme der laufenden `compose.prod.yml` weicht vom Repo-Stand ab
  (ungetrackte Änderungen am Host).

---

## 2. Guard-Policy

Unsere Tools setzen diese Taxonomie wie folgt um:

| Ebene | Mechanismus | Prüfziel |
| :--- | :--- | :--- |
| **CI (Dry)** | `deploy-snapshot.yml` | Prüft Schema-Validität und `compose` Config-Hashbarkeit. Markiert Warnings. |
| **Repo** | `deploy-drift-guard.yml` | Verhindert, dass Infra-Code (`infra/`) geändert wird, ohne dass Doku/Scripte mitziehen. |
| **Live** | `deploy-snapshot.sh` | Erfasst den *Ist-Zustand* (Container, Ports, Volumes) für manuellen Abgleich. |

**Grundsatz:**
> Drift ist kein technischer Fehler, sondern eine semantische Information.
> Ein "roter" Drift muss entweder korrigiert (Fix) oder dokumentiert (Policy-Update) werden.

---

## 3. Offene Flanken (Epistemische Lücken)

Folgende Aspekte sind **noch nicht** durch automatische Drift-Erkennung abgedeckt und erfordern manuelle Disziplin:

1. **Firewall**: UFW/Netzwerk-Regeln auf dem Host sind unsichtbar für Docker-Snapshots.
2. **Backups**: Die Existenz von Backups wird nicht geprüft (nur die Existenz der Volumes).
3. **Host-System**: OS-Updates, Kernel-Versionen oder installierte Pakete (außer Docker) werden nicht überwacht.

Diese Lücken gelten als **akzeptiertes Restrisiko** im aktuellen "Container-First" Modell.
