---
id: deploy.vps
title: VPS-Deployment
doc_type: reference
status: active
summary: Dokumentation zum VPS-basierten Deployment.
relations:
  - type: relates_to
    target: docs/deploy/README.md
  - type: relates_to
    target: scripts/ops/check_public_live_readiness.py
---
# VPS Deployment Runbook

Dieses Runbook beschreibt den aktuellen Public-VPS-Pfad für `weltgewebe.net`.
Der VPS stellt API, Datenbank, NATS und den Caddy-Frontdoor bereit. Das
Frontend wird im VPS-Checkout gebaut und vom Stack-internen Caddy unter der
Domain ausgeliefert.

## Voraussetzungen

1. **VPS**: Ein Linux-Server (z.B. Ubuntu) mit öffentlicher statischer IPv4 (und optional IPv6).
2. **Domain**: Zugriff auf die DNS-Verwaltung deiner Domain (z.B. `weltgewebe.net`).
3. **Docker & Docker Compose**: Müssen auf dem VPS installiert sein.

## 1. DNS Konfiguration

Richte folgende DNS-Records ein, damit die Domain auf deinen VPS zeigt:

* **A-Record**: `weltgewebe.net` -> `<VPS_IPV4_ADRESSE>`
* **A-Record**: `www.weltgewebe.net` -> `<VPS_IPV4_ADRESSE>`
* **A-Record**: `api.weltgewebe.net` -> `<VPS_IPV4_ADRESSE>`
* **AAAA-Record** (nur falls IPv6 geprüft und freigegeben ist): entsprechende Hostnamen -> `<VPS_IPV6_ADRESSE>`

Die Subdomain `api.weltgewebe.net` ist Teil des aktuellen Public-VPS-Zielbilds
und muss auf dieselbe VPS-IPv4 zeigen wie Root und `www`.

## 2. Server Vorbereitung

Stelle sicher, dass Docker und das Docker Compose Plugin installiert sind.

```bash
# Beispiel für Ubuntu
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2
sudo usermod -aG docker $USER
# (Neu einloggen, damit Gruppenrechte greifen)
```

## 3. Deployment

### A. Repository klonen oder Dateien kopieren

Kopiere das Repository auf den VPS (z.B. nach `/opt/weltgewebe` oder `~/weltgewebe`).

### B. Umgebungsvariablen (.env) & Secrets

Erstelle eine `.env` Datei im Root-Verzeichnis (neben `infra/`), basierend auf `.env.prod.example`.

```bash
cp .env.prod.example .env
nano .env
```

**WICHTIG (Secrets):**

* Die `.env` Datei enthält sensible Daten (Passwörter). Sie darf **niemals** ins Git-Repository committet werden.
* Auf dem VPS liegt sie nur lokal vor.

Anpassungen:

* **Datenbank**: Wähle ein starkes Passwort für `POSTGRES_PASSWORD` und passe `DATABASE_URL` entsprechend an.
* **Web Upstream**: Konfiguriere den Host und die URL deines Frontends (Vercel oder Cloudflare).
  * `WEB_UPSTREAM_HOST`: **Nur die Domain** ohne Schema (z.B. `leitstand.pages.dev`).
  * `WEB_UPSTREAM_URL`: Die volle Origin **ohne Pfad**, muss mit `https://` beginnen (z.B. `https://leitstand.pages.dev`).

### C. Starten

Verwende das bereitgestellte Skript oder Docker Compose direkt:

```bash
# Mit Skript (baut oder pullt Container)
./scripts/deploy_vps.sh

# Optional: Mit Image-Cleanup (Vorsicht!)
PRUNE_IMAGES=1 ./scripts/deploy_vps.sh

# Oder manuell
docker compose -f infra/compose/compose.prod.yml up -d --build
```

**Troubleshooting:**

Wenn API-Healthchecks fehlschlagen, prüfe im Container:

```bash
docker compose -f infra/compose/compose.prod.yml logs api
# Teste im Container
docker compose -f infra/compose/compose.prod.yml exec api wget -qO- http://localhost:8080/health/ready
# Oder Fallback
docker compose -f infra/compose/compose.prod.yml exec api wget -qO- http://localhost:8080/health/live
```

### D. Backup (Strategie)

Richte einen Cronjob ein, um regelmäßig Dumps der Datenbank zu erstellen und alte Backups zu rotieren
(z.B. 14 Tage behalten).

1. Verzeichnis anlegen:

   ```bash
   mkdir -p /var/backups/weltgewebe
   ```

