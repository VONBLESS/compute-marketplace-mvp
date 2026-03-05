from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    api_base_url: str = 'http://localhost:8000'
    host_api_key: str = ''
    heartbeat_interval_seconds: int = 10
    poll_interval_seconds: int = 5
    max_parallel_jobs: int = 4
    execution_mode: str = 'docker'
    docker_image: str = 'python:3.12-slim'


def _app_data_dir() -> Path:
    base = os.getenv('APPDATA')
    if base:
        return Path(base) / 'MarketplaceHostAgent'
    return Path.home() / '.marketplace-host-agent'


CONFIG_DIR = _app_data_dir()
CONFIG_FILE = CONFIG_DIR / 'config.json'


def _read_file_config() -> dict[str, str]:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
    except Exception:  # noqa: BLE001
        return {}


def load_settings() -> Settings:
    file_cfg = _read_file_config()
    return Settings(
        api_base_url=os.getenv('API_BASE_URL', file_cfg.get('api_base_url', 'http://localhost:8000')),
        host_api_key=os.getenv('HOST_API_KEY', file_cfg.get('host_api_key', '')),
        heartbeat_interval_seconds=int(os.getenv('HEARTBEAT_INTERVAL_SECONDS', file_cfg.get('heartbeat_interval_seconds', 10))),
        poll_interval_seconds=int(os.getenv('POLL_INTERVAL_SECONDS', file_cfg.get('poll_interval_seconds', 5))),
        max_parallel_jobs=int(os.getenv('MAX_PARALLEL_JOBS', file_cfg.get('max_parallel_jobs', 4))),
        execution_mode=os.getenv('EXECUTION_MODE', file_cfg.get('execution_mode', 'docker')),
        docker_image=os.getenv('DOCKER_IMAGE', file_cfg.get('docker_image', 'python:3.12-slim')),
    )


def reload_settings() -> Settings:
    global settings
    settings = load_settings()
    return settings


def save_settings(settings: Settings) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        'api_base_url': settings.api_base_url,
        'host_api_key': settings.host_api_key,
        'heartbeat_interval_seconds': settings.heartbeat_interval_seconds,
        'poll_interval_seconds': settings.poll_interval_seconds,
        'max_parallel_jobs': settings.max_parallel_jobs,
        'execution_mode': settings.execution_mode,
        'docker_image': settings.docker_image,
    }
    CONFIG_FILE.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return CONFIG_FILE


settings = load_settings()
