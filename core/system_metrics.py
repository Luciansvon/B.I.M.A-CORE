"""System metrics helper buat healthcheck + Anisa reporting.

Pakai psutil. Berguna buat:
- `/anisa status` → Anisa lapor CPU/RAM/disk
- healthcheck.py expose ke dashboard
- Alert kalau RAM/disk threshold lewat

Lazy import — psutil cuma ke-load saat function dipanggil pertama.
"""
import logging
from typing import TypedDict

logger = logging.getLogger("bima_core.metrics")


class SystemSnapshot(TypedDict):
    cpu_percent: float
    ram_used_mb: float
    ram_total_mb: float
    ram_percent: float
    disk_used_gb: float
    disk_total_gb: float
    disk_percent: float
    load_avg_1m: float
    proc_count: int


def snapshot() -> SystemSnapshot:
    """Single-point-in-time snapshot. Cheap, aman dipanggil per request."""
    import psutil

    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    try:
        load1, _, _ = psutil.getloadavg()
    except (AttributeError, OSError):
        load1 = 0.0

    return SystemSnapshot(
        cpu_percent=psutil.cpu_percent(interval=None),
        ram_used_mb=round(vm.used / 1024 / 1024, 1),
        ram_total_mb=round(vm.total / 1024 / 1024, 1),
        ram_percent=vm.percent,
        disk_used_gb=round(disk.used / 1024 / 1024 / 1024, 2),
        disk_total_gb=round(disk.total / 1024 / 1024 / 1024, 2),
        disk_percent=disk.percent,
        load_avg_1m=round(load1, 2),
        proc_count=len(psutil.pids()),
    )


def format_status_text(snap: SystemSnapshot) -> str:
    """Human-readable string buat reply Discord."""
    return (
        f"🖥 **VPS Status**\n"
        f"CPU: `{snap['cpu_percent']:.1f}%`  ·  Load 1m: `{snap['load_avg_1m']}`\n"
        f"RAM: `{snap['ram_used_mb']:.0f} / {snap['ram_total_mb']:.0f} MB` "
        f"({snap['ram_percent']:.1f}%)\n"
        f"Disk /: `{snap['disk_used_gb']:.1f} / {snap['disk_total_gb']:.1f} GB` "
        f"({snap['disk_percent']:.1f}%)\n"
        f"Processes: `{snap['proc_count']}`"
    )


def top_processes_by_memory(n: int = 5) -> list[dict]:
    """Return top-N proses by RAM usage. Useful kalau anisa-v3 leak."""
    import psutil

    procs = []
    for p in psutil.process_iter(attrs=["pid", "name", "memory_info"]):
        try:
            mem_mb = p.info["memory_info"].rss / 1024 / 1024
            procs.append({"pid": p.info["pid"], "name": p.info["name"], "ram_mb": mem_mb})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    procs.sort(key=lambda x: x["ram_mb"], reverse=True)
    return procs[:n]
