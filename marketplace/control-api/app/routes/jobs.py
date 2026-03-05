from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_email, get_host_from_api_key
from app.core.store import store
from app.schemas import JobCreateRequest, JobRecord, JobResultReport, MessageResponse, utc_now

router = APIRouter()


@router.post('', response_model=JobRecord)
def create_job(payload: JobCreateRequest, email: str = Depends(get_current_email)) -> JobRecord:
    store.cleanup_expired_reservations()

    if payload.preferred_host_id:
        preferred_host = store.hosts.get(payload.preferred_host_id)
        if not preferred_host:
            raise HTTPException(status_code=400, detail='Preferred host not found')
        if payload.requested_cpu_cores > preferred_host.cpu_cores:
            raise HTTPException(status_code=400, detail='Requested CPU exceeds preferred host capacity')
        if payload.requested_ram_mb > preferred_host.ram_mb:
            raise HTTPException(status_code=400, detail='Requested RAM exceeds preferred host capacity')
        if payload.requires_gpu and not preferred_host.gpu_name:
            raise HTTPException(status_code=400, detail='Preferred host does not provide GPU')

    job = JobRecord(
        owner_email=email,
        command=payload.command,
        mode=payload.mode,
        requires_gpu=payload.requires_gpu,
        requested_cpu_cores=payload.requested_cpu_cores,
        requested_ram_mb=payload.requested_ram_mb,
        timeout_seconds=payload.timeout_seconds,
        reserve_seconds=payload.reserve_seconds,
        preferred_host_id=payload.preferred_host_id,
    )

    if payload.mode == 'reserve':
        candidate_hosts = []
        if payload.preferred_host_id:
            preferred = store.hosts.get(payload.preferred_host_id)
            if preferred:
                candidate_hosts = [preferred]
        else:
            candidate_hosts = list(store.hosts.values())

        allocated = False
        for host in candidate_hosts:
            if store.allocate(host, job):
                job.status = 'reserved'
                job.assigned_host_id = host.id
                job.reserve_until = utc_now() + timedelta(seconds=job.reserve_seconds)
                store.touch_job(job)
                host.current_job_id = job.id
                allocated = True
                break

        if not allocated:
            raise HTTPException(status_code=409, detail='No host currently has enough free capacity to reserve')

        store.jobs[job.id] = job
        return job

    store.jobs[job.id] = job
    store.queue.append(job.id)
    return job


@router.get('', response_model=list[JobRecord])
def list_jobs(email: str = Depends(get_current_email)) -> list[JobRecord]:
    store.cleanup_expired_reservations()
    return [job for job in store.jobs.values() if job.owner_email == email]


@router.get('/{job_id}', response_model=JobRecord)
def get_job(job_id: str, email: str = Depends(get_current_email)) -> JobRecord:
    store.cleanup_expired_reservations()
    job = store.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job not found')
    if job.owner_email != email:
        raise HTTPException(status_code=403, detail='Forbidden')
    return job


@router.post('/{job_id}/cancel', response_model=MessageResponse)
def cancel_job(job_id: str, email: str = Depends(get_current_email)) -> MessageResponse:
    store.cleanup_expired_reservations()
    job = store.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job not found')
    if job.owner_email != email:
        raise HTTPException(status_code=403, detail='Forbidden')
    if job.status in {'completed', 'failed', 'cancelled', 'expired'}:
        return MessageResponse(message='Job already terminal')
    if job.assigned_host_id and job.status in {'assigned', 'running', 'reserved'}:
        host = store.hosts.get(job.assigned_host_id)
        if host:
            store.release(host, job)
    job.status = 'cancelled'
    store.touch_job(job)
    if job_id in store.queue:
        store.queue.remove(job_id)
    return MessageResponse(message='Job cancelled')


@router.post('/{job_id}/complete', response_model=MessageResponse)
def report_complete(job_id: str, payload: JobResultReport, host_id: str = Depends(get_host_from_api_key)) -> MessageResponse:
    store.cleanup_expired_reservations()
    job = store.jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Job not found')
    if job.assigned_host_id != host_id:
        raise HTTPException(status_code=403, detail='Host is not assigned to this job')

    job.status = payload.status
    store.touch_job(job)

    host = store.hosts.get(host_id)
    if host:
        store.release(host, job)
        if host.current_job_id == job.id:
            host.current_job_id = None

    return MessageResponse(message='Result accepted')
