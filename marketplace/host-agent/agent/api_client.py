from __future__ import annotations

import requests

from agent.config import settings


class ControlApiClient:
    def __init__(self) -> None:
        self.base = settings.api_base_url.rstrip('/')
        self.headers = {'X-Host-Api-Key': settings.host_api_key}

    def heartbeat(self, status: str, current_job_id: str | None, cpu_percent: float, ram_percent: float) -> None:
        requests.post(
            f'{self.base}/hosts/heartbeat',
            headers=self.headers,
            json={
                'status': status,
                'current_job_id': current_job_id,
                'cpu_percent': cpu_percent,
                'ram_percent': ram_percent,
            },
            timeout=10,
        ).raise_for_status()

    def poll_job(self) -> dict | None:
        response = requests.get(f'{self.base}/hosts/assignable-job', headers=self.headers, timeout=15)
        response.raise_for_status()
        return response.json()

    def report_completion(self, job_id: str, status: str, exit_code: int, output: str) -> None:
        requests.post(
            f'{self.base}/jobs/{job_id}/complete',
            headers=self.headers,
            json={'status': status, 'exit_code': exit_code, 'output': output[:2000]},
            timeout=15,
        ).raise_for_status()
