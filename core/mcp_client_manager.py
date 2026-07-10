"""MCP Client Manager — orkestrasi adapter ke MCP server eksternal.

Load `config_mcp.json`, validasi requirement per server (binary + env var),
start `MCPServerAdapter` yang lolos cek, expose tools ke CrewAI agent via
`get_tools_for(agent_name)`. Long-lived: start sekali di bot init, stop saat shutdown.

Failure isolation: kalau salah satu server gagal start, server lain tetap jalan.
Bot lanjut beroperasi dengan tool yang available (subset of configured).
"""
import json
import logging
import os
import re
import shutil
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger("bima_core.mcp_client")

_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

# Direktori yang sering nge-host CLI tool user (uvx, pipx-installed bins, dll)
# tapi gak masuk PATH default subshell non-login. Di-prepend saat manager init.
_EXTRA_PATH_DIRS = [
    str(Path.home() / ".local" / "bin"),
    "/usr/local/bin",
]


def _filter_tools_by_name(tools: list, allowed_names: list[str] | None) -> list:
    """Return only explicitly allowed MCP tools; None preserves all tools."""
    if allowed_names is None:
        return list(tools)
    allowed = set(allowed_names)
    return [tool for tool in tools if getattr(tool, "name", None) in allowed]


def _enrich_path() -> None:
    """Prepend dir yang lazim (mis. ~/.local/bin buat uvx) ke PATH proses ini."""
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    added = []
    for d in _EXTRA_PATH_DIRS:
        if Path(d).is_dir() and d not in parts:
            parts.insert(0, d)
            added.append(d)
    if added:
        os.environ["PATH"] = os.pathsep.join(parts)
        logger.info(f"[mcp_client] PATH enriched: prepend {added}")


def _expand_vars(value: str, extra: dict[str, str]) -> str:
    def repl(m: re.Match) -> str:
        key = m.group(1)
        if key in extra:
            return extra[key]
        return os.environ.get(key, m.group(0))

    return _VAR_PATTERN.sub(repl, value)


def _expand_recursive(obj: Any, extra: dict[str, str]) -> Any:
    if isinstance(obj, str):
        return _expand_vars(obj, extra)
    if isinstance(obj, list):
        return [_expand_recursive(x, extra) for x in obj]
    if isinstance(obj, dict):
        return {k: _expand_recursive(v, extra) for k, v in obj.items()}
    return obj


