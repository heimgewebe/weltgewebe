# VPS Deployment Runbook

Dieses Runbook beschreibt die Schritte zur Bereitstellung der Weltgewebe-Infrastruktur (API, Datenbank, Proxy)
auf einem VPS. Das Frontend wird weiterhin über einen externen Provider (z.B. Vercel oder Cloudflare Pages) ausgeliefert,
aber über den Caddy-Proxy auf dem VPS unter `weltgewebe.net` eingebunden.

## Voraussetzungen

1. **VPS**: Ein Linux-Server (z.B. Ubuntu) mit öffentlicher IPv4 (und optional IPv6).
2. **Domain**: `weltgewebe.net` ist bei IONOS registriert.
3. **Docker & Docker Compose**: Müssen auf dem VPS installiert sein.

## 1. DNS Konfiguration (IONOS)

Richte folgende DNS-Records ein, damit `weltgewebe.net` auf deinen VPS zeigt:

* **A-Record**: `weltgewebe.net` -> `<VPS_IPV4_ADRESSE>`
* **AAAA-Record** (falls IPv6 verfügbar): `weltgewebe.net` -> `<VPS_IPV6_ADRESSE>`

Die Subdomain `api.weltgewebe.net` ist **nicht** erforderlich, da die API unter `weltgewebe.net/api`
erreichbar sein wird.

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
  * `WEB_UPSTREAM_HOST`: z.B. `leitstand.pages.dev` oder `dein-projekt.vercel.app`
  * `WEB_UPSTREAM_URL`: Muss mit `https://` beginnen (z.B. `https://leitstand.pages.dev`).

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

   ```bash
   # Täglich um 3 Uhr nachts: Dump erstellen, zippen und alte Dateien löschen
   0 3 * * * docker compose -f /opt/weltgewebe/infra/compose/compose.prod.yml \
     exec -T db pg_dump -U welt weltgewebe | gzip > /var/backups/weltgewebe/db_$(date +\%F).sql.gz \
     && find /var/backups/weltgewebe/ -name "db_*.sql.gz" -mtime +14 -delete
   ```

## Wartung

* **Logs ansehen**: `docker compose -f infra/compose/compose.prod.yml logs -f`
* **Neustart**: `docker compose -f infra/compose/compose.prod.yml restart`
* **Updates**: Repository aktualisieren (`git pull`), dann `./scripts/deploy_vps.sh` ausführen.
