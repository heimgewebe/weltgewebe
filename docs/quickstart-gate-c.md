# Quickstart · Gate C (Dev-Stack)

```bash
cp .env.example .env
make up
# Web:  http://localhost:5173
# Proxy: http://localhost:8081
# API:  http://localhost:8081/api/version  (-> /version via Caddy)
make logs
make down
```

**Hinweise**
- Frontend nutzt `PUBLIC_API_BASE=/api` (siehe `apps/web/.env.development`).
- Compose-Profil `dev` schützt vor Verwechslungen mit späteren prod-Stacks.
- `make smoke` triggert den GitHub-Workflow `compose-smoke` für einen E2E-Boot-Test.
- CSP ist im Dev gelockert; für externe Tiles Domains ergänzen.
