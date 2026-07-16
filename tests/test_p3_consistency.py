import json
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from langchain_core.callbacks import AsyncCallbackHandler

from core import langgraph_engine
from core.langgraph_nodes import llm_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_manager_prompt_route_count_matches_menu() -> None:
    source = (
        PROJECT_ROOT / "core" / "langgraph_nodes" / "manager.py"
    ).read_text(encoding="utf-8")

    numbered_routes = re.findall(r"^\s*\d+\.\s+\[ROUTE:", source, re.MULTILINE)
    assert len(numbered_routes) == 22
    assert "pilih SATU dari 22 pilihan di atas" in source


@pytest.mark.asyncio
async def test_loop_cache_uses_loop_object_not_reusable_integer_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeLoop:
        pass

    first_loop = FakeLoop()
    second_loop = FakeLoop()
    loops = iter([first_loop, second_loop])
    compiled: list[object] = []

    def fake_compile(**kwargs: object) -> object:
        app = object()
        compiled.append(app)
        return app

    langgraph_engine._app_by_loop.clear()
    langgraph_engine._conn_by_loop.clear()
    monkeypatch.setenv("ENABLE_CHECKPOINTING", "false")
    monkeypatch.setattr(langgraph_engine.workflow, "compile", fake_compile)
    monkeypatch.setattr(
        langgraph_engine.asyncio,
        "get_running_loop",
        lambda: next(loops),
    )
    monkeypatch.setattr(langgraph_engine, "id", lambda _: 7, raising=False)

    first_app = await langgraph_engine._ensure_app()
    second_app = await langgraph_engine._ensure_app()

    assert first_app is not second_app
    assert len(compiled) == 2
    assert set(langgraph_engine._app_by_loop.keys()) == {first_loop, second_loop}
    langgraph_engine._app_by_loop.clear()


def test_discord_cost_guard_runs_sqlite_off_event_loop() -> None:
    source = (PROJECT_ROOT / "core" / "discord_bot.py").read_text(encoding="utf-8")
    assert re.search(
        r"await\s+asyncio\.to_thread\(\s*check_daily_cost",
        source,
    )


@pytest.mark.asyncio
async def test_cost_tracker_is_async_and_offloads_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = llm_config.CostTracker("user-1")
    assert isinstance(tracker, AsyncCallbackHandler)
    response = SimpleNamespace(
        generations=[[
            SimpleNamespace(
                message=SimpleNamespace(
                    response_metadata={"usage": {"cost": 0.25}},
                    usage_metadata={},
                ),
                generation_info={},
            )
        ]]
    )
    offloaded: list[tuple[object, tuple[object, ...]]] = []

    async def fake_to_thread(func, *args):
        offloaded.append((func, args))
        return func(*args)

    monkeypatch.setattr(llm_config.asyncio, "to_thread", fake_to_thread)
    with patch("core.gen_rate_limit.add_actual_cost") as writer:
        await tracker.on_llm_end(response)

    writer.assert_called_once_with("user-1", 0.25)
    assert len(offloaded) == 1


def test_agentmemory_start_script_matches_pm2_tools_profile() -> None:
    package = json.loads(
        (PROJECT_ROOT / "services" / "agentmemory" / "package.json").read_text(
            encoding="utf-8"
        )
    )
    assert package["scripts"]["start"] == "agentmemory --tools core"
