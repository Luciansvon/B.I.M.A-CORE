"""Non-blocking MCP startup supaya channel utama bisa online lebih dulu."""
from __future__ import annotations

import atexit
import logging
import threading
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger("bima_core")


def _init_manager(config_path: Path, project_root: Path) -> object:
    from core.mcp_client_manager import init_manager

    return init_manager(config_path, project_root)


def _shutdown_manager() -> None:
    from core.mcp_client_manager import shutdown_manager

    shutdown_manager()


def start_mcp_clients_in_background(
    config_path: Path,
    project_root: Path,
    on_ready: Callable[[object], None],
) -> threading.Thread:
    """Start MCP di daemon thread dan panggil ``on_ready`` setelah siap."""

    def _run() -> None:
        try:
            manager = _init_manager(config_path, project_root)
            atexit.register(_shutdown_manager)
            on_ready(manager)
            logger.info("[mcp_startup] MCP client siap di background")
        except Exception as e:
            logger.warning(f"MCP client gagal init (bot tetap jalan tanpa MCP eksternal): {e}")

    thread = threading.Thread(target=_run, name="mcp-init", daemon=True)
    thread.start()
    logger.info("[mcp_startup] MCP init jalan di background")
    return thread
