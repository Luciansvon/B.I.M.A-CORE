"""Async httpx client untuk BIMA Desktop Bridge (Windows side, port 9100).

Bridge harus jalan terpisah di Windows: `C:\\Users\\shint\\bima-desktop-bridge\\main.py`.
Lokasi default: WSL gateway IP, biasanya 172.25.64.1 di Hyper-V WSL2.

Safe-fail: kalau bridge mati / unreachable, semua fungsi return None — bot tidak crash.

Resilience:
- `BASE_URL` di-cache, tapi re-detect otomatis kalau ConnectError (WSL gateway IP shift
  sering kejadian setelah WSL restart / network profile change).
- capture() & ui_tree() retry 1x dengan backoff 0.4s buat transient hiccup.
- Differentiate timeout vs connection-refused vs HTTP error di log level INFO/WARN.
"""
import asyncio
import logging
import os
import socket
import subprocess
from typing import Optional

import httpx

logger = logging.getLogger('bima_core')

CAPTURE_TIMEOUT_S = 8.0
TREE_TIMEOUT_S = 12.0
HEALTH_TIMEOUT_S = 3.0  # naik dari 1.5 — cross-VM RTT bisa spike sesaat


def _detect_default_bridge_url() -> str:
    """Auto-detect WSL gateway IP buat reach Windows host. Fallback ke env var."""
    env_url = os.environ.get("DESKTOP_BRIDGE_URL")
    if env_url:
        return env_url.rstrip("/")

    try:
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


def refresh_base_url() -> str:
    """Re-run gateway detection. Update module-level BASE_URL & return new value.

    Dipanggil otomatis kalau ConnectError — WSL gateway IP sering shift setelah
    WSL restart, dan module-level BASE_URL jadi stale sampai service di-restart.
    """
    global BASE_URL
    old = BASE_URL
    BASE_URL = _detect_default_bridge_url()
    if BASE_URL != old:
        logger.info(f"[desktop_bridge] BASE_URL refresh: {old} → {BASE_URL}")
    return BASE_URL


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
    """Cek bridge hidup. True = ready, False = down. Log specific cause kalau fail."""
    try:
        async with httpx.AsyncClient(timeout=HEALTH_TIMEOUT_S) as c:
            r = await c.get(f"{BASE_URL}/health")
            r.raise_for_status()
            data = r.json()
            return bool(data.get("status") == "ok")
    except httpx.ConnectError as e:
        logger.info(f"[desktop_bridge] health ConnectError ({BASE_URL}): {e} — coba refresh IP")
        refresh_base_url()
        return False
    except httpx.TimeoutException:
        logger.info(f"[desktop_bridge] health timeout ({HEALTH_TIMEOUT_S}s @ {BASE_URL})")
        return False
    except Exception as e:
        logger.debug(f"[desktop_bridge] health error: {type(e).__name__}: {e}")
        return False


async def _post_with_retry(
    endpoint: str, timeout: float, label: str,
    params: dict | None = None, method: str = "POST",
) -> Optional[dict]:
    """Helper: 1 retry on transient errors. ConnectError triggers IP refresh."""
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=timeout) as c:
                url = f"{BASE_URL}{endpoint}"
                if method == "POST":
                    r = await c.post(url)
                else:
                    r = await c.get(url, params=params or {})
                r.raise_for_status()
                return r.json()
        except httpx.ConnectError as e:
            logger.info(f"[desktop_bridge] {label} ConnectError attempt {attempt} ({BASE_URL}): {e}")
            if attempt == 1:
                refresh_base_url()
                await asyncio.sleep(0.4)
                continue
            return None
        except httpx.TimeoutException as e:
            logger.info(f"[desktop_bridge] {label} timeout attempt {attempt} ({timeout}s): {e}")
            if attempt == 1:
                await asyncio.sleep(0.4)
                continue
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"[desktop_bridge] {label} HTTP {e.response.status_code}: {e}")
            return None
        except Exception as e:
            logger.warning(f"[desktop_bridge] {label} error: {type(e).__name__}: {e}")
            return None
    return None


async def capture() -> Optional[dict]:
    """Take screenshot + foreground window info. 1 retry on transient fails.

    Return dict dengan keys:
      - screenshot_b64 (str, base64 PNG)
      - perceptual_hash (str)
      - foreground_title (str | None)
      - foreground_process (str | None)
      - width, height (int)
    None kalau bridge gak responding setelah retry.
    """
    return await _post_with_retry("/capture", CAPTURE_TIMEOUT_S, "capture")


async def ui_tree(limit: int = 80) -> Optional[dict]:
    """Return UI elements dari foreground window. None kalau gagal setelah retry."""
    return await _post_with_retry(
        "/tree", TREE_TIMEOUT_S, "ui_tree",
        params={"limit": limit}, method="GET",
    )
