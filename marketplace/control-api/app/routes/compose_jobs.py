from __future__ import annotations

import asyncio
import json
from datetime import timezone, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.security import get_current_email
from app.core.store import store
from app.schemas import ComposeJobCreateRequest, ComposeJobDetailResponse, ComposeJobRecord, JobRecord, MessageResponse

router = APIRouter()


def _touch_compose(compose: ComposeJobRecord) -> None:
    compose.updated_at = datetime.now(timezone.utc)


def _select_host_pair(
    requested_cpu_cores: int,
    requested_ram_mb: int,
    cpu_host_id: str | None = None,
    gpu_host_id: str | None = None,
) -> tuple[str, str]:
    verified_hosts = [host for host in store.hosts.values() if host.verified]
    host_by_id = {host.id: host for host in verified_hosts}

    if cpu_host_id and gpu_host_id:
        if cpu_host_id == gpu_host_id:
            raise HTTPException(status_code=400, detail='CPU host and GPU host must be different')
        cpu_host = host_by_id.get(cpu_host_id)
        gpu_host = host_by_id.get(gpu_host_id)
        if not cpu_host:
            raise HTTPException(status_code=404, detail='Selected CPU host is unavailable or not verified')
        if not gpu_host:
            raise HTTPException(status_code=404, detail='Selected GPU host is unavailable or not verified')
        if cpu_host.cpu_cores_free < requested_cpu_cores or cpu_host.ram_mb_free < requested_ram_mb:
            raise HTTPException(status_code=409, detail='Selected CPU host does not have enough free CPU/RAM')
        if not gpu_host.gpu_name or gpu_host.gpu_in_use:
            raise HTTPException(status_code=409, detail='Selected GPU host does not have a free GPU')
        return cpu_host.id, gpu_host.id

    if cpu_host_id:
        cpu_host = host_by_id.get(cpu_host_id)
        if not cpu_host:
            raise HTTPException(status_code=404, detail='Selected CPU host is unavailable or not verified')
        if cpu_host.cpu_cores_free < requested_cpu_cores or cpu_host.ram_mb_free < requested_ram_mb:
            raise HTTPException(status_code=409, detail='Selected CPU host does not have enough free CPU/RAM')
        gpu_candidates = [host for host in verified_hosts if host.gpu_name and not host.gpu_in_use and host.id != cpu_host.id]
        if not gpu_candidates:
            raise HTTPException(status_code=409, detail='No compatible GPU host is available')
        return cpu_host.id, gpu_candidates[0].id

    if gpu_host_id:
        gpu_host = host_by_id.get(gpu_host_id)
        if not gpu_host:
            raise HTTPException(status_code=404, detail='Selected GPU host is unavailable or not verified')
        if not gpu_host.gpu_name or gpu_host.gpu_in_use:
            raise HTTPException(status_code=409, detail='Selected GPU host does not have a free GPU')
        cpu_candidates = [
            host for host in verified_hosts
            if host.cpu_cores_free >= requested_cpu_cores and host.ram_mb_free >= requested_ram_mb and host.id != gpu_host.id
        ]
        if not cpu_candidates:
            raise HTTPException(status_code=409, detail='No compatible CPU host is available')
        return cpu_candidates[0].id, gpu_host.id

    cpu_candidates = [
        host for host in verified_hosts
        if host.cpu_cores_free >= requested_cpu_cores and host.ram_mb_free >= requested_ram_mb
    ]
    gpu_candidates = [
        host for host in verified_hosts
        if host.gpu_name and not host.gpu_in_use
    ]
    for cpu_host in cpu_candidates:
        for gpu_host in gpu_candidates:
            if gpu_host.id == cpu_host.id:
                continue
            return cpu_host.id, gpu_host.id
    raise HTTPException(status_code=409, detail='No compatible CPU/GPU host pair is available')


def _compute_compose_status(compose: ComposeJobRecord) -> ComposeJobRecord:
    cpu_job = store.jobs.get(compose.cpu_job_id)
    gpu_job = store.jobs.get(compose.gpu_job_id)
    statuses = [job.status for job in [cpu_job, gpu_job] if job]
    if not statuses:
        compose.status = 'failed'
    elif any(status == 'cancelled' for status in statuses):
        compose.status = 'cancelled'
    elif any(status == 'failed' for status in statuses):
        compose.status = 'failed'
    elif all(status == 'completed' for status in statuses):
        compose.status = 'completed'
    elif any(status in {'assigned', 'running'} for status in statuses):
        compose.status = 'running'
    else:
        compose.status = 'queued'
    _touch_compose(compose)
    return compose


def _merge_output(compose: ComposeJobRecord) -> str:
    cpu_job = store.jobs.get(compose.cpu_job_id)
    gpu_job = store.jobs.get(compose.gpu_job_id)
    lines: list[str] = []
    if cpu_job and cpu_job.output:
        lines.append('[cpu]')
        lines.append(cpu_job.output.strip())
    if gpu_job and gpu_job.output:
        if lines:
            lines.append('----------------------------------------')
        lines.append('[gpu]')
        lines.append(gpu_job.output.strip())
    return '\n'.join(lines).strip()


def _compose_detail(compose: ComposeJobRecord) -> ComposeJobDetailResponse:
    _compute_compose_status(compose)
    return ComposeJobDetailResponse(
        compose_job=compose,
        cpu_job=store.jobs.get(compose.cpu_job_id),
        gpu_job=store.jobs.get(compose.gpu_job_id),
        merged_output=_merge_output(compose),
    )


