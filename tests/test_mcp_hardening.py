import json
from pathlib import Path
from types import SimpleNamespace

from core.mcp_client_manager import _filter_tools_by_name


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _mcp_config() -> dict:
    return json.loads((PROJECT_ROOT / "config_mcp.json").read_text(encoding="utf-8"))


def test_tool_allowlist_filters_destructive_tools() -> None:
    tools = [
        SimpleNamespace(name="read_graph"),
        SimpleNamespace(name="search_nodes"),
        SimpleNamespace(name="delete_entities"),
    ]

    filtered = _filter_tools_by_name(tools, ["read_graph", "search_nodes"])

    assert [tool.name for tool in filtered] == ["read_graph", "search_nodes"]


def test_active_mcp_packages_are_pinned_and_sqlite_is_disabled() -> None:
    servers = {server["name"]: server for server in _mcp_config()["servers"]}

    assert servers["sqlite"]["enabled"] is False
    assert servers["fetch"]["args"][:2] == ["--from", "mcp-server-fetch==2026.7.10"]
    assert servers["time"]["args"][:2] == ["--from", "mcp-server-time==2026.7.10"]
    assert servers["git"]["args"][:2] == ["--from", "mcp-server-git==2026.7.10"]
    assert servers["markitdown"]["args"][:2] == ["--from", "markitdown-mcp==0.0.1a4"]
    assert servers["sequential_thinking"]["args"][1].endswith("@2026.7.4")
    assert servers["memory_anthropic"]["args"][1].endswith("@2026.7.4")


def test_legacy_manager_has_no_mcp_access() -> None:
    servers = {server["name"]: server for server in _mcp_config()["servers"]}
    memory = servers["memory_anthropic"]
    sequential = servers["sequential_thinking"]

    assert "manager" not in memory["tool_allowlist_by_agent"]
    assert "manager" not in memory["attach_to"]
    assert sequential["enabled"] is False
    assert "manager" not in sequential["attach_to"]
