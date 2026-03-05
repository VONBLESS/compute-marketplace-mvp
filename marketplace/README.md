# Compute Marketplace MVP Skeleton

This scaffold gives you:
- `control-api`: FastAPI control plane with auth/hosts/jobs endpoints
- `host-agent`: Windows Python service loop skeleton (heartbeat + poll + run)
- `infra`: docker-compose for API, Postgres, Redis
- `worker-images/python-batch`: placeholder container worker image

## Structure

- `control-api/app/main.py`: API entrypoint
- `control-api/app/routes/*.py`: endpoint groups
- `control-api/app/core/store.py`: in-memory state for MVP skeleton
- `host-agent/agent/service.py`: main agent loop
- `infra/docker-compose.yml`: local infra and API startup

## Quick Start

1. Start infra and API:
   - `cd marketplace/infra`
   - `docker compose up`
   - Open `http://localhost:8000`, then choose:
     - `http://localhost:8000/client` for client job submission + capacity view
     - `http://localhost:8000/host` for host registration with auto-detected hardware

2. Create a user token (example):
   - `POST /auth/register` with `{ "email": "host1@example.com", "password": "password123", "role": "host" }`
   - In the web UI at `http://localhost:8000`, register/login creates a browser session cookie automatically (no manual token copy needed).

3. Register a host:
   - `POST /hosts/register` with bearer token
   - Save returned `api_key`

4. Start host agent (Windows PowerShell):
   - Download installer from `http://localhost:8000/downloads/marketplace-host-agent.exe`
   - On host page, register host and copy generated PowerShell start command
   - Run command to start `.exe` with `API_BASE_URL` and `HOST_API_KEY`
   - Host becomes shareable only after first heartbeat verification

5. Submit a job as a client:
   - Register/login client user
   - `POST /jobs` with bearer token and payload like:
     `{ "command": ["python", "--version"], "requested_cpu_cores": 2, "requested_ram_mb": 2048, "requires_gpu": false, "timeout_seconds": 120 }`

## Notes

- Current store is in-memory only; restart clears data.
- Runner currently executes host commands directly as a placeholder.
- Host capacity is now tracked as free/total CPU and RAM for per-job slicing.
- Only verified hosts (agent heartbeat received) are exposed to clients for sharing.
- You can tune host parallelism with `MAX_PARALLEL_JOBS` for `host-agent`.
- Next step is replacing `agent/runner.py` with Docker-isolated execution and adding PostgreSQL persistence.
