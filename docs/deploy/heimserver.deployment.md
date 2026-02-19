# Weltgewebe – Deployment Runbook (Heimserver)

## Architektur (Ist)

- Weltgewebe-Stack läuft als Docker Compose Projekt `weltgewebe`:
  - Services: `db` (Postgres 16), `api`, `nats` (JetStream), optional `caddy` (im Stack meist aus)
- Edge-Gateway läuft separat als Compose Projekt `edge`:
  - Container: `edge-caddy`
  - Edge-Caddy ist mit `weltgewebe_default` verbunden (wichtig für DNS/Reverse Proxy)

## DNS / Hosts

- Intern: `*.home.arpa`
- API: `api.weltgewebe.home.arpa` → edge-caddy → `weltgewebe-api-1:8080`
- Frontend-Alias: `weltgewebe.home.arpa`
  - `/api/*` → lokal an `weltgewebe-api-1:8080`
  - sonst → Cloudflare Pages (Proxy, kein 308 Redirect)

## Env / Secrets

- `/opt/weltgewebe/.env` (wird via `--env-file` genutzt)

## Standard-Kommandos

- Stack:

  ```sh
  docker compose --env-file /opt/weltgewebe/.env -p weltgewebe \
    -f infra/compose/compose.prod.yml -f infra/compose/compose.prod.override.yml \
    up -d --build
  ```

- Edge:
  - `cd /opt/heimgewebe/edge && docker compose -p edge -f docker-compose.yml up -d --force-recreate`

## Healthchecks

- API lokal:
  - `curl -fsS http://127.0.0.1:8081/health/ready`
- API via edge:
  - `curl -kfsS https://api.weltgewebe.home.arpa/health/ready`
- Alias via edge:
  - `curl -kfsS https://weltgewebe.home.arpa/api/health/ready`

## Login (Magic Link)

- Request:

  ```sh
  curl -kfsS -X POST https://weltgewebe.home.arpa/api/auth/login/request \
    -H 'content-type: application/json' -d '{"email":"..."}'
  ```

- Token-Link erscheint in API logs nur wenn `AUTH_LOG_MAGIC_TOKEN=true` (Debug).

## Troubleshooting

### 308 Redirect bei /api

Ursache: alias-block macht `redir` statt `handle_path /api/* reverse_proxy ...`.
Fix: alias-block auf Proxy-Route umbauen.

### 502 no such host / lookup weltgewebe-api-1

Ursache: edge-caddy ist nicht im `weltgewebe_default` Network.
Fix: `docker network connect weltgewebe_default edge-caddy` oder Compose Netz extern eintragen.

### Port 80 already in use beim weltgewebe-caddy

Ursache: ein anderes Caddy (edge) belegt 80/443.
Fix: im weltgewebe stack `caddy` nicht publishen oder `--scale caddy=0`.
