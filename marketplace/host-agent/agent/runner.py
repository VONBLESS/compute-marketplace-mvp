from __future__ import annotations

import shlex
import subprocess
import threading
from collections.abc import Callable

from agent.config import Settings


def _stream_reader(pipe, on_output: Callable[[str], None]) -> None:  # noqa: ANN001
    for line in iter(pipe.readline, ''):
        text = line.rstrip('\r\n')
        if text:
            on_output(text)
    pipe.close()


def _to_shell_command(command: list[str]) -> str:
    if len(command) >= 3 and command[0].lower() == 'cmd' and command[1].lower() == '/c':
        return command[2]
    return shlex.join(command)


def _docker_command(job: dict, settings: Settings, container_name: str) -> list[str]:
    command = job.get('command') or ['python', '--version']
    shell_command = _to_shell_command(command)
    cpu = max(1, int(job.get('requested_cpu_cores', 1)))
    ram_mb = max(128, int(job.get('requested_ram_mb', 512)))

    docker_cmd = [
        'docker',
        'run',
        '--rm',
        '--name',
        container_name,
        '--cpus',
        str(cpu),
        '--memory',
        f'{ram_mb}m',
        '--pids-limit',
        '256',
        '--read-only',
        '--tmpfs',
        '/tmp:rw,noexec,nosuid,size=256m',
        '--tmpfs',
        '/workspace:rw,noexec,nosuid,size=2048m',
        '--workdir',
        '/workspace',
        '--cap-drop',
        'ALL',
        '--security-opt',
        'no-new-privileges',
        '--user',
        '65532:65532',
    ]
    if job.get('requires_gpu'):
        docker_cmd.extend(['--gpus', 'all'])

    docker_cmd.extend([settings.docker_image, 'sh', '-lc', shell_command])
    return docker_cmd


def _run_subprocess(
    command: list[str],
    timeout_seconds: int,
    on_output: Callable[[str], None],
    cleanup: Callable[[], None] | None = None,
) -> tuple[str, int, str]:
    output_lines: list[str] = []

    def _emit(text: str) -> None:
        output_lines.append(text)
        on_output(text)

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
        if cleanup:
            cleanup()
        return 'failed', 124, '\n'.join(output_lines).strip()
    except Exception as exc:  # noqa: BLE001
        proc.kill()
        reader.join(timeout=1)
        _emit(f'Runner error: {exc}')
        if cleanup:
            cleanup()
        return 'failed', 1, '\n'.join(output_lines).strip()


def run_job(job: dict, settings: Settings, on_output: Callable[[str], None] | None = None) -> tuple[str, int, str]:
    """Run a job with optional real-time output callback."""
    stream = on_output or (lambda _: None)
    timeout_seconds = int(job.get('timeout_seconds', 120))

    if settings.execution_mode.lower() == 'local':
        command = job.get('command') or ['python', '--version']
        return _run_subprocess(command, timeout_seconds, stream)

    container_name = f"marketplace-job-{job.get('id', 'unknown')[:12]}"
    command = _docker_command(job, settings, container_name)

    def _cleanup_container() -> None:
        subprocess.run(  # noqa: S603
            ['docker', 'rm', '-f', container_name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

    return _run_subprocess(command, timeout_seconds, stream, cleanup=_cleanup_container)
