"""Spawn agentmemory MCP server di background. Dipanggil dari main.py.

Cek port 3111 dulu — kalau udah listening (mis. user jalanin manual), skip spawn.
Kalau belum, Popen npx -y @agentmemory/agentmemory dengan PATH yang sudah
include ~/.local/bin (lokasi binary iii-engine native v0.11.2).

Idempotent + safe-fail: kalau Node/npx gak ada, log warning lalu return tanpa
nge-crash main loop. Bot tetap jalan, manager_node otomatis fallback ke SQLite.
"""
import logging
import os
import socket
import subprocess
from pathlib import Path

logger = logging.getLogger('bima_core')

AGENTMEMORY_HOST = "127.0.0.1"
AGENTMEMORY_PORT = 3111


def _port_already_listening(host: str = AGENTMEMORY_HOST, port: int = AGENTMEMORY_PORT) -> bool:
    """True kalau ada yang listen di port tersebut (server udah jalan)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        return s.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def start_agentmemory() -> subprocess.Popen | None:
    """Spawn agentmemory REST server kalau belum jalan. Return Popen handle atau None."""
    if _port_already_listening():
        logger.info(f"[agentmemory] Server sudah listen di port {AGENTMEMORY_PORT}, skip spawn")
        return None

    home = Path.home()
    local_bin = home / ".local" / "bin"
    if not (local_bin / "iii").exists():
        logger.warning(
            f"[agentmemory] iii-engine native binary tidak ditemukan di {local_bin}/iii — "
            "server tidak akan jalan. Install: curl -fsSL https://github.com/iii-hq/iii/releases/"
            "download/iii/v0.11.2/iii-x86_64-unknown-linux-gnu.tar.gz | tar -xz -C ~/.local/bin/"
        )
        return None

    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "agentmemory.log"

    env = os.environ.copy()
    env["PATH"] = f"{local_bin}:{env.get('PATH', '')}"

    try:
        log_fh = open(log_file, "a", buffering=1)
        proc = subprocess.Popen(
            ["npx", "-y", "@agentmemory/agentmemory"],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            cwd=str(home),
            start_new_session=True,
        )
        logger.info(
            f"[agentmemory] Server di-spawn (PID {proc.pid}), log → {log_file}. "
            f"Butuh ~30-60s buat REST siap di port {AGENTMEMORY_PORT}"
        )
        return proc
    except FileNotFoundError:
        logger.warning("[agentmemory] npx tidak ada di PATH — server tidak jalan, bot pake fallback SQLite")
        return None
    except Exception as e:
        logger.error(f"[agentmemory] Gagal spawn server: {e}")
        return None
