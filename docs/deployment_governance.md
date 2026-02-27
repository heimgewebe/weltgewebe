# Deployment Governance: Port Ownership

To ensure stable operation on home servers (e.g., Raspberry Pi) alongside other services, `weltgewebe-up` enforces
strict port ownership rules.

## Reserved Ports

| Port | Owner | Description |
| :--- | :--- | :--- |
| **8081** | **Pi-hole (FTL)** | Strictly reserved. Weltgewebe must NOT use this port. |
| **9081** | **Weltgewebe Gateway** | Optional. Recommended port for local gateway access if enabled. |
| **8080** | **Weltgewebe API** | Internal container port. Default unpublished. |

## Health Check Strategy

`weltgewebe-up` uses a prioritized strategy to determine service health without making assumptions about host ports:

1. **Explicit URL (`HEALTH_URL`):**
   * Highest priority. Used if set in environment.
2. **Host Port Mapping:**
   * Used if the API container has a valid, non-zero port published to the host.
   * Example: `127.0.0.1:32768` -> `8080/tcp`.
3. **Gateway (Explicit Only):**
   * Used only if `WELTGEWEBE_GATEWAY_PORT` is set (e.g., `9081`).
   * **Warning:** Setting this to `8081` triggers a warning.
4. **Docker Native Health (Default):**
   * Fallback. Uses `docker inspect` to check the container's internal health status.
   * Does not require `curl` or `wget` inside the container.

## Configuration

| Variable | Default | Description |
| :--- | :--- | :--- |
| `WELTGEWEBE_GATEWAY_PORT` | *(unset)* | Set to enable gateway health check (e.g., `9081`). |
| `API_INTERNAL_PORT` | `8080` | Internal port of the API service (if modified). |
| `HEALTH_URL` | *(unset)* | Full URL to force a specific health check endpoint. |