class MCPClientManager:
    """Singleton-ish manager. Init dengan path config + project root."""

    def __init__(self, config_path: Path, project_root: Path):
        self.config_path = Path(config_path)
        self.project_root = Path(project_root)
        self._adapters: dict[str, Any] = {}
        self._tools_by_agent: dict[str, list] = {}
        self._lock = Lock()
        self._started = False

    def _load_config(self) -> dict:
        if not self.config_path.exists():
            logger.warning(f"[mcp_client] config_mcp.json gak ada di {self.config_path}, skip MCP client")
            return {"servers": []}
        try:
            with self.config_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"[mcp_client] config_mcp.json invalid JSON: {e}")
            return {"servers": []}

    def _check_requirements(self, server: dict) -> tuple[bool, str]:
        bin_name = server.get("requires_bin")
        if bin_name and not shutil.which(bin_name):
            return False, f"binary `{bin_name}` gak ada di PATH"
        for env_var in server.get("requires_env", []):
            if not os.environ.get(env_var):
                return False, f"env var `{env_var}` belum di-set"
        return True, "ok"

    def start(self) -> None:
        """Init semua adapter yang lolos cek. Idempotent."""
        with self._lock:
            if self._started:
                logger.info("[mcp_client] sudah started, skip")
                return

            _enrich_path()  # tambah ~/.local/bin & /usr/local/bin biar uvx ke-detect

            try:
                from crewai_tools import MCPServerAdapter
                from mcp import StdioServerParameters
            except ImportError as e:
                logger.error(f"[mcp_client] import gagal: {e}. MCP client di-skip.")
                return

            config = self._load_config()
            servers = config.get("servers", [])
            extra_vars = {"BIMA_ROOT": str(self.project_root)}

            enabled_count = 0
            success_count = 0
            for server in servers:
                name = server.get("name", "unnamed")
                if not server.get("enabled", False):
                    logger.info(f"[mcp_client] '{name}' disabled, skip")
                    continue
                enabled_count += 1

                ok, reason = self._check_requirements(server)
                if not ok:
                    logger.warning(f"[mcp_client] '{name}' skip — {reason}")
                    continue

                command = server.get("command")
                args = _expand_recursive(server.get("args", []), extra_vars)
                env_overlay = _expand_recursive(server.get("env", {}), extra_vars)
                tool_filter = server.get("tools")

                merged_env = {**os.environ, **{k: v for k, v in env_overlay.items() if v}}

                try:
                    params = StdioServerParameters(
                        command=command,
                        args=args,
                        env=merged_env,
                    )
                    # Catatan: MCPServerAdapter.__init__ auto-call .start() internal.
                    # Jangan call .start() lagi di sini — bikin "threads can only be started once" error.
                    if tool_filter:
                        adapter = MCPServerAdapter(params, *tool_filter, connect_timeout=120)
                    else:
                        adapter = MCPServerAdapter(params, connect_timeout=120)
                    tools = list(adapter.tools or [])
                except Exception as e:
                    logger.warning(f"[mcp_client] '{name}' start gagal: {e}")
                    continue

                self._adapters[name] = adapter
                attach_to = server.get("attach_to", [])
                allowlists = server.get("tool_allowlist_by_agent", {})
                for agent_name in attach_to:
                    agent_tools = _filter_tools_by_name(
                        tools,
                        allowlists.get(agent_name),
                    )
                    self._tools_by_agent.setdefault(agent_name, []).extend(agent_tools)
                success_count += 1
                tool_names = [getattr(t, "name", "?") for t in tools]
                logger.info(
                    f"[mcp_client] '{name}' ✓ started, {len(tools)} tools → agents={attach_to} "
                    f"(tools: {tool_names[:5]}{'...' if len(tool_names) > 5 else ''})"
                )

            self._started = True
            logger.info(
                f"[mcp_client] ready: {success_count}/{enabled_count} enabled server jalan, "
                f"total {sum(len(v) for v in self._tools_by_agent.values())} tool injection"
            )

    def get_tools_for(self, agent_name: str) -> list:
        """Return list BaseTool buat agent tertentu. Kosong kalau gak ada."""
        return list(self._tools_by_agent.get(agent_name, []))

    def list_active_servers(self) -> list[str]:
        return list(self._adapters.keys())

    def list_attached_agents(self) -> list[str]:
        return list(self._tools_by_agent.keys())

    def stop(self) -> None:
        """Stop semua adapter. Aman dipanggil multi kali."""
        with self._lock:
            for name, adapter in list(self._adapters.items()):
                try:
                    adapter.stop()
                    logger.info(f"[mcp_client] '{name}' stopped")
                except Exception as e:
                    logger.warning(f"[mcp_client] '{name}' stop error: {e}")
            self._adapters.clear()
            self._tools_by_agent.clear()
            self._started = False


_manager: MCPClientManager | None = None


def get_manager() -> MCPClientManager | None:
    """Return singleton manager (kalau udah di-init via init_manager)."""
    return _manager


def init_manager(config_path: Path, project_root: Path) -> MCPClientManager:
    """Init + start singleton. Pakai sekali di main.py."""
    global _manager
    if _manager is None:
        _manager = MCPClientManager(config_path, project_root)
        _manager.start()
    return _manager


def shutdown_manager() -> None:
    """Stop singleton. Pakai di bot shutdown hook."""
    global _manager
    if _manager is not None:
        _manager.stop()
        _manager = None
