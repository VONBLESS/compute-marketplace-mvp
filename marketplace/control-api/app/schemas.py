from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_after(seconds: int) -> datetime:
    return utc_now() + timedelta(seconds=seconds)


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    role: Literal['client', 'host'] = 'client'


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'


class HostRegisterRequest(BaseModel):
    host_name: str
    cpu_cores: int = Field(ge=1)
    ram_mb: int = Field(ge=512)
    gpu_name: str | None = None
    vram_mb: int | None = Field(default=None, ge=0)


class HostHeartbeatRequest(BaseModel):
    status: Literal['idle', 'busy', 'offline']
    current_job_id: str | None = None
    cpu_percent: float = Field(ge=0, le=100)
    ram_percent: float = Field(ge=0, le=100)


class HostRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    owner_email: str
    host_name: str
    api_key: str = Field(default_factory=lambda: str(uuid4()))
    cpu_cores: int
    ram_mb: int
    cpu_cores_free: int
    ram_mb_free: int
    gpu_name: str | None = None
    vram_mb: int | None = None
    gpu_in_use: bool = False
    status: str = 'idle'
    current_job_id: str | None = None
    last_seen_at: datetime = Field(default_factory=utc_now)
    verified: bool = False
    verified_at: datetime | None = None


class HostPublicRecord(BaseModel):
    id: str
    host_name: str
    cpu_cores: int
    ram_mb: int
    cpu_cores_free: int
    ram_mb_free: int
    gpu_name: str | None = None
    vram_mb: int | None = None
    status: str
    last_seen_at: datetime
    verified: bool

    @classmethod
    def from_host(cls, host: HostRecord) -> 'HostPublicRecord':
        return cls(
            id=host.id,
            host_name=host.host_name,
            cpu_cores=host.cpu_cores,
            ram_mb=host.ram_mb,
            cpu_cores_free=host.cpu_cores_free,
            ram_mb_free=host.ram_mb_free,
            gpu_name=host.gpu_name,
            vram_mb=host.vram_mb,
            status=host.status,
            last_seen_at=host.last_seen_at,
            verified=host.verified,
        )


class JobCreateRequest(BaseModel):
    command: list[str] | None = None
    command_text: str | None = None
    mode: Literal['quick_run', 'reserve'] = 'quick_run'
    session_id: str | None = None
    retain_progress: bool = False
    requires_gpu: bool = False
    requested_cpu_cores: int = Field(default=1, ge=1)
    requested_ram_mb: int = Field(default=512, ge=128)
    timeout_seconds: int = Field(default=600, ge=10, le=7200)
    reserve_seconds: int = Field(default=120, ge=30, le=86400)
    preferred_host_id: str | None = None


class JobRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    owner_email: str
    command: list[str]
    mode: Literal['quick_run', 'reserve'] = 'quick_run'
    compose_job_id: str | None = None
    compose_role: Literal['cpu', 'gpu'] | None = None
    session_id: str | None = None
    retain_progress: bool = False
    session_action: Literal['none', 'stop'] = 'none'
    requires_gpu: bool
    requested_cpu_cores: int
    requested_ram_mb: int
    timeout_seconds: int
    status: Literal['queued', 'assigned', 'running', 'reserved', 'completed', 'failed', 'cancelled', 'expired'] = 'queued'
    assigned_host_id: str | None = None
    preferred_host_id: str | None = None
    reserve_seconds: int = 120
    reserve_until: datetime | None = None
    exit_code: int | None = None
    output: str = ''
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class JobResultReport(BaseModel):
    status: Literal['completed', 'failed']
    exit_code: int
    output: str = ''


class JobLogChunkRequest(BaseModel):
    chunk: str = Field(min_length=1, max_length=4000)


class MessageResponse(BaseModel):
    message: str


class SessionStopRequest(BaseModel):
    preferred_host_id: str | None = None
    requires_gpu: bool = False


class SessionRecord(BaseModel):
    session_id: str
    owner_email: str
    host_id: str
    cpu_cores: int
    ram_mb: int
    requires_gpu: bool


class ComposeJobCreateRequest(BaseModel):
    command_text: str = Field(min_length=1)
    requested_cpu_cores: int = Field(default=1, ge=1)
    requested_ram_mb: int = Field(default=512, ge=128)
    timeout_seconds: int = Field(default=600, ge=10, le=7200)
    gpu_required: bool = True
    cpu_host_id: str | None = None
    gpu_host_id: str | None = None


class ComposeJobRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    owner_email: str
    command_text: str
    status: Literal['queued', 'running', 'completed', 'failed', 'cancelled'] = 'queued'
    cpu_host_id: str
    gpu_host_id: str
    cpu_job_id: str
    gpu_job_id: str
    requested_cpu_cores: int
    requested_ram_mb: int
    timeout_seconds: int
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ComposeJobDetailResponse(BaseModel):
    compose_job: ComposeJobRecord
    cpu_job: JobRecord | None = None
    gpu_job: JobRecord | None = None
    merged_output: str = ''


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    download_url: str
    expires_at: datetime