2. Cronjob einrichten (`crontab -e`):

   Verwende `set -o pipefail`, um Fehler in der Pipe (z.B. bei `pg_dump`) korrekt zu erkennen und zu loggen.

   ```bash
   # Täglich um 3 Uhr nachts: Dump erstellen, zippen, rotieren und Fehler loggen
   0 3 * * * /bin/bash -c 'set -o pipefail; docker compose -f /opt/weltgewebe/infra/compose/compose.prod.yml \
     exec -T db pg_dump -U welt weltgewebe | gzip > /var/backups/weltgewebe/db_$(date +\%F).sql.gz \
     && find /var/backups/weltgewebe/ -name "db_*.sql.gz" -mtime +14 -delete' \
     || echo "backup failed $(date)" >> /var/backups/weltgewebe/backup.log
   ```

## Wartung

* **Logs ansehen**: `docker compose -f infra/compose/compose.prod.yml logs -f`
* **Neustart**: `docker compose -f infra/compose/compose.prod.yml restart`
* **Updates**: Repository aktualisieren (`git pull`), dann `./scripts/deploy_vps.sh` ausführen.

## 4. Aktueller Zielpfad: VPS als Public Runtime

Für den neuen Public-VPS-Pfad ist `scripts/weltgewebe-up` der bevorzugte
Deploy-Wrapper. Der Zieltyp wird explizit gesetzt:

```bash
cd /opt/weltgewebe
DEPLOY_TARGET=vps ENV_FILE=/opt/weltgewebe/.env ./scripts/weltgewebe-up --branch main
```

Der VPS-Zieltyp unterscheidet sich vom historischen Heimserver-Ziel:

* er nutzt `infra/compose/compose.vps.override.yml`,
* er startet den internen Caddy-Service standardmäßig mit,
* er verwendet `infra/caddy/Caddyfile.vps`,
* er erzwingt keine `*.home.arpa`-DNS-Guards,
* er verlangt kein `/opt/heimgewebe/edge` und kein `edge-ca.crt`.

Vor dem INWX-DNS-Cutover darf der Stack lokal auf dem VPS über den HTTP-Host-Header
geprüft werden, ohne öffentliche DNS-Records umzubiegen:

```bash
curl -H 'Host: weltgewebe.net' http://127.0.0.1/health/proxy
curl -H 'Host: weltgewebe.net' http://127.0.0.1/api/health/ready
```

Nach dem DNS-Cutover sind zusätzlich die öffentlichen HTTPS-Pfade zu prüfen:

```bash
curl -fsS https://weltgewebe.net/api/health/ready
curl -fsS https://api.weltgewebe.net/health/ready
```

### Public live readiness receipt

Nach einem Public-Cutover kann der öffentliche Zustand mit einem read-only
Operator-Check reproduzierbar geprüft werden:

```bash
DEPLOY_COMMIT="<ausgelieferter-commit-sha>"

python3 scripts/ops/check_public_live_readiness.py \
  --expected-ip 94.16.121.119 \
  --expected-version "${DEPLOY_COMMIT:0:8}" \
  --expected-commit "${DEPLOY_COMMIT}" \
  --authoritative-server ns.inwx.de \
  --authoritative-server ns2.inwx.de \
  --authoritative-server ns3.inwx.eu
```

`DEPLOY_COMMIT` ist der Commit, dessen Frontend/API tatsächlich ausgeliefert
werden soll. Das ist nicht automatisch der aktuelle lokale `HEAD`: reine
Doku-/Tooling-PRs können `main` vor den live ausgelieferten App-Build setzen. Für
einen reinen Oberflächen-Receipt ohne Versionsbindung können `--expected-version`
und `--expected-commit` weggelassen werden.

Wenn IPv6 freigegeben und die AAAA-Records gesetzt sind, wird zusätzlich die
IPv6-DNS-Erwartung geprüft:

```bash
  --expected-ipv6 2a03:4000:21:c74:b47a:7bff:fee6:70d
```

Der Check liest keine Runtime-Secrets und verändert keinen Serverzustand. Er
prüft DNS-A-Records, HTTP-zu-HTTPS-Redirect, Root-/`www`-HTTPS, `/map`,
`api.weltgewebe.net/health/ready`, `/_app/version.json`, lokale Basemap-Style-,
Glyph- und PMTiles-Auslieferung. Ein PASS ist ein Public-HTTP(S)-/Basemap-Receipt,
aber kein Beweis für IPv6, Mail/SMTP, Public Login oder Credential-Cutover.
