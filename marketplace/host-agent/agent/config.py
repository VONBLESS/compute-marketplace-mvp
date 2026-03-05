from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    api_base_url: str = os.getenv('API_BASE_URL', 'http://localhost:8000')
    host_api_key: str = os.getenv('HOST_API_KEY', '')
    heartbeat_interval_seconds: int = int(os.getenv('HEARTBEAT_INTERVAL_SECONDS', '10'))
    poll_interval_seconds: int = int(os.getenv('POLL_INTERVAL_SECONDS', '5'))
    max_parallel_jobs: int = int(os.getenv('MAX_PARALLEL_JOBS', '4'))


settings = Settings()
