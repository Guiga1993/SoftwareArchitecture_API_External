# Containerized Deployment

The Compose stack runs three services on one private network:

- `frontend`: nginx serves the static application and proxies `/api/` to the backend.
- `backend`: Gunicorn serves the CRUD and shipping API on container port 5001.
- `shippo-integration`: Gunicorn isolates Shippo access on private container port 8001.

Only the frontend and backend are published to the host. The integration API is reachable only by its Compose service name, and only that service receives `SHIPPO_API_KEY`.

## Prerequisites

- Docker Engine with Docker Compose v2
- A valid Shippo API key

## Configure

From this repository, copy `.env.example` to `.env` and replace the API-key
placeholder. The `.env` file is ignored by Git. Do not place credentials in
Compose files, Dockerfiles, browser code, or documentation.

```powershell
Copy-Item .env.example .env
```

The default host endpoints are:

- Frontend: `http://localhost:8080`
- Backend API: `http://localhost:5001`
- Backend health: `http://localhost:5001/health`

Change `FRONTEND_HOST_PORT` or `BACKEND_HOST_PORT` in `.env` when those host ports are occupied. Container ports and service-to-service URLs remain unchanged.

## Operate

Run all Compose commands from this repository, where `docker-compose.yml` and
`.env` are located.

Build and start the stack:

```powershell
docker compose up --build -d
```

Inspect service health and logs:

```powershell
docker compose ps
docker compose logs --follow
```

Stop containers while retaining SQLite data:

```powershell
docker compose down
```

Delete containers and the named database volume:

```powershell
docker compose down --volumes
```

## Runtime Behavior

The browser sends API requests to nginx under `/api`. Nginx strips that prefix and forwards requests to `http://backend:5001/`. The backend calls `http://shippo-integration:8001` for address validation and shipping quotes. Shippo is never called by browser code or by the backend directly.

The `backend-data` named volume is mounted only at `/app/database`, where the application stores `db.sqlite3`. Backend file logging is disabled in Compose so logs flow to standard output for `docker compose logs`.

Health checks are liveness-only. Backend and integration checks call their local `/health` endpoints with Python's standard library and do not validate credentials or contact Shippo. Compose waits for integration health before starting the backend and for backend health before starting the frontend.

## Local Development

The existing non-container workflow remains supported. When the frontend is served by Live Server on port 5500, browser requests target `http://127.0.0.1:5001`. On other ports, the frontend uses the nginx `/api` route intended for Compose.

Docker was unavailable in the implementation environment. The files were statically validated and the non-Docker test suites were run, but image builds and container runtime behavior must be verified on a Docker-enabled host.