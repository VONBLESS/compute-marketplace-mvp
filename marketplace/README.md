# Compute Marketplace MVP

This MVP gives you:
- `control-api`: FastAPI control plane with auth/hosts/jobs endpoints
- `host-agent`: Windows Python service loop skeleton (heartbeat + poll + run)
- `infra`: docker-compose for API, Postgres, Redis
- `worker-images/python-batch`: placeholder worker image

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
   - Download installer from `http://localhost:8000/downloads/marketplace-host-agent-setup.exe`
   - On host page, register host and copy `API Base URL` + `Host API Key`
   - Open setup `.exe`, paste values, click `Save + Verify + Start`
   - Host becomes shareable only after first heartbeat verification

5. Build setup `.exe` on Windows (for distribution):
   - `cd marketplace/host-agent`
   - `powershell -ExecutionPolicy Bypass -File .\build-setup-exe.ps1`
   - Output: `dist/marketplace-host-agent-setup.exe`

6. Submit a job as a client:
   - Register/login client user
   - `POST /jobs` with bearer token and payload like:
     `{ "command": ["python", "--version"], "requested_cpu_cores": 2, "requested_ram_mb": 2048, "requires_gpu": false, "timeout_seconds": 120 }`

## Deployment (EC2)

1. Clone:
   - `git clone https://github.com/VONBLESS/compute-marketplace-mvp.git`
2. Start stack:
   - `cd compute-marketplace-mvp/marketplace/infra`
   - `docker-compose up -d --build`
3. Verify:
   - `curl http://localhost:8000/health`
4. Open:
   - `http://<EC2_PUBLIC_IP>:8000/client`
   - `http://<EC2_PUBLIC_IP>:8000/host`

## Notes

- Current store is in-memory only; restart clears data.
- Runner currently executes host commands directly as a placeholder.
- Host capacity is now tracked as free/total CPU and RAM for per-job slicing.
- Only verified hosts (agent heartbeat received) are exposed to clients for sharing.
- You can tune host parallelism with `MAX_PARALLEL_JOBS` for `host-agent`.
- Next step is stronger job isolation and persistent runtime state.
