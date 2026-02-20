# Weltgewebe – Deployment Runbook (Heimserver)

## Architektur (Ist)

- Weltgewebe-Stack läuft als Docker Compose Projekt `weltgewebe`:
  - Services: `db` (Postgres 16), `api`, `nats` (JetStream), optional Service `caddy`
    (Container typischerweise `weltgewebe-caddy-1`, im Stack meist aus oder `--scale caddy=0`)
- Edge-Gateway läuft separat als Compose Projekt `edge`:
  - Container: `edge-caddy` (bindet Ports 80/443)
  - Edge-Caddy ist mit `weltgewebe_default` verbunden (wichtig für DNS/Reverse Proxy)
  - Der Service `caddy` (Container typischerweise `weltgewebe-caddy-1`) im Stack ist optional und wird typischerweise
    nicht gestartet, da `edge-caddy` die Ports belegt.

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

Die Edge-CA (Caddy „tls internal") muss einmalig exportiert werden:

```sh
docker exec edge-caddy cat /data/caddy/pki/authorities/local/root.crt \
  > /opt/heimgewebe/edge/edge-ca.crt
```

- API lokal:
  - `curl -fsS http://127.0.0.1:8081/health/ready`
- API via edge:
  - `curl --cacert /opt/heimgewebe/edge/edge-ca.crt -fsS https://api.weltgewebe.home.arpa/health/ready`
- Alias via edge:
  - `curl --cacert /opt/heimgewebe/edge/edge-ca.crt -fsS https://weltgewebe.home.arpa/api/health/ready`

## Login (Magic Link)

- Request:

  ```sh
  curl --cacert /opt/heimgewebe/edge/edge-ca.crt -fsS \
    -X POST https://weltgewebe.home.arpa/api/auth/login/request \
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

### Port 80 already in use beim Service `caddy` (Container typischerweise `weltgewebe-caddy-1`)

Ursache: ein anderes Caddy (edge) belegt 80/443.
Lösung:

- Entweder Service skalieren: `--scale caddy=0`

  ```sh
  docker compose --env-file /opt/weltgewebe/.env -p weltgewebe \
    -f infra/compose/compose.prod.yml -f infra/compose/compose.prod.override.yml \
    up -d --build --scale caddy=0 --remove-orphans
  ```

- Oder Ports im Stack deaktivieren: `ports: []` in `infra/compose/compose.prod.override.yml` definieren.
