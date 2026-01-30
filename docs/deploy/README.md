# Weltgewebe – Deployment

Dieses Dokument beschreibt den **kanonischen Deployment-Stand** von Weltgewebe.
Es ist normativ. Abweichungen davon gelten als Drift.

---

## 1. Zweck

Ziel dieser Dokumentation ist es,

- den **operativen Wahrheitsort** des Deployments festzulegen,
- den **Unterschied zwischen Konfiguration und Live-Zustand** klar zu machen,
- und den **Deployment-Snapshot** semantisch einzuordnen.

Dieses Dokument beschreibt **was gelten soll**.
Der Snapshot beschreibt **was ist**.

---

## 2. Kanonische Wahrheiten

### Operativer Repo-Pfad

```text
/opt/weltgewebe
```

Nur dieser Pfad ist operative Deployment-Quelle.
Andere Kopien oder Exporte gelten als nicht autoritativ.

### Docker-Compose

- **Kanonische Datei:**

  ```text
  infra/compose/compose.prod.yml
  ```

- **Compose-Projektname:**

  ```text
  compose
  ```

- Weitere Compose-Dateien (nicht primär produktiv):
  - `compose.core.yml` – Basiskomponenten
  - `compose.observ.yml` – Observability / Zusatzdienste

---

## 3. Services & Netzwerk

### Services

| Service | Rolle | Netzwerk |
| ------- | ----- | -------- |
| api | Applikationslogik | intern |
| caddy | Entry-Gateway | host-published |
| db | PostgreSQL | intern |

### Netzwerkdetails

- **API**
  - läuft intern auf `8080`
  - **nicht** host-published
- **Caddy**
  - einziges öffentliches Entry-Gateway
  - published:
    - `127.0.0.1:80`
    - `127.0.0.1:443`

**Konsequenz:**
Health-Checks dürfen **nicht** über `127.0.0.1:8080` erfolgen.

---

## 4. Persistenz (Volumes)

Docker Compose verwendet automatisch ein Prefix:

```text
<compose-project>_<volume-name>
```

### Logische Volumes

| Logisch | Compose-Name |
| ------- | ------------ |
| pg_data_prod | compose_pg_data_prod |
| nats_js | compose_nats_js |
| gewebe_fs_data | compose_gewebe_fs_data |
| caddy_data | compose_caddy_data |
| caddy_config | compose_caddy_config |

Snapshots speichern **beide Namen**, um Verwechslungen zu vermeiden.

---

## 5. Konfiguration & Env-Variablen

`docker compose` rendert auch dann, wenn bestimmte Env-Variablen fehlen
(z. B. `DATABASE_URL`, `POSTGRES_*`, `NATS_URL`).

In diesem Fall entstehen **WARNINGS** und Default-Werte (leere Strings).

Der Deployment-Snapshot markiert dies explizit als:

```yaml
render_degraded: true
```

Das ist **keine Validierung**, sondern eine **sichtbare Beobachtung**.

---

## 6. Deployment Snapshot

Der Snapshot ist eine **maschinelle Zustandsaufnahme**.

### Modi

| Modus | Zweck |
| ----- | ----- |
| dry | CI / Konfigurationsstand |
| live | Heimserver / Realzustand |

### Dry Snapshot (CI)

- kein Docker-Daemon erforderlich
- erfasst:
  - Compose-Datei-Hash
  - Render-WARNINGS
  - erwartete Services & Volumes

### Live Snapshot (Heimserver)

```bash
cd /opt/weltgewebe
SNAPSHOT_MODE=live bash scripts/wgx-deploy-snapshot.sh
```

- erfasst zusätzlich:
  - laufende Container
  - Image-Digests
  - Volumes
  - Bind-Mounts
  - Health (standardmäßig per Container-Check)

---

## 7. Nicht-Ziele

Der Snapshot ist **kein**:

- Auto-Deploy-Mechanismus
- Secret-Management
- Monitoring-Ersatz

Er dient ausschließlich der **Drift-Sichtbarmachung**.

---

## 8. Geltung

Bei Widerspruch gilt:

```text
Live-Snapshot > Dokumentation > Annahmen
```

Drift ist kein Fehler – **unsichtbare Drift ist es**.
