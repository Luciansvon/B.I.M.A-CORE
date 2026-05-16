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

logger = logging.getLogger('bima_core')

# Mapping nama agent (di config_mcp.json `attach_to`) → module:attribute
_AGENT_REGISTRY = {
    "intel": "teams.t5_intel:intel_agent",
    "mekanik": "teams.t8_mekanik:mekanik_agent",
    "arsip": "teams.t3_arsip:arsip_agent",
    "visual": "teams.t2_visual:visual_agent",
    "manager": "teams.t1_manager:manager_agent",
    "seniman": "teams.t7_seniman:seniman_agent",
    "admin": "teams.t4_admin:admin_agent",
    "lifestyle": "teams.t6_lifestyle:lifestyle_agent",
    "saham": "teams.t9_saham:saham_agent",
}


def _inject_mcp_tools(mcp_manager) -> None:
    """Inject MCP tools ke CrewAI agent sesuai `attach_to` di config_mcp.json."""
    for agent_name in mcp_manager.list_attached_agents():
        tools = mcp_manager.get_tools_for(agent_name)
        if not tools:
            continue
        ref = _AGENT_REGISTRY.get(agent_name)
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

    # Start agentmemory REST server di background (port 3111)
    try:
        from core.agentmemory_launcher import start_agentmemory
        start_agentmemory()
    except Exception as e:
        logger.warning(f"agentmemory gagal start (bot tetap jalan, fallback SQLite): {e}")

    # Init MCP client manager — consume MCP server eksternal (fetch, markitdown, dll)
    try:
        from config import BASE_DIR, MCP_CLIENTS_CONFIG
        from core.mcp_client_manager import init_manager, shutdown_manager
        mcp_mgr = init_manager(MCP_CLIENTS_CONFIG, BASE_DIR)
        _inject_mcp_tools(mcp_mgr)
        atexit.register(shutdown_manager)
    except Exception as e:
        logger.warning(f"MCP client gagal init (bot tetap jalan tanpa MCP eksternal): {e}")

    run_bot()
