from __future__ import annotations

import logging
import time
from concurrent.futures import Future, ThreadPoolExecutor

from agent.api_client import ControlApiClient
from agent.config import reload_settings
from agent.metrics import collect_basic_metrics
from agent.runner import run_job

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')


def main() -> None:
    settings = reload_settings()

    if not settings.host_api_key:
        raise RuntimeError('HOST_API_KEY is required')

    client = ControlApiClient(settings)
    max_workers = max(1, settings.max_parallel_jobs)
    running_jobs: dict[str, Future[tuple[str, int, str]]] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while True:
            done_job_ids: list[str] = []
            for job_id, future in running_jobs.items():
                if not future.done():
                    continue
                done_job_ids.append(job_id)
                result_status, exit_code, output = future.result()
                try:
                    client.report_completion(job_id, result_status, exit_code, output)
                except Exception as exc:  # noqa: BLE001
                    logging.error('Failed to report completion for %s: %s', job_id, exc)

            for job_id in done_job_ids:
                del running_jobs[job_id]

            cpu, ram = collect_basic_metrics()
            current_job_id = next(iter(running_jobs), None)
            status = 'busy' if running_jobs else 'idle'

            try:
                client.heartbeat(status=status, current_job_id=current_job_id, cpu_percent=cpu, ram_percent=ram)
            except Exception as exc:  # noqa: BLE001
                logging.warning('Heartbeat failed: %s', exc)
                time.sleep(settings.heartbeat_interval_seconds)
                continue

            slots = max_workers - len(running_jobs)
            for _ in range(slots):
                try:
                    job = client.poll_job()
                except Exception as exc:  # noqa: BLE001
                    logging.warning('Job poll failed: %s', exc)
                    break

                if not job:
                    break

                job_id = job['id']
                if job_id in running_jobs:
                    continue

                logging.info(
                    'Running job %s (cpu=%s, ram_mb=%s)',
                    job_id,
                    job.get('requested_cpu_cores'),
                    job.get('requested_ram_mb'),
                )
                running_jobs[job_id] = executor.submit(
                    run_job,
                    job,
                    settings,
                    lambda line, job_id=job_id: client.report_log_chunk(job_id, line),
                )

            time.sleep(settings.poll_interval_seconds)


if __name__ == '__main__':
    main()
