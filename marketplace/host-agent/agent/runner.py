from __future__ import annotations

import subprocess


def run_job(command: list[str], timeout_seconds: int) -> tuple[str, int, str]:
    """Run a job command. This is a placeholder and should be containerized next."""
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
        status = 'completed' if proc.returncode == 0 else 'failed'
        output = (proc.stdout or '') + '\n' + (proc.stderr or '')
        return status, proc.returncode, output.strip()
    except subprocess.TimeoutExpired:
        return 'failed', 124, 'Job timed out'
    except Exception as exc:  # noqa: BLE001
        return 'failed', 1, f'Runner error: {exc}'
