# Weltgewebe – Deployment

Dieses Dokument beschreibt den **kanonischen Deployment-Stand** von Weltgewebe.
Es ist normativ. Abweichungen davon gelten als Drift.

**Weitere Dokumente:**

- [Deployment-Änderungsprotokoll](./CHANGELOG.md) – Infrastrukturänderungen und deren Auswirkungen
- [Drift-Taxonomie & Guard-Policy](./DRIFT_POLICY.md) – Klassifizierung und Handling von Drift

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
  weltgewebe
  ```

### Project Identity Enforcement & Zombie Guard

Das Deployment-Script `weltgewebe-up` erzwingt den Projektnamen `weltgewebe`.
Es verhindert aktiv den Start, wenn ein paralleles "Zombie"-Projekt (z. B. mit Namen `compose` oder `infra`)
erkannt wird, das dieselben Konfigurationsdateien nutzt.

Dies verhindert Drift und Port-Kollisionen.

**Diagnose:**
Der Guard listet alle blockierenden Container mit Name, Projekt-Label und Config-Pfad auf.

**Remediation:**
1. Manuell: `docker compose -p <fremd_projekt> down`
2. Automatisch: Script mit `--purge-compose-leaks` starten (führt `docker rm -f` aus).

**Optionen:**

- `--purge-compose-leaks`: Entfernt automatisch erkannte Zombie-Container.
- `--build-web`: Erzwingt einen Frontend-Build (erfordert `pnpm`).
- `--no-build-web`: Unterdrückt den Auto-Build des Frontends (warnt nur).

- Weitere Compose-Dateien (nicht primär produktiv):
  - `compose.core.yml` – Basiskomponenten
  - `compose.observ.yml` – Observability / Zusatzdienste
  - `compose.ops.override.yml` – Lokale Entwicklungs-/Ops-Umgebung (NATS + API-Port-Mapping für Debugging)

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
    - `0.0.0.0:80` (Host 80 -> Container 80)
    - `0.0.0.0:443` (Host 443 -> Container 443)

**Konsequenz:**
Health-Checks dürfen **nicht** über `127.0.0.1:8080` (Host) erfolgen, sondern müssen container-intern laufen.

---

## 4. Persistenz (Volumes)

Docker Compose verwendet automatisch ein Prefix:

```text
<compose-project>_<volume-name>
```

### Logische Volumes

| Logisch | Compose-Name |
| ------- | ------------ |
| pg_data_prod | weltgewebe_pg_data_prod |
| gewebe_fs_data | weltgewebe_gewebe_fs_data |
| caddy_data | weltgewebe_caddy_data |
| caddy_config | weltgewebe_caddy_config |

Snapshots speichern **beide Namen**, um Verwechslungen zu vermeiden.
Sollten weitere Volumes live existieren (z. B. Legacy-Volumes), werden diese im Live-Snapshot ebenfalls mit Prefix erkannt.

Die kanonischen Volume-Suffixe sind im Compose-YAML definiert; Snapshot erkennt live alle `${COMPOSE_PROJECT}_*`.
Die obige Tabelle dient als Referenz für erwartete Volumes.

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

### Performance & Limits

- **MAX_EDGES_CACHE**: Obergrenze der beim Start geladenen Edges (Default `500000`).
  Bei Erreichen wird die Datei nicht weiter gelesen und eine Warnung geloggt.

---

## 6. Deployment Snapshot

Der Snapshot ist eine **maschinelle Zustandsaufnahme**.

### Modi

| Modus | Zweck |
| ----- | ----- |
| dry | CI / Konfigurationsstand |
| live | Heimserver / Realzustand |

### Dry Snapshot (CI)

- kein laufender Compose-Stack erforderlich; Compose-Rendering erfolgt best-effort (CI-Umgebung).
- erfasst:
  - Compose-Datei-Hash
  - Render-WARNINGS
  - erwartete Services & Volumes

### Live Snapshot (Heimserver)

```bash
cd /opt/weltgewebe
SNAPSHOT_MODE=live bash scripts/deploy-snapshot.sh
```

- erfasst zusätzlich:
  - laufende Container (Status, Digest)
  - Volumes (dynamisch ermittelt per Prefix)
  - Bind-Mounts
  - Health (standardmäßig per Container-Check via `wget`/`curl` Fallback)

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

Detaillierte Klassifizierung: [Drift-Taxonomie & Guard-Policy](./DRIFT_POLICY.md)

---

## 9. Feature Flags (Public Login)

Das System unterstützt einen öffentlichen "Magic Link" Login.
Standardmäßig ist dieser **deaktiviert**.

### Aktivierung

Um den Public Login zu aktivieren, müssen folgende Variablen in der `.env` gesetzt werden:

```bash
AUTH_PUBLIC_LOGIN=1
APP_BASE_URL=https://mein-weltgewebe.de
# Optional: Trusted Proxies konfigurieren (wichtig für Sicherheit hinter Caddy/Proxy)
# Hinweis: wird aktuell nur konfiguriert (plumbing); Auswertung/Enforcement folgt in PR3 (Client-IP trust + Rate-Limit).
AUTH_TRUSTED_PROXIES=172.16.0.0/12,127.0.0.1
```

**Wichtig:**

- Wenn `AUTH_PUBLIC_LOGIN=1` gesetzt ist, **muss** `APP_BASE_URL` gesetzt sein.
  Andernfalls startet der API-Service nicht (Validierungsfehler beim Startup).
- `APP_BASE_URL` wird verwendet, um korrekte Links in E-Mails/Logs zu generieren.

---

## 10. Heimserver-Policy

Für den Betrieb auf einem Heimserver (z. B. hinter einer Firewall oder in einem lokalen Netzwerk) gilt ein striktes **Gateway-Prinzip**.

### Grundsätze

1. **Gateway-Only Entry:**
   Nur der Caddy-Container darf Ports auf dem Host veröffentlichen.
   Alle anderen Services (API, DB, Upstreams) müssen isoliert bleiben.

2. **Loopback Binding:**
   Ports werden standardmäßig auf `127.0.0.1` ("eingesperrt") gebunden, um versehentliche Exponierung im LAN/WAN
   zu verhindern.

3. **Shared Network (Upstreams):**
   Lokale Upstream-Dienste (z. B. Leitstand) werden über ein dediziertes Docker-Netzwerk (`heimnet`) angebunden,
   nicht über Host-Ports.

### Einrichtung

1. **Netzwerk erstellen:**

   ```bash
   docker network create heimnet
   ```

2. **Bind-Adresse setzen (Optional):**
   Standardmäßig bindet Caddy jetzt sicher an `127.0.0.1`.
   Setze `CADDY_BIND=0.0.0.0` (oder eine LAN-IP) in deiner `.env`-Datei, wenn du externen Zugriff benötigst.

3. **Start mit Override:**
   Nutze die `compose.heimserver.override.yml`, um das Netzwerk anzubinden und die VHosts zu laden:

   ```bash
   docker compose \
     -f infra/compose/compose.prod.yml \
     -f infra/compose/compose.heimserver.override.yml \
     up -d
   ```

### Verifikation

Prüfe, ob nur lokale Ports offen sind:

```bash
ss -lntp | grep -E ":(80|443)"
# Erwartet: 127.0.0.1:80, 127.0.0.1:443
```

Prüfe den Upstream-Zugriff (ohne DNS, via curl-Resolve):

```bash
# Zum lokalen Testen gegen den Host via --resolve (IP anpassen je nach Host-Binding):
curl -k --resolve leitstand.heimgewebe.home.arpa:443:<IP> https://leitstand.heimgewebe.home.arpa/

# Beispiele für <IP>:
# - Loopback: 127.0.0.1
# - LAN: 192.168.x.x
```
