from __future__ import annotations

import psutil


def collect_basic_metrics() -> tuple[float, float]:
    cpu = psutil.cpu_percent(interval=0.25)
    ram = psutil.virtual_memory().percent
    return cpu, ram
