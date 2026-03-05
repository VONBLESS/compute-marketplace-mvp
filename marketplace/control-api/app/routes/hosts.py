from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_email, get_host_from_api_key
from app.core.store import store
from app.schemas import HostHeartbeatRequest, HostPublicRecord, HostRecord, HostRegisterRequest, JobRecord

router = APIRouter()


@router.post('/register', response_model=HostRecord)
def register_host(payload: HostRegisterRequest, email: str = Depends(get_current_email)) -> HostRecord:
    for existing in store.hosts.values():
        if existing.owner_email != email or existing.host_name != payload.host_name:
            continue

        # Keep host definition stable until first heartbeat verifies ownership/runtime.
        if not existing.verified:
            return existing

        used_cpu = max(0, existing.cpu_cores - existing.cpu_cores_free)
        used_ram = max(0, existing.ram_mb - existing.ram_mb_free)
        used_vram = 0
        if existing.vram_mb is not None:
            current_vram_free = existing.vram_mb_free if existing.vram_mb_free is not None else existing.vram_mb
            used_vram = max(0, existing.vram_mb - current_vram_free)

        existing.cpu_cores = payload.cpu_cores
        existing.ram_mb = payload.ram_mb
        existing.gpu_name = payload.gpu_name
        existing.vram_mb = payload.vram_mb
        existing.cpu_cores_free = max(0, payload.cpu_cores - used_cpu)
        existing.ram_mb_free = max(0, payload.ram_mb - used_ram)
        if payload.vram_mb is None:
            existing.vram_mb_free = None
            if not payload.gpu_name:
                existing.gpu_in_use = False
        else:
            existing.vram_mb_free = max(0, payload.vram_mb - used_vram)
            existing.gpu_in_use = existing.vram_mb_free < payload.vram_mb
        store.persist_state()
        return existing

    host = HostRecord(
        owner_email=email,
        host_name=payload.host_name,
        cpu_cores=payload.cpu_cores,
        ram_mb=payload.ram_mb,
        cpu_cores_free=payload.cpu_cores,
        ram_mb_free=payload.ram_mb,
        gpu_name=payload.gpu_name,
        vram_mb=payload.vram_mb,
        vram_mb_free=payload.vram_mb,
    )
    store.hosts[host.id] = host
    store.persist_state()
    return host


@router.get('', response_model=list[HostRecord])
def list_hosts(email: str = Depends(get_current_email)) -> list[HostRecord]:
    store.cleanup_expired_reservations()
    return [host for host in store.hosts.values() if host.owner_email == email]


@router.get('/available', response_model=list[HostPublicRecord])
def list_available_hosts(_: str = Depends(get_current_email)) -> list[HostPublicRecord]:
    store.cleanup_expired_reservations()
    return [HostPublicRecord.from_host(host) for host in store.hosts.values() if host.verified]


@router.post('/heartbeat')
def heartbeat(payload: HostHeartbeatRequest, host_id: str = Depends(get_host_from_api_key)) -> dict[str, str]:
    store.cleanup_expired_reservations()
    host = store.hosts.get(host_id)
    if host is None:
        raise HTTPException(status_code=404, detail='Host not found')
    host.status = payload.status
    host.current_job_id = payload.current_job_id
    host.last_seen_at = datetime.now(timezone.utc)
    if not host.verified:
        host.verified = True
        host.verified_at = datetime.now(timezone.utc)
    store.persist_state()
    return {'message': 'heartbeat accepted'}


@router.get('/assignable-job', response_model=JobRecord | None)
def get_assignable_job(host_id: str = Depends(get_host_from_api_key)) -> JobRecord | None:
    store.cleanup_expired_reservations()
    host = store.hosts.get(host_id)
    if host is None:
        raise HTTPException(status_code=404, detail='Host not found')
    if not host.verified:
        return None

    for job_id in list(store.queue):
        job = store.jobs[job_id]
        if job.status != 'queued':
            store.queue.remove(job_id)
            continue
        if job.mode != 'quick_run':
            store.queue.remove(job_id)
            continue
        if job.retain_progress and job.session_id:
            session = store.sessions.get(job.session_id)
            if not session:
                job.status = 'failed'
                store.touch_job(job)
                store.queue.remove(job_id)
                continue
            session_host_id = str(session.get('host_id'))
            if host.id != session_host_id:
                continue
        if job.assigned_host_id and job.assigned_host_id != host.id:
            continue
        if job.preferred_host_id and job.preferred_host_id != host.id:
            continue
        if (not job.retain_progress) and job.session_action != 'stop':
            if not store.allocate(host, job):
                continue
        job.status = 'assigned'
        job.assigned_host_id = host.id
        store.touch_job(job)
        store.queue.remove(job_id)
        host.current_job_id = job.id
        return job

    return None
