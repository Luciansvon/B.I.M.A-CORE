"""Cheap, durable operational snapshot for Anisa and other agents."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

SCHEMA_VERSION = 1
SNAPSHOT_MAX_AGE_SECONDS = 90
REQUIRED_SERVICES = ("anisa-v3", "bima-whatsapp", "bima-tunnel", "agentmemory")
STATUS_PRIORITY = {"healthy": 0, "degraded": 1, "down": 2}

ServiceReader = Callable[[], dict[str, dict[str, Any]]]
MetricsReader = Callable[[], dict[str, float]]
HealthReader = Callable[[], str]
GitReader = Callable[[], dict[str, Any]]
ErrorReader = Callable[[], str | None]


def determine_overall(states: list[str]) -> str:
    """Return the most severe known state."""
    return max(states, key=STATUS_PRIORITY.__getitem__, default="healthy")


def is_snapshot_fresh(
    snapshot: dict[str, Any],
    *,
    now: datetime | None = None,
) -> bool:
    """Return whether a snapshot is valid and no older than 90 seconds."""
    try:
        updated = datetime.fromisoformat(str(snapshot["updated_at"]))
    except (KeyError, TypeError, ValueError):
        return False
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return timedelta(0) <= current - updated <= timedelta(seconds=SNAPSHOT_MAX_AGE_SECONDS)


def sanitize_error(message: str) -> str:
    """Redact common credentials before an error enters the snapshot."""
    sanitized = re.sub(
        r"(?i)(authorization\s*:\s*bearer\s+)[^\s]+",
        r"\1[REDACTED]",
        message,
    )
    sanitized = re.sub(
        r"(?i)\b([A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD))\s*=\s*[^\s]+",
        r"\1=[REDACTED]",
        sanitized,
    )
    sanitized = re.sub(r"\b(?:sk-[A-Za-z0-9_-]{12,}|AIza[A-Za-z0-9_-]{12,})\b", "[REDACTED]", sanitized)
    return sanitized[:500]


def write_snapshot_atomic(target: Path, snapshot: dict[str, Any]) -> None:
    """Write complete JSON and atomically replace the previous snapshot."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)


def read_pm2_services() -> dict[str, dict[str, Any]]:
    """Read only fields needed from PM2's process list."""
    result = subprocess.run(
        ["pm2", "jlist"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    services: dict[str, dict[str, Any]] = {}
    for process in json.loads(result.stdout):
        name = process.get("name")
        if name not in REQUIRED_SERVICES:
            continue
        environment = process.get("pm2_env", {})
        uptime_ms = environment.get("pm_uptime")
        uptime_seconds = max(0, int((now_ms - uptime_ms) / 1000)) if uptime_ms else 0
        services[name] = {
            "status": environment.get("status", "unknown"),
            "uptime_seconds": uptime_seconds,
            "restarts": int(environment.get("restart_time", 0)),
        }
    return services


def read_system_metrics() -> dict[str, float]:
    """Reuse the existing lightweight system metric reader."""
    from core.system_metrics import snapshot

    current = snapshot()
    return {
        "cpu_percent": current["cpu_percent"],
        "ram_percent": current["ram_percent"],
        "disk_percent": current["disk_percent"],
    }


def probe_backend() -> str:
    """Probe the local dashboard without external network access."""
    with urlopen("http://127.0.0.1:8000/api/metrics", timeout=2) as response:
        return "reachable" if 200 <= response.status < 500 else "unreachable"


def read_git_status(project_root: Path) -> dict[str, Any]:
    """Read commit identity and a compact dirty flag."""
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=3,
    ).stdout.strip()
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        timeout=3,
    ).stdout
    return {"commit": commit, "dirty": bool(porcelain.strip())}


def read_last_error(project_root: Path) -> str | None:
    """Read and sanitize the latest non-empty backend error line."""
    path = project_root / "logs" / "error.log"
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return sanitize_error(next((line for line in reversed(lines) if line.strip()), "")) or None


def collect_snapshot(
    *,
    project_root: Path,
    pm2_reader: ServiceReader = read_pm2_services,
    metrics_reader: MetricsReader = read_system_metrics,
    health_reader: HealthReader = probe_backend,
    git_reader: GitReader | None = None,
    error_reader: ErrorReader | None = None,
) -> dict[str, Any]:
    """Collect independent sources without letting one failure erase the rest."""
    states: list[str] = []
    try:
        discovered_services = pm2_reader()
    except (OSError, subprocess.SubprocessError, ValueError, json.JSONDecodeError):
        discovered_services = {}
    services: dict[str, dict[str, Any]] = {}
    for name in REQUIRED_SERVICES:
        service = discovered_services.get(name, {"status": "unknown"})
        services[name] = service
        if service.get("status") != "online":
            states.append("down" if name == "anisa-v3" else "degraded")

    try:
        resources = metrics_reader()
        if any(resources.get(name, 0.0) >= 90 for name in ("cpu_percent", "ram_percent", "disk_percent")):
            states.append("degraded")
    except (OSError, RuntimeError, ValueError):
        resources = {}
        states.append("degraded")

    try:
        backend = health_reader()
    except (OSError, TimeoutError, ValueError):
        backend = "unreachable"
    if backend != "reachable":
        states.append("down")

    indexes = {
        name: "ready" if (project_root / name).is_dir() else "missing"
        for name in ("search_index", "repo_index", "vault_index")
    }
    if "missing" in indexes.values():
        states.append("degraded")

    resolved_git_reader = git_reader or (lambda: read_git_status(project_root))
    try:
        code = resolved_git_reader()
    except (OSError, subprocess.SubprocessError, ValueError):
        code = {"commit": None, "dirty": None}
        states.append("degraded")

    resolved_error_reader = error_reader or (lambda: read_last_error(project_root))
    try:
        last_error = resolved_error_reader()
    except OSError:
        last_error = None

    return {
        "schema_version": SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "overall": determine_overall(states),
        "services": services,
        "resources": resources,
        "health": {"backend": backend},
        "indexes": indexes,
        "code": code,
        "last_error": sanitize_error(last_error) if last_error else None,
    }
