"""BIMA CORE — Observability Scheduler

Memantau performa host (CPU, RAM, GPU VRAM, status PM2) secara periodik.
Mengirimkan notifikasi peringatan/alert ke Discord channel (BOT_STATUS_CHANNEL_ID) jika terdeteksi anomali.
"""
import os
import logging
import psutil
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger('bima_core.observability')
WIB = ZoneInfo("Asia/Jakarta")

# Cooldown alert untuk mencegah spamming (default: 30 menit per alert key)
_last_alert_times = {}

def _should_alert(alert_key: str, cooldown_seconds: int = 1800) -> bool:
    now = datetime.now()
    last_time = _last_alert_times.get(alert_key)
    if last_time is None or (now - last_time).total_seconds() > cooldown_seconds:
        _last_alert_times[alert_key] = now
        return True
    return False

def _get_gpu_vram_usage() -> tuple[float, float, float] | None:
    """Mengembalikan (used_mb, total_mb, percentage) dari GPU VRAM menggunakan nvidia-smi.
    Safe-fail jika nvidia-smi tidak tersedia atau tidak ada GPU Nvidia.
    """
    try:
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,nounits,noheader"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5
        )
        if res.returncode == 0:
            lines = res.stdout.strip().split("\n")
            if lines:
                used, total = map(float, lines[0].split(","))
                return used, total, (used / total) * 100.0
    except Exception:
        pass
    return None

def _get_pm2_status() -> list[dict]:
    """Memeriksa status proses PM2 menggunakan 'pm2 jlist'.
    Safe-fail jika PM2 tidak terpasang atau mengembalikan format JSON tidak valid.
    """
    try:
        # Panggil pm2 jlist menggunakan shell agar bisa terbaca jika dipasang secara global
        res = subprocess.run(
            ["pm2", "jlist"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5, shell=True
        )
        if res.returncode == 0:
            import json
            data = json.loads(res.stdout)
            status_list = []
            for proc in data:
                status_list.append({
                    "name": proc.get("name"),
                    "status": proc.get("pm2_env", {}).get("status"),
                    "restart_count": proc.get("pm2_env", {}).get("restart_time", 0),
                    "mem": proc.get("monit", {}).get("memory", 0) / (1024 * 1024), # MB
                    "cpu": proc.get("monit", {}).get("cpu", 0),
                })
            return status_list
    except Exception:
        pass
    return []

async def _check_observability(client) -> None:
    channel_id_str = os.environ.get("BOT_STATUS_CHANNEL_ID")
    if not channel_id_str:
        return
    
    try:
        channel_id = int(channel_id_str)
        ch = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
        if ch is None:
            return

        cpu_usage = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        ram_usage = ram.percent

        alerts = []

        # 1. Alert CPU tinggi (>90%)
        if cpu_usage > 90.0:
            if _should_alert("cpu_high"):
                alerts.append(f"⚠️ **CPU High Usage**: {cpu_usage:.1f}%")

        # 2. Alert RAM tinggi (>90%)
        if ram_usage > 90.0:
            if _should_alert("ram_high"):
                alerts.append(f"⚠️ **RAM High Usage**: {ram_usage:.1f}% ({ram.used / (1024**3):.1f} GB / {ram.total / (1024**3):.1f} GB)")

        # 3. Alert VRAM GPU tinggi (>90%)
        gpu_info = _get_gpu_vram_usage()
        if gpu_info:
            used_vram, total_vram, pct = gpu_info
            if pct > 90.0:
                if _should_alert("gpu_high"):
                    alerts.append(f"⚠️ **GPU VRAM High Usage**: {pct:.1f}% ({used_vram:.0f}MB / {total_vram:.0f}MB)")

        # 4. Alert proses PM2 Offline (stopped atau errored)
        pm2_status = _get_pm2_status()
        for proc in pm2_status:
            name = proc["name"]
            status = proc["status"]
            if status in ["errored", "stopped"]:
                if _should_alert(f"pm2_offline_{name}"):
                    alerts.append(f"🚨 **PM2 Process Offline**: `{name}` status-nya adalah `{status}`!")

        if alerts:
            alert_text = "🚨 **[BIMA CORE - OBSERVABILITY ALERT]** 🚨\n" + "\n".join(alerts)
            await ch.send(alert_text)
            logger.warning(f"[OBSERVABILITY] Sent alert to Discord: {alerts}")

    except Exception as e:
        logger.error(f"[OBSERVABILITY] Gagal memproses loop cek observability: {e}", exc_info=True)

_scheduler_started = False

def start_observability_scheduler(client):
    global _scheduler_started
    if _scheduler_started:
        logger.info("[OBSERVABILITY] Scheduler sudah berjalan, skip")
        return None
    
    if os.environ.get("ENABLE_OBSERVABILITY", "true").lower() != "true":
        logger.info("[OBSERVABILITY] ENABLE_OBSERVABILITY=false, scheduler tidak di-start")
        return None

    if not os.environ.get("BOT_STATUS_CHANNEL_ID"):
        logger.warning("[OBSERVABILITY] BOT_STATUS_CHANNEL_ID tidak ditemukan di .env, scheduler tidak di-start")
        return None

    interval_minutes = int(os.environ.get("OBSERVABILITY_INTERVAL_MINUTES", "5"))

    scheduler = AsyncIOScheduler(timezone=WIB)
    scheduler.add_job(
        _check_observability,
        IntervalTrigger(minutes=interval_minutes, timezone=WIB),
        args=[client], id="observability_check",
    )
    scheduler.start()
    _scheduler_started = True
    logger.info(f"[OBSERVABILITY] ✅ Scheduler dimulai — mengecek berkala setiap {interval_minutes} menit.")
    return scheduler
