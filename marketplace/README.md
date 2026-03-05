# Compute Marketplace Cross-Host Variant

This variant extends the MVP with cross-host compose scheduling:

- CPU/RAM workload can run on one verified host
- GPU workload can run on another verified host
- Both child jobs are tracked under one compose parent job

## What is in this variant

- `control-api`: FastAPI control plane with auth, hosts, jobs, compose jobs, files
- `host-agent`: Windows host agent + setup EXE flow
- `infra`: docker-compose for API, Postgres, Redis
- `worker-images/python-batch`: placeholder worker image

## Key Endpoints

- `POST /compose-jobs`
- `GET /compose-jobs`
- `GET /compose-jobs/{compose_id}`
- `GET /compose-jobs/{compose_id}/status`
- `GET /compose-jobs/{compose_id}/stream`
- `POST /compose-jobs/{compose_id}/cancel`

## Quick Start

1. Start stack:
   - `cd marketplace/infra`
   - `docker compose up -d --build`

2. Open UI:
   - `http://localhost:8000/client`
   - `http://localhost:8000/host`

3. Register host(s):
   - host page register/login
   - publish host
   - install/start host agent
   - wait for heartbeat verification

4. Run jobs:
   - client page for normal terminal jobs
   - client split mode for CPU+RAM host + GPU host selection

## Current limits

- Store is still in-memory for runtime scheduling state.
- Compose execution is coordinated by parent/child jobs, not deep distributed model offload.
- True cross-host tensor/layer offload in one inference pass is not implemented.
