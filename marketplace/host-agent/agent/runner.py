from __future__ import annotations

import subprocess
import threading
from collections.abc import Callable


def _stream_reader(pipe, on_output: Callable[[str], None]) -> None:  # noqa: ANN001
    for line in iter(pipe.readline, ''):
        text = line.rstrip('\r\n')
        if text:
            on_output(text)
    pipe.close()


def run_job(command: list[str], timeout_seconds: int, on_output: Callable[[str], None] | None = None) -> tuple[str, int, str]:
    """Run a job command with optional real-time output callback."""
    stream = on_output or (lambda _: None)
    output_lines: list[str] = []

    def _emit(text: str) -> None:
        output_lines.append(text)
        stream(text)

    try:
        proc = subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as exc:  # noqa: BLE001
        message = f'Runner start error: {exc}'
        _emit(message)
        return 'failed', 1, message

    reader = threading.Thread(target=_stream_reader, args=(proc.stdout, _emit), daemon=True)
    reader.start()

    try:
        return_code = proc.wait(timeout=timeout_seconds)
        reader.join(timeout=1)
        status = 'completed' if return_code == 0 else 'failed'
        return status, return_code, '\n'.join(output_lines).strip()
    except subprocess.TimeoutExpired:
        proc.kill()
        reader.join(timeout=1)
        _emit('Job timed out')
        return 'failed', 124, '\n'.join(output_lines).strip()
    except Exception as exc:  # noqa: BLE001
        proc.kill()
        reader.join(timeout=1)
        _emit(f'Runner error: {exc}')
        return 'failed', 1, '\n'.join(output_lines).strip()
