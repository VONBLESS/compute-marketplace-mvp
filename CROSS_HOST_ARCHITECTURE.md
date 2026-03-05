# Cross-Host Compose Plan

## Goal
Allow a single user task to consume:
- CPU/RAM from one host node
- GPU from a different host node

while keeping the existing single-host mode untouched.

## Core Idea
Split one user task into two coordinated workloads:
- `cpu_worker` on CPU host
- `gpu_worker` on GPU host

and connect them through an internal control/data channel (job coordinator service).

## Required New Components
1. `compose_jobs` table / model (parent job)
2. `sub_jobs` table / model (cpu + gpu child jobs)
3. `coordinator` runtime service for synchronization and heartbeats
4. host capability registry (`cpu_only`, `gpu_enabled`, bandwidth hints)
5. scheduler that can pair compatible hosts for one compose job

## Execution Modes
1. `single_host` (existing behavior)
2. `cross_host_compose` (new mode)

## First Milestone
1. Add API contracts for compose job create/get/cancel.
2. Add scheduler pairing logic (CPU host + GPU host).
3. Dispatch and track two sub-jobs under one parent.
4. Aggregate status/logs back into one parent job view.

## Constraints
- Higher latency than single-host mode.
- Requires stable host-to-host networking path.
- Failure handling must support partial success (one side fails).