@router.post('', response_model=ComposeJobDetailResponse)
def create_compose_job(payload: ComposeJobCreateRequest, email: str = Depends(get_current_email)) -> ComposeJobDetailResponse:
    if not payload.gpu_required:
        raise HTTPException(status_code=400, detail='cross_host_compose requires gpu_required=true')

    cpu_host_id, gpu_host_id = _select_host_pair(
        payload.requested_cpu_cores,
        payload.requested_ram_mb,
        payload.cpu_host_id,
        payload.gpu_host_id,
    )
    command = ['cmd', '/c', payload.command_text.strip()]

    cpu_job = JobRecord(
        owner_email=email,
        command=command,
        mode='quick_run',
        compose_role='cpu',
        requires_gpu=False,
        requested_cpu_cores=payload.requested_cpu_cores,
        requested_ram_mb=payload.requested_ram_mb,
        timeout_seconds=payload.timeout_seconds,
        preferred_host_id=cpu_host_id,
    )
    gpu_job = JobRecord(
        owner_email=email,
        command=command,
        mode='quick_run',
        compose_role='gpu',
        requires_gpu=True,
        requested_cpu_cores=1,
        requested_ram_mb=512,
        timeout_seconds=payload.timeout_seconds,
        preferred_host_id=gpu_host_id,
    )
    store.jobs[cpu_job.id] = cpu_job
    store.jobs[gpu_job.id] = gpu_job
    store.queue.append(cpu_job.id)
    store.queue.append(gpu_job.id)

    compose = ComposeJobRecord(
        owner_email=email,
        command_text=payload.command_text.strip(),
        status='queued',
        cpu_host_id=cpu_host_id,
        gpu_host_id=gpu_host_id,
        cpu_job_id=cpu_job.id,
        gpu_job_id=gpu_job.id,
        requested_cpu_cores=payload.requested_cpu_cores,
        requested_ram_mb=payload.requested_ram_mb,
        timeout_seconds=payload.timeout_seconds,
    )
    cpu_job.compose_job_id = compose.id
    gpu_job.compose_job_id = compose.id
    store.compose_jobs[compose.id] = compose
    store.persist_state()
    return _compose_detail(compose)


@router.get('', response_model=list[ComposeJobRecord])
def list_compose_jobs(email: str = Depends(get_current_email)) -> list[ComposeJobRecord]:
    rows = [compose for compose in store.compose_jobs.values() if compose.owner_email == email]
    for row in rows:
        _compute_compose_status(row)
    return sorted(rows, key=lambda row: row.created_at, reverse=True)


@router.get('/{compose_id}', response_model=ComposeJobDetailResponse)
def get_compose_job(compose_id: str, email: str = Depends(get_current_email)) -> ComposeJobDetailResponse:
    compose = store.compose_jobs.get(compose_id)
    if not compose:
        raise HTTPException(status_code=404, detail='Compose job not found')
    if compose.owner_email != email:
        raise HTTPException(status_code=403, detail='Forbidden')
    return _compose_detail(compose)


@router.get('/{compose_id}/status', response_model=ComposeJobDetailResponse)
def get_compose_job_status(compose_id: str, email: str = Depends(get_current_email)) -> ComposeJobDetailResponse:
    compose = store.compose_jobs.get(compose_id)
    if not compose:
        raise HTTPException(status_code=404, detail='Compose job not found')
    if compose.owner_email != email:
        raise HTTPException(status_code=403, detail='Forbidden')
    return _compose_detail(compose)


@router.get('/{compose_id}/stream')
async def stream_compose_job(compose_id: str, email: str = Depends(get_current_email)) -> StreamingResponse:
    compose = store.compose_jobs.get(compose_id)
    if not compose:
        raise HTTPException(status_code=404, detail='Compose job not found')
    if compose.owner_email != email:
        raise HTTPException(status_code=403, detail='Forbidden')

    async def event_gen():
        last_payload = ''
        for _ in range(120):
            current = store.compose_jobs.get(compose_id)
            if not current:
                break
            detail = _compose_detail(current).model_dump(mode='json')
            payload = json.dumps(detail)
            if payload != last_payload:
                yield f'data: {payload}\n\n'
                last_payload = payload
            if detail['compose_job']['status'] in {'completed', 'failed', 'cancelled'}:
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_gen(), media_type='text/event-stream')


@router.post('/{compose_id}/cancel', response_model=MessageResponse)
def cancel_compose_job(compose_id: str, email: str = Depends(get_current_email)) -> MessageResponse:
    compose = store.compose_jobs.get(compose_id)
    if not compose:
        raise HTTPException(status_code=404, detail='Compose job not found')
    if compose.owner_email != email:
        raise HTTPException(status_code=403, detail='Forbidden')

    for child_id in [compose.cpu_job_id, compose.gpu_job_id]:
        job = store.jobs.get(child_id)
        if not job:
            continue
        if job.status in {'completed', 'failed', 'cancelled', 'expired'}:
            continue
        if job.assigned_host_id and job.status in {'assigned', 'running', 'reserved'}:
            host = store.hosts.get(job.assigned_host_id)
            if host:
                store.release(host, job)
                if host.current_job_id == job.id:
                    host.current_job_id = None
        if child_id in store.queue:
            store.queue.remove(child_id)
        job.status = 'cancelled'
        store.touch_job(job)

    compose.status = 'cancelled'
    _touch_compose(compose)
    store.persist_state()
    return MessageResponse(message='Compose job cancelled')
