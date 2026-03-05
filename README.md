# Compute Marketplace MVP

This repository hosts the MVP for a compute marketplace.

Primary project folder:
- `marketplace/`

Open the full MVP documentation here:
- [marketplace/README.md](./marketplace/README.md)

## Quick Start

1. `cd marketplace/infra`
2. `docker compose up -d --build`
3. Open:
- `http://localhost:8000/client`
- `http://localhost:8000/host`

## EC2 Quick Start

1. Clone: `git clone https://github.com/VONBLESS/compute-marketplace-mvp.git`
2. `cd compute-marketplace-mvp/marketplace/infra`
3. `docker-compose up -d --build`
4. Open:
- `http://<EC2_PUBLIC_IP>:8000/client`
- `http://<EC2_PUBLIC_IP>:8000/host`
