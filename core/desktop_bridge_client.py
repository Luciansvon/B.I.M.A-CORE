"""Async httpx client untuk BIMA Desktop Bridge (Windows side, port 9100).

Bridge harus jalan terpisah di Windows: `C:\\Users\\shint\\bima-desktop-bridge\\main.py`.
Lokasi default: WSL gateway IP, biasanya 172.25.64.1 di Hyper-V WSL2.

Safe-fail: kalau bridge mati / unreachable, semua fungsi return None — bot tidak crash.
"""
import logging
import os
import socket
import subprocess
from typing import Optional

import httpx

logger = logging.getLogger('bima_core')

CAPTURE_TIMEOUT_S = 8.0
TREE_TIMEOUT_S = 12.0
HEALTH_TIMEOUT_S = 1.5


def _detect_default_bridge_url() -> str:
    """Auto-detect WSL gateway IP buat reach Windows host. Fallback ke env var."""
    env_url = os.environ.get("DESKTOP_BRIDGE_URL")
    if env_url:
        return env_url.rstrip("/")

    try:
        # `ip route show default | awk '{print $3}'`
        result = subprocess.run(
            ["ip", "route", "show", "default"],
            capture_output=True, text=True, timeout=2,
        )
        parts = result.stdout.split()
        if "via" in parts:
            gw = parts[parts.index("via") + 1]
            return f"http://{gw}:9100"
    except Exception as e:
        logger.debug(f"[desktop_bridge] gateway detect fail: {e}")

    return "http://172.25.64.1:9100"  # last-resort default


BASE_URL = _detect_default_bridge_url()


def _port_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    except OSError:
        return False
    finally:
        s.close()


async def health() -> bool:
    """Cek bridge hidup. True = ready, False = down."""
    try:
        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT_S) as c:
            r = await c.get(f"{BASE_URL}/health")
            r.raise_for_status()
            data = r.json()
            return bool(data.get("status") == "ok")
    except Exception:
        return False


async def capture() -> Optional[dict]:
    """Take screenshot + foreground window info.

    Return dict dengan keys:
      - screenshot_b64 (str, base64 PNG)
      - perceptual_hash (str)
      - foreground_title (str | None)
      - foreground_process (str | None)
      - width, height (int)
    None kalau bridge gak responding.
    """
    try:
        async with httpx.AsyncClient(timeout=CAPTURE_TIMEOUT_S) as c:
            r = await c.post(f"{BASE_URL}/capture")
            r.raise_for_status()
            return r.json()
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        logger.debug(f"[desktop_bridge] capture gagal: {e}")
        return None
    except Exception as e:
        logger.warning(f"[desktop_bridge] capture error: {e}")
        return None


async def ui_tree(limit: int = 80) -> Optional[dict]:
    """Return UI elements dari foreground window. None kalau gagal.

    Return dict:
      - foreground_title (str | None)
      - elements (list of {name, control_type, rect})
      - truncated (bool)
    """
    try:
        async with httpx.AsyncClient(timeout=TREE_TIMEOUT_S) as c:
            r = await c.get(f"{BASE_URL}/tree", params={"limit": limit})
            r.raise_for_status()
            return r.json()
    except (httpx.TimeoutException, httpx.HTTPError) as e:
        logger.debug(f"[desktop_bridge] ui_tree gagal: {e}")
        return None
    except Exception as e:
        logger.warning(f"[desktop_bridge] ui_tree error: {e}")
        return None
