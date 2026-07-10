import json
from pathlib import Path

from core import agentmemory_launcher


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_agentmemory_readiness_does_not_spawn_process(monkeypatch) -> None:
    monkeypatch.setattr(agentmemory_launcher, "_port_already_listening", lambda: True)

    assert agentmemory_launcher.agentmemory_is_ready() is True
    assert not hasattr(agentmemory_launcher, "subprocess")


def test_agentmemory_dependency_is_pinned_locally() -> None:
    package = json.loads(
        (PROJECT_ROOT / "services" / "agentmemory" / "package.json").read_text(
            encoding="utf-8"
        )
    )

    assert package["dependencies"] == {"@agentmemory/agentmemory": "0.9.27"}


def test_agentmemory_is_pm2_managed_but_opt_in_by_default() -> None:
    ecosystem = (PROJECT_ROOT / "ecosystem.config.js").read_text(encoding="utf-8")
    main_source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")

    assert 'name: "agentmemory"' in ecosystem
    assert 'script: "node_modules/.bin/agentmemory"' in ecosystem
    assert 'process.env.AGENTMEMORY_ENABLED === "true"' in ecosystem
    assert "...agentMemoryApps" in ecosystem
    assert "start_agentmemory" not in main_source
    assert "agentmemory_is_ready" in main_source
