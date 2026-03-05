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

## Architecture

- `control-api` serves REST APIs and static UI pages (`/`, `/client`, `/host`).
- `host-agent` runs on host machines, sends heartbeats, pulls jobs, executes jobs, streams logs, and reports completion.
- Runtime store is in-process (`InMemoryStore`) with partial persistence to `.runtime/store_state.json`.
- Job execution is Docker-first (resource-limited containers), with optional retained session containers.

Key code:
- `control-api/app/main.py`
- `control-api/app/routes/auth.py`
- `control-api/app/routes/hosts.py`
- `control-api/app/routes/jobs.py`
- `control-api/app/routes/files.py`
- `control-api/app/core/store.py`
- `host-agent/agent/service.py`
- `host-agent/agent/runner.py`

## API Endpoints

Auth:
- `POST /auth/register`: create user, issue token, set `session_token` cookie.
- `POST /auth/login`: login, issue token, set cookie.
- `POST /auth/logout`: revoke cookie token.

Hosts:
- `POST /hosts/register`: create host record or update existing host specs.
- `GET /hosts`: list current user hosts.
- `GET /hosts/available`: list verified public hosts.
- `POST /hosts/heartbeat`: host liveness signal; first successful heartbeat marks host verified.
- `GET /hosts/assignable-job`: host polls one assignable queued quick-run job.

Jobs:
- `POST /jobs`: create `quick_run` or `reserve` job.
- `GET /jobs`: list my jobs.
- `GET /jobs/{job_id}`: get one job.
- `POST /jobs/{job_id}/cancel`: cancel job.
- `DELETE /jobs/{job_id}`: delete job.
- `POST /jobs/{job_id}/log`: host appends log chunk.
- `POST /jobs/{job_id}/complete`: host posts final status/output.
- `GET /jobs/sessions`: list retained sessions.
- `POST /jobs/sessions/{session_id}/stop`: release retained session resources and stop session container.

Files:
- `POST /files/upload`: upload a file for job usage.
- `GET /files/{file_id}/{filename}?token=...`: tokenized temporary download.

Utility/UI:
- `GET /health`
- `GET /`, `GET /client`, `GET /host`
- `GET /downloads/marketplace-host-agent-setup.exe`

## Resource Sharing Logic

Host capacity is tracked as total + free pools:
- CPU: `cpu_cores`, `cpu_cores_free`
- RAM: `ram_mb`, `ram_mb_free`
- GPU lock: `gpu_name`, `gpu_in_use`

Allocation flow:
- `can_allocate(host, job)` checks CPU/RAM free and GPU availability for GPU jobs.
- `allocate(host, job)` decrements free CPU/RAM and locks GPU if required.
- `release(host, job)` returns CPU/RAM, unlocks GPU, and updates host status.

This allows slicing host capacity across multiple concurrent jobs while preventing over-allocation.

## Scheduling Logic

Model: pull-based scheduling.
- Client creates jobs -> API stores in queue.
- Host agents poll `/hosts/assignable-job`.
- API assigns the first eligible queued quick-run job that matches host/session/pinning constraints.

Assignment constraints include:
- Host must be verified.
- If job has `preferred_host_id`, only that host can get it.
- Retained session jobs are pinned to session host.
- Non-retained jobs consume/release resources per job lifecycle.

## Scaling and Retained Sessions

Retained sessions (`retain_progress=true`) reserve resources at session level:
- First request with a new `session_id` reserves requested CPU/RAM/GPU and pins to one host.
- Later requests with same `session_id` can scale up/down:
  - Increasing CPU/RAM checks free headroom and applies delta allocation.
  - Decreasing CPU/RAM returns the delta immediately.
  - GPU toggle checks availability and updates GPU lock.

Stopping a retained session:
- `POST /jobs/sessions/{session_id}/stop` releases held resources and enqueues a stop action for host-agent.

## Execution Modes and Isolation

Host-agent defaults to Docker mode:
- Ephemeral jobs: `docker run --rm` with:
  - `--cpus`, `--memory`
  - read-only rootfs
  - tmpfs work areas
  - dropped Linux caps
  - non-root user
- Retained sessions: long-lived container + volume; commands run via `docker exec`.

Agent controls:
- `MAX_PARALLEL_JOBS` controls concurrent job slots per host.
- `EXECUTION_MODE=docker|local`
- `DOCKER_IMAGE` to select runtime image.

## Persistence Behavior

Persisted:
- users
- tokens
- hosts
- retained sessions

Not persisted as durable DB state in current MVP:
- jobs history/queue
- live upload registry metadata

Result: login/host/session continuity survives API restart, but runtime job queues/history are not full durable workflow storage yet.

## Notes

- Runtime store is in-process with partial file persistence (`.runtime/store_state.json`).
- Job execution is Docker-based in host-agent; this is MVP isolation, not full multi-tenant hard isolation.
- Host capacity is now tracked as free/total CPU and RAM for per-job slicing.
- Only verified hosts (agent heartbeat received) are exposed to clients for sharing.
- You can tune host parallelism with `MAX_PARALLEL_JOBS` for `host-agent`.
- Next step is stronger job isolation and persistent runtime state.
