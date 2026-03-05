from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import threading
from collections.abc import Callable

from agent.config import Settings

SESSION_SPECS: dict[str, dict[str, str | int | bool]] = {}


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


def _check_docker_ready() -> str | None:
    if shutil.which('docker') is None:
        return 'Docker is not installed or not in PATH. Install Docker Desktop/Engine and restart the host agent.'
    try:
        probe = subprocess.run(  # noqa: S603
            ['docker', 'info'],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return f'Failed to run docker info: {exc}'
    if probe.returncode != 0:
        details = (probe.stdout or '').strip()
        return (
            'Docker daemon is not reachable. Start Docker Desktop/Engine first.'
            + (f' Details: {details}' if details else '')
        )
    return None


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


def _session_slug(session_id: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_.-]', '-', session_id)[:48]


def _session_container_name(session_id: str) -> str:
    return f'marketplace-session-{_session_slug(session_id)}'


def _session_volume_name(session_id: str) -> str:
    return f'marketplace-session-vol-{_session_slug(session_id)}'


def _container_running(container_name: str) -> bool:
    probe = subprocess.run(  # noqa: S603
        ['docker', 'inspect', '-f', '{{.State.Running}}', container_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return probe.returncode == 0 and probe.stdout.strip().lower() == 'true'


def _remove_container(container_name: str) -> None:
    subprocess.run(  # noqa: S603
        ['docker', 'rm', '-f', container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def _ensure_session_container(job: dict, settings: Settings) -> tuple[str, str]:
    session_id = str(job.get('session_id') or '')
    if not session_id:
        raise RuntimeError('Missing session_id for retained session job.')

    container_name = _session_container_name(session_id)
    volume_name = _session_volume_name(session_id)
    cpu = max(1, int(job.get('requested_cpu_cores', 1)))
    ram_mb = max(128, int(job.get('requested_ram_mb', 512)))
    gpu = bool(job.get('requires_gpu'))
    spec = {'cpu': cpu, 'ram_mb': ram_mb, 'gpu': gpu, 'image': settings.docker_image}
    previous = SESSION_SPECS.get(session_id)

    running = _container_running(container_name)
    needs_recreate = (not running) or (previous is not None and previous != spec)
    if needs_recreate:
        _remove_container(container_name)
        create_cmd = [
            'docker',
            'run',
            '-d',
            '--name',
            container_name,
            '--cpus',
            str(cpu),
            '--memory',
            f'{ram_mb}m',
            '--pids-limit',
            '512',
            '--read-only',
            '--tmpfs',
            '/tmp:rw,noexec,nosuid,size=256m',
            '--tmpfs',
            '/run:rw,noexec,nosuid,size=64m',
            '--mount',
            f'type=volume,src={volume_name},dst=/workspace',
            '--workdir',
            '/workspace',
            '--cap-drop',
            'ALL',
            '--security-opt',
            'no-new-privileges',
            '--user',
            '65532:65532',
        ]
        if gpu:
            create_cmd.extend(['--gpus', 'all'])
        create_cmd.extend([settings.docker_image, 'sh', '-lc', 'while true; do sleep 3600; done'])
        create = subprocess.run(  # noqa: S603
            create_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if create.returncode != 0:
            details = (create.stdout or '').strip()
            raise RuntimeError(f'Failed to create retained session container. {details}')
        SESSION_SPECS[session_id] = spec

    return session_id, container_name


def _run_ephemeral_docker(job: dict, settings: Settings, stream: Callable[[str], None]) -> tuple[str, int, str]:
    command = job.get('command') or ['python', '--version']
    shell_command = _to_shell_command(command)
    cpu = max(1, int(job.get('requested_cpu_cores', 1)))
    ram_mb = max(128, int(job.get('requested_ram_mb', 512)))
    container_name = f"marketplace-job-{str(job.get('id', 'unknown'))[:12]}"
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

    def _cleanup_container() -> None:
        _remove_container(container_name)

    return _run_subprocess(docker_cmd, int(job.get('timeout_seconds', 120)), stream, cleanup=_cleanup_container)


def _run_retained_session(job: dict, settings: Settings, stream: Callable[[str], None]) -> tuple[str, int, str]:
    session_id, container_name = _ensure_session_container(job, settings)
    if job.get('session_action') == 'stop':
        _remove_container(container_name)
        SESSION_SPECS.pop(session_id, None)
        message = f'Retained session {session_id} stopped.'
        stream(message)
        return 'completed', 0, message

    command = job.get('command') or ['python', '--version']
    shell_command = _to_shell_command(command)
    exec_cmd = ['docker', 'exec', container_name, 'sh', '-lc', shell_command]
    return _run_subprocess(exec_cmd, int(job.get('timeout_seconds', 120)), stream)


def run_job(job: dict, settings: Settings, on_output: Callable[[str], None] | None = None) -> tuple[str, int, str]:
    """Run a job with optional real-time output callback."""
    stream = on_output or (lambda _: None)
    timeout_seconds = int(job.get('timeout_seconds', 120))

    if settings.execution_mode.lower() == 'local':
        command = job.get('command') or ['python', '--version']
        return _run_subprocess(command, timeout_seconds, stream)

    docker_issue = _check_docker_ready()
    if docker_issue:
        stream(docker_issue)
        return 'failed', 1, docker_issue

    if job.get('retain_progress') and job.get('session_id'):
        try:
            return _run_retained_session(job, settings, stream)
        except Exception as exc:  # noqa: BLE001
            message = f'Session runner error: {exc}'
            stream(message)
            return 'failed', 1, message

    return _run_ephemeral_docker(job, settings, stream)
