import asyncio
import threading
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

import core.langgraph_nodes.manager as manager
import core.langgraph_nodes.state as state_module


EXPECTED_ROUTES = {
    "santai": ["santai"],
    "intel": ["intel"],
    "seniman": ["seniman"],
    "admin": ["admin"],
    "visual": ["visual"],
    "arsip": ["arsip"],
    "lifestyle": ["lifestyle"],
    "mekanik": ["mekanik"],
    "saham": ["saham"],
    "kodok": ["kodok"],
    "observer": ["observer"],
    "seniman+admin": ["seniman", "admin"],
    "arsip+seniman": ["arsip", "seniman"],
    "arsip+admin": ["arsip", "admin"],
    "arsip+seniman+admin": ["arsip", "seniman", "admin"],
    "intel+seniman": ["intel", "seniman"],
    "intel+admin": ["intel", "admin"],
    "intel+arsip": ["intel", "arsip"],
    "intel+seniman+admin": ["intel", "seniman", "admin"],
    "intel+arsip+seniman": ["intel", "arsip", "seniman"],
    "intel+arsip+admin": ["intel", "arsip", "admin"],
    "intel+arsip+seniman+admin": ["intel", "arsip", "seniman", "admin"],
}


def test_manager_route_table_is_complete() -> None:
    assert getattr(manager, "ROUTE_TEAMS") == EXPECTED_ROUTES


@pytest.mark.parametrize("route, teams", EXPECTED_ROUTES.items())
def test_parse_manager_output_accepts_every_route(route: str, teams: list[str]) -> None:
    suffix = "\nHalo Bima" if route == "santai" else ""
    parsed_route, parsed_teams, reply = manager.parse_manager_output(
        f"[ROUTE: {route.upper()}]{suffix}"
    )

    assert parsed_route == route
    assert parsed_teams == teams
    assert reply == ("Halo Bima" if route == "santai" else "")


@pytest.mark.parametrize(
    "raw",
    [
        "tidak ada tag",
        "[ROUTE: unknown]",
        "[ROUTE: intel]\n[ROUTE: admin]",
        "[ROUTE: santai]",
    ],
)
def test_parse_manager_output_rejects_invalid_contract(raw: str) -> None:
    error_type = getattr(manager, "ManagerRouteError")
    with pytest.raises(error_type):
        manager.parse_manager_output(raw)


class FakeStreamingLLM:
    def __init__(self, output: str):
        self.output = output

    async def astream(self, _messages):
        yield SimpleNamespace(content=self.output)


def run_manager(monkeypatch, output: str):
    main_thread = threading.get_ident()
    memory_threads: list[int] = []

    async def no_progress(_state, _message):
        return None

    async def empty_recall(_query, _limit):
        return ""

    def recent_context(_limit):
        memory_threads.append(threading.get_ident())
        return "histori test"

    monkeypatch.setattr(manager, "default_llm", FakeStreamingLLM(output))
    monkeypatch.setattr(manager, "notify_progress", no_progress)
    monkeypatch.setattr(manager.agentmemory_client, "recall", empty_recall)
    monkeypatch.setattr(manager, "get_recent_context", recent_context)

    result = asyncio.run(
        manager.manager_node(
            {
                "messages": [],
                "user_request": "test request",
                "realtime_context": "",
            }
        )
    )
    return result, main_thread, memory_threads


def test_specialist_route_does_not_add_hidden_message(monkeypatch) -> None:
    result, main_thread, memory_threads = run_manager(
        monkeypatch,
        "[ROUTE: intel]\nnarasi yang harus dibuang",
    )

    assert result == {"active_teams": ["intel"], "is_finished": False}
    assert memory_threads and memory_threads[0] != main_thread


def test_santai_route_returns_only_clean_reply(monkeypatch) -> None:
    result, _, _ = run_manager(monkeypatch, "[ROUTE: santai]\nHalo Bima")

    assert result["active_teams"] == ["santai"]
    assert result["is_finished"] is True
    assert len(result["messages"]) == 1
    assert result["messages"][0].content == "Halo Bima"


def test_manager_stream_event_is_not_user_facing() -> None:
    import core.langgraph_engine as engine

    manager_event = {"metadata": {"langgraph_node": "manager_node"}}
    intel_event = {"metadata": {"langgraph_node": "intel_node"}}

    assert engine.is_user_facing_stream_event(manager_event) is False
    assert engine.is_user_facing_stream_event(intel_event) is True


@pytest.mark.parametrize("target", ["admin", "seniman"])
def test_direct_route_rejects_stale_upstream_message(target: str) -> None:
    helper = getattr(state_module, "get_current_upstream_text")
    state = {
        "active_teams": [target],
        "messages": [AIMessage(content="STALE REQUEST LAMA")],
    }

    assert helper(state, target) == ""


@pytest.mark.parametrize(
    "active_teams, target",
    [
        (["intel", "seniman"], "seniman"),
        (["arsip", "seniman"], "seniman"),
        (["intel", "admin"], "admin"),
        (["arsip", "admin"], "admin"),
        (["seniman", "admin"], "admin"),
    ],
)
def test_multiteam_route_accepts_current_upstream_message(
    active_teams: list[str], target: str
) -> None:
    helper = getattr(state_module, "get_current_upstream_text")
    state = {
        "active_teams": active_teams,
        "messages": [AIMessage(content="HASIL REQUEST AKTIF")],
    }

    assert helper(state, target) == "HASIL REQUEST AKTIF"
