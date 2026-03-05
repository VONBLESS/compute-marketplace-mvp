from __future__ import annotations

from collections import deque
from datetime import datetime, timezone

from app.schemas import HostRecord, JobRecord


class InMemoryStore:
    def __init__(self) -> None:
        self.users: dict[str, dict[str, str]] = {}
        self.tokens: dict[str, str] = {}
        self.hosts: dict[str, HostRecord] = {}
        self.jobs: dict[str, JobRecord] = {}
        self.queue: deque[str] = deque()

    def touch_job(self, job: JobRecord) -> None:
        job.updated_at = datetime.now(timezone.utc)

    def can_allocate(self, host: HostRecord, job: JobRecord) -> bool:
        if job.requested_cpu_cores > host.cpu_cores_free:
            return False
        if job.requested_ram_mb > host.ram_mb_free:
            return False
        if job.requires_gpu and (not host.gpu_name or host.gpu_in_use):
            return False
        return True

    def allocate(self, host: HostRecord, job: JobRecord) -> bool:
        if not self.can_allocate(host, job):
            return False
        host.cpu_cores_free -= job.requested_cpu_cores
        host.ram_mb_free -= job.requested_ram_mb
        if job.requires_gpu:
            host.gpu_in_use = True
        host.status = 'busy'
        return True

    def release(self, host: HostRecord, job: JobRecord) -> None:
        host.cpu_cores_free = min(host.cpu_cores, host.cpu_cores_free + job.requested_cpu_cores)
        host.ram_mb_free = min(host.ram_mb, host.ram_mb_free + job.requested_ram_mb)
        if job.requires_gpu:
            host.gpu_in_use = False
        host.status = 'busy' if (host.cpu_cores_free < host.cpu_cores or host.ram_mb_free < host.ram_mb or host.gpu_in_use) else 'idle'

    def cleanup_expired_reservations(self) -> None:
        now = datetime.now(timezone.utc)
        for job in self.jobs.values():
            if job.mode != 'reserve' or job.status != 'reserved' or not job.reserve_until:
                continue
            if job.reserve_until > now:
                continue
            if job.assigned_host_id:
                host = self.hosts.get(job.assigned_host_id)
                if host:
                    self.release(host, job)
                    if host.current_job_id == job.id:
                        host.current_job_id = None
            job.status = 'expired'
            self.touch_job(job)


store = InMemoryStore()
