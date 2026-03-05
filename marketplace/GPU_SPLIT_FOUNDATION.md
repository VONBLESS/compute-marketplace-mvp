# GPU Split Foundation (Scheduler-Level)

This branch adds logical GPU VRAM slicing in the scheduler.

What it does:
- Host can publish `vram_mb` (total GPU memory).
- API tracks `vram_mb_free` per host.
- Jobs can request `requested_vram_mb`.
- Scheduler allocates/releases VRAM for quick runs, reserves, and retained sessions.

What it does not do:
- Hardware-level GPU isolation.
- Guaranteed VRAM enforcement by GPU driver.
- vGPU/MIG partitioning.

Important:
- This is a control-plane reservation model.
- Real hard isolation requires infrastructure support (NVIDIA vGPU/MIG or equivalent).
