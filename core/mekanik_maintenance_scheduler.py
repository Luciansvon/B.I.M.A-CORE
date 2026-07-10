"""Team Mekanik maintenance scheduler.

Report-only health check for Anisa. This module intentionally does not
restart services, write files, or run Git commands.
"""
import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import BASE_DIR, MCP_CLIENTS_CONFIG
from core.system_metrics import snapshot

logger = logging.getLogger("bima_core.mekanik_maintenance")
WIB = ZoneInfo("Asia/Jakarta")
DISCORD_CHUNK_LIMIT = 1900

_scheduler_started = False


def _get_gpu_vram_usage() -> tuple[float, float, float] | None:
    """Return GPU VRAM usage as (used_mb, total_mb, percent), if available."""
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return None

        first_line = res.stdout.strip().splitlines()[0]
        used, total = [float(part.strip()) for part in first_line.split(",", 1)]
        if total <= 0:
            return None
        return used, total, (used / total) * 100.0
    except Exception:
        return None


def _get_pm2_status() -> list[dict]:
    """Return compact PM2 process status. Safe-fails to an empty list."""
    try:
        res = subprocess.run(
            ["pm2", "jlist"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if res.returncode != 0:
            return []

        data = json.loads(res.stdout)
        return [
            {
                "name": proc.get("name", "?"),
                "status": proc.get("pm2_env", {}).get("status", "unknown"),
                "restart_count": proc.get("pm2_env", {}).get("restart_time", 0),
                "mem": round(proc.get("monit", {}).get("memory", 0) / (1024 * 1024), 1),
                "cpu": proc.get("monit", {}).get("cpu", 0),
            }
            for proc in data
        ]
    except Exception:
        return []


def _scan_recent_log_errors(log_dir: Path | None = None, max_lines: int = 400) -> list[str]:
    """Collect recent error-looking lines from local logs without mutating files."""
    logs_path = log_dir or (BASE_DIR / "logs")
    if not logs_path.exists():
        return []

    keywords = ("ERROR", "CRITICAL", "Traceback", "Exception")
    samples: list[str] = []

    try:
        log_files = sorted(
            logs_path.rglob("*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
    except Exception:
        return []

    for log_file in log_files[:3]:
        try:
            lines = log_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            continue

        for line in lines[-max_lines:]:
            if any(keyword in line for keyword in keywords):
                clean = line.strip()
                if clean:
                    samples.append(f"{log_file.name}: {clean[:220]}")
            if len(samples) >= 5:
                return samples

    return samples


def _audit_mcp() -> dict:
    """Run existing MCP security audit and safe-fail into a report row."""
    try:
        from core.mcp_security import audit_mcp_config

        return audit_mcp_config(MCP_CLIENTS_CONFIG)
    except Exception as e:
        return {"status": "error", "message": f"MCP audit gagal: {e}", "issues": []}


def _format_pm2_status(processes: list[dict]) -> list[str]:
    if not processes:
        return ["- PM2: tidak terbaca atau belum jalan"]

    return [
        (
            f"- {proc['name']}: {proc['status']} | "
            f"RAM {proc['mem']:.1f} MB | CPU {proc['cpu']}% | "
            f"restarts {proc['restart_count']}"
        )
        for proc in processes
    ]


def _chunk_text(text: str, limit: int = DISCORD_CHUNK_LIMIT) -> list[str]:
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            if current:
                chunks.append(current)
            current = line[:limit]
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


def build_mekanik_maintenance_report(now: datetime | None = None) -> str:
    """Build a deterministic report-only Team Mekanik maintenance summary."""
    current_time = now.astimezone(WIB) if now else datetime.now(WIB)
    snap = snapshot()
    gpu_info = _get_gpu_vram_usage()
    pm2_status = _get_pm2_status()
    log_errors = _scan_recent_log_errors()
    mcp_audit = _audit_mcp()

    risks: list[str] = []
    if snap["cpu_percent"] >= 90.0:
        risks.append(f"CPU tinggi {snap['cpu_percent']:.1f}%")
    if snap["ram_percent"] >= 90.0:
        risks.append(f"RAM tinggi {snap['ram_percent']:.1f}%")
    if snap["disk_percent"] >= 90.0:
        risks.append(f"Disk hampir penuh {snap['disk_percent']:.1f}%")

    offline_pm2 = [
        proc for proc in pm2_status
        if proc.get("status") not in {"online", "launching"}
    ]
    if offline_pm2:
        risks.append("PM2 bermasalah: " + ", ".join(proc["name"] for proc in offline_pm2))

    mcp_status = mcp_audit.get("status", "unknown")
    if mcp_status not in {"secure", "warning"}:
        risks.append(f"MCP status {mcp_status}")
    if log_errors:
        risks.append(f"{len(log_errors)} error log terbaru")

    health_line = "OK" if not risks else "PERLU CEK - " + "; ".join(risks[:4])

    lines = [
        "Team Mekanik MT Check",
        f"Waktu: {current_time.strftime('%Y-%m-%d %H:%M')} WIB",
        "Jadwal: Senin/Rabu/Jumat 21:30 WIB",
        "Mode: report only - Tidak ada auto-restart, write/delete, atau git.",
        f"Status: {health_line}",
        "",
        "Host:",
        f"- CPU: {snap['cpu_percent']:.1f}% | Load 1m: {snap['load_avg_1m']}",
        (
            f"- RAM: {snap['ram_used_mb']:.0f}/{snap['ram_total_mb']:.0f} MB "
            f"({snap['ram_percent']:.1f}%)"
        ),
        (
            f"- Disk /: {snap['disk_used_gb']:.1f}/{snap['disk_total_gb']:.1f} GB "
            f"({snap['disk_percent']:.1f}%)"
        ),
        f"- Processes: {snap['proc_count']}",
        "",
        "PM2:",
        *_format_pm2_status(pm2_status),
        "",
    ]

    if gpu_info:
        used_vram, total_vram, pct = gpu_info
        lines.append(f"GPU: VRAM {used_vram:.0f}/{total_vram:.0f} MB ({pct:.1f}%)")
    else:
        lines.append("GPU: tidak terbaca / tidak ada Nvidia GPU")

    lines.extend([
        f"MCP: {mcp_status} - {mcp_audit.get('message', '')}",
        "",
        "Recent logs:",
    ])

    if log_errors:
        lines.extend(f"- {line}" for line in log_errors)
    else:
        lines.append("- tidak ada error log terbaru yang kebaca")

    lines.extend([
        "",
        "Catatan Mekanik:",
        "- Tidak ada auto-restart. Kalau ada masalah, Bima approve tindakan manual.",
    ])

    return "\n".join(lines)


async def _send_mekanik_maintenance_report(client) -> None:
    channel_id_str = os.environ.get("BOT_STATUS_CHANNEL_ID")
    if not channel_id_str:
        return

    try:
        channel_id = int(channel_id_str)
        channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        if channel is None:
            return

        report = build_mekanik_maintenance_report()
        for chunk in _chunk_text(report):
            await channel.send(chunk)
        logger.info("[MEKANIK_MT] Report terkirim ke Discord")
    except Exception as e:
        logger.error(f"[MEKANIK_MT] Gagal kirim maintenance report: {e}", exc_info=True)


def _int_env(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"[MEKANIK_MT] {name} bukan angka valid: {raw!r}, pakai {default}")
        return default
    if value < minimum or value > maximum:
        logger.warning(f"[MEKANIK_MT] {name} di luar range, pakai {default}")
        return default
    return value


def start_mekanik_maintenance_scheduler(client):
    """Start report-only Team Mekanik maintenance scheduler."""
    global _scheduler_started
    if _scheduler_started:
        logger.info("[MEKANIK_MT] Scheduler sudah berjalan, skip")
        return None

    if os.environ.get("ENABLE_MEKANIK_MT", "true").lower() != "true":
        logger.info("[MEKANIK_MT] ENABLE_MEKANIK_MT=false, scheduler tidak start")
        return None

    if not os.environ.get("BOT_STATUS_CHANNEL_ID"):
        logger.warning("[MEKANIK_MT] BOT_STATUS_CHANNEL_ID belum di-set, scheduler tidak start")
        return None

    days = os.environ.get("MEKANIK_MT_DAYS", "mon,wed,fri").strip() or "mon,wed,fri"
    hour = _int_env("MEKANIK_MT_HOUR", 21, 0, 23)
    minute = _int_env("MEKANIK_MT_MINUTE", 30, 0, 59)

    scheduler = AsyncIOScheduler(timezone=WIB)
    scheduler.add_job(
        _send_mekanik_maintenance_report,
        CronTrigger(day_of_week=days, hour=hour, minute=minute, timezone=WIB),
        args=[client],
        id="mekanik_mt_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    _scheduler_started = True
    logger.info(f"[MEKANIK_MT] Scheduler aktif: {days} {hour:02d}:{minute:02d} WIB")
    return scheduler
