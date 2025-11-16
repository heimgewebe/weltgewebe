# Quickstart · Gate C (Dev-Stack)

```bash
# 1. Env-Datei erstellen (falls noch nicht geschehen)
cp .env.example .env

# 2. Stack starten
make up

# 3. URLs prüfen
#    - Frontend: http://localhost:8081
#    - API Live: http://localhost:8081/api/health/live
#    - API Version: http://localhost:8081/api/version

# 4. Logs verfolgen (optional)
make logs

# 5. Stack anhalten
make down
```

## Hinweise

- Der primäre Einstiegspunkt ist der Proxy auf Port `8081`.
- Das Frontend (Port `5173`) wird automatisch vom Proxy bedient.
- Frontend nutzt `PUBLIC_API_BASE=/api` (siehe `apps/web/.env.development`).
- Compose-Profil `dev` schützt vor Verwechslungen mit späteren prod-Stacks.
- `make smoke` triggert den GitHub-Workflow `compose-smoke` für einen E2E-Boot-Test.
- CSP ist im Dev gelockert; für externe Tiles Domains ergänzen.
