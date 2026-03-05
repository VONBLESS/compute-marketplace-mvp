from __future__ import annotations

import subprocess
import sys
import tkinter as tk
import os
import shutil
import webbrowser
from tkinter import messagebox

import requests

from agent.config import Settings, load_settings, save_settings
from agent.service import main as service_main


def _verify_connection(api_base_url: str, host_api_key: str) -> None:
    requests.post(
        f'{api_base_url.rstrip("/")}/hosts/heartbeat',
        headers={'X-Host-Api-Key': host_api_key},
        json={
            'status': 'idle',
            'current_job_id': None,
            'cpu_percent': 0,
            'ram_percent': 0,
        },
        timeout=10,
    ).raise_for_status()


def _start_agent_process() -> None:
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    child_env = os.environ.copy()
    # Avoid one-file temp extraction reuse that can trigger _MEI cleanup warnings on exit.
    child_env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'

    if getattr(sys, 'frozen', False):
        subprocess.Popen([sys.executable, '--run-agent'], creationflags=creationflags, env=child_env, close_fds=True)
    else:
        subprocess.Popen([sys.executable, '-m', 'agent.service'], creationflags=creationflags, env=child_env, close_fds=True)


def _check_runtime_requirements(settings: Settings) -> tuple[bool, str]:
    issues: list[str] = []

    if settings.execution_mode.lower() == 'docker':
        if shutil.which('docker') is None:
            issues.append('Docker is not installed or not available in PATH.')
        else:
            try:
                probe = subprocess.run(  # noqa: S603
                    ['docker', 'info'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=10,
                    check=False,
                )
                if probe.returncode != 0:
                    details = (probe.stdout or '').strip()
                    issues.append(
                        'Docker daemon is not running/reachable.'
                        + (f' Details: {details}' if details else '')
                    )
            except Exception as exc:  # noqa: BLE001
                issues.append(f'Failed to run docker info: {exc}')

    if issues:
        return False, '\n'.join(f'- {issue}' for issue in issues)
    return True, 'Runtime requirements look good.'


def _run_gui() -> None:
    cfg = load_settings()

    root = tk.Tk()
    root.title('Marketplace Host Agent Setup')
    root.geometry('560x320')
    root.resizable(False, False)

    tk.Label(root, text='API Base URL').pack(anchor='w', padx=16, pady=(16, 4))
    api_var = tk.StringVar(value=cfg.api_base_url)
    api_entry = tk.Entry(root, textvariable=api_var, width=70)
    api_entry.pack(anchor='w', padx=16)

    tk.Label(root, text='Host API Key').pack(anchor='w', padx=16, pady=(12, 4))
    key_var = tk.StringVar(value=cfg.host_api_key)
    key_entry = tk.Entry(root, textvariable=key_var, width=70)
    key_entry.pack(anchor='w', padx=16)

    tk.Label(root, text='Max Parallel Jobs').pack(anchor='w', padx=16, pady=(12, 4))
    parallel_var = tk.StringVar(value=str(cfg.max_parallel_jobs))
    parallel_entry = tk.Entry(root, textvariable=parallel_var, width=10)
    parallel_entry.pack(anchor='w', padx=16)

    info_text = (
        'Flow: Save config -> Verify (sends heartbeat) -> Start Agent.\n'
        'Once heartbeat succeeds, host is verified on the marketplace backend.'
    )
    tk.Label(root, text=info_text, justify='left').pack(anchor='w', padx=16, pady=(12, 0))

    def build_settings() -> Settings:
        max_parallel = int(parallel_var.get().strip() or '4')
        return Settings(
            api_base_url=api_var.get().strip(),
            host_api_key=key_var.get().strip(),
            heartbeat_interval_seconds=10,
            poll_interval_seconds=5,
            max_parallel_jobs=max(1, max_parallel),
        )

    def save_only() -> None:
        settings = build_settings()
        if not settings.api_base_url or not settings.host_api_key:
            messagebox.showerror('Missing Fields', 'API Base URL and Host API Key are required.')
            return
        save_settings(settings)
        messagebox.showinfo('Saved', 'Configuration saved successfully.')

    def verify_only() -> None:
        settings = build_settings()
        if not settings.api_base_url or not settings.host_api_key:
            messagebox.showerror('Missing Fields', 'API Base URL and Host API Key are required.')
            return
        ok, report = _check_runtime_requirements(settings)
        if not ok:
            messagebox.showerror('Runtime Check Failed', report)
            return
        try:
            _verify_connection(settings.api_base_url, settings.host_api_key)
            messagebox.showinfo('Verified', 'Heartbeat succeeded. Host is verified.')
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Verification Failed', str(exc))

    def check_requirements_only() -> None:
        settings = build_settings()
        ok, report = _check_runtime_requirements(settings)
        if ok:
            messagebox.showinfo('Runtime Check', report)
            return
        if messagebox.askyesno('Runtime Check Failed', f'{report}\n\nOpen Docker download page now?'):
            webbrowser.open('https://www.docker.com/products/docker-desktop/')

    def save_verify_start() -> None:
        settings = build_settings()
        if not settings.api_base_url or not settings.host_api_key:
            messagebox.showerror('Missing Fields', 'API Base URL and Host API Key are required.')
            return

        try:
            save_settings(settings)
            ok, report = _check_runtime_requirements(settings)
            if not ok:
                raise RuntimeError(report)
            _verify_connection(settings.api_base_url, settings.host_api_key)
            _start_agent_process()
            messagebox.showinfo('Started', 'Host agent started in background.')
            root.destroy()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror('Start Failed', str(exc))

    button_frame = tk.Frame(root)
    button_frame.pack(anchor='w', padx=16, pady=(18, 0))

    tk.Button(button_frame, text='Save', width=12, command=save_only).pack(side='left', padx=(0, 8))
    tk.Button(button_frame, text='Check Runtime', width=14, command=check_requirements_only).pack(side='left', padx=(0, 8))
    tk.Button(button_frame, text='Verify', width=12, command=verify_only).pack(side='left', padx=(0, 8))
    tk.Button(button_frame, text='Save + Verify + Start', width=22, command=save_verify_start).pack(side='left')

    root.mainloop()


def main() -> None:
    if '--run-agent' in sys.argv:
        service_main()
        return
    _run_gui()


if __name__ == '__main__':
    main()
