import atexit
import importlib
import logging
import os
import sys

import uvloop
uvloop.install()

# Sentry error tracking — no-op kalau SENTRY_DSN ga di-set di .env.
# Set SENTRY_DSN di .env (https://sentry.io free tier 5k events/bulan) buat aktif.
import sentry_sdk
sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", ""),
    traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
    send_default_pii=False,
    environment=os.environ.get("BIMA_ENV", "prod"),
)

from loguru import logger as _loguru


class _InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = _loguru.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        _loguru.opt(depth=depth, exception=record.exc_info).bind(source=record.name).log(
            level, record.getMessage()
        )


_loguru.remove()
_loguru.add(
    sys.stderr,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <7}</level> | "
        "<cyan>{extra[source]:<24}</cyan> | {message}"
    ),
    level="INFO",
    backtrace=True,
    diagnose=False,
)
_loguru.configure(extra={"source": "loguru"})
logging.basicConfig(handlers=[_InterceptHandler()], level=logging.INFO, force=True)

from core.discord_bot import run_bot
from core.agent_registry import AGENT_REGISTRY

logger = logging.getLogger('bima_core')

def _inject_mcp_tools(mcp_manager) -> None:
    """Inject MCP tools ke CrewAI agent sesuai `attach_to` di config_mcp.json."""
    for agent_name in mcp_manager.list_attached_agents():
        tools = mcp_manager.get_tools_for(agent_name)
        if not tools:
            continue
        ref = AGENT_REGISTRY.get(agent_name)
        if not ref:
            logger.warning(f"[mcp_inject] agent '{agent_name}' tidak dikenal, skip")
            continue
        mod_name, attr = ref.split(":")
        try:
            mod = importlib.import_module(mod_name)
            agent = getattr(mod, attr)
            agent.tools.extend(tools)
            tool_names = [getattr(t, "name", "?") for t in tools]
            logger.info(f"[mcp_inject] {agent_name} ← {len(tools)} tools: {tool_names}")
        except Exception as e:
            logger.warning(f"[mcp_inject] gagal inject '{agent_name}': {e}")


if __name__ == "__main__":
    # Start WA bridge server di background (port 8001)
    try:
        from core.wa_server import start_wa_bridge
        start_wa_bridge(host="127.0.0.1", port=8001)
    except Exception as e:
        logger.warning(f"WA bridge gagal start (bot tetap jalan): {e}")

    # Dashboard server dimatikan — sudah tidak dipakai.

    # AgentMemory lifecycle dikelola PM2 sebagai service terpisah.
    try:
        from core.agentmemory_launcher import agentmemory_is_ready
        if agentmemory_is_ready():
            logger.info("[agentmemory] PM2 service ready di port 3111")
        else:
            logger.warning("[agentmemory] PM2 service belum ready; sementara pakai fallback SQLite")
    except Exception as e:
        logger.warning(f"agentmemory readiness check gagal (fallback SQLite): {e}")

    # Verify MCP Security (Bumblebee Audit)
    try:
        from config import MCP_CLIENTS_CONFIG
        from core.mcp_security import verify_and_alert_mcp
        if not verify_and_alert_mcp(MCP_CLIENTS_CONFIG):
            logger.error("[SECURITY] Sistem dinonaktifkan karena konfigurasi MCP tidak aman!")
            sys.exit(1)
    except Exception as e:
        logger.warning(f"[SECURITY] Gagal melakukan audit keamanan MCP: {e}")

    # Init MCP client manager di background supaya timeout server eksternal gak
    # menahan startup Discord.
    try:
        from config import BASE_DIR, MCP_CLIENTS_CONFIG
        from core.mcp_startup import start_mcp_clients_in_background

        def _on_mcp_ready(mcp_mgr: object) -> None:
            _inject_mcp_tools(mcp_mgr)
            from teams.t3_arsip import start_vault_index_background

            start_vault_index_background()

        start_mcp_clients_in_background(
            MCP_CLIENTS_CONFIG,
            BASE_DIR,
            _on_mcp_ready,
        )
    except Exception as e:
        logger.warning(f"MCP client gagal init (bot tetap jalan tanpa MCP eksternal): {e}")

    # Plugin system — custom tools dari tools/plugins/ ke mekanik agent
    if os.environ.get("ENABLE_PLUGINS", "true").lower() == "true":
        try:
            from tools.plugin_loader import load_plugins
            from teams.t8_mekanik import mekanik_agent
            plugin_tools = load_plugins()
            if plugin_tools:
                mekanik_agent.tools.extend(plugin_tools)
                tool_names = [getattr(t, "name", "?") for t in plugin_tools]
                logger.info(f"[plugins] {len(plugin_tools)} custom tool(s) → mekanik: {tool_names}")
        except Exception as e:
            logger.warning(f"Plugin loader gagal (bot tetap jalan tanpa custom plugins): {e}")

    # T1-A: Register shutdown hook untuk close checkpoint connection saat exit.
    # atexit jalanin sync, wrap async shutdown_engine() dalam asyncio.run() guard.
    def _shutdown_checkpoint_engine():
        try:
            import asyncio as _asyncio
            from core.langgraph_engine import shutdown_engine
            try:
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    # Event loop masih jalan (rare di atexit) — schedule task
                    loop.create_task(shutdown_engine())
                else:
                    _asyncio.run(shutdown_engine())
            except RuntimeError:
                # No loop di thread ini — bikin baru
                _asyncio.run(shutdown_engine())
        except Exception as e:
            logger.warning(f"Shutdown checkpoint engine error (non-fatal): {e}")
    atexit.register(_shutdown_checkpoint_engine)

    run_bot()
