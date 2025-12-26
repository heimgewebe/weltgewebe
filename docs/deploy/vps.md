# VPS Deployment Runbook

Dieses Runbook beschreibt die Schritte zur Bereitstellung der Weltgewebe-Infrastruktur (API, Datenbank, Proxy) auf einem VPS. Das Frontend wird weiterhin über Vercel ausgeliefert, aber über den Caddy-Proxy auf dem VPS unter `weltgewebe.net` eingebunden.

## Voraussetzungen

1.  **VPS**: Ein Linux-Server (z.B. Ubuntu) mit öffentlicher IPv4 (und optional IPv6).
2.  **Domain**: `weltgewebe.net` ist bei IONOS registriert.
3.  **Docker & Docker Compose**: Müssen auf dem VPS installiert sein.

## 1. DNS Konfiguration (IONOS)

Richte folgende DNS-Records ein, damit `weltgewebe.net` auf deinen VPS zeigt:

*   **A-Record**: `weltgewebe.net` -> `<VPS_IPV4_ADRESSE>`
*   **AAAA-Record** (falls IPv6 verfügbar): `weltgewebe.net` -> `<VPS_IPV6_ADRESSE>`

Die Subdomain `api.weltgewebe.net` ist **nicht** erforderlich, da die API unter `weltgewebe.net/api` erreichbar sein wird.

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

### B. Umgebungsvariablen (.env)

Erstelle eine `.env` Datei im Root-Verzeichnis (neben `infra/`), basierend auf `.env.example`. Für die Produktion sind folgende Anpassungen wichtig:

```ini
# Datenbank (starke Passwörter verwenden!)
POSTGRES_USER=welt
POSTGRES_PASSWORD=secure_password_here
POSTGRES_DB=weltgewebe
DATABASE_URL=postgres://welt:secure_password_here@db:5432/weltgewebe

# Vercel Upstream (Die Production URL von Vercel)
VERCEL_PROD_DOMAIN=dein-projekt.vercel.app

# Logging
RUST_LOG=info
```

### C. Starten

Verwende das bereitgestellte Skript oder Docker Compose direkt:

```bash
# Mit Skript (baut oder pullt Container)
./scripts/deploy_vps.sh

# Oder manuell
docker compose -f infra/compose/compose.prod.yml up -d --build
```

### D. Backup

Richte einen Cronjob ein, um regelmäßig Dumps der Datenbank zu erstellen:

```bash
# Beispiel: Tägliches Backup um 3 Uhr nachts
0 3 * * * docker compose -f /path/to/infra/compose/compose.prod.yml exec -T db pg_dump -U welt weltgewebe > /path/to/backups/db_$(date +\%F).sql
```

## Wartung

*   **Logs ansehen**: `docker compose -f infra/compose/compose.prod.yml logs -f`
*   **Neustart**: `docker compose -f infra/compose/compose.prod.yml restart`
*   **Updates**: Repository aktualisieren (`git pull`), dann `./scripts/deploy_vps.sh` ausführen.
