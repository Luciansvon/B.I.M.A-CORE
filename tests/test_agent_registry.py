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
