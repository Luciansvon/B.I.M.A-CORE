import json
from pathlib import Path

from core.agent_registry import AGENT_REGISTRY


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_registry_covers_every_enabled_mcp_target() -> None:
    config = json.loads((PROJECT_ROOT / "config_mcp.json").read_text(encoding="utf-8"))
    targets = {
        agent_name
        for server in config["servers"]
        if server.get("enabled")
        for agent_name in server.get("attach_to", [])
    }

    assert targets <= set(AGENT_REGISTRY)
    assert AGENT_REGISTRY["kodok"] == "teams.t10_kodok:kodok_agent"


def test_legacy_manager_has_no_registry_or_mcp_target() -> None:
    config = json.loads((PROJECT_ROOT / "config_mcp.json").read_text(encoding="utf-8"))

    assert "manager" not in AGENT_REGISTRY
    assert all(
        "manager" not in server.get("attach_to", [])
        for server in config["servers"]
    )
    assert all(
        "manager" not in server.get("tool_allowlist_by_agent", {})
        for server in config["servers"]
    )


def test_legacy_manager_module_and_imports_are_removed() -> None:
    assert not (PROJECT_ROOT / "teams/t1_manager.py").exists()

    callers = [
        "core/discord_bot.py",
        "core/wa_server.py",
        "core/dashboard_server.py",
        "core/furniture_qc.py",
    ]
    for relative_path in callers:
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "teams.t1_manager" not in source
